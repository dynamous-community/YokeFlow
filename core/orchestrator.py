"""
Agent Orchestrator
========================================

Centralized orchestration layer for managing autonomous agent sessions.

This module provides a clean interface for:
- Creating projects
- Starting/stopping agent sessions
- Querying session status
- Managing the agent lifecycle

Design Philosophy:
- Independent (can be called from API or tests)
- Uses PostgreSQL database for all data access
- Async-first for scalability
- Foundation for future job queue integration (Celery/Redis)
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Awaitable, TYPE_CHECKING
from datetime import datetime
from uuid import UUID
import os

import asyncpg

from core.client import create_client
from core.database_connection import get_db, DatabaseManager, is_postgresql_configured
from core.orchestrator_models import SessionStatus, SessionType, SessionInfo
from core.quality_integration import QualityIntegration
from core.structured_logging import get_logger, setup_structured_logging

if TYPE_CHECKING:
    from core.database import TaskDatabase
from core.prompts import (
    get_initializer_prompt,
    get_coding_prompt,
    copy_spec_to_project,
)
from core.observability import SessionLogger, QuietOutputFilter, create_session_logger
from core.agent import run_agent_session, SessionManager
from core.config import Config
from core.sandbox_manager import SandboxManager
from core.sandbox_hooks import set_active_sandbox, clear_active_sandbox

# Initialize structured logging if not already done (for CLI usage)
if not any(isinstance(h.formatter, type(None)) for h in get_logger(__name__).handlers):
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    log_format = os.getenv('LOG_FORMAT', 'dev')
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    setup_structured_logging(
        level=log_level,
        format_type=log_format,
        log_file=logs_dir / "yokeflow.log"
    )

logger = get_logger(__name__)

# Re-export models for backward compatibility
__all__ = ['AgentOrchestrator', 'SessionInfo', 'SessionStatus', 'SessionType']


class AgentOrchestrator:
    """
    Orchestrates autonomous agent sessions using PostgreSQL.

    Provides a high-level interface for managing agent lifecycle via the API.
    All sessions raise exceptions on interrupt rather than calling sys.exit().
    """

    def __init__(self, verbose: bool = False, event_callback=None):
        """
        Initialize the orchestrator.

        Args:
            verbose: If True, show detailed output during sessions
            event_callback: Optional async callback function for session events.
                          Called with (project_id, event_type, data) parameters.
        """
        self.verbose = verbose
        self.event_callback = event_callback
        self.config = Config.load_default()

        # Quality system integration
        self.quality = QualityIntegration(self.config, event_callback)

        # Session managers for graceful shutdown
        self.session_managers: Dict[str, SessionManager] = {}

        # Session control flags (per-project)
        self.stop_after_current: Dict[str, bool] = {}  # project_id -> flag

    # =========================================================================
    # Project Operations
    # =========================================================================

    async def create_project(
        self,
        project_name: str,
        spec_source: Optional[Path] = None,
        spec_content: Optional[str] = None,
        user_id: Optional[UUID] = None,
        force: bool = False,
        sandbox_type: str = "docker",
        initializer_model: Optional[str] = None,
        coding_model: Optional[str] = None,
        context_files: Optional[List[Dict[str, str]]] = None,  # List of {"filename": str, "content": str}
        context_strategy: Optional[Dict[str, Any]] = None,  # Strategy from spec generation analysis
    ) -> Dict[str, Any]:
        """
        Create a new project from a specification.

        Args:
            project_name: Name for the project (must be unique)
            spec_source: Path to spec file or folder (optional)
            spec_content: Spec content as string (optional)
            user_id: User ID (optional, for future multi-user support)
            force: If True, overwrite existing project
            sandbox_type: Sandbox type (docker or local), default: docker
            initializer_model: Model for initialization session (optional)
            coding_model: Model for coding sessions (optional)
            context_files: Optional list of dicts with {"filename", "content"} for project context
            context_strategy: Optional dict with context injection strategy ("load_all" or "task_specific")

        Returns:
            Dict with project info: {"project_id": UUID, "name": str, ...}

        Raises:
            ValueError: If project already exists and force=False
        """
        async with DatabaseManager() as db:
            # Check if project exists
            existing = await db.get_project_by_name(project_name)
            if existing and not force:
                raise ValueError(
                    f"A project named '{project_name}' already exists. Please choose a different name or delete the existing project first."
                )

            if existing and force:
                # Delete existing project before creating new one
                await db.delete_project(existing['id'])

            # Determine spec path/content
            spec_path = str(spec_source) if spec_source else None

            # If spec_source is provided, read its content if not already provided
            if spec_source and not spec_content:
                spec_source = Path(spec_source)
                if spec_source.is_file():
                    spec_content = spec_source.read_text()
                elif spec_source.is_dir():
                    # For directories, concatenate all relevant files
                    spec_files = []
                    for pattern in ["*.md", "*.txt", "README*"]:
                        spec_files.extend(spec_source.glob(pattern))
                    spec_content = "\n\n".join(
                        f"# {f.name}\n\n{f.read_text()}"
                        for f in sorted(spec_files)
                    )

            # Create project directory in generations
            generations_dir = Path(self.config.project.default_generations_dir)
            project_path = generations_dir / project_name
            project_path.mkdir(parents=True, exist_ok=True)

            # Copy spec files to project directory if source provided
            if spec_source:
                copy_spec_to_project(project_path, spec_source)
            elif spec_content:
                # Write spec_content to app_spec.md (using new markdown format)
                (project_path / "app_spec.md").write_text(spec_content)

            # Persist context files if provided
            if context_files:
                context_dir = project_path / ".yokeflow" / "context"
                context_dir.mkdir(parents=True, exist_ok=True)
                
                for ctx_file in context_files:
                    try:
                        file_path = context_dir / ctx_file["filename"]
                        file_path.write_text(ctx_file["content"])
                    except Exception as e:
                        logger.warning(f"Failed to save context file {ctx_file.get('filename')}: {e}")
                
                logger.info(f"Saved {len(context_files)} context files to {context_dir}")
                
                # Create manifest with summaries
                try:
                    from core.context_manifest import create_context_manifest, save_manifest
                    manifest = await create_context_manifest(context_files)
                    save_manifest(manifest, context_dir)
                    logger.info(f"Created context manifest for {len(context_files)} files")
                except Exception as e:
                    logger.warning(f"Failed to create context manifest: {e}")

            # Create project in database
            project = await db.create_project(
                name=project_name,
                spec_file_path=spec_path or "",
                spec_content=spec_content,
                user_id=user_id,
            )

            # Update project with local_path and initial settings
            await db.update_project(project['id'], local_path=str(project_path))
            project['local_path'] = str(project_path)

            # Set initial project settings
            settings = {
                'sandbox_type': sandbox_type,
                'max_iterations': None,  # None = unlimited (auto-continue)
            }
            if initializer_model:
                settings['initializer_model'] = initializer_model
            if coding_model:
                settings['coding_model'] = coding_model
            if context_strategy:
                settings['context_strategy'] = context_strategy.get('strategy', 'load_all')
                settings['context_strategy_reason'] = context_strategy.get('reason', '')
                settings['context_strategy_metrics'] = context_strategy.get('metrics', {})
                logger.info(f"Stored context strategy: {settings['context_strategy']}")

            await db.update_project_settings(project['id'], settings)

            return project

    async def get_project_info(self, project_id: UUID) -> Dict[str, Any]:
        """
        Get information about a project.

        Args:
            project_id: UUID of the project

        Returns:
            Dict with project info and progress statistics

        Raises:
            ValueError: If project doesn't exist
        """
        async with DatabaseManager() as db:
            project = await db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Compute local_path from project name
            generations_dir = Path(self.config.project.default_generations_dir)
            project_path = generations_dir / project['name']
            project['local_path'] = str(project_path)

            # Get progress statistics
            progress = await db.get_progress(project_id)
            next_task = await db.get_next_task(project_id)

            # Check for active sessions
            active_session = await db.get_active_session(project_id)
            active_sessions = [active_session] if active_session else []

            # Check environment configuration
            env_file = project_path / ".env" if project_path else None
            env_example = project_path / ".env.example" if project_path else None
            has_env_file = env_file and env_file.exists()
            has_env_example = env_example and env_example.exists()

            # Check if .env.example actually has variables (not just empty file)
            has_env_variables = False
            if has_env_example and env_example:
                try:
                    content = env_example.read_text()
                    # Count non-empty, non-comment lines
                    lines = [line.strip() for line in content.splitlines()]
                    var_lines = [line for line in lines if line and not line.startswith('#')]
                    has_env_variables = len(var_lines) > 0
                except Exception:
                    # If we can't read the file, assume it has variables
                    has_env_variables = True

            # Determine if initialization is complete (Session 1 has created epics/tasks)
            is_initialized = progress.get("total_epics", 0) > 0

            # Determine if env configuration is needed
            # Only flag if .env.example exists AND has actual variables
            needs_env_config = (
                is_initialized and
                has_env_variables and
                not project.get('env_configured', False)
            )

            return {
                **project,
                "is_initialized": is_initialized,
                "progress": progress,
                "next_task": next_task,
                "active_sessions": active_sessions,
                "has_env_file": has_env_file,
                "has_env_example": has_env_example,
                "needs_env_config": needs_env_config,
            }

    async def get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """
        Get project by name.

        Args:
            project_name: Name of the project

        Returns:
            Project dict if found, None otherwise
        """
        async with DatabaseManager() as db:
            project = await db.get_project_by_name(project_name)
            if project:
                return await self.get_project_info(project['id'])
            return None

    async def list_projects(self, user_id: Optional[UUID] = None) -> List[Dict[str, Any]]:
        """
        List all projects.

        Args:
            user_id: Optional user ID to filter projects

        Returns:
            List of project info dicts
        """
        async with DatabaseManager() as db:
            projects = await db.list_projects(user_id=user_id)

            # Enrich with progress info
            enriched = []
            for project in projects:
                try:
                    info = await self.get_project_info(project['id'])
                    enriched.append(info)
                except Exception as e:
                    logger.warning(f"Could not get info for project {project['name']}: {e}")
                    enriched.append(project)

            return enriched

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def start_initialization(
        self,
        project_id: UUID,
        initializer_model: Optional[str] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> SessionInfo:
        """
        Run initialization session (Session 1) for a project.

        This method:
        - Creates the project structure (epics, tasks, tests)
        - Runs init.sh to setup the environment
        - ALWAYS stops after Session 1 completes
        - Does NOT auto-continue to coding sessions

        Args:
            project_id: UUID of the project
            initializer_model: Model to use (defaults to config.models.initializer)
            progress_callback: Optional async callback for real-time progress updates

        Returns:
            SessionInfo for the completed initialization session

        Raises:
            ValueError: If project doesn't exist or already initialized
        """
        async with DatabaseManager() as db:
            # Verify project exists
            project = await db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Check if already initialized
            epics = await db.list_epics(project_id)
            if len(epics) > 0:
                raise ValueError(
                    f"Project already initialized with {len(epics)} epics. "
                    f"Use start_coding_sessions() instead."
                )

        # Use default model if not provided
        if not initializer_model:
            initializer_model = self.config.models.initializer

        # Run Session 1 (initialization only, no looping)
        return await self.start_session(
            project_id=project_id,
            initializer_model=initializer_model,
            coding_model=None,  # Not needed for initialization
            max_iterations=None,  # Not applicable
            progress_callback=progress_callback
        )

    async def start_coding_sessions(
        self,
        project_id: UUID,
        coding_model: Optional[str] = None,
        max_iterations: Optional[int] = 0,  # 0 = unlimited by default
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> SessionInfo:
        """
        Run coding sessions (Session 2+) for a project.

        This method:
        - Verifies initialization is complete
        - Runs multiple sessions with auto-continue
        - Respects max_iterations setting (0/None = unlimited)
        - Respects stop_after_current flag

        Args:
            project_id: UUID of the project
            coding_model: Model to use (defaults to config.models.coding)
            max_iterations: Maximum sessions to run (0 or None = unlimited)
            progress_callback: Optional async callback for real-time progress updates

        Returns:
            SessionInfo for the LAST completed session

        Raises:
            ValueError: If project doesn't exist or not initialized
        """
        async with DatabaseManager() as db:
            # Verify project exists
            project = await db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Check if initialization is complete
            epics = await db.list_epics(project_id)
            if len(epics) == 0:
                raise ValueError(
                    "Project not initialized. Run start_initialization() first."
                )

        # Use default model if not provided
        if not coding_model:
            coding_model = self.config.models.coding

        # Normalize max_iterations (0 and None both mean unlimited)
        if max_iterations is None or max_iterations == 0:
            max_iterations = None  # Unlimited

        # Auto-continue loop for coding sessions
        iteration = 0
        last_session = None

        while True:
            # Check max_iterations
            if max_iterations is not None and iteration >= max_iterations:
                logger.info(f"Reached max_iterations ({max_iterations}). Stopping.")
                break

            # Check stop_after_current flag
            project_id_str = str(project_id)
            if self.stop_after_current.get(project_id_str, False):
                logger.info(f"Stop after current requested. Stopping.")
                # Clear flag
                self.stop_after_current[project_id_str] = False
                break

            # Check if all epics are complete (more reliable than checking tasks)
            async with DatabaseManager() as db:
                progress = await db.get_progress(project_id)
                if progress:
                    completed_epics = progress.get('completed_epics', 0)
                    total_epics = progress.get('total_epics', 0)
                    logger.info(f"Auto-continue check: {completed_epics}/{total_epics} epics complete")
                    if completed_epics == total_epics and total_epics > 0:
                        logger.info(f"✅ All epics complete ({completed_epics}/{total_epics}). Stopping auto-continue.")
                        # Notify via callback
                        if self.event_callback:
                            await self.event_callback(project_id, "all_epics_complete", {
                                "completed_epics": completed_epics,
                                "total_epics": total_epics,
                                "completed_tasks": progress.get('completed_tasks', 0),
                                "total_tasks": progress.get('total_tasks', 0)
                            })
                        break

            iteration += 1

            # Delay between sessions (except first)
            if iteration > 1:
                delay = self.config.timing.auto_continue_delay
                logger.info(f"Auto-continue delay: {delay}s before session {iteration}")

                # Notify via callback about delay
                if self.event_callback:
                    await self.event_callback(project_id, "auto_continue_delay", {
                        "delay": delay,
                        "next_iteration": iteration
                    })

                await asyncio.sleep(delay)

            # Run single coding session
            last_session = await self.start_session(
                project_id=project_id,
                initializer_model=None,  # Not needed
                coding_model=coding_model,
                max_iterations=None,  # Don't pass to individual session
                progress_callback=progress_callback
            )

            # Check if session failed
            if last_session.status in [SessionStatus.ERROR, SessionStatus.INTERRUPTED]:
                logger.info(f"Session ended with status {last_session.status}. Stopping auto-continue.")
                break

            # Check if project is complete (all tasks done)
            async with DatabaseManager() as db:
                progress = await db.get_progress(project_id)
                total_tasks = progress.get('total_tasks', 0)
                completed_tasks = progress.get('completed_tasks', 0)

                if total_tasks > 0 and completed_tasks >= total_tasks:
                    logger.info(f"Project complete! All {total_tasks} tasks done.")

                    # Mark project as complete in database
                    await db.mark_project_complete(project_id)
                    logger.info("✅ Project marked as complete in database")

                    # Stop Docker container to free up ports
                    # This is best-effort - don't fail if container doesn't exist or can't be stopped
                    try:
                        from core.sandbox_manager import SandboxManager
                        project = await db.get_project(project_id)
                        if project and project.get('sandbox_type') == 'docker':
                            project_name = project.get('name')
                            logger.info(f"Stopping Docker container for completed project: {project_name}")
                            stopped = SandboxManager.stop_docker_container(project_name)
                            if stopped:
                                logger.info(f"✅ Docker container stopped successfully")
                            else:
                                logger.info(f"Docker container was not running or doesn't exist")
                    except Exception as e:
                        logger.warning(f"Failed to stop Docker container (non-fatal): {e}")

                    # Trigger final deep review on last session (if not already done recently)
                    # This ensures we get a review even if project completes between 5-session intervals
                    if last_session:
                        # Get project path from database
                        project = await db.get_project(project_id)
                        if project and project.get('local_path'):
                            project_path = Path(project['local_path'])
                            logger.info("🔍 Triggering final deep review for completed project")
                            await self.quality.maybe_trigger_deep_review(
                                session_id=last_session.session_id,
                                project_path=project_path,
                                session_quality=None,  # Will check if needed based on interval
                                force_final_review=True  # Override interval check for project completion
                            )

                    # Notify via callback
                    if self.event_callback:
                        await self.event_callback(project_id, "project_complete", {
                            "total_tasks": total_tasks,
                            "completed_tasks": completed_tasks
                        })
                    break

        return last_session

    async def start_session(
        self,
        project_id: UUID,
        initializer_model: Optional[str] = None,
        coding_model: Optional[str] = None,
        max_iterations: Optional[int] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
        resume_context: Optional[Dict[str, Any]] = None,
    ) -> SessionInfo:
        """
        Start an agent session for a project.

        This is the main entry point for running the agent. It handles:
        - Determining session type (initializer vs coding)
        - Creating appropriate client and logger
        - Running the session
        - Updating session status

        Args:
            project_id: UUID of the project
            initializer_model: Model to use for initialization (if first session)
            coding_model: Model to use for coding sessions
            max_iterations: Maximum iterations for this invocation (None = unlimited)
            progress_callback: Optional async callback for real-time progress updates.
                             Called with event dict on each tool use/result.

        Returns:
            SessionInfo object with session details

        Raises:
            ValueError: If project doesn't exist or model not provided
        """
        # Cleanup any stale sessions before starting (handles ungraceful shutdowns)
        # This is especially important for CLI usage where the API's periodic cleanup isn't running
        await self.cleanup_stale_sessions()

        async with DatabaseManager() as db:
            # Get project info
            project = await db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # CONCURRENCY CHECK: Prevent creating a new session while another is running
            # This prevents phantom sessions from double-clicks or rapid API calls
            active_session = await db.get_active_session(project_id)
            if active_session:
                raise ValueError(
                    f"Cannot start new session: Session {active_session['session_number']} "
                    f"is already running (started {active_session['started_at']}). "
                    f"Wait for it to complete or stop it first."
                )

            project_name = project['name']
            local_path = project.get('local_path', '')

            # Get sandbox type from project metadata (not global config)
            project_metadata = project.get('metadata', {})
            if isinstance(project_metadata, str):
                import json
                project_metadata = json.loads(project_metadata)

            # Extract sandbox_type from metadata, default to config if not found
            project_sandbox_type = project_metadata.get('settings', {}).get('sandbox_type')
            if not project_sandbox_type:
                project_sandbox_type = self.config.sandbox.type
                logger.warning(f"No sandbox_type in project metadata, using config default: {project_sandbox_type}")

            # Ensure project path is valid and exists
            if not local_path or local_path == '':
                # Create project directory
                generations_dir = Path(self.config.project.default_generations_dir)
                project_path = generations_dir / project_name
                project_path.mkdir(parents=True, exist_ok=True)

                # Update project with local path
                await db.update_project(project_id, local_path=str(project_path))
            else:
                project_path = Path(local_path)
                if not project_path.exists():
                    project_path.mkdir(parents=True, exist_ok=True)

            # Determine session type
            epics = await db.list_epics(project_id)
            is_initializer = len(epics) == 0

            if is_initializer and not initializer_model:
                raise ValueError("initializer_model required for first session")
            if not is_initializer and not coding_model:
                raise ValueError("coding_model required for coding sessions")

            session_type = SessionType.INITIALIZER if is_initializer else SessionType.CODING
            current_model = initializer_model if is_initializer else coding_model

            # Get next session number
            session_number = await db.get_next_session_number(project_id)

            # Create session in database with unique constraint protection
            try:
                session = await db.create_session(
                    project_id=project_id,
                    session_number=session_number,
                    session_type=session_type.value,
                    model=current_model,
                    max_iterations=max_iterations,
                )
            except asyncpg.UniqueViolationError as e:
                # Race condition: another session with same number was created concurrently
                # This can happen with rapid double-clicks or simultaneous API calls
                raise ValueError(
                    f"Session {session_number} already exists for this project. "
                    f"Another session may have started concurrently. Please try again."
                ) from e

            session_id = session['id']
            session_number = session['session_number']

            # Create session info
            # Note: PostgreSQL returns datetime objects, not strings
            created_at = session['created_at']
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            session_info = SessionInfo(
                session_id=str(session_id),
                project_id=str(project_id),
                session_number=session_number,
                session_type=session_type,
                model=current_model,
                status=SessionStatus.PENDING,
                created_at=created_at,
            )

            # Setup signal handlers for graceful shutdown
            session_manager = SessionManager()
            session_manager.setup_handlers()
            self.session_managers[str(session_id)] = session_manager

            # Create sandbox using project-specific sandbox type
            sandbox_config = {
                "image": self.config.sandbox.docker_image,
                "network": self.config.sandbox.docker_network,
                "memory_limit": self.config.sandbox.docker_memory_limit,
                "cpu_limit": self.config.sandbox.docker_cpu_limit,
                "ports": self.config.sandbox.docker_ports,
                "session_type": session_type.value,  # "initializer" or "coding"
            }
            logger.info(f"Creating {project_sandbox_type} sandbox for project {project_name}")
            sandbox = SandboxManager.create_sandbox(
                sandbox_type=project_sandbox_type,  # Use project-specific, not global config
                project_dir=project_path,
                config=sandbox_config
            )

            try:
                # Start sandbox
                logger.info(f"Starting {project_sandbox_type} sandbox for session {session_number}")
                await sandbox.start()
                set_active_sandbox(sandbox)

                # Get Docker container name if sandbox is Docker
                docker_container = None
                from core.sandbox_manager import DockerSandbox
                if isinstance(sandbox, DockerSandbox):
                    docker_container = sandbox.container_name
                    logger.info(f"Docker sandbox active: {docker_container}")

                # Determine sandbox type for prompt selection and logging
                sandbox_type = "docker" if docker_container else "local"

                # Create event callback for logger (sync wrapper for async callback)
                def logger_event_callback(event_type: str, data: dict):
                    """Sync wrapper for async event callback."""
                    if self.event_callback:
                        # Add project_id and session_id to event data
                        data['project_id'] = str(project_id)
                        data['session_id'] = str(session_id)
                        # Schedule async callback
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.create_task(self.event_callback(project_id, event_type, data))
                        except RuntimeError:
                            # No event loop running, skip
                            pass

                # Create logger with event callback and sandbox type
                session_logger = create_session_logger(
                    project_path, session_number, session_type.value, current_model,
                    sandbox_type=sandbox_type,
                    event_callback=logger_event_callback
                )
                # Add session and project IDs for intervention system
                session_logger.session_id = str(session_id)
                session_logger.project_id = str(project_id)

                # Register logger with session manager
                session_manager.set_current_logger(session_logger)

                # Update session status
                await db.start_session(session_id)
                session_info.status = SessionStatus.RUNNING
                session_info.started_at = datetime.now()

                # Notify via callback that session has started
                if self.event_callback:
                    await self.event_callback(project_id, "session_started", {
                        "session": session_info.to_dict()
                    })

                # Create client (pass project_id and docker_container for MCP task-manager)
                client = create_client(
                    project_path,
                    current_model,
                    project_id=str(project_id),
                    docker_container=docker_container
                )

                # Get prompt based on session type and sandbox
                if is_initializer:
                    prompt = get_initializer_prompt(sandbox_type=sandbox_type)
                elif resume_context:
                    # Include resume context in the prompt
                    base_prompt = get_coding_prompt(sandbox_type=sandbox_type)
                    resume_prompt = resume_context.get("resume_prompt", "")
                    prompt = f"{base_prompt}\n\n{resume_prompt}"
                else:
                    prompt = get_coding_prompt(sandbox_type=sandbox_type)

                # Inject project context files (for both initializer and coding sessions)
                # Use manifest-based approach to avoid memory issues with large files
                context_dir = project_path / ".yokeflow" / "context"
                if context_dir.exists():
                    # Get context strategy from project metadata
                    context_strategy = project_metadata.get('settings', {}).get('context_strategy', 'load_all')
                    logger.info(f"Using context strategy: {context_strategy}")
                    
                    # Try to load manifest
                    from core.context_manifest import load_manifest, manifest_to_prompt
                    manifest = load_manifest(context_dir)
                    
                    if manifest:
                        # Inject manifest (summaries only, ~3KB instead of 130KB+)
                        manifest_prompt = manifest_to_prompt(manifest)
                        prompt += "\n\n# Project Context Files\n"
                        prompt += "The following context files are available. Use `cat .yokeflow/context/<filename>` to read when needed.\n\n"
                        prompt += manifest_prompt
                        logger.info(f"Injected manifest with {manifest['total_files']} files ({manifest['total_size_kb']}KB total) into system prompt")
                    else:
                        # Fallback: no manifest, load small files only
                        small_file_parts = []
                        for ctx_file in sorted(context_dir.glob("*")):
                            if ctx_file.is_file() and ctx_file.name != "manifest.json":
                                try:
                                    content = ctx_file.read_text(encoding='utf-8')
                                    # Only include small files (<5KB) directly
                                    if len(content) <= 5000:
                                        small_file_parts.append(f"## {ctx_file.name}\n```\n{content}\n```")
                                    else:
                                        # Just note that large files exist
                                        small_file_parts.append(f"## {ctx_file.name}\n(Large file, {len(content)//1024}KB - use get_context_file tool to read)")
                                except Exception as e:
                                    logger.warning(f"Failed to read context file {ctx_file}: {e}")
                        
                        if small_file_parts:
                            prompt += "\n\n# Project Context Files\n"
                            prompt += "\n\n".join(small_file_parts)
                            logger.info(f"Injected {len(small_file_parts)} context file references (no manifest)")

                # Start heartbeat task to prevent false-positive stale detection
                heartbeat_task = None
                async def send_heartbeats():
                    """Send periodic heartbeats to indicate session is still active."""
                    try:
                        while True:
                            await asyncio.sleep(60)  # Send heartbeat every 60 seconds
                            await db.update_session_heartbeat(session_id)
                            logger.debug(f"Sent heartbeat for session {session_id}")
                    except asyncio.CancelledError:
                        logger.debug("Heartbeat task cancelled")
                        raise

                heartbeat_task = asyncio.create_task(send_heartbeats())

                # Run session
                try:
                    async with client:
                        # Prepare intervention config
                        intervention_config = {
                            "enabled": self.config.intervention.enabled,
                            "max_retries": self.config.intervention.max_retries,
                            "notifications": {
                                "enabled": bool(self.config.intervention.webhook_url),
                                "webhook_url": self.config.intervention.webhook_url
                            }
                        }

                        status, response, session_summary = await run_agent_session(
                            client, prompt, project_path, logger=session_logger, verbose=self.verbose,
                            session_manager=session_manager, progress_callback=progress_callback,
                            intervention_config=intervention_config
                        )
                finally:
                    # Stop heartbeat task
                    if heartbeat_task:
                        heartbeat_task.cancel()
                        try:
                            await heartbeat_task
                        except asyncio.CancelledError:
                            pass

                # Build comprehensive metrics from session summary
                metrics = {
                    "duration_seconds": session_summary.get("duration_seconds", 0),
                    "status": status,
                    "message_count": session_summary.get("message_count", 0),
                    "tool_calls_count": session_summary.get("tool_use_count", 0),
                    "errors_count": session_summary.get("tool_errors", 0),
                    "tasks_completed": session_summary.get("tasks_completed", 0),
                    "tests_passed": session_summary.get("tests_passed", 0),
                    "browser_verifications": session_summary.get("browser_verifications", 0),
                    "response_length": session_summary.get("response_length", 0),
                    # Token usage and cost from ResultMessage
                    "tokens_input": session_summary.get("tokens_input", 0),
                    "tokens_output": session_summary.get("tokens_output", 0),
                    "tokens_cache_creation": session_summary.get("tokens_cache_creation", 0),
                    "tokens_cache_read": session_summary.get("tokens_cache_read", 0),
                }

                # Add cost if available
                if "cost_usd" in session_summary:
                    metrics["cost_usd"] = session_summary["cost_usd"]

                # Update session info based on result
                if status == "error":
                    session_info.status = SessionStatus.ERROR
                    session_info.error_message = response
                    await db.end_session(session_id, SessionStatus.ERROR.value, error_message=response, metrics=metrics)
                else:
                    session_info.status = SessionStatus.COMPLETED
                    await db.end_session(session_id, SessionStatus.COMPLETED.value, metrics=metrics)

                session_info.ended_at = datetime.now()
                session_info.metrics = metrics

                # Phase 1 Review System: Quick quality check (only for coding sessions)
                if not is_initializer:
                    await self.quality.run_quality_check(session_id, project_path, session_logger, status, session_type)

                # Test Coverage Analysis: Run after initialization session
                if is_initializer and status != "error":
                    await self.quality.run_test_coverage_analysis(project_id, db)

                # Clear logger from session manager
                session_manager.set_current_logger(None)

            except KeyboardInterrupt:
                # Graceful shutdown was triggered
                session_info.status = SessionStatus.INTERRUPTED
                session_info.ended_at = datetime.now()

                duration = (session_info.ended_at - session_info.started_at).total_seconds() if session_info.started_at else 0
                metrics = {"duration_seconds": duration, "status": "interrupted"}

                await db.end_session(
                    session_id,
                    SessionStatus.INTERRUPTED.value,
                    interruption_reason="User interrupted",
                    metrics=metrics
                )

                # Finalize the logger
                if session_manager.current_logger:
                    try:
                        session_manager.current_logger.finalize("interrupted", "Session interrupted by user")
                    except Exception as e:
                        print(f"Warning: Could not finalize session logs: {e}")

                # Clear logger from session manager
                session_manager.set_current_logger(None)

            except Exception as e:
                # Unexpected error
                session_info.status = SessionStatus.ERROR
                session_info.error_message = str(e)
                session_info.ended_at = datetime.now()

                duration = (session_info.ended_at - session_info.started_at).total_seconds() if session_info.started_at else 0
                metrics = {"duration_seconds": duration, "status": "error"}

                await db.end_session(
                    session_id,
                    SessionStatus.ERROR.value,
                    error_message=str(e),
                    metrics=metrics
                )

                # Log the error for debugging
                logger.error(f"Session {session_id} failed with error: {e}", exc_info=True)

                # Don't re-raise - return session_info with ERROR status instead
                # This allows the API auto-continue loop to detect the error and stop
                # (line 1247 in api/main.py checks session.status == "error")

            finally:
                # Stop sandbox
                try:
                    clear_active_sandbox()
                    await sandbox.stop()
                    logger.info(f"Sandbox stopped for session {session_number}")
                except Exception as e:
                    logger.error(f"Error stopping sandbox: {e}")

                # Restore signal handlers
                session_manager.restore_handlers()

                # Remove from session managers
                if str(session_id) in self.session_managers:
                    del self.session_managers[str(session_id)]

            return session_info

    async def stop_session(self, session_id: UUID, reason: str = "User requested stop") -> bool:
        """
        Stop an active session immediately.

        Args:
            session_id: UUID of the session to stop
            reason: Reason for stopping

        Returns:
            True if session was stopped, False if not found or not running
        """
        session_id_str = str(session_id)

        if session_id_str in self.session_managers:
            manager = self.session_managers[session_id_str]
            manager.interrupted = True

            # Update database
            async with DatabaseManager() as db:
                await db.end_session(
                    session_id,
                    SessionStatus.INTERRUPTED.value,
                    interruption_reason=reason
                )

            return True

        return False

    def set_stop_after_current(self, project_id: UUID, stop: bool = True):
        """
        Set flag to stop auto-continue after current session completes.

        This allows graceful stopping: the current session finishes normally,
        but no new session is started.

        Args:
            project_id: UUID of the project
            stop: If True, stop after current. If False, clear flag.
        """
        self.stop_after_current[str(project_id)] = stop

    def should_stop_after_current(self, project_id: UUID) -> bool:
        """
        Check if auto-continue should be stopped after current session.

        Args:
            project_id: UUID of the project

        Returns:
            True if should stop after current session
        """
        return self.stop_after_current.get(str(project_id), False)

    async def get_session_info(self, session_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get information about a session.

        Args:
            session_id: UUID of the session

        Returns:
            Session dict if found, None otherwise
        """
        async with DatabaseManager() as db:
            # Get session from history (there's no get_session method)
            # We'll need to query by session_id from the sessions table
            async with db.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM sessions WHERE id = $1",
                    session_id
                )
                return dict(row) if row else None

    async def list_sessions(self, project_id: UUID) -> List[Dict[str, Any]]:
        """
        List all sessions for a project.

        Args:
            project_id: UUID of the project

        Returns:
            List of session dicts
        """
        async with DatabaseManager() as db:
            return await db.get_session_history(project_id, limit=100)

    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all currently active sessions.

        Returns:
            List of active session dicts
        """
        async with DatabaseManager() as db:
            # Get all projects and check for active sessions
            projects = await db.list_projects()
            active_sessions = []
            for project in projects:
                session = await db.get_active_session(project['id'])
                if session:
                    active_sessions.append(session)
            return active_sessions

    # =========================================================================
    # Environment Configuration
    # =========================================================================

    async def mark_env_configured(self, project_id: UUID) -> bool:
        """
        Mark a project's environment as configured.

        Args:
            project_id: UUID of the project

        Returns:
            True if successful
        """
        async with DatabaseManager() as db:
            await db.update_project_env_configured(project_id, configured=True)
            return True

    async def delete_project(self, project_id: UUID) -> bool:
        """
        Delete a project and all associated data.

        This removes:
        - Database records (project, epics, tasks, tests, sessions)
        - Generated code directory
        - Log files
        - Docker container (if it exists)

        Args:
            project_id: UUID of the project to delete

        Returns:
            True if successful

        Raises:
            ValueError: If project doesn't exist
        """
        import shutil
        from core.sandbox_manager import SandboxManager

        async with DatabaseManager() as db:
            # Get project info
            project = await db.get_project(project_id)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Get project path
            project_name = project['name']
            generations_dir = Path(self.config.project.default_generations_dir)
            project_path = generations_dir / project_name

            # Delete from database first (this will cascade to all related tables)
            await db.delete_project(project_id)

            # Delete Docker container if it exists (best effort - don't fail if error)
            try:
                deleted = SandboxManager.delete_docker_container(project_name)
                if deleted:
                    logger.info(f"Successfully deleted Docker container for project {project_name}")
                else:
                    logger.info(f"No Docker container found for project {project_name}")
            except Exception as e:
                logger.error(f"Failed to delete Docker container for project {project_name}: {e}", exc_info=True)

            # Delete project directory if it exists
            if project_path.exists():
                shutil.rmtree(project_path)

            return True

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def is_postgresql_configured(self) -> bool:
        """Check if PostgreSQL is configured."""
        return is_postgresql_configured()

    async def cleanup_stale_sessions(self) -> int:
        """
        Clean up stale sessions across all projects.

        Marks sessions as 'interrupted' if they're still marked as 'running'
        but have been inactive for longer than type-specific thresholds:
        - Initializer: 30 minutes
        - Coding: 10 minutes
        - Review: 5 minutes

        This handles ungraceful shutdowns:
        - System sleep/hibernation
        - Process killed without cleanup
        - Orchestrator crash

        Returns:
            Number of sessions marked as interrupted
        """
        async with DatabaseManager() as db:
            return await db.cleanup_stale_sessions()
