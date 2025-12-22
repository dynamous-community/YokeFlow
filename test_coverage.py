"""
Test Coverage Analysis Module
==============================

Analyzes test coverage by epic for projects after initialization.
Provides statistics and identifies epics with poor test coverage.
"""
from collections import defaultdict
from typing import Dict, List, Any, Optional
from uuid import UUID
from decimal import Decimal


def serialize_for_json(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects to JSON-serializable types.

    Handles:
    - UUID -> str
    - Decimal -> float
    - datetime -> ISO format string
    - dict -> recursively processed dict
    - list -> recursively processed list
    """
    from datetime import datetime

    if isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: serialize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [serialize_for_json(item) for item in obj]
    else:
        return obj


async def analyze_test_coverage(db, project_id: UUID) -> Dict[str, Any]:
    """
    Analyze test coverage for a project.

    Args:
        db: TaskDatabase instance (already connected)
        project_id: UUID of the project to analyze

    Returns:
        Dictionary with coverage analysis results:
        {
            'overall': {
                'total_epics': int,
                'total_tasks': int,
                'total_tests': int,
                'tasks_with_tests': int,
                'tasks_without_tests': int,
                'avg_tests_per_task': float,
                'coverage_percentage': float  # % of tasks with at least 1 test
            },
            'by_epic': [
                {
                    'epic_id': int,
                    'epic_name': str,
                    'total_tasks': int,
                    'tasks_with_tests': int,
                    'tasks_without_tests': int,
                    'total_tests': int,
                    'coverage_percentage': float,
                    'tasks_0_tests': [task_dict, ...],
                    'tasks_1_test': [task_dict, ...],
                    'tasks_2plus_tests': [task_dict, ...]
                },
                ...
            ],
            'poor_coverage_epics': [
                {
                    'epic_id': int,
                    'epic_name': str,
                    'tasks_without_tests': int,
                    'total_tasks': int,
                    'coverage_percentage': float,
                    'tasks': [task_dict, ...]  # Tasks without tests
                },
                ...
            ],
            'warnings': [str, ...]  # Human-readable warnings
        }
    """
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
            'epic_id': 0,
            'epic_name': '',
            'total_tasks': 0,
            'tasks_with_tests': 0,
            'tasks_without_tests': 0,
            'total_tests': 0,
            'coverage_percentage': 0.0,
            'tasks_0_tests': [],
            'tasks_1_test': [],
            'tasks_2plus_tests': []
        })

        for task in tasks:
            epic_id = task['epic_id']
            test_count = task_test_counts.get(task['id'], 0)

            stats = epic_stats[epic_id]
            stats['epic_id'] = epic_id
            stats['epic_name'] = epics[epic_id]['name']
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
            else:
                stats['tasks_2plus_tests'].append(task)

        # Calculate coverage percentages
        for stats in epic_stats.values():
            if stats['total_tasks'] > 0:
                stats['coverage_percentage'] = (stats['tasks_with_tests'] / stats['total_tasks']) * 100

        # Overall statistics
        tasks_with_tests = sum(1 for t in tasks if task_test_counts.get(t['id'], 0) > 0)
        tasks_without_tests = len(tasks) - tasks_with_tests
        avg_tests_per_task = len(tests) / len(tasks) if len(tasks) > 0 else 0
        coverage_percentage = (tasks_with_tests / len(tasks) * 100) if len(tasks) > 0 else 0

        overall = {
            'total_epics': len(epics),
            'total_tasks': len(tasks),
            'total_tests': len(tests),
            'tasks_with_tests': tasks_with_tests,
            'tasks_without_tests': tasks_without_tests,
            'avg_tests_per_task': round(avg_tests_per_task, 2),
            'coverage_percentage': round(coverage_percentage, 1)
        }

        # Identify epics with poor coverage (>50% tasks without tests)
        poor_coverage_epics = []
        for epic_id, stats in epic_stats.items():
            if stats['total_tasks'] > 0:
                pct_without = stats['tasks_without_tests'] / stats['total_tasks'] * 100
                if pct_without > 50:
                    poor_coverage_epics.append({
                        'epic_id': epic_id,
                        'epic_name': stats['epic_name'],
                        'tasks_without_tests': stats['tasks_without_tests'],
                        'total_tasks': stats['total_tasks'],
                        'coverage_percentage': round(100 - pct_without, 1),
                        'tasks': stats['tasks_0_tests'][:10]  # Limit to 10 examples
                    })

        # Sort by worst coverage first
        poor_coverage_epics.sort(key=lambda x: x['coverage_percentage'])

        # Generate warnings
        warnings = []
        if coverage_percentage < 50:
            warnings.append(f"⚠️ Overall test coverage is low ({coverage_percentage:.0f}%). Consider adding more tests.")
        if len(poor_coverage_epics) > 0:
            warnings.append(f"⚠️ {len(poor_coverage_epics)} epic(s) have poor test coverage (>50% tasks without tests).")
        if tasks_without_tests > len(tasks) * 0.3:
            warnings.append(f"⚠️ {tasks_without_tests} tasks ({tasks_without_tests/len(tasks)*100:.0f}%) have no tests.")

        # Convert epic_stats to list and sort by epic_id
        by_epic = sorted(epic_stats.values(), key=lambda x: x['epic_id'])

        # Serialize all data to ensure JSON compatibility (convert UUIDs, Decimals, etc.)
        result = {
            'overall': overall,
            'by_epic': by_epic,
            'poor_coverage_epics': poor_coverage_epics,
            'warnings': warnings
        }
        return serialize_for_json(result)


def format_coverage_summary(coverage_data: Dict[str, Any]) -> str:
    """
    Format coverage analysis results as human-readable text.

    Args:
        coverage_data: Result from analyze_test_coverage()

    Returns:
        Formatted text summary
    """
    lines = []
    overall = coverage_data['overall']

    lines.append("=" * 80)
    lines.append("TEST COVERAGE ANALYSIS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Overall Statistics:")
    lines.append(f"  Total epics: {overall['total_epics']}")
    lines.append(f"  Total tasks: {overall['total_tasks']}")
    lines.append(f"  Total tests: {overall['total_tests']}")
    lines.append(f"  Tasks with tests: {overall['tasks_with_tests']} ({overall['coverage_percentage']:.1f}%)")
    lines.append(f"  Tasks without tests: {overall['tasks_without_tests']}")
    lines.append(f"  Average tests per task: {overall['avg_tests_per_task']:.2f}")
    lines.append("")

    # Warnings
    if coverage_data['warnings']:
        lines.append("Warnings:")
        for warning in coverage_data['warnings']:
            lines.append(f"  {warning}")
        lines.append("")

    # Epic breakdown
    lines.append("=" * 100)
    lines.append(f"{'Epic ID':<10} {'Epic Name':<50} {'Tasks':<8} {'W/Tests':<10} {'No Tests':<10} {'Coverage %':<12}")
    lines.append("=" * 100)

    for epic in coverage_data['by_epic']:
        name = epic['epic_name'][:48] + '..' if len(epic['epic_name']) > 50 else epic['epic_name']
        lines.append(f"{epic['epic_id']:<10} {name:<50} {epic['total_tasks']:<8} "
                    f"{epic['tasks_with_tests']:<10} {epic['tasks_without_tests']:<10} {epic['coverage_percentage']:<12.1f}")

    lines.append("=" * 100)
    lines.append("")

    # Poor coverage epics
    if coverage_data['poor_coverage_epics']:
        lines.append("Epics with Poor Test Coverage (>50% tasks without tests):")
        lines.append("-" * 100)

        for epic in coverage_data['poor_coverage_epics']:
            lines.append(f"\nEpic {epic['epic_id']}: {epic['epic_name']}")
            lines.append(f"  {epic['tasks_without_tests']}/{epic['total_tasks']} tasks without tests ({100-epic['coverage_percentage']:.0f}%)")
            lines.append(f"  Tasks without tests:")
            for task in epic['tasks'][:5]:
                desc = task['description'][:90] + '...' if len(task['description']) > 93 else task['description']
                lines.append(f"    - Task {task['id']}: {desc}")
            if len(epic['tasks']) > 5:
                lines.append(f"    ... and {len(epic['tasks']) - 5} more")

    return "\n".join(lines)
