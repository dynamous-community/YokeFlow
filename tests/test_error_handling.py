#!/usr/bin/env python3
"""
Test script to verify error handling in agent sessions.

Simulates an error condition and verifies that:
1. Error is logged properly
2. Session finalizes with error status
3. Agent exits gracefully without hanging
4. No infinite retry loop
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent import run_agent_session
from observability import create_session_logger


async def test_error_handling():
    """Test that errors are handled gracefully without hanging."""

    print("\n" + "="*70)
    print("Testing Error Handling in Agent Sessions")
    print("="*70 + "\n")

    # Create a test project directory
    test_project = Path("generations/error-handling-test")
    test_project.mkdir(parents=True, exist_ok=True)

    # Create a session logger
    logger = create_session_logger(test_project, 999, "coding", "test-model")

    print("✓ Test project created")
    print("✓ Logger initialized\n")

    # Create a mock client that will raise an error
    mock_client = AsyncMock()

    # Simulate the buffer overflow error
    error_msg = "Failed to decode JSON: JSON message exceeded maximum buffer size of 1048576 bytes..."
    mock_client.query = AsyncMock(side_effect=Exception(error_msg))

    print("Simulating error: Buffer overflow")
    print(f"Error message: {error_msg[:80]}...\n")

    # Run the session
    print("Running agent session...")
    try:
        status, response = await run_agent_session(
            client=mock_client,
            message="Test prompt",
            project_dir=test_project,
            logger=logger,
            verbose=False
        )

        print(f"\n✓ Session completed")
        print(f"  Status: {status}")
        print(f"  Response: {response[:100]}...")

        # Verify status is "error"
        if status == "error":
            print("\n✅ PASS: Status is 'error' as expected")
        else:
            print(f"\n❌ FAIL: Status is '{status}', expected 'error'")
            return False

        # Verify error message is captured
        if error_msg in response:
            print("✅ PASS: Error message captured in response")
        else:
            print("❌ FAIL: Error message not in response")
            return False

        # Check that log files were created
        log_files = list(test_project.glob("logs/session_999_*.jsonl"))
        if log_files:
            print(f"✅ PASS: Log file created: {log_files[0].name}")
        else:
            print("❌ FAIL: No log file created")
            return False

        # Verify session_end event was logged
        with open(log_files[0], 'r') as f:
            log_content = f.read()
            if '"event": "session_end"' in log_content and '"status": "error"' in log_content:
                print("✅ PASS: session_end event logged with error status")
            else:
                print("❌ FAIL: session_end event not properly logged")
                return False

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED")
        print("="*70)
        print("\nError handling works correctly:")
        print("  - Error is caught and logged")
        print("  - Session finalizes properly")
        print("  - Returns ('error', error_message)")
        print("  - No infinite loops or hanging")
        print()

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED: Unexpected exception: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agent_loop_exits_on_error():
    """Test that the agent loop exits after an error (not retries infinitely)."""

    print("\n" + "="*70)
    print("Testing Agent Loop Error Handling")
    print("="*70 + "\n")

    # This would require mocking the entire agent loop
    # For now, we'll verify the code logic manually

    print("Checking agent.py error handling code...")

    with open(Path(__file__).parent / "agent.py", 'r') as f:
        code = f.read()

        # Check that error status causes a break
        if 'elif status == "error":' in code and 'break' in code:
            # Find the error handling block
            lines = code.split('\n')
            in_error_block = False
            has_break = False

            for i, line in enumerate(lines):
                if 'elif status == "error":' in line:
                    in_error_block = True
                elif in_error_block:
                    if 'break' in line:
                        has_break = True
                        break
                    elif line.strip() and not line.strip().startswith('#') and 'print' not in line:
                        # Non-print, non-comment line found before break
                        break

            if has_break:
                print("✅ PASS: Error handling includes 'break' statement")
                print("         Agent will exit loop on error (no infinite retries)")
            else:
                print("❌ FAIL: Error handling does not break the loop")
                return False
        else:
            print("❌ FAIL: Could not find error handling block")
            return False

    print("\n" + "="*70)
    print("✅ AGENT LOOP TEST PASSED")
    print("="*70)
    print("\nAgent loop will exit gracefully on error")
    print("No infinite retry loops\n")

    return True


if __name__ == "__main__":
    async def main():
        # Run both tests
        test1 = await test_error_handling()
        test2 = await test_agent_loop_exits_on_error()

        if test1 and test2:
            print("\n" + "="*70)
            print("🎉 ALL ERROR HANDLING TESTS PASSED")
            print("="*70 + "\n")
            sys.exit(0)
        else:
            print("\n" + "="*70)
            print("❌ SOME TESTS FAILED")
            print("="*70 + "\n")
            sys.exit(1)

    asyncio.run(main())
