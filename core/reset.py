#!/usr/bin/env python3
"""
Project Reset Module
====================

YokeFlow utility to reset a project back to the state immediately after
initialization session. This allows iteration on coding sessions and prompt
improvements without re-running the time-consuming initialization (10-20 minutes).

This module is designed for API integration and programmatic use.

What gets reset:
- Database: All task/test completion status, session records (keeps roadmap)
- Git: Resets to commit after initialization session
- Logs: Archives coding session logs to logs/old_attempts/
- Docker: Stops and removes sandbox container if applicable

What is preserved:
- Complete project roadmap (epics, tasks, tests) in PostgreSQL
- Initialization session (Session 0) and its commit
- Project structure and init.sh
- Configuration files (.env.example, etc.)
"""

import asyncio
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from uuid import UUID

from core.database_connection import DatabaseManager


class ProjectResetter:
    """Handles resetting a project to post-initialization state."""

    def __init__(self, project_id: UUID, project_path: Path):
        """
        Initialize the resetter.

        Args:
            project_id: UUID of the project in database
            project_path: Path to project directory
        """
        self.project_id = project_id
        self.project_path = Path(project_path).resolve()
        self.logs_dir = self.project_path / "logs"
        self.project_name = self.project_path.name

    def is_git_repository(self) -> bool:
        """Check if project is a git repository."""
        return (self.project_path / ".git").exists()

    async def validate_project(self) -> Tuple[bool, Optional[str]]:
        """
        Validate that the project exists and is in a valid state.

        Returns:
            Tuple of (success, error_message)
        """
        # Check project directory exists
        if not self.project_path.exists():
            return False, f"Project directory not found: {self.project_path}"

        # Note: Git is now optional - we'll skip git operations if not a repo

        # Check if project exists in PostgreSQL database
        async with DatabaseManager() as db:
            project = await db.get_project(self.project_id)
            if not project:
                return False, f"Project not found in database: {self.project_id}"

        # Check if initialization is complete (has epics)
        async with DatabaseManager() as db:
            epics = await db.list_epics(self.project_id)
            if len(epics) == 0:
                return False, "Project has not been initialized yet (no epics found)"

        return True, None

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
            "coding_sessions": 0,
            "git_commits": 0,
            "coding_logs": 0,
        }

        # Get database state
        async with DatabaseManager() as db:
            # Get progress
            progress = await db.get_progress(self.project_id)
            if progress:
                state["completed_tasks"] = progress.get("completed_tasks", 0)
                state["passing_tests"] = progress.get("passing_tests", 0)
                state["total_tasks"] = progress.get("total_tasks", 0)
                state["total_tests"] = progress.get("total_tests", 0)

            # Count coding sessions (> 0)
            async with db.acquire() as conn:
                result = await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM sessions
                    WHERE project_id = $1 AND session_number > 0
                    """,
                    self.project_id,
                )
                state["coding_sessions"] = result or 0

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
        except Exception:
            state["git_commits"] = 0

        # Count coding session logs (not session_000)
        if self.logs_dir.exists():
            logs = [
                f
                for f in self.logs_dir.glob("session_*")
                if f.is_file() and not f.name.startswith("session_000")
            ]
            state["coding_logs"] = len(logs)

        return state

    def find_init_commit(self) -> str:
        """
        Find the commit hash for the initialization session.

        Returns:
            Commit hash string, or empty string if not found
        """
        try:
            # Get all commits in reverse chronological order
            result = subprocess.run(
                ["git", "log", "--reverse", "--format=%H %s"],
                cwd=self.project_path,
                capture_output=True,
                text=True,
                check=True,
            )
            all_commits = result.stdout.strip().split("\n")

            # Find "Initial setup" or similar init commit in first 5 commits
            for i, commit_line in enumerate(all_commits[:5]):
                if "Initial setup" in commit_line or "init" in commit_line.lower():
                    # Return the next commit (which should be the progress/roadmap)
                    if i + 1 < len(all_commits):
                        return all_commits[i + 1].split()[0]
                    else:
                        # If no next commit, return this one
                        return commit_line.split()[0]

            # Last resort: use second commit (after initial commit)
            if len(all_commits) >= 2:
                return all_commits[1].split()[0]

            return ""

        except Exception as e:
            print(f"Warning: Could not find initialization commit: {e}")
            return ""

    async def reset_database(self) -> Tuple[bool, Optional[str]]:
        """
        Reset database to post-initialization state.

        - Resets all task completion status
        - Resets all test results
        - Resets epic status
        - Deletes all session records except Session 0 (initialization)

        Returns:
            Tuple of (success, error_message)
        """
        try:
            async with DatabaseManager() as db:
                async with db.acquire() as conn:
                    # Reset tasks
                    await conn.execute(
                        """
                        UPDATE tasks
                        SET done = FALSE,
                            completed_at = NULL,
                            session_id = NULL,
                            session_notes = NULL
                        WHERE project_id = $1
                        """,
                        self.project_id,
                    )

                    # Reset tests
                    await conn.execute(
                        """
                        UPDATE tests
                        SET passes = FALSE,
                            verified_at = NULL,
                            session_id = NULL,
                            result = '{}'
                        WHERE project_id = $1
                        """,
                        self.project_id,
                    )

                    # Reset epics
                    await conn.execute(
                        """
                        UPDATE epics
                        SET status = 'pending',
                            started_at = NULL,
                            completed_at = NULL
                        WHERE project_id = $1
                        """,
                        self.project_id,
                    )

                    # Clear project completion timestamp
                    await conn.execute(
                        """
                        UPDATE projects
                        SET completed_at = NULL
                        WHERE id = $1
                        """,
                        self.project_id,
                    )

                    # Delete coding session records (keep Session 0 - initialization)
                    await conn.execute(
                        """
                        DELETE FROM sessions
                        WHERE project_id = $1
                          AND session_number > 0
                        """,
                        self.project_id,
                    )

                    # Note: github_commits table removed in Migration 007 (never used)

            return True, None

        except Exception as e:
            return False, f"Database reset failed: {e}"

    def reset_git(self, init_commit: str) -> Tuple[bool, Optional[str]]:
        """
        Reset git repository to initialization commit.

        Args:
            init_commit: Commit hash to reset to

        Returns:
            Tuple of (success, error_message)
        """
        if not init_commit:
            return False, "No initialization commit found"

        try:
            # Reset to init commit
            subprocess.run(
                ["git", "reset", "--hard", init_commit],
                cwd=self.project_path,
                check=True,
                capture_output=True,
            )

            return True, None

        except subprocess.CalledProcessError as e:
            return False, f"Git reset failed: {e}"

    def archive_logs(self) -> Tuple[bool, Optional[str], Optional[Path]]:
        """
        Archive coding session logs to logs/old_attempts/.

        Preserves Session 0 (initialization) log.
        Moves all other session logs to archive with timestamp.

        Returns:
            Tuple of (success, error_message, archive_path)
        """
        if not self.logs_dir.exists():
            return True, None, None

        # Create archive directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = self.logs_dir / "old_attempts" / f"reset_{timestamp}"

        try:
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Find all session logs except Session 0 (session_000_*)
            logs_to_archive = [
                f
                for f in self.logs_dir.glob("session_*")
                if f.is_file() and not f.name.startswith("session_000")
            ]

            if not logs_to_archive:
                return True, None, None

            # Move logs to archive
            for log_file in logs_to_archive:
                dest = archive_dir / log_file.name
                shutil.move(str(log_file), str(dest))

            # Note: sessions_summary.jsonl has been removed from the codebase
            # All session metrics are now stored in PostgreSQL database

            return True, None, archive_dir

        except Exception as e:
            return False, f"Log archival failed: {e}", None

    def reset_progress_notes(self, archive_dir: Optional[Path] = None) -> Tuple[bool, Optional[str]]:
        """
        Reset or archive claude-progress.md.

        Creates a backup and resets to post-initialization state.

        Args:
            archive_dir: Directory to backup to (if None, creates new one)

        Returns:
            Tuple of (success, error_message)
        """
        progress_file = self.project_path / "claude-progress.md"

        if not progress_file.exists():
            return True, None

        try:
            # Backup existing progress file
            if archive_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_dir = self.logs_dir / "old_attempts" / f"reset_{timestamp}"
                archive_dir.mkdir(parents=True, exist_ok=True)

            backup_file = archive_dir / "claude-progress_backup.md"
            shutil.copy(str(progress_file), str(backup_file))

            # Create fresh progress file
            initial_content = f"""# Project Progress

## Current Status

Session 0 (Initialization) complete.
Project reset to post-initialization state on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}.

Ready to begin coding sessions.

## Initialization Summary

See session_000 logs for initialization details.
"""

            progress_file.write_text(initial_content)

            return True, None

        except Exception as e:
            return False, f"Progress notes reset failed: {e}"

    async def stop_docker_sandbox(self) -> Tuple[bool, Optional[str]]:
        """
        Stop and remove Docker sandbox container if it exists.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            # Get project info to check sandbox type
            async with DatabaseManager() as db:
                project = await db.get_project(self.project_id)
                if not project:
                    return False, "Project not found"

                # Check if using Docker sandbox
                # (This will be in project metadata or settings)
                # For now, we'll try to stop the container if it exists

            # Container name pattern: autonomous-coding-{project_name}
            container_name = f"autonomous-coding-{self.project_name}"

            # Check if container exists
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
            )

            if container_name in result.stdout:
                # Stop and remove container
                subprocess.run(
                    ["docker", "stop", container_name],
                    capture_output=True,
                    timeout=30,
                )
                subprocess.run(
                    ["docker", "rm", container_name],
                    capture_output=True,
                    timeout=10,
                )
                return True, f"Stopped and removed Docker container: {container_name}"

            return True, None  # No container found, that's fine

        except subprocess.TimeoutExpired:
            return False, "Docker container stop timed out"
        except Exception as e:
            # Don't fail the reset if Docker cleanup fails
            return True, f"Warning: Docker cleanup encountered an issue: {e}"

    async def perform_reset(self) -> Dict[str, Any]:
        """
        Perform the complete reset operation.

        Returns:
            Dict with reset results and details:
            {
                "success": bool,
                "error": str | None,
                "state_before": dict,
                "state_after": dict,
                "archive_path": str | None,
                "steps": {
                    "validation": {"success": bool, "error": str | None},
                    "docker": {"success": bool, "message": str | None},
                    "database": {"success": bool, "error": str | None},
                    "git": {"success": bool, "error": str | None},
                    "logs": {"success": bool, "error": str | None},
                    "progress": {"success": bool, "error": str | None}
                }
            }
        """
        result = {
            "success": False,
            "error": None,
            "state_before": {},
            "state_after": {},
            "archive_path": None,
            "steps": {}
        }

        # Validate project
        valid, error = await self.validate_project()
        result["steps"]["validation"] = {"success": valid, "error": error}
        if not valid:
            result["error"] = error
            return result

        # Get state before reset
        result["state_before"] = await self.get_current_state()

        # Stop Docker sandbox if applicable
        docker_success, docker_msg = await self.stop_docker_sandbox()
        result["steps"]["docker"] = {"success": docker_success, "message": docker_msg}

        # Check if this is a git repository
        is_git_repo = self.is_git_repository()

        # Find initialization commit (only if git repo)
        init_commit = None
        if is_git_repo:
            init_commit = self.find_init_commit()
            if not init_commit:
                result["error"] = "Could not find initialization commit"
                result["steps"]["git"] = {"success": False, "error": "No initialization commit found"}
                return result

        # Reset database
        db_success, db_error = await self.reset_database()
        result["steps"]["database"] = {"success": db_success, "error": db_error}
        if not db_success:
            result["error"] = db_error
            return result

        # Archive logs
        logs_success, logs_error, archive_path = self.archive_logs()
        result["steps"]["logs"] = {"success": logs_success, "error": logs_error}
        if archive_path:
            result["archive_path"] = str(archive_path.relative_to(self.project_path))
        if not logs_success:
            result["error"] = logs_error
            return result

        # Reset progress notes
        progress_success, progress_error = self.reset_progress_notes(archive_path)
        result["steps"]["progress"] = {"success": progress_success, "error": progress_error}
        if not progress_success:
            result["error"] = progress_error
            return result

        # Reset git (only if git repository - do this last so we can rollback if needed)
        if is_git_repo and init_commit:
            git_success, git_error = self.reset_git(init_commit)
            result["steps"]["git"] = {"success": git_success, "error": git_error}
            if not git_success:
                result["error"] = git_error
                return result
        else:
            result["steps"]["git"] = {"success": True, "error": "Skipped (not a git repository)" if not is_git_repo else None}

        # Get state after reset
        result["state_after"] = await self.get_current_state()
        result["success"] = True

        return result


async def reset_project(project_id: UUID, project_path: Path) -> Dict[str, Any]:
    """
    Reset a project to post-initialization state.

    Convenience function for API use.

    Args:
        project_id: UUID of the project
        project_path: Path to project directory

    Returns:
        Dict with reset results (see ProjectResetter.perform_reset)
    """
    resetter = ProjectResetter(project_id, project_path)
    return await resetter.perform_reset()
