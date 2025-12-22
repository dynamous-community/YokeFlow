"""
Sandbox Manager
===============

Provides isolated execution environments for autonomous agent sessions.

Supports multiple sandbox backends:
- LocalSandbox: No isolation (current behavior, for testing)
- DockerSandbox: Docker container isolation (testing and development)
- E2BSandbox: E2B cloud sandbox (production deployment)

Architecture:
    AgentOrchestrator
      ↓
    SandboxManager.create()
      ↓
    Sandbox (base class)
      ├── LocalSandbox (no isolation)
      ├── DockerSandbox (Docker containers)
      └── E2BSandbox (E2B cloud - future)
"""

import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Sandbox(ABC):
    """
    Base class for sandbox implementations.

    Provides a consistent interface for running code in isolated environments.
    """

    def __init__(self, project_dir: Path, config: Dict[str, Any] = None):
        """
        Initialize sandbox.

        Args:
            project_dir: Path to the project directory
            config: Sandbox-specific configuration
        """
        self.project_dir = project_dir
        self.config = config or {}
        self.is_running = False

    @abstractmethod
    async def start(self) -> None:
        """Start the sandbox environment."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop and clean up the sandbox environment."""
        pass

    @abstractmethod
    async def execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a command in the sandbox.

        Args:
            command: The command to execute
            timeout: Optional timeout in seconds

        Returns:
            Dict with keys: stdout, stderr, returncode
        """
        pass

    @abstractmethod
    async def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload a file to the sandbox."""
        pass

    @abstractmethod
    async def download_file(self, remote_path: str, local_path: Path) -> None:
        """Download a file from the sandbox."""
        pass

    @abstractmethod
    async def sync_directory(self, direction: str = "to_sandbox") -> None:
        """
        Sync entire project directory.

        Args:
            direction: "to_sandbox" or "from_sandbox"
        """
        pass

    def get_working_directory(self) -> str:
        """Get the working directory path inside the sandbox."""
        return "/workspace"


class LocalSandbox(Sandbox):
    """
    No-isolation sandbox that runs commands directly on the host.

    This is the current behavior - useful for local development and testing
    where you want to inspect the generated code directly.

    WARNING: No environment isolation - API keys can leak!
    """

    async def start(self) -> None:
        """No-op for local sandbox."""
        self.is_running = True
        logger.info(f"LocalSandbox started (no isolation) for {self.project_dir}")

    async def stop(self) -> None:
        """No-op for local sandbox."""
        self.is_running = False
        logger.info(f"LocalSandbox stopped for {self.project_dir}")

    async def execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute command directly on host (no isolation).

        This preserves the current behavior where commands run in the project directory.
        """
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self.project_dir),
                capture_output=True,
                text=True,
                timeout=timeout
            )

            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "stdout": e.stdout.decode() if e.stdout else "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1,
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    async def upload_file(self, local_path: Path, remote_path: str) -> None:
        """No-op for local sandbox - files are already local."""
        pass

    async def download_file(self, remote_path: str, local_path: Path) -> None:
        """No-op for local sandbox - files are already local."""
        pass

    async def sync_directory(self, direction: str = "to_sandbox") -> None:
        """No-op for local sandbox - directory is already local."""
        pass

    def get_working_directory(self) -> str:
        """Return the actual project directory path."""
        return str(self.project_dir.resolve())


class DockerSandbox(Sandbox):
    """
    Docker container sandbox for isolated execution.

    Provides strong isolation including:
    - Separate filesystem
    - Separate environment variables
    - Network isolation (optional)
    - Resource limits (CPU, memory)

    Perfect for testing and single-user development.
    """

    def __init__(self, project_dir: Path, config: Dict[str, Any] = None):
        super().__init__(project_dir, config)
        self.container_id: Optional[str] = None
        self.container_name: Optional[str] = None
        self.client: Optional[Any] = None  # Docker client (reused across commands)

        # Docker configuration
        self.image = self.config.get("image", "node:20-slim")
        self.network = self.config.get("network", "bridge")
        self.memory_limit = self.config.get("memory_limit", "2g")
        self.cpu_limit = self.config.get("cpu_limit", "2.0")
        self.port_mappings = self.config.get("ports", [])
        self.session_type = self.config.get("session_type", "coding")  # "initializer" or "coding"

    async def start(self) -> None:
        """Create and start Docker container (with reuse for coding sessions)."""
        import docker
        import os
        import subprocess
        import json

        try:
            # Detect Docker socket path from docker context
            # This handles custom paths (e.g., home on external SSD)
            result = subprocess.run(['docker', 'context', 'inspect'],
                                  capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                context = json.loads(result.stdout)[0]
                socket_path = context['Endpoints']['docker']['Host']
                logger.info(f"Using Docker socket: {socket_path}")
                self.client = docker.DockerClient(base_url=socket_path)
            else:
                # Fallback to from_env()
                logger.info("Using docker.from_env() for client")
                self.client = docker.from_env()

            # Generate unique container name
            self.container_name = f"autonomous-agent-{self.project_dir.name}"

            # Container reuse strategy: Reuse for coding sessions, recreate for initializer
            existing_container = None
            try:
                existing_container = self.client.containers.get(self.container_name)
                logger.info(f"Found existing container: {self.container_name}")
            except docker.errors.NotFound:
                logger.info(f"No existing container found for: {self.container_name}")

            # Decide whether to reuse or recreate
            if self.session_type == "initializer" and existing_container:
                # Always recreate for initializer sessions (clean slate)
                logger.info("Initializer session: Removing existing container for clean slate")
                existing_container.remove(force=True)
                existing_container = None
            elif self.session_type == "coding" and existing_container:
                # Reuse for coding sessions if running, restart if stopped
                if existing_container.status == "running":
                    logger.info("Coding session: Reusing running container (cleaning up processes)")
                    self.container_id = existing_container.id
                    self.is_running = True

                    # Enhanced cleanup for coding sessions
                    await self._cleanup_container()
                    return  # Container ready, skip creation
                else:
                    logger.info("Coding session: Restarting stopped container")
                    existing_container.start()
                    self.container_id = existing_container.id
                    self.is_running = True

                    # Enhanced cleanup for coding sessions
                    await self._cleanup_container()
                    return  # Container ready, skip creation

            # Parse port mappings from config
            # Format: ["3001:3001", "5173:5173"] -> {'3001/tcp': 3001, '5173/tcp': 5173}
            # Kill orphaned processes from previous sessions, then bind ports
            port_bindings = {}
            if hasattr(self, 'port_mappings') and self.port_mappings:
                for port_mapping in self.port_mappings:
                    if ':' in port_mapping:
                        container_port, host_port = port_mapping.split(':')

                        # Check if port is available
                        import socket
                        try:
                            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                s.bind(('', int(host_port)))
                                # Port is available, add to bindings
                                port_bindings[f'{container_port}/tcp'] = int(host_port)
                        except OSError:
                            # Port in use - try to kill orphaned processes from this project
                            logger.warning(f"Port {host_port} already in use, attempting to free it...")
                            try:
                                import subprocess
                                # Find process using the port
                                result = subprocess.run(['lsof', '-ti', f':{host_port}'],
                                                      capture_output=True, text=True, timeout=5)
                                if result.returncode == 0 and result.stdout.strip():
                                    pids = result.stdout.strip().split('\n')
                                    for pid in pids:
                                        # Verify it's related to this project directory
                                        check_cwd = subprocess.run(['lsof', '-p', pid],
                                                                 capture_output=True, text=True, timeout=5)
                                        if str(self.project_dir) in check_cwd.stdout:
                                            # It's from this project, safe to kill
                                            subprocess.run(['kill', pid], timeout=5)
                                            logger.info(f"Killed orphaned process {pid} from previous session")
                                            # Try binding again
                                            try:
                                                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                                                    s.bind(('', int(host_port)))
                                                    port_bindings[f'{container_port}/tcp'] = int(host_port)
                                                    logger.info(f"Port {host_port} freed and bound successfully")
                                            except OSError:
                                                logger.warning(f"Port {host_port} still in use after cleanup, skipping")
                                        else:
                                            logger.warning(f"Port {host_port} in use by unrelated process, skipping")
                                else:
                                    logger.warning(f"Could not identify process using port {host_port}, skipping")
                            except Exception as e:
                                logger.warning(f"Failed to free port {host_port}: {e}")

                if port_bindings:
                    logger.info(f"Port forwarding enabled: {port_bindings}")
                else:
                    logger.warning("No ports available for forwarding - Playwright testing may be limited")

            # Create container with project directory mounted
            container = self.client.containers.run(
                self.image,
                command="sleep infinity",  # Keep container running
                name=self.container_name,
                detach=True,
                network=self.network,
                mem_limit=self.memory_limit,
                nano_cpus=int(float(self.cpu_limit) * 1e9),
                ports=port_bindings if port_bindings else None,
                volumes={
                    str(self.project_dir.resolve()): {
                        "bind": "/workspace",
                        "mode": "rw"
                    }
                },
                working_dir="/workspace",
                # Prevent environment leakage - start with minimal environment
                environment={
                    "HOME": "/root",
                    "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                }
            )

            self.container_id = container.id
            self.is_running = True

            logger.info(f"DockerSandbox started: {self.container_name} (ID: {self.container_id[:12]})")

            # Install basic dependencies in container
            await self._setup_container()

        except Exception as e:
            logger.error(f"Failed to start Docker sandbox: {e}")
            raise RuntimeError(f"Failed to start Docker sandbox: {e}")

    async def _setup_container(self) -> None:
        """Install basic dependencies in the container."""
        # Install common dependencies (git, curl, etc.)
        # Added procps for process management (ps, pkill, pgrep)
        # Added lsof for port management
        # Added jq for JSON processing
        setup_commands = [
            "apt-get update -qq",
            "apt-get install -y -qq git curl build-essential python3 python3-pip procps lsof jq sqlite3",
            "npm install -g pnpm npm",  # Ensure latest npm/pnpm
        ]

        for cmd in setup_commands:
            result = await self.execute_command(cmd, timeout=120)
            if result["returncode"] != 0:
                logger.warning(f"Setup command failed: {cmd}\n{result['stderr']}")

    async def _cleanup_container(self) -> None:
        """
        Enhanced cleanup for reused containers (coding sessions only).

        Kills stray processes that might interfere with the new session:
        - Node/npm processes (dev servers, build processes)
        - Python processes (API servers, background tasks)
        - Clears temp files

        This prevents port conflicts and resource leaks across sessions.
        """
        if not self.container_id or not self.client:
            return

        logger.info("Performing enhanced cleanup for reused container...")

        cleanup_commands = [
            # Kill all node processes (dev servers, etc.)
            "pkill -9 node 2>/dev/null || true",
            # Kill all npm processes
            "pkill -9 npm 2>/dev/null || true",
            # Kill all python processes
            "pkill -9 python 2>/dev/null || true",
            # Kill all pnpm processes
            "pkill -9 pnpm 2>/dev/null || true",
            # Clear temp files
            "rm -rf /tmp/* 2>/dev/null || true",
            # Clear node_modules/.cache directories if they exist
            "find /workspace -type d -name '.cache' -exec rm -rf {} + 2>/dev/null || true",
        ]

        for cmd in cleanup_commands:
            result = await self.execute_command(cmd, timeout=30)
            if result["returncode"] != 0 and result["stderr"]:
                # Only log if there's actual stderr (ignore pkill "no process found")
                if "no process found" not in result["stderr"].lower():
                    logger.debug(f"Cleanup command: {cmd}\n{result['stderr']}")

        logger.info("Container cleanup complete")

    async def stop(self) -> None:
        """
        Stop Docker container (but keep it for reuse).

        For container reuse strategy:
        - Keep container running for coding sessions (reused next session)
        - Only remove if explicitly requested (force_remove=True)

        The container will be automatically cleaned up:
        - On next initializer session (recreated for clean slate)
        - On manual cleanup (docker rm)
        """
        if not self.container_id or not self.client:
            return

        try:
            # Keep container running for reuse
            # It will be cleaned up on next initializer session or manual cleanup
            logger.info(f"DockerSandbox keeping container for reuse: {self.container_name}")

        except Exception as e:
            logger.error(f"Failed to manage Docker sandbox: {e}")

        finally:
            self.is_running = False
            self.container_id = None
            self.client = None

    async def execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        """Execute command in Docker container."""
        if not self.container_id or not self.client:
            raise RuntimeError("Docker sandbox not started")

        try:
            container = self.client.containers.get(self.container_id)

            # Execute command in container
            exit_code, output = container.exec_run(
                f"sh -c '{command}'",
                workdir="/workspace",
                demux=True,  # Separate stdout/stderr
            )

            stdout = output[0].decode() if output[0] else ""
            stderr = output[1].decode() if output[1] else ""

            return {
                "stdout": stdout,
                "stderr": stderr,
                "returncode": exit_code,
            }

        except Exception as e:
            logger.error(f"Failed to execute command in Docker: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    async def upload_file(self, local_path: Path, remote_path: str) -> None:
        """Upload file to container (not needed with volume mount)."""
        # With volume mounting, files are automatically synced
        pass

    async def download_file(self, remote_path: str, local_path: Path) -> None:
        """Download file from container (not needed with volume mount)."""
        # With volume mounting, files are automatically synced
        pass

    async def sync_directory(self, direction: str = "to_sandbox") -> None:
        """Sync directory (not needed with volume mount)."""
        # With volume mounting, directory is automatically synced
        pass


class E2BSandbox(Sandbox):
    """
    E2B cloud sandbox for production deployment.

    TODO: Implement E2B integration
    - Use E2B Python SDK
    - Handle pause/resume for long sessions
    - Manage file upload/download
    - Handle session limits (1 hour free, 24 hour pro)
    """

    async def start(self) -> None:
        raise NotImplementedError("E2B sandbox not yet implemented")

    async def stop(self) -> None:
        raise NotImplementedError("E2B sandbox not yet implemented")

    async def execute_command(self, command: str, timeout: Optional[int] = None) -> Dict[str, Any]:
        raise NotImplementedError("E2B sandbox not yet implemented")

    async def upload_file(self, local_path: Path, remote_path: str) -> None:
        raise NotImplementedError("E2B sandbox not yet implemented")

    async def download_file(self, remote_path: str, local_path: Path) -> None:
        raise NotImplementedError("E2B sandbox not yet implemented")

    async def sync_directory(self, direction: str = "to_sandbox") -> None:
        raise NotImplementedError("E2B sandbox not yet implemented")


class SandboxManager:
    """
    Factory for creating sandbox instances.

    Usage:
        sandbox = SandboxManager.create_sandbox(
            sandbox_type="docker",
            project_dir=Path("generations/my-project"),
            config={"image": "node:20-slim"}
        )

        await sandbox.start()
        result = await sandbox.execute_command("npm install")
        await sandbox.stop()
    """

    @staticmethod
    def create_sandbox(
        sandbox_type: str,
        project_dir: Path,
        config: Dict[str, Any] = None
    ) -> Sandbox:
        """
        Create a sandbox instance.

        Args:
            sandbox_type: "none", "docker", or "e2b"
            project_dir: Path to project directory
            config: Sandbox-specific configuration

        Returns:
            Sandbox instance
        """
        if sandbox_type == "none" or sandbox_type == "local":
            return LocalSandbox(project_dir, config)
        elif sandbox_type == "docker":
            return DockerSandbox(project_dir, config)
        elif sandbox_type == "e2b":
            return E2BSandbox(project_dir, config)
        else:
            raise ValueError(
                f"Unknown sandbox type: {sandbox_type}. "
                f"Valid options: 'none', 'docker', 'e2b'"
            )
