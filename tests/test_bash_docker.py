#!/usr/bin/env python3
"""
Test script for bash_docker MCP tool.

Verifies that the bash_docker tool can execute commands in Docker containers.
"""

import asyncio
import logging
from pathlib import Path

from client import create_client
from sandbox_manager import DockerSandbox

# Enable detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_bash_docker_tool():
    """Test the bash_docker MCP tool."""

    logger.info("=" * 80)
    logger.info("BASH_DOCKER TOOL TEST")
    logger.info("=" * 80)

    # Setup
    project_dir = Path(__file__).parent / "generations" / "docker-test"
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create Docker sandbox
    logger.info("Creating Docker sandbox...")
    sandbox = DockerSandbox(
        project_dir=project_dir,
        config={
            "image": "node:20-slim",
            "network": "bridge",
            "memory_limit": "2g",
            "cpu_limit": "2.0"
        }
    )

    # Start sandbox
    logger.info("Starting Docker container...")
    await sandbox.start()
    logger.info(f"Container running: {sandbox.container_name}")

    try:
        # Create Claude SDK client with Docker container configuration
        logger.info("Creating Claude SDK client with Docker configuration...")
        client = create_client(
            project_dir=project_dir,
            model="claude-sonnet-4-5-20250929",
            project_id="test-bash-docker-tool",
            docker_container=sandbox.container_name
        )

        # Connect to SDK
        logger.info("Connecting to Claude SDK...")
        await client.connect()

        logger.info("=" * 80)
        logger.info("TESTING BASH_DOCKER TOOL")
        logger.info("=" * 80)

        # Test prompt that uses bash_docker tool
        prompt = """
        Please test the Docker sandbox by running these commands using the bash_docker tool:

        1. Run 'pwd' to show the current directory (should be /workspace)
        2. Run 'whoami' to show the current user
        3. Run 'echo "Hello from Docker!"'

        Use the mcp__task-manager__bash_docker tool for these commands.
        """

        # Send query
        await client.query(prompt)

        logger.info("Waiting for response...")

        # Collect response
        responses = []
        async for msg in client.receive_response():
            logger.info(f"Received: {type(msg).__name__}")
            responses.append(msg)

            # Show tool results
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                for block in msg.content:
                    # Show tool use
                    if hasattr(block, 'name'):
                        logger.info(f"  Tool: {block.name}")
                        if hasattr(block, 'input'):
                            logger.info(f"  Input: {block.input}")
                    # Show tool result
                    elif hasattr(block, 'tool_use_id') and hasattr(block, 'content'):
                        logger.info(f"  Result for {block.tool_use_id}:")
                        logger.info(f"    {block.content[:200]}")
                    # Show text
                    elif hasattr(block, 'text'):
                        logger.info(f"  Text: {block.text[:200]}")

        logger.info("=" * 80)
        logger.info("TEST COMPLETE")
        logger.info("=" * 80)

        # Check if bash_docker was used
        tool_uses = [
            msg for msg in responses
            if hasattr(msg, 'content') and isinstance(msg.content, list)
            for block in msg.content
            if hasattr(block, 'name') and 'bash_docker' in str(block.name)
        ]

        if tool_uses:
            logger.info(f"✅ bash_docker tool was used {len(tool_uses)} time(s)!")
        else:
            logger.warning("⚠️ bash_docker tool was not used - check if agent knows about it")

        logger.info("Full response summary:")
        for i, msg in enumerate(responses):
            logger.info(f"  Message {i+1}: {type(msg).__name__}")

    finally:
        # Cleanup
        logger.info("Cleaning up...")
        try:
            await client.disconnect()
        except:
            pass
        await sandbox.stop()
        logger.info("Test complete!")


if __name__ == "__main__":
    asyncio.run(test_bash_docker_tool())
