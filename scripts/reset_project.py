#!/usr/bin/env python3
"""
Reset Project to Post-Initialization State
===========================================

YokeFlow utility to reset a project back to the state immediately after the
initialization session. This allows you to iterate on coding sessions and
prompt improvements without re-running the time-consuming initialization
(which can take 10-20 minutes).

What gets reset:
- Database: All task/test completion status, session records (keeps epics/tasks/tests structure)
- Git: Resets to the first commit after initialization session
- Logs: Archives coding session logs to logs/old_attempts/

What is preserved:
- Complete project roadmap (epics, tasks, tests) in PostgreSQL
- Initialization commit and all setup
- Project structure and init.sh
- .env.example and configuration files

Usage:
    python reset_project.py --project-dir my-project
    python reset_project.py --project-dir my-project --yes  # Skip confirmation
    python reset_project.py --project-dir my-project --dry-run  # Show what would be reset
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import shutil
from typing import Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database_connection import DatabaseManager


class ProjectResetter:
    """Handles resetting a project to post-initialization state."""

    def __init__(self, project_path: Path, dry_run: bool = False):
        """
        Initialize the resetter.

        Args:
            project_path: Path to project directory
            dry_run: If True, only show what would be done
        """
        self.project_path = Path(project_path).resolve()
        self.dry_run = dry_run
        self.logs_dir = self.project_path / "logs"
        self.project_name = self.project_path.name
        self.project_id = None  # Will be set during validation

    async def validate_project(self) -> bool:
        """
        Validate that the project exists and is in a valid state.

        Returns:
            True if valid, False otherwise
        """
        # Check project directory exists
        if not self.project_path.exists():
            print(f"❌ Error: Project directory not found: {self.project_path}")
            return False

        # Check if it's a git repository
        if not (self.project_path / ".git").exists():
            print(f"❌ Error: Project is not a git repository: {self.project_path}")
            return False

        # Check if project exists in PostgreSQL database
        async with DatabaseManager() as db:
            project = await db.get_project_by_name(self.project_name)
            if not project:
                print(f"❌ Error: Project not found in database: {self.project_name}")
                print("   This doesn't appear to be an initialized autonomous coding project.")
                return False

            self.project_id = project['id']

        return True

    async def get_current_state(self) -> Dict[str, Any]:
        """
        Get current project state for display.

        Returns:
            Dict with current state information
        """
        state = {
            "completed_tasks": 0,
            "passing_tests": 0,
            "total_tasks": 0,
            "total_tests": 0,
            "sessions": 0,
            "git_commits": 0,
            "coding_logs": 0,
        }

        # Get database stats from PostgreSQL
        try:
            async with DatabaseManager() as db:
                progress = await db.get_progress(self.project_id)
                state["completed_tasks"] = progress.get("completed_tasks", 0)
                state["total_tasks"] = progress.get("total_tasks", 0)
                state["passing_tests"] = progress.get("passing_tests", 0)
                state["total_tests"] = progress.get("total_tests", 0)

                # Count sessions
                sessions = await db.list_sessions(self.project_id)
                state["sessions"] = len(sessions)
        except Exception as e:
            print(f"⚠️  Warning: Could not read database: {e}")

        # Get git commit count
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            state["git_commits"] = int(result.stdout.strip())
        except Exception as e:
            print(f"⚠️  Warning: Could not count git commits: {e}")

        # Count coding session logs (session_002 and higher)
        if self.logs_dir.exists():
            state["coding_logs"] = len(
                [f for f in self.logs_dir.glob("session_0*") if not f.stem.startswith("session_001")]
            )

        return state

    def find_init_commit(self) -> str:
        """
        Find the git commit hash for the initialization session.

        The initialization session ends with a commit that adds claude-progress.md.
        We want to reset to this commit (not the earlier "Initial setup" commit).

        Search strategies in order of preference:
        1. "Add claude-progress.md" or "log session 1" - most reliable
        2. "Session 1 complete" - explicit end marker
        3. "Initial setup" - fallback, but then check for next commit

        Returns:
            Commit hash as string, or empty string if not found
        """
        try:
            # Strategy 1: Look for "Initialization complete" (current commit message format)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--grep=Initialization complete",
                    "-i",
                    "--format=%H %s",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            commits = result.stdout.strip().split("\n")
            if commits and commits[0]:
                commit_hash = commits[0].split()[0]
                return commit_hash

            # Strategy 2: Look for commit with "log session" or "session 0" (old format)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--grep=log session",
                    "--grep=session 0",
                    "-i",
                    "--format=%H %s",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            commits = result.stdout.strip().split("\n")
            if commits and commits[0]:
                # Should only match one commit - the end of init session
                commit_hash = commits[0].split()[0]
                return commit_hash

            # Strategy 3: Look for "Session 1 complete" or similar (even older format)
            result = subprocess.run(
                [
                    "git",
                    "log",
                    "--all",
                    "--grep=Session 1 complete",
                    "--grep=session 1 complete",
                    "-i",  # case insensitive
                    "--format=%H %s",
                ],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )

            commits = result.stdout.strip().split("\n")
            if commits and commits[0]:
                commit_hash = commits[0].split()[0]
                return commit_hash

            # Strategy 3: Look for "Initial setup" commit, then use the NEXT commit
            result = subprocess.run(
                ["git", "log", "--reverse", "--format=%H %s"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            all_commits = result.stdout.strip().split("\n")

            # Find "Initial setup" in first 5 commits, then return the next one
            for i, commit_line in enumerate(all_commits[:5]):
                if "Initial setup" in commit_line:
                    # Return the next commit (which should be the progress/session log)
                    if i + 1 < len(all_commits):
                        next_commit_hash = all_commits[i + 1].split()[0]
                        return next_commit_hash
                    else:
                        # If no next commit, return this one
                        commit_hash = commit_line.split()[0]
                        return commit_hash

            # Last resort: use second commit
            if len(all_commits) >= 2:
                return all_commits[1].split()[0]

            return ""

        except Exception as e:
            print(f"⚠️  Warning: Could not find initialization commit: {e}")
            return ""

    async def reset_database(self) -> bool:
        """
        Reset database to post-initialization state.

        - Resets all task completion status
        - Resets all test results
        - Resets epic status (except fully complete ones)
        - Deletes all session records except session 1

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print("\n[DRY RUN] Would reset database:")
            print("  - Reset tasks: done=FALSE, completed_at=NULL")
            print("  - Reset tests: passes=FALSE, verified_at=NULL")
            print("  - Reset epics: status='pending', started_at=NULL, completed_at=NULL")
            print("  - Delete sessions with session_number > 0 (keep session 0 - initialization)")
            return True

        try:
            async with DatabaseManager() as db:
                async with db.acquire() as conn:
                    # Reset tasks
                    result = await conn.execute(
                        """
                        UPDATE tasks
                        SET done = FALSE,
                            completed_at = NULL
                        WHERE project_id = $1
                        """,
                        self.project_id,
                    )
                    print(f"  ✅ Reset tasks to incomplete")

                    # Reset tests
                    result = await conn.execute(
                        """
                        UPDATE tests
                        SET passes = FALSE,
                            verified_at = NULL
                        FROM tasks
                        WHERE tests.task_id = tasks.id
                          AND tasks.project_id = $1
                        """,
                        self.project_id,
                    )
                    print(f"  ✅ Reset tests to not passing")

                    # Reset epics (only those not complete)
                    result = await conn.execute(
                        """
                        UPDATE epics
                        SET status = 'pending',
                            started_at = NULL,
                            completed_at = NULL
                        WHERE project_id = $1
                          AND status != 'completed'
                        """,
                        self.project_id,
                    )
                    print(f"  ✅ Reset epics to pending")

                    # Delete coding session records (keep session 0 - initialization)
                    result = await conn.execute(
                        """
                        DELETE FROM sessions
                        WHERE project_id = $1
                          AND session_number > 0
                        """,
                        self.project_id,
                    )
                    print(f"  ✅ Deleted coding session records (kept session 0 - initialization)")

            return True

        except Exception as e:
            print(f"❌ Error resetting database: {e}")
            import traceback
            traceback.print_exc()
            return False

    def reset_git(self, init_commit: str) -> bool:
        """
        Reset git to the initialization commit and clean history.

        This performs a hard reset to the init commit, then cleans up:
        - Removes commits from reflog (so git log doesn't show them)
        - Prunes orphaned objects
        - Cleans working directory

        Args:
            init_commit: Commit hash to reset to

        Returns:
            True if successful, False otherwise
        """
        if not init_commit:
            print("❌ Error: No initialization commit found")
            return False

        if self.dry_run:
            print(f"\n[DRY RUN] Would reset git to commit: {init_commit[:8]}")
            print("  Commands:")
            print("    git reset --hard <commit>")
            print("    git reflog expire --expire=now --all")
            print("    git gc --prune=now --aggressive")
            print("    git clean -fdx")
            return True

        try:
            # Get current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

            # 1. Reset to init commit (moves HEAD and branch pointer)
            subprocess.run(
                ["git", "reset", "--hard", init_commit],
                cwd=self.project_path,
                check=True,
                capture_output=True,
            )
            print(f"  ✅ Reset HEAD to: {init_commit[:8]}")

            # 2. Expire reflog immediately (makes old commits invisible to git log --all)
            subprocess.run(
                ["git", "reflog", "expire", "--expire=now", "--all"],
                cwd=self.project_path,
                check=True,
                capture_output=True,
            )
            print(f"  ✅ Expired reflog entries")

            # 3. Prune orphaned objects (removes unreachable commits)
            subprocess.run(
                ["git", "gc", "--prune=now", "--aggressive"],
                cwd=self.project_path,
                check=True,
                capture_output=True,
            )
            print(f"  ✅ Pruned orphaned commits")

            # 4. Clean working directory (remove untracked files)
            subprocess.run(
                ["git", "clean", "-fdx"],
                cwd=self.project_path,
                check=True,
                capture_output=True,
            )
            print(f"  ✅ Cleaned working directory")

            print(f"  ✅ Git fully reset to initialization commit")
            print(f"     Branch: {current_branch}")
            print(f"     Commit: {init_commit[:8]}")

            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Error resetting git: {e}")
            return False

    def archive_logs(self) -> bool:
        """
        Archive coding session logs to logs/old_attempts/.

        Preserves session 1 (initialization) log.
        Moves all other session logs to archive with timestamp.

        Returns:
            True if successful, False otherwise
        """
        if not self.logs_dir.exists():
            print("  ℹ️  No logs directory found, skipping log archival")
            return True

        # Create archive directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = self.logs_dir / "old_attempts" / f"reset_{timestamp}"

        if self.dry_run:
            print(f"\n[DRY RUN] Would archive logs to: {archive_dir}")
            print("  - Move all session_0* logs (except session_001)")
            return True

        try:
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Find all session logs except session 1
            logs_to_archive = [
                f
                for f in self.logs_dir.glob("session_*")
                if f.is_file() and not f.name.startswith("session_001")
            ]

            if not logs_to_archive:
                print("  ℹ️  No coding session logs found to archive")
                return True

            # Move logs to archive
            for log_file in logs_to_archive:
                dest = archive_dir / log_file.name
                shutil.move(str(log_file), str(dest))

            print(f"  ✅ Archived {len(logs_to_archive)} log files to:")
            print(f"     {archive_dir.relative_to(self.project_path)}")

            # Note: sessions_summary.jsonl has been removed from codebase
            # All session metrics are now in PostgreSQL database

            return True

        except Exception as e:
            print(f"❌ Error archiving logs: {e}")
            return False

    def reset_progress_notes(self) -> bool:
        """
        Reset or archive claude-progress.md.

        Creates a backup and resets to post-initialization state.

        Returns:
            True if successful, False otherwise
        """
        progress_file = self.project_path / "claude-progress.md"

        if not progress_file.exists():
            print("  ℹ️  No claude-progress.md found, skipping")
            return True

        if self.dry_run:
            print("\n[DRY RUN] Would backup and reset claude-progress.md")
            return True

        try:
            # Backup existing progress file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.logs_dir / "old_attempts" / f"reset_{timestamp}"
            backup_dir.mkdir(parents=True, exist_ok=True)

            backup_file = backup_dir / f"claude-progress_backup.md"
            shutil.copy(str(progress_file), str(backup_file))

            # Create fresh progress file
            initial_content = f"""# Project Progress

## Current Status

Session 1 (Initialization) complete.
Project reset to post-initialization state on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Ready to begin coding sessions.

Use `python yokeflow.py --project-dir {self.project_path.name}` to start.

## Initialization Summary

See session_001 logs for initialization details.
"""

            progress_file.write_text(initial_content)
            print("  ✅ Backed up and reset claude-progress.md")

            return True

        except Exception as e:
            print(f"❌ Error resetting progress notes: {e}")
            return False

    async def perform_reset(self) -> bool:
        """
        Perform the complete reset operation.

        Returns:
            True if successful, False otherwise
        """
        print(f"\n{'='*70}")
        print("  PROJECT RESET TO POST-INITIALIZATION STATE")
        print(f"{'='*70}\n")
        print(f"Project: {self.project_path.name}")
        print(f"Path: {self.project_path}")

        # Show current state
        state = await self.get_current_state()
        print(f"\nCurrent state:")
        print(f"  - Tasks: {state['completed_tasks']}/{state['total_tasks']} completed")
        print(f"  - Tests: {state['passing_tests']}/{state['total_tests']} passing")
        print(f"  - Sessions: {state['sessions']}")
        print(f"  - Git commits: {state['git_commits']}")
        print(f"  - Coding logs: {state['coding_logs']}")

        # Find initialization commit
        print(f"\nFinding initialization commit...")
        init_commit = self.find_init_commit()

        if not init_commit:
            print("❌ Could not find initialization commit.")
            print("   Cannot safely reset without knowing the init commit.")
            return False

        # Show commit info
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--oneline", init_commit],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            print(f"  ✅ Found: {result.stdout.strip()}")
        except Exception as e:
            print(f"  ⚠️  Could not display commit: {e}")

        if self.dry_run:
            print("\n[DRY RUN MODE - No changes will be made]")

        # Perform reset operations
        print(f"\n{'─'*70}")
        print("Step 1: Reset Database (PostgreSQL)")
        print(f"{'─'*70}")
        if not await self.reset_database():
            return False

        print(f"\n{'─'*70}")
        print("Step 2: Archive Coding Session Logs")
        print(f"{'─'*70}")
        if not self.archive_logs():
            return False

        print(f"\n{'─'*70}")
        print("Step 3: Reset Progress Notes")
        print(f"{'─'*70}")
        if not self.reset_progress_notes():
            return False

        print(f"\n{'─'*70}")
        print("Step 4: Reset Git Repository")
        print(f"{'─'*70}")
        if not self.reset_git(init_commit):
            return False

        # Final summary
        print(f"\n{'='*70}")
        if self.dry_run:
            print("  DRY RUN COMPLETE - No changes made")
        else:
            print("  ✅ RESET COMPLETE")
        print(f"{'='*70}\n")

        if not self.dry_run:
            print("Project has been reset to post-initialization state.")
            print("\nNext steps:")
            print(f"  1. Review initialization: git log --oneline")
            print(
                f"  2. Start coding sessions: python yokeflow.py --project-dir {self.project_path.name}"
            )
            print(f"  3. Old logs archived in: logs/old_attempts/")

        return True


async def async_main(args):
    """Async main logic."""
    # Handle project directory path
    project_dir = Path(args.project_dir)

    # If the path is relative and doesn't start with "generations/",
    # automatically place it in generations/ directory
    if not project_dir.is_absolute():
        if not str(project_dir).startswith("generations/"):
            project_dir = Path("generations") / project_dir

    # Create resetter
    resetter = ProjectResetter(project_dir, dry_run=args.dry_run)

    # Validate project
    if not await resetter.validate_project():
        return False

    # Confirmation (unless --yes or --dry-run)
    if not args.yes and not args.dry_run:
        print("\n⚠️  WARNING: This will reset the project to post-initialization state.")
        print("   - All task/test completion will be cleared in PostgreSQL")
        print("   - Git history will be reset to initialization commit")
        print("   - Coding session logs will be archived")
        print("\n   The complete roadmap (epics/tasks/tests) will be preserved.")
        response = input("\nContinue? [y/N]: ").strip().lower()

        if response not in ["y", "yes"]:
            print("Reset cancelled.")
            return False

    # Perform reset
    return await resetter.perform_reset()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Reset project to post-initialization state (PostgreSQL version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Show what would be reset (dry run)
  python reset_project.py --project-dir my-project --dry-run

  # Reset with confirmation
  python reset_project.py --project-dir my-project

  # Reset without confirmation
  python reset_project.py --project-dir my-project --yes

Benefits:
  - Save 10-20 minutes by avoiding re-initialization
  - Iterate on prompt improvements faster
  - Test different approaches without losing roadmap
  - Keep complete epic/task/test structure intact in PostgreSQL
""",
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        required=True,
        help="Directory for the project (e.g., my-project). Relative paths automatically use generations/ directory.",
    )

    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )

    args = parser.parse_args()

    # Run async main
    try:
        success = asyncio.run(async_main(args))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nReset cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Reset failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
