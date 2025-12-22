"""
Autonomous Coding Agent API (PostgreSQL Version)
=================================================

RESTful API for managing autonomous coding agent projects and sessions.
Uses PostgreSQL for all project and session state management.

This API provides:
- Project management (create, list, get details)
- Session control (start, stop, status)
- Real-time progress updates via WebSocket
- Integration with PostgreSQL-based AgentOrchestrator

Design Philosophy:
- Fully async with PostgreSQL
- UUID-based project identification
- Database as single source of truth
- Real-time updates via WebSocket
- Authentication-ready architecture
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID
import asyncio
import logging

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File, Form, Body, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Import authentication
from api.auth import verify_password, create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES

# Load environment variables from .env file in agent root directory
# CRITICAL: Do NOT load from CWD, which might be a generated project directory
# Get agent root directory (parent of api/ directory)
_api_dir = Path(__file__).parent
_agent_root = _api_dir.parent
_agent_env_file = _agent_root / ".env"

# Load from agent's .env only, not from any project directory
load_dotenv(dotenv_path=_agent_env_file)

# Ensure authentication is available for Claude SDK
# The SDK expects CLAUDE_CODE_OAUTH_TOKEN (preferred) or ANTHROPIC_API_KEY
import os

# Remove any leaked ANTHROPIC_API_KEY from environment
# (might have been set by system or previous imports)
leaked_api_key = os.getenv("ANTHROPIC_API_KEY")
if leaked_api_key:
    os.environ.pop("ANTHROPIC_API_KEY", None)
    logger = logging.getLogger(__name__)
    logger.warning(
        f"Removed leaked ANTHROPIC_API_KEY from environment. "
        f"This should not happen - check for .env files in project directories."
    )

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import AgentOrchestrator, SessionInfo, SessionStatus, SessionType
from database_connection import DatabaseManager, is_postgresql_configured, get_db
from config import Config
from reset import reset_project
from api.prompt_improvements_routes import router as prompt_improvements_router

logger = logging.getLogger(__name__)

# =============================================================================
# API Models (Request/Response)
# =============================================================================


class ProjectCreate(BaseModel):
    """Request model for creating a new project."""
    name: str = Field(..., description="Unique project name")
    spec_content: Optional[str] = Field(None, description="Specification content")
    spec_source: Optional[str] = Field(None, description="Path to spec file (if uploading)")
    force: bool = Field(False, description="Overwrite existing project if it exists")


class ProjectResponse(BaseModel):
    """Response model for project information."""
    model_config = {"extra": "ignore"}  # Ignore extra fields from database

    id: str  # UUID as string
    name: str
    created_at: str
    updated_at: Optional[str] = None
    status: str = "active"
    is_initialized: bool = False  # NEW: Whether initialization (Session 1) is complete
    completed_at: Optional[str] = None  # Timestamp when all tasks completed
    progress: Dict[str, Any]
    next_task: Optional[Dict[str, Any]] = None
    active_sessions: List[Dict[str, Any]] = []
    has_env_file: bool = False
    has_env_example: bool = False
    needs_env_config: bool = False
    env_configured: bool = False
    spec_file_path: Optional[str] = None


class SessionStart(BaseModel):
    """Request model for starting a session."""
    initializer_model: Optional[str] = Field(None, description="Model for initialization session")
    coding_model: Optional[str] = Field(None, description="Model for coding sessions")
    max_iterations: Optional[int] = Field(None, description="Maximum sessions to run (None = unlimited if auto_continue enabled)")
    auto_continue: bool = Field(True, description="Auto-continue to next session after completion")


class SessionResponse(BaseModel):
    """Response model for session information."""
    session_id: str  # UUID as string
    project_id: str  # UUID as string
    session_number: int
    session_type: str
    model: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Dict[str, Any] = {}


# =============================================================================
# FastAPI Application
# =============================================================================

# Global orchestrator instance (needs to be created before lifespan)
# Use allow_exit=False to prevent sessions from calling sys.exit() and killing the API server
async def orchestrator_event_callback(project_id: UUID, event_type: str, data: Dict[str, Any]):
    """Handle events from the orchestrator and broadcast via WebSocket."""
    await notify_project_update(str(project_id), {
        "type": event_type,
        **data
    })

orchestrator = AgentOrchestrator(verbose=False, allow_exit=False, event_callback=orchestrator_event_callback)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager - runs on startup and shutdown."""
    # Startup: Clean up stale sessions from previous runs
    logger.info("API starting up - cleaning up stale sessions...")
    try:
        count = await orchestrator.cleanup_stale_sessions()
        if count > 0:
            logger.info(f"Marked {count} stale session(s) as interrupted on startup")
        else:
            logger.info("No stale sessions found")
    except Exception as e:
        logger.error(f"Failed to cleanup stale sessions on startup: {e}")

    # Start periodic cleanup background task
    cleanup_task = None
    async def periodic_cleanup():
        """Periodically clean up stale sessions (every 5 minutes)."""
        while True:
            try:
                await asyncio.sleep(300)  # 5 minutes
                count = await orchestrator.cleanup_stale_sessions()
                if count > 0:
                    logger.info(f"Periodic cleanup: marked {count} stale session(s) as interrupted")
            except asyncio.CancelledError:
                logger.info("Periodic cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")

    cleanup_task = asyncio.create_task(periodic_cleanup())
    logger.info("Started periodic stale session cleanup (every 5 minutes)")

    yield

    # Shutdown: cancel background task
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    logger.info("API shutting down")


app = FastAPI(
    title="Autonomous Coding Agent API (PostgreSQL)",
    description="API for managing autonomous coding agent projects and sessions with PostgreSQL backend",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware (allow all origins for now - restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(prompt_improvements_router)

# Load configuration
config = Config.load_default()

# Active WebSocket connections (project_id -> list of WebSockets)
active_connections: Dict[str, List[WebSocket]] = {}

# Background tasks for running sessions
running_sessions: Dict[str, asyncio.Task] = {}


# Helper function to convert datetime fields
def convert_datetimes_to_str(data: Dict[str, Any], fields: List[str] = None) -> Dict[str, Any]:
    """Convert datetime fields to ISO format strings for JSON serialization."""
    if fields is None:
        fields = ['created_at', 'updated_at', 'started_at', 'ended_at', 'env_configured_at', 'completed_at']

    for field in fields:
        if field in data and data[field]:
            if hasattr(data[field], 'isoformat'):
                data[field] = data[field].isoformat()
            else:
                data[field] = str(data[field])
    return data


# =============================================================================
# Startup/Shutdown Events
# =============================================================================

async def cleanup_orphaned_sessions(db: Any) -> int:
    """
    Clean up sessions that were marked as 'running' when the server was stopped.

    This handles the case where Ctrl+C stops the API server while a session
    is active. The signal handler in agent.py sets the interrupted flag, but
    the database update might not complete before the server exits.

    On startup, we detect any sessions still marked as 'running' and
    immediately mark them as 'interrupted'. This provides fast UX feedback
    (within seconds of restart) rather than waiting 10+ minutes for the
    stale session cleanup.

    Returns:
        Number of sessions cleaned up
    """
    async with db.acquire() as conn:
        # Mark any 'running' sessions as interrupted
        # These are sessions from the previous server instance that didn't clean up
        result = await conn.execute(
            """
            UPDATE sessions
            SET status = 'interrupted',
                ended_at = COALESCE(ended_at, NOW()),
                interruption_reason = 'Server was restarted while session was running'
            WHERE status = 'running'
              AND ended_at IS NULL
            """
        )

        # Extract count from "UPDATE N" result
        count = int(result.split()[-1]) if result else 0
        return count


@app.on_event("startup")
async def startup_event():
    """Initialize database connection on startup."""
    if not is_postgresql_configured():
        logger.warning("PostgreSQL not configured - API will have limited functionality")
    else:
        # Test database connection
        try:
            async with DatabaseManager() as db:
                logger.info("PostgreSQL connection verified")

                # Clean up orphaned "running" sessions from previous server instance
                # This provides fast UX feedback (within seconds) when server restarts
                cleaned = await cleanup_orphaned_sessions(db)
                if cleaned > 0:
                    logger.info(f"✓ Cleaned up {cleaned} orphaned session(s) from previous server instance")
        except Exception as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    # Cancel any running sessions
    for session_id, task in running_sessions.items():
        if not task.done():
            task.cancel()

    # Close WebSocket connections
    for connections in active_connections.values():
        for ws in connections:
            try:
                await ws.close()
            except Exception:
                pass


# =============================================================================
# Health & Info Endpoints
# =============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    db_status = "healthy" if is_postgresql_configured() else "not configured"

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0",
        "database": db_status,
    }


@app.get("/api/info")
async def get_info(current_user: dict = Depends(get_current_user)):
    """Get API information."""
    return {
        "version": "2.0.0",
        "database_configured": is_postgresql_configured(),
        "default_models": {
            "initializer": config.models.initializer,
            "coding": config.models.coding,
        },
        "generations_dir": config.project.default_generations_dir,
    }


@app.post("/api/admin/cleanup-orphaned-sessions")
async def trigger_orphaned_session_cleanup(current_user: dict = Depends(get_current_user)):
    """
    Manually trigger cleanup of orphaned sessions.

    Marks any sessions still showing as 'running' as 'interrupted'.
    Useful when sessions are interrupted but database wasn't updated.
    """
    if not is_postgresql_configured():
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        async with DatabaseManager() as db:
            cleaned = await cleanup_orphaned_sessions(db)
            return {
                "success": True,
                "cleaned_count": cleaned,
                "message": f"Cleaned up {cleaned} orphaned session(s)"
            }
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Authentication Endpoints
# =============================================================================

class LoginRequest(BaseModel):
    """Login request model."""
    password: str = Field(..., description="UI password")


class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in minutes")


@app.post("/api/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate and receive a JWT token.

    Args:
        request: Login request with password

    Returns:
        JWT access token for API authentication

    Raises:
        401: Invalid password
    """
    if not verify_password(request.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect password"
        )

    # Create access token
    access_token = create_access_token(
        data={"authenticated": True}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES
    }


@app.get("/api/auth/verify")
async def verify_token(current_user: dict = Depends(get_current_user)):
    """
    Verify that the current token is valid.

    Requires valid JWT token in Authorization header.

    Returns:
        User information from token
    """
    return {
        "authenticated": True,
        "user": current_user
    }


# =============================================================================
# Project Endpoints
# =============================================================================

@app.get("/api/projects", response_model=List[ProjectResponse])
async def list_projects(current_user: dict = Depends(get_current_user)):
    """List all projects."""
    try:
        projects = await orchestrator.list_projects()

        # Convert UUIDs and datetimes for JSON serialization
        response_projects = []
        for p in projects:
            project_dict = dict(p)
            project_dict['id'] = str(project_dict.get('id', ''))
            project_dict = convert_datetimes_to_str(project_dict)
            response_projects.append(project_dict)

        return response_projects
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects", response_model=ProjectResponse)
async def create_project(
    name: str = Form(...),
    spec_file: Optional[UploadFile] = File(None),
    force: bool = Form(False),
    sandbox_type: str = Form("docker"),
    initializer_model: Optional[str] = Form(None),
    coding_model: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """
    Create a new project.

    Accepts either:
    - Form data with spec_file upload
    - JSON body with spec_content
    """
    try:
        # Validate project name format
        import re
        if not re.match(r'^[a-z0-9_-]+$', name):
            raise HTTPException(
                status_code=400,
                detail="Project name must contain only lowercase letters, numbers, hyphens, and underscores (no spaces or special characters)"
            )

        spec_content = None
        spec_source = None

        if spec_file:
            # Read uploaded file
            spec_content = (await spec_file.read()).decode('utf-8')
            # Don't pass spec_source when we have content from upload
            # The orchestrator will handle writing it to the project directory

        # Create project
        project = await orchestrator.create_project(
            project_name=name,
            spec_source=spec_source,  # None for uploads
            spec_content=spec_content,
            force=force,
            sandbox_type=sandbox_type,
            initializer_model=initializer_model,
            coding_model=coding_model,
        )

        # Convert for response
        project_dict = dict(project)
        project_dict['id'] = str(project_dict.get('id', ''))
        project_dict = convert_datetimes_to_str(project_dict)

        # Add default values for response
        project_dict['progress'] = {'total_tasks': 0, 'completed_tasks': 0}
        project_dict['active_sessions'] = []

        return project_dict

    except HTTPException:
        # Re-raise HTTPException (like validation errors) without catching
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    """Get project details by ID."""
    try:
        # Convert string to UUID
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        # Convert for response
        project_dict = dict(project_info)
        project_dict['id'] = str(project_dict.get('id', ''))
        project_dict = convert_datetimes_to_str(project_dict)

        return project_dict
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all associated data."""
    try:
        # Convert string to UUID
        project_uuid = UUID(project_id)

        # Delete the project
        await orchestrator.delete_project(project_uuid)

        return {"message": f"Project {project_id} deleted successfully"}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/progress")
async def get_project_progress(project_id: str):
    """Get project progress statistics."""
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            progress = await db.get_progress(project_uuid)

            # Convert Decimal values to float for JSON serialization
            if 'task_completion_pct' in progress:
                progress['task_completion_pct'] = float(progress['task_completion_pct'])
            if 'test_pass_pct' in progress:
                progress['test_pass_pct'] = float(progress['test_pass_pct'])

            return progress
    except Exception as e:
        logger.error(f"Failed to get progress for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/coverage")
async def get_test_coverage(project_id: str):
    """
    Get test coverage analysis for a project.

    Returns coverage data generated after initialization session,
    including overall statistics, per-epic breakdown, and warnings.
    """
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            coverage = await db.get_test_coverage(project_uuid)

            if not coverage:
                raise HTTPException(
                    status_code=404,
                    detail="Test coverage not available. Run initialization session first."
                )

            return coverage
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get test coverage for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/epics")
async def get_project_epics(project_id: str):
    """Get all epics for a project."""
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            epics = await db.list_epics(project_uuid)
            return epics
    except Exception as e:
        logger.error(f"Failed to get epics for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/tasks")
async def get_project_tasks(project_id: str, status: Optional[str] = None):
    """Get all tasks for a project."""
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            tasks = await db.list_tasks(project_uuid)
            # Filter by status if provided
            if status:
                tasks = [t for t in tasks if t.get('status') == status]
            return tasks
    except Exception as e:
        logger.error(f"Failed to get tasks for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/tasks/{task_id}")
async def get_task_detail(project_id: str, task_id: int):
    """Get detailed task information including tests and epic context."""
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            task = await db.get_task_with_tests(task_id, project_uuid)
            if not task:
                raise HTTPException(status_code=404, detail="Task not found")
            return task
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/epics/{epic_id}")
async def get_epic_detail(project_id: str, epic_id: int):
    """Get detailed epic information including all tasks."""
    try:
        logger.info(f"Getting epic detail for project={project_id}, epic_id={epic_id}")
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            epic = await db.get_epic_with_tasks(epic_id, project_uuid)
            logger.info(f"Epic result: {epic is not None}, tasks: {len(epic.get('tasks', [])) if epic else 0}")
            if not epic:
                raise HTTPException(status_code=404, detail="Epic not found")
            return epic
    except ValueError as e:
        logger.error(f"ValueError: {e}")
        raise HTTPException(status_code=400, detail="Invalid project ID")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get epic {epic_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/env")
async def get_env_config(project_id: str):
    """Get environment configuration for a project."""
    try:
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        # Get project path from local_path field
        project_path = Path(project_info.get('local_path', ''))
        if not project_path or not project_path.exists():
            return {"has_env_example": False, "variables": []}

        env_example_path = project_path / ".env.example"
        env_path = project_path / ".env"

        if not env_example_path.exists():
            return {"has_env_example": False, "variables": []}

        # Parse .env.example for variable structure and comments
        variables = []
        current_comment = None

        with open(env_example_path, 'r') as f:
            for line in f:
                line = line.rstrip()

                # Comment line
                if line.startswith('#'):
                    comment_text = line.lstrip('#').strip()
                    if comment_text:
                        current_comment = comment_text
                    continue

                # Variable line
                if '=' in line:
                    key, default_value = line.split('=', 1)
                    key = key.strip()
                    default_value = default_value.strip().strip('"').strip("'")

                    # Determine if required
                    required = not default_value or default_value.startswith('your_') or default_value == ''

                    variables.append({
                        "key": key,
                        "value": default_value,
                        "comment": current_comment,
                        "required": required
                    })
                    current_comment = None

        # Load current values from .env if it exists
        if env_path.exists():
            env_values = {}
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_values[key.strip()] = value.strip().strip('"').strip("'")

            # Update variables with current values
            for var in variables:
                if var["key"] in env_values:
                    var["value"] = env_values[var["key"]]

        return {"has_env_example": True, "variables": variables}

    except Exception as e:
        logger.error(f"Failed to get env config for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/env")
async def save_env_config(project_id: str, payload: Dict[str, Any]):
    """Save environment configuration to .env file."""
    try:
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        # Get project path
        project_path = Path(project_info.get('local_path', ''))
        if not project_path or not project_path.exists():
            raise HTTPException(status_code=404, detail="Project directory not found")

        variables = payload.get("variables", [])
        env_path = project_path / ".env"

        with open(env_path, 'w') as f:
            f.write("# Environment Configuration\n")
            f.write("# Generated by Autonomous Coding Agent Web UI\n")
            f.write(f"# Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for var in variables:
                key = var.get("key", "")
                value = var.get("value", "")
                comment = var.get("comment", "")

                if comment:
                    f.write(f"# {comment}\n")

                # Quote value if it contains spaces
                if ' ' in value:
                    f.write(f'{key}="{value}"\n')
                else:
                    f.write(f'{key}={value}\n')

                f.write('\n')

        # Mark environment as configured in database
        await orchestrator.mark_env_configured(project_uuid)

        return {
            "status": "saved",
            "message": "Environment configuration saved successfully",
            "path": str(env_path)
        }

    except Exception as e:
        logger.error(f"Failed to save env config for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Settings Endpoints
# =============================================================================

@app.get("/api/projects/{project_id}/settings")
async def get_project_settings(project_id: str):
    """Get project settings."""
    try:
        project_uuid = UUID(project_id)

        async with DatabaseManager() as db:
            settings = await db.get_project_settings(project_uuid)

        return settings

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to get settings for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/projects/{project_id}/settings")
async def update_project_settings(project_id: str, settings: Dict[str, Any]):
    """
    Update project settings.

    Supported settings:
    - auto_continue: bool - Auto-start next session after completion
    - sandbox_type: str - 'docker' or 'local'
    - coding_model: str - LLM model for coding sessions
    - initializer_model: str - LLM model for initialization
    - max_iterations: int | null - Max sessions per auto-run
    """
    try:
        project_uuid = UUID(project_id)

        async with DatabaseManager() as db:
            await db.update_project_settings(project_uuid, settings)

        return {
            "status": "updated",
            "message": "Settings updated successfully",
            "settings": settings
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to update settings for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/projects/{project_id}")
async def rename_project(project_id: str, name: str = Body(..., embed=True)):
    """
    Rename a project.

    Args:
        project_id: UUID of the project
        name: New name for the project

    Returns:
        Updated project details

    Raises:
        400: Invalid project ID format
        404: Project not found
        409: Name already in use
        500: Server error
    """
    try:
        project_uuid = UUID(project_id)

        async with DatabaseManager() as db:
            # Rename the project (will raise ValueError if name in use or project not found)
            await db.rename_project(project_uuid, name)

        # Get updated project info
        project = await orchestrator.get_project_info(project_uuid)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found after rename")

        return project

    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        elif "already in use" in error_msg.lower():
            raise HTTPException(status_code=409, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        logger.error(f"Failed to rename project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/reset")
async def reset_project_endpoint(project_id: str):
    """
    Reset project to post-initialization state.

    This endpoint:
    - Validates the project exists and is initialized
    - Stops any running Docker sandbox containers
    - Resets database (tasks, tests, epics, deletes coding sessions)
    - Resets git to initialization commit
    - Archives coding session logs
    - Resets progress notes

    Args:
        project_id: UUID of the project

    Returns:
        Dict with reset results and details

    Raises:
        400: Invalid project ID or project not initialized
        404: Project not found
        409: Active session running (cannot reset)
        500: Reset operation failed
    """
    try:
        project_uuid = UUID(project_id)

        # Get project info
        async with DatabaseManager() as db:
            project = await db.get_project(project_uuid)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Check if there's an active session
            active_session = await db.get_active_session(project_uuid)
            if active_session:
                raise HTTPException(
                    status_code=409,
                    detail="Cannot reset project while a session is running. Stop the session first."
                )

            # Get local_path from metadata
            metadata = project.get('metadata', {})
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            local_path = metadata.get('local_path')
            if not local_path:
                raise HTTPException(
                    status_code=400,
                    detail="Project has no local path configured"
                )

        # Perform reset
        result = await reset_project(project_uuid, Path(local_path))

        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Reset failed"))

        # Notify via WebSocket
        await notify_project_update(project_id, {
            "type": "project_reset",
            "result": result
        })

        return {
            "success": True,
            "message": "Project successfully reset to post-initialization state",
            **result
        }

    except ValueError as e:
        error_msg = str(e)
        if "not initialized" in error_msg.lower():
            raise HTTPException(status_code=400, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid project ID: {project_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Session Endpoints
# =============================================================================

@app.post("/api/projects/{project_id}/initialize", response_model=SessionResponse)
async def initialize_project(
    project_id: str,
    initializer_model: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Run initialization session (Session 1) for a project.

    This endpoint:
    - Creates the project structure (epics, tasks, tests)
    - Runs init.sh to setup the environment
    - ALWAYS stops after Session 1 completes
    - Does NOT auto-continue to coding sessions

    Args:
        project_id: UUID of the project
        initializer_model: Model to use (optional, defaults to config)

    Returns:
        SessionResponse with session details

    Raises:
        400: Invalid project ID or project already initialized
        404: Project not found
        500: Server error during initialization
    """
    try:
        project_uuid = UUID(project_id)

        # Start initialization session asynchronously
        async def run_initialization():
            try:
                # Create progress callback for real-time WebSocket updates
                async def progress_update(event: Dict[str, Any]):
                    """Broadcast progress events to connected WebSocket clients."""
                    await notify_project_update(str(project_uuid), {
                        "type": "progress",
                        "event": event
                    })

                session = await orchestrator.start_initialization(
                    project_id=project_uuid,
                    initializer_model=initializer_model,
                    progress_callback=progress_update
                )

                # Send WebSocket notification
                await notify_project_update(str(project_uuid), {
                    "type": "initialization_complete",
                    "session": session.to_dict()
                })

            except Exception as e:
                logger.error(f"Initialization failed: {e}")
                await notify_project_update(str(project_uuid), {
                    "type": "initialization_error",
                    "error": str(e)
                })

        # Run in background
        task = asyncio.create_task(run_initialization())
        running_sessions[project_id] = task

        return {
            "session_id": "pending",  # Will be set once session starts
            "project_id": project_id,
            "session_number": 1,
            "session_type": "initializer",
            "model": initializer_model or config.models.initializer,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "message": "Initialization started"
        }

    except ValueError as e:
        if "already initialized" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        elif "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start initialization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/initialize/cancel")
async def cancel_initialization(project_id: str):
    """
    Cancel running initialization session and clean up.

    This endpoint:
    - Stops the running initialization session
    - Removes any created epics/tasks/tests from database
    - Deletes project files created during initialization
    - Allows user to restart from scratch

    Note: This is different from "Stop Now" which keeps partial work.
    Cancellation assumes the spec needs to be changed and we start over.

    Returns:
        Status message

    Raises:
        400: No initialization session running
        404: Project not found
        500: Server error
    """
    try:
        project_uuid = UUID(project_id)

        async with DatabaseManager() as db:
            # Get project
            project = await db.get_project(project_uuid)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Find running initialization session
            sessions = await db.list_sessions(project_uuid)
            init_session = None
            for session in sessions:
                if session.get('session_type') == 'initializer' and session.get('status') == 'running':
                    init_session = session
                    break

            if not init_session:
                raise HTTPException(
                    status_code=400,
                    detail="No initialization session running. Nothing to cancel."
                )

            session_id = init_session['id']

            # Stop the session (interrupt it)
            await orchestrator.stop_session(str(session_id))

            # Clean up database: Remove all epics, tasks, tests
            epics = await db.list_epics(project_uuid)
            for epic in epics:
                # This will cascade delete tasks and tests
                await db.execute(
                    "DELETE FROM epics WHERE id = $1",
                    epic['id']
                )

            # Mark session as cancelled (not just interrupted)
            await db.execute(
                "UPDATE sessions SET status = $1, interruption_reason = $2, ended_at = NOW() WHERE id = $3",
                "interrupted",
                "Initialization cancelled by user",
                session_id
            )

            # Note: We keep the project directory and spec file
            # User may want to modify spec and re-initialize

        return {
            "status": "cancelled",
            "message": "Initialization cancelled. Project ready for re-initialization.",
            "project_id": project_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel initialization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/coding/start", response_model=SessionResponse)
async def start_coding_sessions(
    project_id: str,
    coding_model: Optional[str] = None,
    max_iterations: Optional[int] = 0,  # 0 = unlimited
    background_tasks: BackgroundTasks = None
):
    """
    Run coding sessions (Session 2+) for a project.

    This endpoint:
    - Verifies initialization is complete
    - Runs multiple sessions with auto-continue
    - Respects max_iterations setting (0/None = unlimited)
    - Respects stop_after_current flag

    Args:
        project_id: UUID of the project
        coding_model: Model to use (optional, defaults to config)
        max_iterations: Maximum sessions to run (0 or None = unlimited)

    Returns:
        SessionResponse with initial session details

    Raises:
        400: Invalid project ID or project not initialized
        404: Project not found
        500: Server error during session start
    """
    try:
        project_uuid = UUID(project_id)

        # Start coding sessions asynchronously
        async def run_coding():
            try:
                # Create progress callback for real-time WebSocket updates
                async def progress_update(event: Dict[str, Any]):
                    """Broadcast progress events to connected WebSocket clients."""
                    await notify_project_update(str(project_uuid), {
                        "type": "progress",
                        "event": event
                    })

                last_session = await orchestrator.start_coding_sessions(
                    project_id=project_uuid,
                    coding_model=coding_model,
                    max_iterations=max_iterations,
                    progress_callback=progress_update
                )

                # Send WebSocket notification about completion
                await notify_project_update(str(project_uuid), {
                    "type": "coding_sessions_complete",
                    "last_session": last_session.to_dict()
                })

            except Exception as e:
                logger.error(f"Coding sessions failed: {e}")
                await notify_project_update(str(project_uuid), {
                    "type": "coding_sessions_error",
                    "error": str(e)
                })

        # Run in background
        task = asyncio.create_task(run_coding())
        running_sessions[project_id] = task

        return {
            "session_id": "pending",  # Will be set once session starts
            "project_id": project_id,
            "session_number": 0,  # Will be determined dynamically
            "session_type": "coding",
            "model": coding_model or config.models.coding,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "max_iterations": max_iterations,
            "message": f"Coding sessions starting (max: {max_iterations or 'unlimited'})"
        }

    except ValueError as e:
        if "not initialized" in str(e):
            raise HTTPException(status_code=400, detail=str(e))
        elif "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start coding sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/sessions/start", response_model=SessionResponse)
async def start_session(project_id: str, session_config: SessionStart, background_tasks: BackgroundTasks):
    """
    **DEPRECATED**: Use /initialize or /coding/start instead.

    Start a new coding session (legacy endpoint for backward compatibility).
    """
    try:
        project_uuid = UUID(project_id)

        # Get default models from config if not provided
        initializer_model = session_config.initializer_model or config.models.initializer
        coding_model = session_config.coding_model or config.models.coding

        # Start session asynchronously
        async def run_session():
            try:
                if session_config.auto_continue:
                    # Auto-continue loop: run multiple sessions
                    iteration = 0
                    while True:
                        # Check max_iterations
                        if session_config.max_iterations is not None and iteration >= session_config.max_iterations:
                            await notify_project_update(str(project_uuid), {
                                "type": "auto_continue_stopped",
                                "reason": "max_iterations_reached",
                                "iterations": iteration
                            })
                            break

                        iteration += 1

                        # Wait between sessions (except first)
                        if iteration > 1:
                            delay = config.timing.auto_continue_delay
                            await notify_project_update(str(project_uuid), {
                                "type": "auto_continue_delay",
                                "delay": delay,
                                "next_session": iteration
                            })
                            await asyncio.sleep(delay)

                        # Create progress callback for real-time WebSocket updates
                        async def progress_update(event: Dict[str, Any]):
                            """Broadcast progress events to connected WebSocket clients."""
                            await notify_project_update(str(project_uuid), {
                                "type": "progress",
                                "event": event
                            })

                        # Start session (this blocks until session completes)
                        session = await orchestrator.start_session(
                            project_id=project_uuid,
                            initializer_model=initializer_model,
                            coding_model=coding_model,
                            max_iterations=None,  # Don't pass to individual session
                            progress_callback=progress_update
                        )

                        # Send WebSocket notification about session completion
                        await notify_project_update(str(project_uuid), {
                            "type": "session_completed",
                            "session": session.to_dict(),
                            "auto_continue": True,
                            "iteration": iteration
                        })

                        # Check session status
                        if session.status.value == "error":
                            await notify_project_update(str(project_uuid), {
                                "type": "auto_continue_stopped",
                                "reason": "session_error",
                                "error": session.error_message
                            })
                            break
                        elif session.status.value == "interrupted":
                            await notify_project_update(str(project_uuid), {
                                "type": "auto_continue_stopped",
                                "reason": "session_interrupted"
                            })
                            break

                else:
                    # Single session mode (original behavior)

                    # Create progress callback for real-time WebSocket updates
                    async def progress_update(event: Dict[str, Any]):
                        """Broadcast progress events to connected WebSocket clients."""
                        await notify_project_update(str(project_uuid), {
                            "type": "progress",
                            "event": event
                        })

                    session = await orchestrator.start_session(
                        project_id=project_uuid,
                        initializer_model=initializer_model,
                        coding_model=coding_model,
                        max_iterations=session_config.max_iterations,
                        progress_callback=progress_update
                    )

                    # Send WebSocket notification
                    await notify_project_update(str(project_uuid), {
                        "type": "session_completed",
                        "session": session.to_dict()
                    })

            except Exception as e:
                logger.error(f"Session failed: {e}")
                await notify_project_update(str(project_uuid), {
                    "type": "session_error",
                    "error": str(e)
                })

        # Create task for background execution and store it to prevent garbage collection
        background_tasks.add_task(run_session)

        # Get the actual session info that will be created
        db = await get_db()
        try:
            next_session_num = await db.get_next_session_number(project_uuid)
            # Return info about the session that will be created
            # WebSocket will provide real-time updates when session actually starts
            return SessionResponse(
                session_id="pending",  # Will be updated via WebSocket
                project_id=str(project_uuid),
                session_number=next_session_num,
                session_type="coding" if next_session_num > 0 else "initializer",
                model=initializer_model if next_session_num == 0 else coding_model,
                status="starting",
                created_at=datetime.now().isoformat(),
                metrics={}
            )
        finally:
            await db.disconnect()

    except Exception as e:
        logger.error(f"Failed to start session for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/sessions")
async def list_sessions(project_id: str):
    """List all sessions for a project."""
    try:
        project_uuid = UUID(project_id)
        sessions = await orchestrator.list_sessions(project_uuid)

        # Convert UUIDs and timestamps for response
        response_sessions = []
        for session in sessions:
            session_dict = dict(session)
            # Map 'id' to 'session_id' for frontend compatibility
            session_dict['session_id'] = str(session_dict.get('id', ''))
            session_dict['project_id'] = str(session_dict.get('project_id', ''))

            # Convert timestamps
            for field in ['created_at', 'started_at', 'ended_at']:
                if field in session_dict and session_dict[field]:
                    if hasattr(session_dict[field], 'isoformat'):
                        session_dict[field] = session_dict[field].isoformat()
                    else:
                        session_dict[field] = str(session_dict[field])

            # Parse metrics JSONB field (comes as string from asyncpg)
            if 'metrics' in session_dict:
                if isinstance(session_dict['metrics'], str):
                    try:
                        session_dict['metrics'] = json.loads(session_dict['metrics'])
                    except (json.JSONDecodeError, TypeError):
                        session_dict['metrics'] = {}
                elif session_dict['metrics'] is None:
                    session_dict['metrics'] = {}

            response_sessions.append(session_dict)

        return response_sessions

    except Exception as e:
        logger.error(f"Failed to list sessions for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/sessions/{session_id}")
async def get_session(project_id: str, session_id: str):
    """Get session details."""
    try:
        session_uuid = UUID(session_id)
        session_info = await orchestrator.get_session_info(session_uuid)

        if not session_info:
            raise HTTPException(status_code=404, detail="Session not found")

        # Convert for response
        session_dict = dict(session_info)
        # Map 'id' to 'session_id' for frontend compatibility
        session_dict['session_id'] = str(session_dict.get('id', ''))
        session_dict['project_id'] = str(session_dict.get('project_id', ''))

        # Convert timestamps
        for field in ['created_at', 'started_at', 'ended_at']:
            if field in session_dict and session_dict[field]:
                if hasattr(session_dict[field], 'isoformat'):
                    session_dict[field] = session_dict[field].isoformat()
                else:
                    session_dict[field] = str(session_dict[field])

        return session_dict

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/sessions/{session_id}/stop")
async def stop_session(project_id: str, session_id: str):
    """Stop a running session immediately."""
    try:
        session_uuid = UUID(session_id)
        stopped = await orchestrator.stop_session(session_uuid, reason="User requested immediate stop")

        if stopped:
            return {"status": "stopped", "message": "Session stopped successfully"}
        else:
            return {"status": "not_running", "message": "Session was not running"}

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    except Exception as e:
        logger.error(f"Failed to stop session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/projects/{project_id}/stop-after-current")
async def stop_after_current_session(project_id: str):
    """
    Stop auto-continue after current session completes.

    The current session will finish normally, but no new session will start.
    """
    try:
        project_uuid = UUID(project_id)
        orchestrator.set_stop_after_current(project_uuid, stop=True)

        return {
            "status": "set",
            "message": "Will stop after current session completes"
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to set stop-after-current for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/projects/{project_id}/stop-after-current")
async def cancel_stop_after_current(project_id: str):
    """Cancel the stop-after-current flag, allowing auto-continue to resume."""
    try:
        project_uuid = UUID(project_id)
        orchestrator.set_stop_after_current(project_uuid, stop=False)

        return {
            "status": "cleared",
            "message": "Auto-continue will resume"
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to clear stop-after-current for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# WebSocket for Real-time Updates
# =============================================================================

async def notify_project_update(project_id: str, data: Dict[str, Any]):
    """Send update to all WebSocket connections for a project."""
    if project_id in active_connections:
        disconnected = []
        for websocket in active_connections[project_id]:
            try:
                await websocket.send_json(data)
            except Exception:
                disconnected.append(websocket)

        # Remove disconnected websockets
        for ws in disconnected:
            active_connections[project_id].remove(ws)

        # Clean up empty lists
        if not active_connections[project_id]:
            del active_connections[project_id]


@app.websocket("/api/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    """WebSocket endpoint for real-time project updates."""
    await websocket.accept()

    # Add to active connections
    if project_id not in active_connections:
        active_connections[project_id] = []
    active_connections[project_id].append(websocket)

    try:
        # Send initial connection message
        try:
            await websocket.send_json({
                "type": "connected",
                "project_id": project_id,
                "timestamp": datetime.now().isoformat()
            })
        except (WebSocketDisconnect, RuntimeError) as e:
            # Client disconnected before we could send initial message
            logger.debug(f"WebSocket disconnected during initial message: {e}")
            # Clean up connection
            if project_id in active_connections and websocket in active_connections[project_id]:
                active_connections[project_id].remove(websocket)
                if not active_connections[project_id]:
                    del active_connections[project_id]
            return

        # Send initial state with progress
        try:
            project_uuid = UUID(project_id)
            async with DatabaseManager() as db:
                project = await db.get_project(project_uuid)
                if project:
                    progress = await db.get_progress(project_uuid)

                    # Convert UUIDs and Decimals to JSON-serializable types
                    if progress:
                        if 'project_id' in progress:
                            progress['project_id'] = str(progress['project_id'])
                        # Convert Decimal to float
                        for key in ['task_completion_pct', 'test_pass_pct']:
                            if key in progress and progress[key] is not None:
                                progress[key] = float(progress[key])

                    # Parse metadata - asyncpg may return JSONB as string or dict
                    metadata = project.get('metadata', {})
                    if isinstance(metadata, str):
                        try:
                            import json
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse metadata as JSON: {metadata}")
                            metadata = {}
                    elif metadata is None:
                        metadata = {}

                    # Ensure metadata is a dict
                    if not isinstance(metadata, dict):
                        logger.warning(f"Metadata is not a dict after parsing: {type(metadata)}")
                        metadata = {}

                    is_initialized = metadata.get('is_initialized', False)

                    await websocket.send_json({
                        "type": "initial_state",
                        "progress": progress,
                        "is_initialized": is_initialized
                    })
                    logger.debug(f"Sent initial state to WebSocket client for project {project_id}")
        except (WebSocketDisconnect, RuntimeError) as e:
            # Client disconnected before we could send initial state
            logger.debug(f"WebSocket disconnected during initial state: {e}")
            # Clean up connection
            if project_id in active_connections and websocket in active_connections[project_id]:
                active_connections[project_id].remove(websocket)
                if not active_connections[project_id]:
                    del active_connections[project_id]
            return
        except Exception as e:
            logger.error(f"Failed to send initial state: {e}", exc_info=True)
            # Don't fail the whole connection, just log the error

        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for messages (ping/pong or commands)
                data = await websocket.receive_text()

                # Echo back or handle commands
                if data == "ping":
                    await websocket.send_text("pong")
            except (WebSocketDisconnect, RuntimeError):
                # Connection closed normally
                break

    except WebSocketDisconnect:
        # Remove from active connections
        if project_id in active_connections:
            active_connections[project_id].remove(websocket)
            if not active_connections[project_id]:
                del active_connections[project_id]


# =============================================================================
# Log Endpoints (Compatibility - logs are file-based)
# =============================================================================

@app.get("/api/projects/{project_id}/logs")
async def list_logs(project_id: str):
    """List available log files for a project."""
    try:
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        project_path = Path(project_info.get('local_path', ''))
        if not project_path or not project_path.exists():
            return []

        logs_path = project_path / "logs"
        if not logs_path.exists():
            return []

        # Find all session log files
        log_files = []
        for log_file in sorted(logs_path.glob("session_*.txt")):
            # Parse session number from filename
            parts = log_file.stem.split('_')
            if len(parts) >= 2 and parts[1].isdigit():
                session_num = int(parts[1])
                log_files.append({
                    "filename": log_file.name,
                    "session_number": session_num,
                    "type": "human",
                    "size": log_file.stat().st_size,
                    "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                })

        # Also find JSONL logs
        for log_file in sorted(logs_path.glob("session_*.jsonl")):
            parts = log_file.stem.split('_')
            if len(parts) >= 2 and parts[1].isdigit():
                session_num = int(parts[1])
                log_files.append({
                    "filename": log_file.name,
                    "session_number": session_num,
                    "type": "events",
                    "size": log_file.stat().st_size,
                    "modified": datetime.fromtimestamp(log_file.stat().st_mtime).isoformat()
                })

        return log_files

    except Exception as e:
        logger.error(f"Failed to list logs for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/logs/human/{filename}")
async def get_human_log(project_id: str, filename: str):
    """
    Get human-readable log file content.

    Accepts either:
    - Full filename: session_027_20251217_151146.txt
    - Session number prefix: session_027

    If prefix is provided, finds the matching log file.
    """
    try:
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        project_path = Path(project_info.get('local_path', ''))
        if not project_path:
            raise HTTPException(status_code=404, detail="Project path not found")

        # Security check
        if ".." in filename or "/" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        logs_dir = project_path / "logs"

        # Try exact filename first
        log_path = logs_dir / filename

        # If not found and filename looks like a session prefix (e.g., "session_027")
        # find the matching log file
        if not log_path.exists() and filename.startswith("session_"):
            # Look for files matching the pattern: session_NNN_*.txt
            pattern = f"{filename}_*.txt"
            matching_files = list(logs_dir.glob(pattern))

            if matching_files:
                # Use the first match (should only be one)
                log_path = matching_files[0]
                filename = log_path.name  # Update filename to actual file
            else:
                raise HTTPException(status_code=404, detail=f"Log file not found for {filename}")

        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        content = log_path.read_text()
        return {"content": content, "filename": filename}

    except Exception as e:
        logger.error(f"Failed to get log {filename} for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/logs/events/{filename}")
async def get_events_log(project_id: str, filename: str):
    """
    Get JSONL events log file content.

    Accepts either:
    - Full filename: session_027_20251217_151146.jsonl
    - Session number prefix: session_027

    If prefix is provided, finds the matching log file.
    """
    import json

    try:
        project_uuid = UUID(project_id)
        project_info = await orchestrator.get_project_info(project_uuid)

        project_path = Path(project_info.get('local_path', ''))
        if not project_path:
            raise HTTPException(status_code=404, detail="Project path not found")

        # Security check
        if ".." in filename or "/" in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        logs_dir = project_path / "logs"

        # Try exact filename first
        log_path = logs_dir / filename

        # If not found and filename looks like a session prefix (e.g., "session_027")
        # find the matching log file
        if not log_path.exists() and filename.startswith("session_"):
            # Look for files matching the pattern: session_NNN_*.jsonl
            pattern = f"{filename}_*.jsonl"
            matching_files = list(logs_dir.glob(pattern))

            if matching_files:
                # Use the first match (should only be one)
                log_path = matching_files[0]
                filename = log_path.name  # Update filename to actual file
            else:
                raise HTTPException(status_code=404, detail=f"Log file not found for {filename}")

        if not log_path.exists():
            raise HTTPException(status_code=404, detail="Log file not found")

        # Return raw JSONL content as text (don't parse)
        with open(log_path, 'r') as f:
            content = f.read()

        return {"content": content, "filename": filename}

    except Exception as e:
        logger.error(f"Failed to get events log {filename} for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Quality Check Endpoints (Phase 1 Review System Integration)
# =============================================================================

@app.get("/api/projects/{project_id}/quality")
async def get_project_quality(project_id: str):
    """
    Get overall quality summary for a project.

    Returns aggregate quality metrics across all sessions.
    """
    try:
        project_uuid = UUID(project_id)
        db = await get_db()
        try:
            summary = await db.get_project_quality_summary(project_uuid)
            return summary
        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to get quality summary for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/sessions/{session_id}/quality")
async def get_session_quality(project_id: str, session_id: str):
    """
    Get quality check results for a specific session.

    Returns quick quality check metrics and any deep review results.
    """
    try:
        session_uuid = UUID(session_id)
        db = await get_db()
        try:
            quality = await db.get_session_quality(session_uuid)

            if not quality:
                raise HTTPException(status_code=404, detail="Quality check not found for this session")

            return quality
        finally:
            await db.disconnect()

    except HTTPException:
        # Re-raise HTTP exceptions (like 404) without wrapping
        raise
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    except Exception as e:
        logger.error(f"Failed to get quality for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/quality/issues")
async def get_quality_issues(project_id: str, limit: int = 10):
    """
    Get recent sessions with quality issues for a project.

    Args:
        limit: Maximum number of sessions to return (default: 10)
    """
    try:
        project_uuid = UUID(project_id)
        db = await get_db()
        try:
            issues = await db.get_sessions_with_quality_issues(project_uuid, limit)
            return {"issues": issues, "count": len(issues)}
        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to get quality issues for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/projects/{project_id}/quality/browser-verification")
async def get_browser_verification_compliance(project_id: str):
    """
    Get browser verification compliance statistics for a project.

    Returns breakdown of sessions by Playwright usage level.
    Critical quality metric (r=0.98 correlation with session quality).
    """
    try:
        project_uuid = UUID(project_id)
        db = await get_db()
        try:
            compliance = await db.get_browser_verification_compliance(project_uuid)
            return compliance
        finally:
            await db.disconnect()

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    except Exception as e:
        logger.error(f"Failed to get browser verification compliance for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Run the API server
# =============================================================================

if __name__ == "__main__":
    print("\n" + "="*80)
    print("ERROR: Do not run this file directly")
    print("="*80)
    print("\nTo start the API server, use uvicorn from the project root:")
    print("\n  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
    print("\nOr use the wrapper script:")
    print("\n  python start_api.py")
    print("\n" + "="*80 + "\n")
    sys.exit(1)