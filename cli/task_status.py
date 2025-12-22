#!/usr/bin/env python3
"""
Task Status Viewer
==================

A simple CLI tool to view the status of tasks in a project database.
Can be used while the agent is running or standalone.

Uses PostgreSQL database via database_connection.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import asyncio
from typing import Optional, Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn
from rich.panel import Panel
from rich.layout import Layout
from rich import box
import json

from database_connection import DatabaseManager
from uuid import UUID

console = Console()

async def show_overall_progress(db, project_id: UUID) -> None:
    """Show overall project progress."""
    # Get overall stats
    stats = await db.get_progress(project_id)

    # Create progress display
    epic_progress = (stats['completed_epics'] / stats['total_epics'] * 100) if stats['total_epics'] > 0 else 0
    task_progress = (stats['completed_tasks'] / stats['total_tasks'] * 100) if stats['total_tasks'] > 0 else 0
    test_progress = (stats['passing_tests'] / stats['total_tests'] * 100) if stats['total_tests'] > 0 else 0

    # Create a nice panel with progress bars
    progress_text = f"""
[bold cyan]📊 Overall Progress[/bold cyan]

[yellow]Epics:[/yellow]    {stats['completed_epics']}/{stats['total_epics']} ({epic_progress:.1f}%)
[green]Tasks:[/green]    {stats['completed_tasks']}/{stats['total_tasks']} ({task_progress:.1f}%)
[blue]Tests:[/blue]    {stats['passing_tests']}/{stats['total_tests']} ({test_progress:.1f}%)
"""

    console.print(Panel(progress_text, title="Project Status", border_style="bright_blue"))

async def show_epic_details(db, project_id: UUID, epic_id: Optional[int] = None) -> None:
    """Show detailed epic information."""
    if epic_id:
        # Get single epic
        async with db.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM epics WHERE id = $1 AND project_id = $2", epic_id, project_id)
            if row:
                epic = dict(row)
                # Get task counts
                tasks = await db.list_tasks(project_id, epic_id=epic_id)
                epic['total_tasks'] = len(tasks)
                epic['completed_tasks'] = sum(1 for t in tasks if t.get('done'))
                epics = [epic]
            else:
                epics = []
    else:
        # Get all epics with progress
        epics_list = await db.list_epics(project_id)
        epic_progress = await db.get_epic_progress(project_id)

        # Merge epic data with progress
        progress_by_id = {ep['epic_id']: ep for ep in epic_progress}
        epics = []
        for epic in epics_list:
            epic_data = dict(epic)
            prog = progress_by_id.get(epic['id'], {})
            epic_data['total_tasks'] = prog.get('total_tasks', 0)
            epic_data['completed_tasks'] = prog.get('completed_tasks', 0)
            epics.append(epic_data)

    # Create table
    table = Table(title="Epics", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Tasks", justify="center")
    table.add_column("Progress", justify="center")
    table.add_column("Priority", justify="center")

    for epic in epics:
        completed = epic.get('completed_tasks', 0) or 0
        total = epic.get('total_tasks', 0) or 0
        progress = f"{completed}/{total}"

        # Color code status
        status_style = {
            'pending': 'dim',
            'in_progress': 'yellow',
            'completed': 'green'
        }.get(epic.get('status', 'pending'), 'white')

        table.add_row(
            str(epic['id']),
            epic['name'][:40],
            f"[{status_style}]{epic.get('status', 'pending')}[/{status_style}]",
            progress,
            f"{(completed/total*100) if total > 0 else 0:.0f}%",
            str(epic.get('priority', 0))
        )

    console.print(table)

async def show_pending_tasks(db, project_id: UUID, limit: int = 10) -> None:
    """Show pending tasks."""
    tasks = await db.list_tasks(project_id, only_pending=True, limit=limit)

    if not tasks:
        console.print("[green]✨ No pending tasks![/green]")
        return

    table = Table(title=f"Next {limit} Pending Tasks", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Epic", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Priority", justify="center")

    for task in tasks:
        table.add_row(
            str(task['id']),
            task.get('epic_name', 'Unknown')[:30],
            task['description'][:50],
            str(task.get('priority', 0))
        )

    console.print(table)

async def show_recent_activity(db, project_id: UUID, limit: int = 10) -> None:
    """Show recent completed tasks."""
    # Get completed tasks
    tasks = await db.list_tasks(project_id, only_pending=False, limit=limit * 3)
    completed_tasks = [t for t in tasks if t.get('done')][:limit]

    if not completed_tasks:
        console.print("[dim]No recently completed tasks[/dim]")
        return

    table = Table(title=f"Recent Activity", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Epic", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Completed", style="green")

    for task in completed_tasks:
        completed_at = task.get('completed_at')
        if completed_at:
            completed_at = str(completed_at)[:19]
        else:
            completed_at = 'Unknown'

        table.add_row(
            str(task['id']),
            task.get('epic_name', 'Unknown')[:30],
            task['description'][:50],
            completed_at
        )

    console.print(table)

async def show_next_task(db, project_id: UUID) -> None:
    """Show the next task to work on."""
    task = await db.get_next_task(project_id)

    if not task:
        console.print("[green]✨ All tasks completed![/green]")
        return

    # Tests are already included in the task from get_next_task()
    tests = task.get('tests', [])

    # Create nice display
    task_info = f"""
[bold cyan]📋 Next Task[/bold cyan]

[yellow]Task ID:[/yellow] {task['id']}
[yellow]Epic:[/yellow] {task.get('epic_name', 'Unknown')}
[yellow]Description:[/yellow] {task['description']}

[dim]Action:[/dim]
{task.get('action', 'No action specified')}

[cyan]Tests ({len(tests)}):[/cyan]"""

    for test in tests:
        status = "✅" if test.get('passes') else "⭕"
        task_info += f"\n  {status} [{test.get('category', 'unknown')}] {test['description']}"

    console.print(Panel(task_info, border_style="green"))

async def watch_mode(project_name: str, refresh_interval: int = 5) -> None:
    """Watch mode - continuously update display."""
    import time
    import os

    while True:
        os.system('clear' if os.name == 'posix' else 'cls')

        try:
            async with DatabaseManager() as db:
                # Get project
                project = await db.get_project_by_name(project_name)
                if not project:
                    console.print(f"[red]Project not found: {project_name}[/red]")
                    break

                project_id = project['id']

                # Show header
                console.print("[bold magenta]Task Status Monitor[/bold magenta]", justify="center")
                console.print(f"[dim]Project: {project_name}[/dim]", justify="center")
                console.print()

                # Show progress
                await show_overall_progress(db, project_id)
                console.print()

                # Show next task
                await show_next_task(db, project_id)
                console.print()

                # Show pending tasks
                await show_pending_tasks(db, project_id, limit=5)

            console.print(f"\n[dim]Refreshing in {refresh_interval} seconds... (Ctrl+C to exit)[/dim]")
            time.sleep(refresh_interval)

        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped watching[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            import traceback
            traceback.print_exc()
            time.sleep(refresh_interval)

async def async_main(args):
    """Async main logic."""
    # Get project name from directory
    project_name = args.project_dir.name

    async with DatabaseManager() as db:
        # Get project from database
        project = await db.get_project_by_name(project_name)

        if not project:
            console.print(f"[red]Project not found in database: {project_name}[/red]")
            console.print("[dim]Make sure the project has been initialized[/dim]")
            return

        project_id = project['id']

        # Default view if no specific flag
        if not any([args.epics, args.epic, args.pending, args.recent, args.next]):
            await show_overall_progress(db, project_id)
            console.print()
            await show_next_task(db, project_id)
            console.print()
            await show_pending_tasks(db, project_id, limit=5)
        else:
            # Show requested views
            if args.epics:
                await show_epic_details(db, project_id)

            if args.epic:
                await show_epic_details(db, project_id, args.epic)

            if args.pending:
                await show_pending_tasks(db, project_id, limit=20)

            if args.recent:
                await show_recent_activity(db, project_id)

            if args.next:
                await show_next_task(db, project_id)

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="View task status for autonomous coding projects")
    parser.add_argument(
        "project_dir",
        type=Path,
        nargs="?",
        default=Path.cwd(),
        help="Project directory (default: current directory)"
    )
    parser.add_argument(
        "--epics",
        action="store_true",
        help="Show epic details"
    )
    parser.add_argument(
        "--epic",
        type=int,
        help="Show specific epic details"
    )
    parser.add_argument(
        "--pending",
        action="store_true",
        help="Show pending tasks"
    )
    parser.add_argument(
        "--recent",
        action="store_true",
        help="Show recent activity"
    )
    parser.add_argument(
        "--next",
        action="store_true",
        help="Show next task to work on"
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode - continuously update display"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Refresh interval in seconds for watch mode (default: 5)"
    )

    args = parser.parse_args()

    try:
        if args.watch:
            asyncio.run(watch_mode(args.project_dir.name, args.interval))
        else:
            asyncio.run(async_main(args))
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
