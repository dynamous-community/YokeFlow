"""
Progress Tracking Utilities
===========================

Functions for tracking and displaying progress of the autonomous coding agent.
Uses PostgreSQL database via database_connection.py
"""

import asyncio
from pathlib import Path
from typing import Dict, Any
from database_connection import DatabaseManager


async def get_progress_from_db_async(project_dir: Path) -> Dict[str, Any]:
    """
    Get progress statistics from the PostgreSQL database (async version).

    Args:
        project_dir: Project directory (used to derive project name)

    Returns:
        Dict with progress statistics
    """
    project_name = project_dir.name

    try:
        async with DatabaseManager() as db:
            # Get project by name
            project = await db.get_project_by_name(project_name)

            if not project:
                # Project doesn't exist yet
                return {
                    "total_epics": 0,
                    "completed_epics": 0,
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "total_tests": 0,
                    "passing_tests": 0,
                    "task_pct": 0.0,
                    "test_pct": 0.0,
                }

            project_id = project['id']

            # Get progress stats
            progress = await db.get_progress(project_id)

            # Calculate percentages
            task_pct = 0.0
            if progress.get("total_tasks", 0) > 0:
                task_pct = (progress.get("completed_tasks", 0) / progress["total_tasks"]) * 100

            test_pct = 0.0
            if progress.get("total_tests", 0) > 0:
                test_pct = (progress.get("passing_tests", 0) / progress["total_tests"]) * 100

            # Map field names for backward compatibility
            return {
                "total_epics": progress.get("total_epics", 0),
                "completed_epics": progress.get("completed_epics", 0),
                "total_tasks": progress.get("total_tasks", 0),
                "completed_tasks": progress.get("completed_tasks", 0),
                "total_tests": progress.get("total_tests", 0),
                "passing_tests": progress.get("passing_tests", 0),
                "task_pct": task_pct,
                "test_pct": test_pct,
            }
    except Exception as e:
        # If database connection fails, return empty stats
        print(f"Warning: Could not get progress from database: {e}")
        return {
            "total_epics": 0,
            "completed_epics": 0,
            "total_tasks": 0,
            "completed_tasks": 0,
            "total_tests": 0,
            "passing_tests": 0,
            "task_pct": 0.0,
            "test_pct": 0.0,
        }


def get_progress_from_db(project_dir: Path) -> Dict[str, Any]:
    """
    Get progress statistics from the PostgreSQL database (sync wrapper).

    Args:
        project_dir: Project directory (used to derive project name)

    Returns:
        Dict with progress statistics
    """
    # Run the async function synchronously
    return asyncio.run(get_progress_from_db_async(project_dir))


def print_session_header(session_num: int, is_initializer: bool) -> None:
    """Print a formatted header for the session."""
    session_type = "INITIALIZER" if is_initializer else "CODING AGENT"

    print("\n" + "=" * 70)
    print(f"  SESSION {session_num}: {session_type}")
    print("=" * 70)
    print()


def print_progress_summary(project_dir: Path) -> None:
    """Print a summary of current progress."""
    progress = get_progress_from_db(project_dir)

    if progress["total_tasks"] > 0:
        print(f"\nProgress Summary:")
        print(f"  Epics: {progress['completed_epics']}/{progress['total_epics']} complete")
        print(f"  Tasks: {progress['completed_tasks']}/{progress['total_tasks']} complete ({progress['task_pct']:.1f}%)")
        print(f"  Tests: {progress['passing_tests']}/{progress['total_tests']} passing ({progress['test_pct']:.1f}%)")
    else:
        print("\nProgress: Task database not yet populated")
