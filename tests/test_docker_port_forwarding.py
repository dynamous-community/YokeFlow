"""
Test Docker Port Forwarding
============================

Validates that Docker container port forwarding is configured correctly
and Playwright can access localhost ports from the host machine.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sandbox_manager import SandboxManager
from config import Config


async def test_port_forwarding():
    """Test that Docker container forwards ports correctly."""

    print("Testing Docker Port Forwarding\n" + "="*50)

    # Load config
    config_path = Path(__file__).parent.parent / ".autonomous-coding.yaml"
    if not config_path.exists():
        print("❌ Config file not found:", config_path)
        return False

    config = Config.load_from_file(config_path)

    # Verify ports are in config
    print(f"\n✅ Config loaded: {len(config.sandbox.docker_ports)} ports configured")
    print(f"   Ports: {', '.join(config.sandbox.docker_ports)}")

    # Create test project directory
    test_dir = Path(__file__).parent / "test_docker_project"
    test_dir.mkdir(exist_ok=True)

    # Create sandbox config
    sandbox_config = {
        "image": config.sandbox.docker_image,
        "network": config.sandbox.docker_network,
        "memory_limit": config.sandbox.docker_memory_limit,
        "cpu_limit": config.sandbox.docker_cpu_limit,
        "ports": config.sandbox.docker_ports,
    }

    print(f"\n✅ Creating Docker sandbox...")
    sandbox = SandboxManager.create_sandbox(
        sandbox_type="docker",
        project_dir=test_dir,
        config=sandbox_config
    )

    try:
        # Start container
        print("   Starting container...")
        await sandbox.start()
        print(f"✅ Container started: {sandbox.container_name}")

        # Start a simple HTTP server on port 3001
        print(f"\n✅ Starting test HTTP server on port 3001...")
        start_server_cmd = """
node -e "
const http = require('http');
const server = http.createServer((req, res) => {
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({status: 'ok', message: 'Port forwarding works!'}));
});
server.listen(3001, '0.0.0.0', () => {
  console.log('Server running on port 3001');
});
" > /tmp/server.log 2>&1 &
"""
        result = await sandbox.execute_command(start_server_cmd)
        await asyncio.sleep(3)  # Wait for server to start

        # Test from inside container (should work)
        print("\n✅ Testing from INSIDE container (curl localhost:3001)...")
        result = await sandbox.execute_command("curl -s http://localhost:3001")
        if result["returncode"] == 0:
            print(f"   ✅ Response: {result['stdout'][:100]}")
        else:
            print(f"   ❌ Failed: {result['stderr']}")
            return False

        # Test from host (this is what Playwright does)
        print("\n✅ Testing from HOST (curl localhost:3001)...")
        import subprocess
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:3001"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"   ✅ Port forwarding working! Response: {result.stdout[:100]}")
                print(f"\n{'='*50}")
                print("✅ SUCCESS: Playwright will be able to access container ports!")
                print("='*50")
                return True
            else:
                print(f"   ❌ curl from host failed: {result.stderr}")
                return False
        except Exception as e:
            print(f"   ❌ Error testing from host: {e}")
            return False

    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await sandbox.stop()

        # Remove test directory
        import shutil
        if test_dir.exists():
            shutil.rmtree(test_dir)
        print("   ✅ Cleanup complete")


if __name__ == "__main__":
    success = asyncio.run(test_port_forwarding())
    sys.exit(0 if success else 1)
