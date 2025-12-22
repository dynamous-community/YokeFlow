"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
"""

import json
import os
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, HookMatcher

from security import bash_security_hook
from sandbox_hooks import sandbox_bash_hook, test_hook



def get_mcp_env(project_dir: Path, project_id: str = None, docker_container: str = None) -> dict:
    """
    Get environment variables for MCP task-manager server.

    Args:
        project_dir: Project directory path
        project_id: UUID of the project in the database (optional, will be generated if not provided)
        docker_container: Docker container name for bash_docker tool (optional)
    """
    import os
    import uuid

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required")

    # Use provided project_id or generate from project name
    if not project_id:
        project_name = project_dir.name
        # Generate deterministic UUID based on project name (fallback)
        project_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, project_name))
        print(f"[DEBUG] MCP task-manager using generated UUID for project: {project_name} (ID: {project_id})")
    else:
        project_name = project_dir.name
        print(f"[DEBUG] MCP task-manager using PostgreSQL for project: {project_name} (ID: {project_id})")

    env = {
        "DATABASE_URL": database_url,
        "PROJECT_ID": project_id
    }

    # Add Docker container name if provided (for bash_docker tool)
    if docker_container:
        env["DOCKER_CONTAINER_NAME"] = docker_container
        print(f"[DEBUG] MCP task-manager configured for Docker sandbox: {docker_container}")

    return env


def create_client(project_dir: Path, model: str, project_id: str = None, docker_container: str = None) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        project_id: UUID of the project in the database (optional)
        docker_container: Docker container name for sandbox execution (optional)

    Returns:
        Configured ClaudeSDKClient

    Security layers (defense in depth):
    1. BypassPermissions - Agent has broad tool access for autonomous operation
    2. Security hooks - Bash commands validated against a blocklist
       (see security.py for BLOCKED_COMMANDS)

    This configuration is designed for containerized environments where the agent
    needs broad command access to work autonomously without constant permission prompts.
    """

    # Ensure authentication is properly configured
    # The generated app may set ANTHROPIC_API_KEY in its environment, which can leak
    # into our agent process. We explicitly remove it and prefer CLAUDE_CODE_OAUTH_TOKEN.
    from dotenv import load_dotenv

    # CRITICAL FIX: Remove any leaked ANTHROPIC_API_KEY BEFORE loading agent's .env
    # If we don't do this first, the leaked key persists in os.environ and gets picked up
    # by the Claude SDK even though we load our .env file after.
    # This happens because environment variables persist across module imports.
    os.environ.pop("ANTHROPIC_API_KEY", None)

    # CRITICAL: Load .env from agent's root directory, NOT from project directory
    # The project directory may have its own .env file with ANTHROPIC_API_KEY for the generated app
    agent_root = Path(__file__).parent  # /path/to/autonomous-coding/
    agent_env_file = agent_root / ".env"
    load_dotenv(dotenv_path=agent_env_file)  # Load from agent's .env file only

    # Now check for authentication (after cleaning environment and loading our .env)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    oauth_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")

    if api_key:
        raise RuntimeError(
            "  - ANTHROPIC_API_KEY is set"
        )

    # Explicitly set OAuth token for the Claude SDK subprocess
    if oauth_token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

    # Configure MCP task manager server
    mcp_server_path = Path(__file__).parent / "mcp-task-manager" / "dist" / "index.js"
    if not mcp_server_path.exists():
        raise FileNotFoundError(
            f"MCP task manager server not found at {mcp_server_path}. "
            f"Run 'cd mcp-task-manager && npm install && npm run build' to build it."
        )

    # Configure MCP servers
    mcp_servers = {
        "playwright": {
            "command": "npx",
            "args": [
                "@playwright/mcp@latest",
                "--browser", "chrome",
                "--headless",
                "--snapshot-mode", "incremental"  # Reduce snapshot size to avoid buffer overflow
            ]
        },
        "task-manager": {
            "command": "node",
            "args": [str(mcp_server_path)],
            "env": get_mcp_env(project_dir, project_id, docker_container)
        }
    }

    # Build system prompt
    # NOTE: Sandbox-specific guidance (tool selection) is now prepended to prompts
    # in prompts.py (get_initializer_prompt/get_coding_prompt with sandbox_type parameter)
    # This base prompt is minimal and generic
    system_prompt = "You are an expert full-stack developer building a production-quality web application."

    # Prepare environment for SDK subprocess
    # CRITICAL: Explicitly pass cleaned environment to prevent .env leakage
    # The SDK subprocess will have cwd=project_dir, and if it calls load_dotenv(),
    # it would load the project's .env file. By explicitly setting env vars here,
    # we ensure our cleaned environment takes precedence.
    sdk_env = {}

    # Only pass OAuth token if we have it (preferred authentication method)
    if oauth_token:
        sdk_env["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token

    # CRITICAL: Explicitly unset ANTHROPIC_API_KEY in subprocess environment
    # Even though we removed it from parent process, the subprocess might load it
    # from the project's .env file when it runs with cwd=project_dir.
    # The env dict in ClaudeAgentOptions MERGES with parent environment, so we
    # need to explicitly override ANTHROPIC_API_KEY to prevent it from being used.
    # Setting to empty string tells the SDK not to use an API key.
    sdk_env["ANTHROPIC_API_KEY"] = ""

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",
            mcp_servers=mcp_servers,
            hooks={
                "PreToolUse": [
                    # Test hook to verify hooks work at all (matches ALL tools)
                    HookMatcher(matcher="*", hooks=[test_hook]),
                    # Security hook runs first (validates commands)
                    HookMatcher(matcher="Bash", hooks=[bash_security_hook]),
                    # Sandbox hook runs second (routes to container if sandbox active)
                    HookMatcher(matcher="Bash", hooks=[sandbox_bash_hook]),
                ],
            },
            max_turns=1000,
            max_buffer_size=10485760,  # 10MB (10x default of 1MB) - prevents Playwright snapshot crashes
            cwd=str(project_dir.resolve()),
            env=sdk_env  # Explicitly set environment to prevent .env leakage
        )
    )
