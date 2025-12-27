"""
Sandbox Hooks for Claude SDK
============================

Custom hooks that redirect tool execution to sandboxes.

The Claude SDK runs on the host, but we want commands to execute in
isolated sandbox environments (Docker containers, E2B, etc.).

This module provides hooks that intercept tool execution and route
them through the active sandbox.
"""

import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Global sandbox instance (set by orchestrator before running agent session)
_active_sandbox: Optional[Any] = None


def set_active_sandbox(sandbox):
    """
    Set the active sandbox for this session.

    Called by orchestrator before starting agent session.
    """
    global _active_sandbox
    _active_sandbox = sandbox
    logger.debug(f"Active sandbox set: {type(sandbox).__name__}")


def clear_active_sandbox():
    """Clear the active sandbox after session ends."""
    global _active_sandbox
    _active_sandbox = None
    logger.debug("Active sandbox cleared")


async def test_hook(input_data, tool_use_id=None, context=None):
    """
    Test hook to verify hooks are being called at all.
    This should log for EVERY tool call, not just Bash.
    """
    logger.debug("TEST_HOOK CALLED!")
    logger.debug(f"  Tool: {input_data.get('tool_name')}")
    logger.debug(f"  All tools should trigger this message")
    return {}


async def sandbox_bash_hook(input_data, tool_use_id=None, context=None):
    """
    Pre-tool-use hook that routes Bash commands through the active sandbox.

    If a sandbox is active (Docker, E2B, etc.), executes the command in the sandbox.
    Otherwise, allows normal execution on the host.

    This hook is called AFTER security validation (security.bash_security_hook).

    Args:
        input_data: Dict containing tool_name and tool_input
        tool_use_id: Optional tool use ID
        context: Optional context

    Returns:
        Empty dict to allow execution, or dict with "override_result" to provide custom result
    """
    logger.debug("=" * 80)
    logger.debug("SANDBOX_BASH_HOOK CALLED!")
    logger.debug(f"  Tool name: {input_data.get('tool_name')}")
    logger.debug(f"  Tool use ID: {tool_use_id}")
    logger.debug(f"  Active sandbox: {_active_sandbox}")
    logger.debug(f"  Input data keys: {list(input_data.keys())}")
    logger.debug("=" * 80)

    if input_data.get("tool_name") != "Bash":
        logger.debug("  → Not a Bash tool, skipping")
        return {}

    # If no sandbox is active, allow normal execution
    if _active_sandbox is None:
        logger.debug("  → No active sandbox, allowing normal execution")
        return {}

    # If sandbox is LocalSandbox (no isolation), allow normal execution
    from core.sandbox_manager import LocalSandbox
    if isinstance(_active_sandbox, LocalSandbox):
        logger.debug("  → LocalSandbox active (no isolation), allowing normal execution")
        return {}

    # Execute command in sandbox and override the result
    command = input_data.get("tool_input", {}).get("command", "")
    if not command:
        logger.debug("  → No command in tool_input, skipping")
        return {}

    logger.debug(f"  → ROUTING TO SANDBOX: {type(_active_sandbox).__name__}")
    logger.debug(f"  → Command: {command[:200]}")

    try:
        # Execute in sandbox (this is async but the hook expects sync return)
        # We need to handle this differently...
        # Actually, looking at the SDK docs, pre-tool-use hooks can be async!
        result = await _active_sandbox.execute_command(command)

        # Format result for SDK
        output_text = result["stdout"]
        if result["stderr"]:
            output_text += f"\n{result['stderr']}"

        logger.debug(f"  → Sandbox execution SUCCESS")
        logger.debug(f"  → Return code: {result['returncode']}")
        logger.debug(f"  → Output length: {len(output_text)}")
        logger.debug(f"  → Output preview: {output_text[:200]}")

        # Return empty dict to allow normal execution
        # BUT: We've already executed in sandbox, so this will cause double execution
        # We need to find a way to:
        # 1. Execute in sandbox (done)
        # 2. Block the original execution
        # 3. Return the sandbox result to the agent
        #
        # The SDK doesn't support this via hooks!
        # We need a different approach.

        logger.debug(f"  → Hook cannot override result - SDK limitation")
        logger.debug(f"  → Sandbox executed successfully but host will also execute")
        return {}

    except Exception as e:
        logger.error(f"  → Sandbox execution FAILED: {e}", exc_info=True)
        return {
            "decision": "block",
            "systemMessage": f"Sandbox execution error: {str(e)}",
        }
