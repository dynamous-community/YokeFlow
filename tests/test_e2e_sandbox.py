#!/usr/bin/env python3
"""
End-to-end test for Docker sandbox integration.

Verifies that the agent automatically uses bash_docker when Docker is active.
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


async def test_sandbox_integration():
    """Test end-to-end Docker sandbox integration."""

    logger.info("=" * 80)
    logger.info("END-TO-END DOCKER SANDBOX TEST")
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
        # Create Claude SDK client with Docker configuration
        logger.info("Creating Claude SDK client with Docker sandbox...")
        client = create_client(
            project_dir=project_dir,
            model="claude-sonnet-4-5-20250929",
            project_id="test-e2e-sandbox",
            docker_container=sandbox.container_name
        )

        # Connect to SDK
        logger.info("Connecting to Claude SDK...")
        await client.connect()

        logger.info("=" * 80)
        logger.info("TESTING AUTOMATIC BASH_DOCKER USAGE")
        logger.info("=" * 80)

        # Simple prompt that requires a command - DON'T mention bash_docker
        # The agent should automatically use it based on system prompt
        prompt = """
        Please run 'pwd' to show me the current working directory.
        Then tell me what the output was.
        """

        # Send query
        await client.query(prompt)

        logger.info("Waiting for response...")

        # Collect response
        tool_used = None
        result = None

        async for msg in client.receive_response():
            if hasattr(msg, 'content') and isinstance(msg.content, list):
                for block in msg.content:
                    # Check which tool was used
                    if hasattr(block, 'name'):
                        tool_used = block.name
                        logger.info(f"Tool used: {tool_used}")

                    # Get result
                    elif hasattr(block, 'content') and isinstance(block.content, list):
                        for item in block.content:
                            if isinstance(item, dict) and 'text' in item:
                                result = item['text']
                                logger.info(f"Result: {result}")

                    # Get final text response
                    elif hasattr(block, 'text'):
                        logger.info(f"Agent response: {block.text[:300]}")

        logger.info("=" * 80)
        logger.info("TEST RESULTS")
        logger.info("=" * 80)

        # Verify correct tool was used
        if tool_used and 'bash_docker' in tool_used:
            logger.info("✅ SUCCESS: Agent used bash_docker automatically!")
        elif tool_used == "Bash":
            logger.error("❌ FAIL: Agent used regular Bash tool (should use bash_docker)")
        else:
            logger.warning(f"⚠️  UNKNOWN: Agent used tool: {tool_used}")

        # Verify correct result
        if result and '/workspace' in result:
            logger.info("✅ SUCCESS: Command executed in Docker (returned /workspace)")
        elif result and 'Ext_SSD' in result:
            logger.error("❌ FAIL: Command executed on host (returned host path)")
        else:
            logger.warning(f"⚠️  UNKNOWN: Result: {result}")

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
    asyncio.run(test_sandbox_integration())
