#!/usr/bin/env python3
"""
Analyze test coverage by epic for any project.

This script analyzes the relationship between tasks and tests created during
the initialization session. It provides:
- Overall statistics (tasks, tests, coverage percentages)
- Test distribution (0 tests, 1 test, 2+ tests per task)
- Epic-level breakdown showing which epics have poor test coverage
- List of tasks without tests for review

Usage:
    export DATABASE_URL=postgresql://user:pass@host:port/db
    python analyze_test_coverage.py

Note: Update the project name in the script to analyze different projects,
or pass as command-line argument in future enhancement.

Future Enhancement: See TODO.md "Post-Initialization Test Coverage Report"
for plans to integrate this into the platform workflow.
"""
import asyncio
import os
import sys
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import TaskDatabase

async def analyze_coverage():
    # Get DATABASE_URL from environment
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return

    db = TaskDatabase(db_url)
    await db.connect()

    try:
        # Get project ID
        projects = await db.list_projects()
        youtube_coach = [p for p in projects if p['name'] == 'youtube-coach']
        if not youtube_coach:
            print('Project not found')
            return

        project_id = youtube_coach[0]['id']
        print(f"=== Test Coverage Analysis for youtube-coach ===")
        print(f"Project ID: {project_id}")
        print()

        # Query using raw SQL
        async with db.acquire() as conn:
            # Get all epics
            epic_rows = await conn.fetch(
                "SELECT * FROM epics WHERE project_id = $1 ORDER BY id",
                project_id
            )
            epics = {row['id']: dict(row) for row in epic_rows}

            # Get all tasks
            task_rows = await conn.fetch(
                "SELECT * FROM tasks WHERE project_id = $1 ORDER BY epic_id, id",
                project_id
            )
            tasks = [dict(row) for row in task_rows]

            # Get all tests
            test_rows = await conn.fetch(
                "SELECT * FROM tests WHERE project_id = $1 ORDER BY task_id",
                project_id
            )
            tests = [dict(row) for row in test_rows]

            # Build map of task_id -> test count
            task_test_counts = {}
            for test in tests:
                task_id = test['task_id']
                task_test_counts[task_id] = task_test_counts.get(task_id, 0) + 1

            # Analyze by epic
            epic_stats = defaultdict(lambda: {
                'name': '',
                'total_tasks': 0,
                'tasks_with_tests': 0,
                'tasks_without_tests': 0,
                'total_tests': 0,
                'tasks_0_tests': [],
                'tasks_1_test': [],
                'tasks_2_tests': []
            })

            for task in tasks:
                epic_id = task['epic_id']
                test_count = task_test_counts.get(task['id'], 0)

                stats = epic_stats[epic_id]
                stats['name'] = epics[epic_id]['name']
                stats['total_tasks'] += 1
                stats['total_tests'] += test_count

                if test_count > 0:
                    stats['tasks_with_tests'] += 1
                else:
                    stats['tasks_without_tests'] += 1

                # Track by test count
                if test_count == 0:
                    stats['tasks_0_tests'].append(task)
                elif test_count == 1:
                    stats['tasks_1_test'].append(task)
                elif test_count == 2:
                    stats['tasks_2_tests'].append(task)

            # Overall summary
            print(f"Overall Statistics:")
            print(f"  Total epics: {len(epics)}")
            print(f"  Total tasks: {len(tasks)}")
            print(f"  Total tests: {len(tests)}")
            print(f"  Tasks with tests: {sum(1 for t in tasks if task_test_counts.get(t['id'], 0) > 0)}")
            print(f"  Tasks without tests: {sum(1 for t in tasks if task_test_counts.get(t['id'], 0) == 0)}")
            print(f"  Average tests per task: {len(tests) / len(tasks):.2f}")
            print()

            # Epic-level breakdown
            print("=" * 100)
            print(f"{'Epic ID':<10} {'Epic Name':<50} {'Tasks':<8} {'W/Tests':<10} {'No Tests':<10} {'Total Tests':<12}")
            print("=" * 100)

            for epic_id in sorted(epic_stats.keys()):
                stats = epic_stats[epic_id]
                name = stats['name'][:48] + '..' if len(stats['name']) > 50 else stats['name']
                print(f"{epic_id:<10} {name:<50} {stats['total_tasks']:<8} "
                      f"{stats['tasks_with_tests']:<10} {stats['tasks_without_tests']:<10} {stats['total_tests']:<12}")

            print("=" * 100)
            print()

            # Epics with poor test coverage (more than 50% tasks without tests)
            print("Epics with Poor Test Coverage (>50% tasks without tests):")
            print("-" * 100)
            poor_coverage = []
            for epic_id, stats in epic_stats.items():
                if stats['total_tasks'] > 0:
                    pct_without = stats['tasks_without_tests'] / stats['total_tasks'] * 100
                    if pct_without > 50:
                        poor_coverage.append((epic_id, stats, pct_without))

            poor_coverage.sort(key=lambda x: x[2], reverse=True)

            for epic_id, stats, pct in poor_coverage:
                print(f"\nEpic {epic_id}: {stats['name']}")
                print(f"  {stats['tasks_without_tests']}/{stats['total_tasks']} tasks without tests ({pct:.0f}%)")
                print(f"  Tasks without tests:")
                for task in stats['tasks_0_tests'][:5]:
                    desc = task['description'][:90] + '...' if len(task['description']) > 93 else task['description']
                    print(f"    - Task {task['id']}: {desc}")
                if len(stats['tasks_0_tests']) > 5:
                    print(f"    ... and {len(stats['tasks_0_tests']) - 5} more")

    finally:
        await db.disconnect()

if __name__ == '__main__':
    asyncio.run(analyze_coverage())
