#!/usr/bin/env python3
"""
Test Database Abstraction Layer
================================

Simple test script to verify the database abstraction layer works correctly.

Usage: python tests/test_database_abstraction.py <project_path>
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from database import get_database, TaskDatabase


def test_database_abstraction(project_path: str):
    """Test all database abstraction methods."""
    print("=" * 70)
    print("Testing Database Abstraction Layer")
    print("=" * 70)
    print()

    try:
        # Initialize database
        print(f"Loading database from: {project_path}")
        db = get_database(project_path)
        print(f"✓ Database loaded: {db.get_db_path()}")
        print()

        # Test 1: Get Progress
        print("1. Testing get_progress()...")
        progress = db.get_progress()
        print(f"   Total Epics: {progress['total_epics']}")
        print(f"   Total Tasks: {progress['total_tasks']}")
        print(f"   Total Tests: {progress['total_tests']}")
        print(f"   Task Completion: {progress['task_completion_pct']:.1f}%")
        print(f"   ✓ get_progress() works")
        print()

        # Test 2: Get All Epics
        print("2. Testing get_all_epics()...")
        epics = db.get_all_epics(include_task_counts=True)
        print(f"   Found {len(epics)} epics")
        if epics:
            first_epic = epics[0]
            print(f"   First epic: {first_epic['name']}")
            print(f"   Tasks: {first_epic.get('completed_tasks', 0)}/{first_epic.get('total_tasks', 0)}")
        print(f"   ✓ get_all_epics() works")
        print()

        # Test 3: Get Next Task
        print("3. Testing get_next_task()...")
        next_task = db.get_next_task()
        if next_task:
            print(f"   Next task: {next_task['description'][:50]}...")
            print(f"   Epic: {next_task.get('epic_name', 'Unknown')}")
            print(f"   Tests: {len(next_task.get('tests', []))}")
        else:
            print(f"   No pending tasks (all complete!)")
        print(f"   ✓ get_next_task() works")
        print()

        # Test 4: Get Pending Tasks
        print("4. Testing get_pending_tasks()...")
        pending = db.get_pending_tasks(limit=5)
        print(f"   Found {len(pending)} pending tasks (limit 5)")
        print(f"   ✓ get_pending_tasks() works")
        print()

        # Test 5: Get Completed Tasks
        print("5. Testing get_completed_tasks()...")
        completed = db.get_completed_tasks(limit=5)
        print(f"   Found {len(completed)} completed tasks (limit 5)")
        print(f"   ✓ get_completed_tasks() works")
        print()

        # Test 6: Get Epic with Tasks
        if epics:
            print(f"6. Testing get_epic(include_tasks=True)...")
            epic = db.get_epic(epics[0]['id'], include_tasks=True)
            if epic:
                print(f"   Epic: {epic['name']}")
                print(f"   Tasks in epic: {len(epic.get('tasks', []))}")
                print(f"   ✓ get_epic() works")
            else:
                print(f"   ✗ Failed to get epic")
            print()

        # Test 7: Get Task with Tests
        if next_task:
            print(f"7. Testing get_task(include_tests=True)...")
            task = db.get_task(next_task['id'], include_tests=True)
            if task:
                print(f"   Task: {task['description'][:50]}...")
                print(f"   Tests: {len(task.get('tests', []))}")
                print(f"   ✓ get_task() works")
            else:
                print(f"   ✗ Failed to get task")
            print()

        # Test 8: Get Epic Progress
        print("8. Testing get_epic_progress()...")
        epic_progress = db.get_epic_progress()
        print(f"   Progress for {len(epic_progress)} epics")
        if epic_progress:
            for ep in epic_progress[:3]:  # Show first 3
                # Use .get() to handle varying column names
                epic_name = ep.get('epic_name') or ep.get('name', 'Unknown')
                completed = ep.get('completed_tasks', 0)
                total = ep.get('total_tasks', 0)
                pct = ep.get('completion_pct', 0)
                print(f"   - {epic_name}: {completed}/{total} ({pct:.0f}%)")
        print(f"   ✓ get_epic_progress() works")
        print()

        # All tests passed!
        print("=" * 70)
        print("✅ All database abstraction tests passed!")
        print("=" * 70)

    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        print("Make sure you provide a valid project directory with tasks.db")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_database_abstraction.py <project_directory>")
        print()
        print("Example:")
        print("  python test_database_abstraction.py generations/my_project")
        sys.exit(1)

    project_path = sys.argv[1]
    test_database_abstraction(project_path)
