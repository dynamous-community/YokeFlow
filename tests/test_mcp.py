#!/usr/bin/env python3
"""
Test script to verify MCP task manager server is working.
Run this to test the MCP tools before running the full autonomous agent.

Usage: python tests/test_mcp.py (from project root)
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from client import create_client

async def test_mcp_tools():
    """Test basic MCP tools functionality."""
    print("Testing MCP Task Manager Integration")
    print("=" * 50)

    # Create a test project directory
    test_dir = Path("test_mcp_project")
    test_dir.mkdir(exist_ok=True)

    # Initialize database
    # Path from tests/ to project root
    project_root = Path(__file__).parent.parent
    schema_path = project_root / "schema" / "schema.sql"
    tasks_db = test_dir / "tasks.db"

    if not tasks_db.exists():
        import subprocess
        print("Creating test database...")
        subprocess.run(f"sqlite3 {tasks_db} < {schema_path}", shell=True)

    # Create client with MCP
    print("Creating Claude client with MCP task manager...")
    client = create_client(test_dir, "claude-3-5-sonnet-20241022")

    # Test prompts
    test_prompts = [
        # Test 1: Check status
        """Use the MCP tool mcp__task-manager__task_status to check the overall project status.
        Just call the tool and show me the results.""",

        # Test 2: Create an epic
        """Use the MCP tool mcp__task-manager__create_epic to create an epic with:
        name: "Test Epic"
        description: "This is a test epic for MCP verification"
        priority: 1

        Then use mcp__task-manager__list_epics to show all epics.""",

        # Test 3: Expand the epic
        """Use the MCP tool mcp__task-manager__expand_epic to expand epic 1 with these tasks:
        [
            {
                "description": "First test task",
                "action": "This is the action for the first test task"
            },
            {
                "description": "Second test task",
                "action": "This is the action for the second test task"
            }
        ]

        Then use mcp__task-manager__get_epic with epic_id 1 to show the epic details.""",
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n\nTest {i}:")
        print("-" * 30)
        print(f"Prompt: {prompt[:100]}...")

        async with client:
            try:
                response = await client.send_message(prompt)
                print(f"Response: {response.content[:200]}...")
                print("✅ Test passed")
            except Exception as e:
                print(f"❌ Test failed: {e}")
                break

    print("\n" + "=" * 50)
    print("MCP Testing Complete")
    print(f"Check {test_dir}/tasks.db for the created data")

if __name__ == "__main__":
    try:
        asyncio.run(test_mcp_tools())
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()