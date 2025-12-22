#!/usr/bin/env python3
"""
analyze_sessions.py - Analyze agent sessions from database

Usage:
    python scripts/analyze_sessions.py <project_name_or_id>
    python scripts/analyze_sessions.py --list  # List all projects
    python scripts/analyze_sessions.py --all   # Analyze all projects

Replaces the old analyze_logs.sh which read from sessions_summary.jsonl
"""

import asyncio
import sys
import os
from typing import Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path

# Add parent directory to path so we can import database
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import TaskDatabase

# Load .env file if it exists
def load_env():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key, value)

load_env()


async def list_projects(db: TaskDatabase):
    """List all projects."""
    projects = await db.list_projects()

    print("=" * 70)
    print("AVAILABLE PROJECTS")
    print("=" * 70)

    if not projects:
        print("No projects found.")
        return

    for p in projects:
        status = p.get('status', 'unknown')
        created = p['created_at'].strftime('%Y-%m-%d')
        print(f"{p['name']}")
        print(f"  ID: {p['id']}")
        print(f"  Status: {status}")
        print(f"  Created: {created}")
        print(f"  Path: {p.get('project_path', 'N/A')}")
        print()


async def analyze_project(db: TaskDatabase, project_id: UUID, project_name: str):
    """Analyze sessions for a specific project."""

    # Get project info
    project = await db.get_project(project_id)
    if not project:
        print(f"Error: Project not found")
        return

    # Get all sessions (use large limit to get all)
    sessions = await db.get_session_history(project_id, limit=1000)

    print("=" * 70)
    print("AGENT SESSION ANALYSIS")
    print("=" * 70)
    print(f"Project: {project_name}")
    print(f"Project ID: {project_id}")
    print(f"Total Sessions: {len(sessions)}")
    print()

    if not sessions:
        print("No sessions found.")
        return

    # Session overview
    print("-" * 70)
    print("SESSION OVERVIEW")
    print("-" * 70)

    for session in sessions:
        session_num = session['session_number']
        session_type = session['type']
        status = session['status']

        # Extract metrics
        metrics = session.get('metrics', {})
        duration_min = round(metrics.get('duration_seconds', 0) / 60, 1)
        tool_calls = metrics.get('tool_calls_count', 0)
        # Support both old (tool_errors) and new (errors_count) field names
        errors = metrics.get('errors_count', metrics.get('tool_errors', 0))
        tasks_completed = metrics.get('tasks_completed', 0)
        tests_passed = metrics.get('tests_passed', 0)
        browser_checks = metrics.get('browser_verifications', 0)

        print(f"Session {session_num} [{session_type}] - {status}")
        print(f"  Duration: {duration_min} minutes")
        print(f"  Tool Calls: {tool_calls}")
        print(f"  Errors: {errors}")
        print(f"  Tasks Completed: {tasks_completed}")
        print(f"  Tests Passed: {tests_passed}")
        print(f"  Browser Checks: {browser_checks}")

        if session.get('error_message'):
            print(f"  Error: {session['error_message'][:100]}")

        print()

    # Aggregate statistics
    print("-" * 70)
    print("AGGREGATE STATISTICS")
    print("-" * 70)

    total_duration = sum(s.get('metrics', {}).get('duration_seconds', 0) for s in sessions)
    total_tools = sum(s.get('metrics', {}).get('tool_calls_count', 0) for s in sessions)
    # Support both old (tool_errors) and new (errors_count) field names
    total_errors = sum(s.get('metrics', {}).get('errors_count', s.get('metrics', {}).get('tool_errors', 0)) for s in sessions)
    total_tasks = sum(s.get('metrics', {}).get('tasks_completed', 0) for s in sessions)
    total_tests = sum(s.get('metrics', {}).get('tests_passed', 0) for s in sessions)
    total_browser = sum(s.get('metrics', {}).get('browser_verifications', 0) for s in sessions)

    total_input_tokens = sum(s.get('metrics', {}).get('tokens_input', 0) for s in sessions)
    total_output_tokens = sum(s.get('metrics', {}).get('tokens_output', 0) for s in sessions)
    total_cost = sum(s.get('metrics', {}).get('cost_usd', 0) for s in sessions)

    print(f"Total Duration: {round(total_duration / 60, 1)} minutes")
    print(f"Total Tool Calls: {total_tools}")
    print(f"Total Errors: {total_errors}")
    print(f"Total Tasks Completed: {total_tasks}")
    print(f"Total Tests Passed: {total_tests}")
    print(f"Total Browser Verifications: {total_browser}")
    print()

    if len(sessions) > 0:
        avg_tools = round(total_tools / len(sessions))
        avg_duration = round(total_duration / len(sessions) / 60, 1)
        print(f"Average Duration per Session: {avg_duration} minutes")
        print(f"Average Tool Calls per Session: {avg_tools}")
        print()

    # Token and cost statistics
    print("-" * 70)
    print("TOKEN & COST STATISTICS")
    print("-" * 70)
    print(f"Total Input Tokens: {total_input_tokens:,}")
    print(f"Total Output Tokens: {total_output_tokens:,}")
    print(f"Total Tokens: {(total_input_tokens + total_output_tokens):,}")
    print(f"Total Cost: ${total_cost:.4f}")
    print()

    # Session type breakdown
    init_sessions = [s for s in sessions if s['type'] == 'initialization']
    coding_sessions = [s for s in sessions if s['type'] == 'coding']

    print("-" * 70)
    print("SESSION TYPE BREAKDOWN")
    print("-" * 70)
    print(f"Initialization Sessions: {len(init_sessions)}")
    print(f"Coding Sessions: {len(coding_sessions)}")
    print()

    # Status breakdown
    status_counts = {}
    for session in sessions:
        status = session['status']
        status_counts[status] = status_counts.get(status, 0) + 1

    print("-" * 70)
    print("STATUS BREAKDOWN")
    print("-" * 70)
    for status, count in sorted(status_counts.items()):
        print(f"{status}: {count}")
    print()

    # Error summary
    error_sessions = [s for s in sessions if s.get('error_message')]
    if error_sessions:
        print("-" * 70)
        print(f"ERRORS ({len(error_sessions)} sessions with errors)")
        print("-" * 70)
        for session in error_sessions[:10]:  # Show first 10
            session_num = session['session_number']
            error = session.get('error_message', '')
            # First line only
            error_line = error.split('\n')[0][:80]
            print(f"Session {session_num}: {error_line}")

        if len(error_sessions) > 10:
            print(f"... and {len(error_sessions) - 10} more errors")
        print()

    # Most recent session
    print("-" * 70)
    print("MOST RECENT SESSION")
    print("-" * 70)
    latest = max(sessions, key=lambda s: s['session_number'])
    print(f"Session {latest['session_number']} [{latest['type']}] - {latest['status']}")
    print(f"Model: {latest.get('model', 'unknown')}")

    if latest.get('started_at'):
        print(f"Started: {latest['started_at'].strftime('%Y-%m-%d %H:%M:%S')}")
    if latest.get('ended_at'):
        print(f"Ended: {latest['ended_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    metrics = latest.get('metrics', {})
    print(f"Duration: {round(metrics.get('duration_seconds', 0) / 60, 1)} minutes")
    print(f"Tool Calls: {metrics.get('tool_calls_count', 0)}")
    print(f"Tasks Completed: {metrics.get('tasks_completed', 0)}")
    print(f"Tests Passed: {metrics.get('tests_passed', 0)}")

    if latest.get('log_path'):
        print(f"\nLog file: {latest['log_path']}")

    print()
    print("=" * 70)


async def analyze_all_projects(db: TaskDatabase):
    """Analyze all projects."""
    projects = await db.list_projects()

    for i, project in enumerate(projects):
        if i > 0:
            print("\n\n")
        await analyze_project(db, project['id'], project['name'])


async def main():
    """Main entry point."""

    # Get database URL from environment
    db_url = os.getenv('DATABASE_URL', 'postgresql://localhost/autonomous_coding')
    db = TaskDatabase(db_url)
    await db.connect()

    try:
        # Parse arguments
        if len(sys.argv) < 2:
            print("Usage:")
            print("  python scripts/analyze_sessions.py <project_name_or_id>")
            print("  python scripts/analyze_sessions.py --list")
            print("  python scripts/analyze_sessions.py --all")
            sys.exit(1)

        arg = sys.argv[1]

        if arg == '--list':
            await list_projects(db)
        elif arg == '--all':
            await analyze_all_projects(db)
        else:
            # Try to parse as UUID first
            try:
                project_id = UUID(arg)
                await analyze_project(db, project_id, arg)
            except ValueError:
                # Not a UUID, try as project name
                projects = await db.list_projects()
                matching = [p for p in projects if p['name'].lower() == arg.lower()]

                if not matching:
                    # Try partial match
                    matching = [p for p in projects if arg.lower() in p['name'].lower()]

                if len(matching) == 0:
                    print(f"Error: No project found matching '{arg}'")
                    print("\nAvailable projects:")
                    for p in projects:
                        print(f"  - {p['name']}")
                    sys.exit(1)
                elif len(matching) > 1:
                    print(f"Error: Multiple projects match '{arg}':")
                    for p in matching:
                        print(f"  - {p['name']} ({p['id']})")
                    print("\nPlease use the exact name or UUID.")
                    sys.exit(1)
                else:
                    project = matching[0]
                    await analyze_project(db, project['id'], project['name'])

    finally:
        await db.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
