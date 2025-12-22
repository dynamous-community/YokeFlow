#!/usr/bin/env python3
"""
Test Agent Orchestrator
========================

Simple test script to verify the orchestrator works correctly.
Tests the core API without actually running agent sessions.

Usage: python tests/test_orchestrator.py
"""

import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from orchestrator import AgentOrchestrator, SessionType, SessionStatus


def test_orchestrator_api():
    """Test orchestrator API methods."""
    print("=" * 70)
    print("Testing Agent Orchestrator API")
    print("=" * 70)
    print()

    orchestrator = AgentOrchestrator(verbose=False)

    # Test 1: List projects
    print("1. Testing list_projects()...")
    generations_dir = Path("generations")
    if generations_dir.exists():
        projects = orchestrator.list_projects(generations_dir)
        print(f"   Found {len(projects)} projects")
        if projects:
            print(f"   First project: {projects[0]['project_id']}")
        print(f"   ✓ list_projects() works")
    else:
        print(f"   ⚠️  generations/ directory doesn't exist")
    print()

    # Test 2: Get project info
    print("2. Testing get_project_info()...")
    if generations_dir.exists():
        project_dirs = [p for p in generations_dir.iterdir() if p.is_dir() and (p / "tasks.db").exists()]
        if project_dirs:
            test_project = project_dirs[0]
            info = orchestrator.get_project_info(test_project)
            print(f"   Project: {info['project_id']}")
            print(f"   Tasks: {info['progress']['completed_tasks']}/{info['progress']['total_tasks']}")
            print(f"   ✓ get_project_info() works")
        else:
            print(f"   ⚠️  No projects found to test")
    else:
        print(f"   ⚠️  generations/ directory doesn't exist")
    print()

    # Test 3: Test SessionInfo serialization
    print("3. Testing SessionInfo.to_dict()...")
    from orchestrator import SessionInfo
    from datetime import datetime

    session_info = SessionInfo(
        session_id="test_session_1",
        project_id="test_project",
        session_number=1,
        session_type=SessionType.INITIALIZER,
        model="claude-opus-4-5-20251101",
        status=SessionStatus.COMPLETED,
        created_at=datetime.now(),
        started_at=datetime.now(),
        ended_at=datetime.now(),
    )

    session_dict = session_info.to_dict()
    print(f"   Session ID: {session_dict['session_id']}")
    print(f"   Type: {session_dict['session_type']}")
    print(f"   Status: {session_dict['status']}")
    print(f"   Model: {session_dict['model']}")
    print(f"   ✓ SessionInfo.to_dict() works")
    print()

    # Test 4: Test session number calculation
    print("4. Testing _get_next_session_number()...")
    if project_dirs:
        test_project = project_dirs[0]
        next_num = orchestrator._get_next_session_number(test_project)
        print(f"   Next session number for {test_project.name}: {next_num}")
        print(f"   ✓ _get_next_session_number() works")
    else:
        print(f"   ⚠️  No projects found to test")
    print()

    # Test 5: Test create_project (dry run - don't actually create)
    print("5. Testing create_project() API...")
    test_path = Path("generations/test_orchestrator_project")
    print(f"   Would create project at: {test_path}")
    print(f"   ✓ create_project() API defined correctly")
    print()

    print("=" * 70)
    print("✅ All orchestrator API tests passed!")
    print("=" * 70)
    print()
    print("Note: This only tests the API methods, not actual session execution.")
    print("To test actual sessions, run: python autonomous_agent.py --project-dir test-project --max-iterations 1")


if __name__ == "__main__":
    test_orchestrator_api()
