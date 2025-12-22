"""
PostgreSQL Database Abstraction Layer
=====================================

Database interface for the autonomous coding agent using PostgreSQL.
Uses asyncpg for high-performance async database operations.

This module replaces the SQLite-based database.py with a PostgreSQL
implementation optimized for the new unified database structure.
"""

import asyncpg
import json
from pathlib import Path
from typing import Optional, Dict, List, Any, Union
from datetime import datetime
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
import hashlib
import logging

logger = logging.getLogger(__name__)


class TaskDatabase:
    """
    PostgreSQL database interface for task management.

    Handles all interactions with the PostgreSQL database using asyncpg
    for high-performance async operations.
    """

    def __init__(self, connection_url: str):
        """
        Initialize database connection parameters.

        Args:
            connection_url: PostgreSQL connection string
                Format: postgresql://user:password@host:port/database
        """
        self.connection_url = connection_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self, min_size: int = 10, max_size: int = 20):
        """
        Create connection pool to PostgreSQL.

        Args:
            min_size: Minimum number of connections in pool
            max_size: Maximum number of connections in pool
        """
        self.pool = await asyncpg.create_pool(
            self.connection_url,
            min_size=min_size,
            max_size=max_size,
            command_timeout=60
        )
        logger.info(f"Connected to PostgreSQL with pool size {min_size}-{max_size}")

    async def disconnect(self):
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Disconnected from PostgreSQL")

    @asynccontextmanager
    async def acquire(self):
        """Acquire a connection from the pool."""
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def transaction(self):
        """Create a transaction context."""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    # =========================================================================
    # Project Operations
    # =========================================================================

    async def create_project(
        self,
        name: str,
        spec_file_path: str,
        spec_content: Optional[str] = None,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            name: Unique project name
            spec_file_path: Path to specification file
            spec_content: Content of spec file (for hash calculation)
            user_id: Optional user ID for multi-user support

        Returns:
            Created project record as dictionary
        """
        spec_hash = None
        if spec_content:
            spec_hash = hashlib.sha256(spec_content.encode()).hexdigest()

        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO projects (name, spec_file_path, spec_hash, user_id)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                name, spec_file_path, spec_hash, user_id
            )
            return dict(row)

    async def get_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get project by name.

        Args:
            name: Project name

        Returns:
            Project record or None if not found
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE name = $1",
                name
            )
            return dict(row) if row else None

    async def get_project(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get project by ID.

        Args:
            project_id: Project UUID

        Returns:
            Project record or None if not found
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM projects WHERE id = $1",
                project_id
            )
            if not row:
                return None

            project = dict(row)

            # Extract local_path from metadata JSONB if present
            if project.get('metadata') and isinstance(project['metadata'], dict):
                if 'local_path' in project['metadata']:
                    project['local_path'] = project['metadata']['local_path']

            return project

    async def update_project(
        self,
        project_id: UUID,
        **kwargs
    ) -> None:
        """
        Update project fields.

        Args:
            project_id: Project UUID
            **kwargs: Fields to update (local_path, github_repo_url, etc.)
        """
        # Store local_path in metadata JSONB field
        if 'local_path' in kwargs:
            async with self.acquire() as conn:
                # Get current metadata
                row = await conn.fetchrow(
                    "SELECT metadata FROM projects WHERE id = $1",
                    project_id
                )

                # Parse metadata - asyncpg may return it as string or dict
                if row and row['metadata']:
                    if isinstance(row['metadata'], str):
                        metadata = json.loads(row['metadata'])
                    else:
                        metadata = dict(row['metadata'])
                else:
                    metadata = {}

                metadata['local_path'] = kwargs['local_path']

                # Update metadata
                await conn.execute(
                    "UPDATE projects SET metadata = $1 WHERE id = $2",
                    json.dumps(metadata), project_id
                )
            return

        # For other fields, build dynamic UPDATE query
        if not kwargs:
            return

        set_clauses = []
        values = []
        param_num = 1

        for key, value in kwargs.items():
            set_clauses.append(f"{key} = ${param_num}")
            values.append(value)
            param_num += 1

        values.append(project_id)

        query = f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ${param_num}"

        async with self.acquire() as conn:
            await conn.execute(query, *values)

    async def rename_project(
        self,
        project_id: UUID,
        new_name: str
    ) -> None:
        """
        Rename a project (database name only).

        NOTE: This only updates the project name in the database.
        The directory name in the generations/ folder is NOT changed.
        This is intentional to avoid breaking running sessions and
        maintain filesystem stability.

        Args:
            project_id: Project UUID
            new_name: New project name

        Raises:
            ValueError: If project doesn't exist or name already in use
        """
        # Check if project exists
        project = await self.get_project(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Check if new name is already in use by another project
        async with self.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id FROM projects WHERE name = $1 AND id != $2",
                new_name, project_id
            )
            if existing:
                raise ValueError(f"Project name '{new_name}' is already in use")

            # Update the name
            await conn.execute(
                "UPDATE projects SET name = $1, updated_at = NOW() WHERE id = $2",
                new_name, project_id
            )

    async def update_project_env_configured(
        self,
        project_id: UUID,
        configured: bool = True
    ) -> None:
        """
        Update project environment configuration status.

        Args:
            project_id: Project UUID
            configured: Whether environment is configured
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET env_configured = $1,
                    env_configured_at = CASE WHEN $1 THEN NOW() ELSE NULL END
                WHERE id = $2
                """,
                configured, project_id
            )

    async def mark_project_complete(self, project_id: UUID) -> None:
        """
        Mark a project as complete.

        Sets the completed_at timestamp to NOW() if not already set.

        Args:
            project_id: Project UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE projects
                SET completed_at = COALESCE(completed_at, NOW())
                WHERE id = $1
                """,
                project_id
            )

    async def delete_project(self, project_id: UUID) -> None:
        """
        Delete a project and all associated data.

        This will cascade to delete:
        - All epics
        - All tasks
        - All tests
        - All sessions
        - All reviews
        - All github commits

        Args:
            project_id: Project UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                "DELETE FROM projects WHERE id = $1",
                project_id
            )

    async def get_project_settings(self, project_id: UUID) -> Dict[str, Any]:
        """
        Get project settings from metadata JSONB field.

        Returns default settings if none exist.

        Args:
            project_id: Project UUID

        Returns:
            Dictionary of settings with defaults applied
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                # Return default settings
                return {
                    'sandbox_type': 'docker',
                    'coding_model': 'claude-sonnet-4-5-20250929',
                    'initializer_model': 'claude-opus-4-5-20251101',
                    'max_iterations': None,  # None = unlimited (auto-continue)
                }

            metadata = row['metadata']
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            settings = metadata.get('settings', {})

            # Apply defaults for missing keys
            defaults = {
                'sandbox_type': 'docker',
                'coding_model': 'claude-sonnet-4-5-20250929',
                'initializer_model': 'claude-opus-4-5-20251101',
                'max_iterations': None,  # None = unlimited (auto-continue)
            }

            return {**defaults, **settings}

    async def update_project_settings(
        self,
        project_id: UUID,
        settings: Dict[str, Any]
    ) -> None:
        """
        Update project settings in metadata JSONB field.

        Args:
            project_id: Project UUID
            settings: Dictionary of settings to update
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            metadata = row['metadata'] if row and row['metadata'] else {}
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)

            current_settings = metadata.get('settings', {})

            # Merge with new settings
            updated_settings = {**current_settings, **settings}
            metadata['settings'] = updated_settings

            # Update in database
            await conn.execute(
                "UPDATE projects SET metadata = $1 WHERE id = $2",
                json.dumps(metadata),
                project_id
            )

    async def store_test_coverage(
        self,
        project_id: UUID,
        coverage_data: Dict[str, Any]
    ) -> None:
        """
        Store test coverage analysis results in project metadata.

        Args:
            project_id: Project UUID
            coverage_data: Coverage analysis results from test_coverage.analyze_test_coverage()
        """
        async with self.acquire() as conn:
            # Get current metadata
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            metadata = row['metadata'] if row and row['metadata'] else {}
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # Store coverage data with timestamp
            from datetime import datetime
            metadata['test_coverage'] = {
                'analyzed_at': datetime.now().isoformat(),
                'data': coverage_data
            }

            # Update metadata
            await conn.execute(
                "UPDATE projects SET metadata = $1 WHERE id = $2",
                json.dumps(metadata),
                project_id
            )

    async def get_test_coverage(
        self,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get test coverage analysis results from project metadata.

        Args:
            project_id: Project UUID

        Returns:
            Coverage data with 'analyzed_at' timestamp and 'data', or None if not available
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT metadata FROM projects WHERE id = $1",
                project_id
            )

            if not row or not row['metadata']:
                return None

            metadata = row['metadata']
            # asyncpg returns JSONB as string, parse if needed
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            return metadata.get('test_coverage')

    async def list_projects(
        self,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List all projects with optional filtering.

        Args:
            user_id: Filter by user ID
            status: Filter by project status

        Returns:
            List of project records
        """
        query = "SELECT * FROM projects WHERE 1=1"
        params = []

        if user_id:
            params.append(user_id)
            query += f" AND user_id = ${len(params)}"

        if status:
            params.append(status)
            query += f" AND status = ${len(params)}"

        query += " ORDER BY created_at DESC"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Session Operations
    # =========================================================================

    async def create_session(
        self,
        project_id: UUID,
        session_number: int,
        session_type: str,
        model: str,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Create a new session.

        Args:
            project_id: Project UUID
            session_number: Sequential session number
            session_type: 'initializer', 'coding', or 'review'
            model: Model name
            max_iterations: Optional iteration limit

        Returns:
            Created session record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO sessions
                (project_id, session_number, type, model, max_iterations, status)
                VALUES ($1, $2, $3, $4, $5, 'pending')
                RETURNING *
                """,
                project_id, session_number, session_type, model, max_iterations
            )
            return dict(row)

    async def start_session(self, session_id: UUID) -> None:
        """
        Mark session as started.

        Args:
            session_id: Session UUID
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = 'running', started_at = NOW()
                WHERE id = $1
                """,
                session_id
            )

    async def end_session(
        self,
        session_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        interruption_reason: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark session as ended with outcome.

        Args:
            session_id: Session UUID
            status: 'completed', 'error', or 'interrupted'
            error_message: Error message if applicable
            interruption_reason: Reason for interruption
            metrics: Session metrics dictionary
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET status = $1,
                    ended_at = NOW(),
                    error_message = $2,
                    interruption_reason = $3,
                    metrics = COALESCE($4::jsonb, metrics)
                WHERE id = $5
                """,
                status, error_message, interruption_reason,
                json.dumps(metrics) if metrics else None,
                session_id
            )

    async def update_session_metrics(
        self,
        session_id: UUID,
        metrics: Dict[str, Any]
    ) -> None:
        """
        Update session metrics (merges with existing).

        Args:
            session_id: Session UUID
            metrics: Metrics to update
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE sessions
                SET metrics = metrics || $1::jsonb
                WHERE id = $2
                """,
                json.dumps(metrics), session_id
            )

    async def get_active_session(
        self,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get currently active session for a project.

        Args:
            project_id: Project UUID

        Returns:
            Active session or None
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM sessions
                WHERE project_id = $1 AND status = 'running'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                project_id
            )
            return dict(row) if row else None

    async def get_next_session_number(self, project_id: UUID) -> int:
        """
        Get next session number for a project.

        Args:
            project_id: Project UUID

        Returns:
            Next session number (0-based: 0 for initialization, 1+ for coding)
        """
        async with self.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT COALESCE(MAX(session_number), -1) + 1
                FROM sessions
                WHERE project_id = $1
                """,
                project_id
            )
            return result

    async def get_session_history(
        self,
        project_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get session history for a project.

        Args:
            project_id: Project UUID
            limit: Maximum number of sessions to return

        Returns:
            List of session records
        """
        import json
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM sessions
                WHERE project_id = $1
                ORDER BY session_number DESC
                LIMIT $2
                """,
                project_id, limit
            )
            # Convert rows to dicts and parse JSONB fields
            result = []
            for row in rows:
                session_dict = dict(row)
                # Parse metrics JSONB field (asyncpg returns it as a string)
                if 'metrics' in session_dict and isinstance(session_dict['metrics'], str):
                    try:
                        session_dict['metrics'] = json.loads(session_dict['metrics'])
                    except (json.JSONDecodeError, TypeError):
                        session_dict['metrics'] = {}
                result.append(session_dict)
            return result

    async def cleanup_stale_sessions(self) -> int:
        """
        Clean up stale sessions (sessions marked as 'running' but inactive).

        A session is considered stale if:
        - Status is 'running'
        - started_at is older than threshold (varies by session type)
        - No recent activity (based on updated_at or started_at)

        Thresholds by session type:
        - Initializer: 30 minutes (can take 20+ minutes for large projects)
        - Coding: 10 minutes (typically 5-15 minutes)
        - Review: 5 minutes (fast analysis)

        This handles cases where sessions were interrupted ungracefully:
        - System sleep/hibernation
        - Process killed without cleanup
        - Orchestrator crash

        Returns:
            Number of sessions marked as interrupted
        """
        async with self.acquire() as conn:
            # Update stale sessions to 'interrupted' status
            # Use different thresholds based on session type
            result = await conn.execute(
                """
                UPDATE sessions
                SET status = 'interrupted',
                    ended_at = COALESCE(ended_at, NOW()),
                    interruption_reason = 'Marked as stale (ungraceful shutdown detected)'
                WHERE status = 'running'
                  AND ended_at IS NULL
                  AND (
                    (type = 'initializer' AND started_at < NOW() - INTERVAL '30 minutes')
                    OR (type = 'coding' AND started_at < NOW() - INTERVAL '10 minutes')
                    OR (type = 'review' AND started_at < NOW() - INTERVAL '5 minutes')
                    OR (type IS NULL AND started_at < NOW() - INTERVAL '10 minutes')  -- Default
                  )
                """
            )

            # Extract number of updated rows from result
            # asyncpg returns "UPDATE N" where N is the count
            count = int(result.split()[-1]) if result else 0

            if count > 0:
                logger.info(f"Cleaned up {count} stale session(s)")

            return count

    # =========================================================================
    # Epic Operations
    # =========================================================================

    async def create_epic(
        self,
        project_id: UUID,
        name: str,
        description: Optional[str] = None,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Create a new epic.

        Args:
            project_id: Project UUID
            name: Epic name
            description: Epic description
            priority: Epic priority (lower = higher priority)

        Returns:
            Created epic record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO epics (project_id, name, description, priority)
                VALUES ($1, $2, $3, $4)
                RETURNING *
                """,
                project_id, name, description, priority
            )
            return dict(row)

    async def list_epics(
        self,
        project_id: UUID,
        only_pending: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List epics for a project.

        Args:
            project_id: Project UUID
            only_pending: Only return non-completed epics

        Returns:
            List of epic records
        """
        query = "SELECT * FROM epics WHERE project_id = $1"
        if only_pending:
            query += " AND status != 'completed'"
        query += " ORDER BY priority, id"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, project_id)
            return [dict(row) for row in rows]

    async def get_epics_needing_expansion(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get epics that have no tasks yet.

        Args:
            project_id: Project UUID

        Returns:
            List of epics needing expansion
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT e.*
                FROM epics e
                LEFT JOIN tasks t ON e.id = t.epic_id
                WHERE e.project_id = $1
                GROUP BY e.id
                HAVING COUNT(t.id) = 0
                ORDER BY e.priority
                """,
                project_id
            )
            return [dict(row) for row in rows]

    # =========================================================================
    # Task Operations
    # =========================================================================

    async def create_task(
        self,
        epic_id: int,
        project_id: UUID,
        description: str,
        action: Optional[str] = None,
        priority: int = 0
    ) -> Dict[str, Any]:
        """
        Create a new task.

        Args:
            epic_id: Epic ID
            project_id: Project UUID
            description: Task description
            action: Implementation details
            priority: Task priority

        Returns:
            Created task record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tasks (epic_id, project_id, description, action, priority)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                epic_id, project_id, description, action, priority
            )
            return dict(row)

    async def get_next_task(self, project_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Get next task to work on for a project.

        Args:
            project_id: Project UUID

        Returns:
            Next task with epic info and tests, or None
        """
        async with self.acquire() as conn:
            # Get the next task
            task_row = await conn.fetchrow(
                """
                SELECT
                    t.*,
                    e.name as epic_name,
                    e.description as epic_description
                FROM tasks t
                JOIN epics e ON t.epic_id = e.id
                WHERE t.project_id = $1
                    AND t.done = false
                    AND e.status != 'completed'
                ORDER BY e.priority, t.priority, t.id
                LIMIT 1
                """,
                project_id
            )

            if not task_row:
                return None

            task = dict(task_row)

            # Get tests for this task
            test_rows = await conn.fetch(
                """
                SELECT * FROM tests
                WHERE task_id = $1
                ORDER BY id
                """,
                task['id']
            )

            task['tests'] = [dict(row) for row in test_rows]

            return task

    async def update_task_status(
        self,
        task_id: int,
        done: bool,
        session_id: Optional[UUID] = None,
        session_notes: Optional[str] = None
    ) -> None:
        """
        Update task completion status.

        Args:
            task_id: Task ID
            done: Whether task is complete
            session_id: Session that completed the task
            session_notes: Notes from session
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET done = $1,
                    completed_at = CASE WHEN $1 THEN NOW() ELSE NULL END,
                    session_id = COALESCE($2, session_id),
                    session_notes = COALESCE($3, session_notes)
                WHERE id = $4
                """,
                done, session_id, session_notes, task_id
            )

    async def list_tasks(
        self,
        project_id: UUID,
        epic_id: Optional[int] = None,
        only_pending: bool = False,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List tasks with optional filtering.

        Args:
            project_id: Project UUID
            epic_id: Filter by epic
            only_pending: Only incomplete tasks
            limit: Maximum tasks to return

        Returns:
            List of task records
        """
        query = """
            SELECT t.*, e.name as epic_name
            FROM tasks t
            JOIN epics e ON t.epic_id = e.id
            WHERE t.project_id = $1
        """
        params = [project_id]

        if epic_id:
            params.append(epic_id)
            query += f" AND t.epic_id = ${len(params)}"

        if only_pending:
            query += " AND t.done = false"

        query += " ORDER BY e.priority, t.priority, t.id"

        if limit:
            params.append(limit)
            query += f" LIMIT ${len(params)}"

        async with self.acquire() as conn:
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]

    # =========================================================================
    # Test Operations
    # =========================================================================

    async def create_test(
        self,
        task_id: int,
        project_id: UUID,
        category: str,
        description: str,
        steps: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create a new test for a task.

        Args:
            task_id: Task ID
            project_id: Project UUID
            category: Test category
            description: Test description
            steps: List of test steps

        Returns:
            Created test record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO tests (task_id, project_id, category, description, steps)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *
                """,
                task_id, project_id, category, description,
                json.dumps(steps) if steps else '[]'
            )
            return dict(row)

    async def update_test_result(
        self,
        test_id: int,
        passes: bool,
        session_id: Optional[UUID] = None,
        result: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update test result.

        Args:
            test_id: Test ID
            passes: Whether test passed
            session_id: Session that ran the test
            result: Test result details
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                UPDATE tests
                SET passes = $1,
                    verified_at = CASE WHEN $1 THEN NOW() ELSE NULL END,
                    session_id = COALESCE($2, session_id),
                    result = COALESCE($3::jsonb, result)
                WHERE id = $4
                """,
                passes, session_id,
                json.dumps(result) if result else None,
                test_id
            )

    # =========================================================================
    # Progress and Statistics
    # =========================================================================

    async def get_progress(self, project_id: UUID) -> Dict[str, Any]:
        """
        Get overall project progress statistics.

        Args:
            project_id: Project UUID

        Returns:
            Progress statistics dictionary
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_progress
                WHERE project_id = $1
                """,
                project_id
            )

            if row:
                return dict(row)
            else:
                # Return empty stats if no data
                return {
                    "project_id": project_id,
                    "total_epics": 0,
                    "completed_epics": 0,
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "total_tests": 0,
                    "passing_tests": 0,
                    "task_completion_pct": 0.0,
                    "test_pass_pct": 0.0
                }

    async def get_epic_progress(
        self,
        project_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Get progress for each epic.

        Args:
            project_id: Project UUID

        Returns:
            List of epic progress records
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM v_epic_progress
                WHERE project_id = $1
                ORDER BY epic_id
                """,
                project_id
            )
            return [dict(row) for row in rows]

    async def get_task_with_tests(
        self,
        task_id: int,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get task with all associated tests and epic context.

        Args:
            task_id: Task ID
            project_id: Project UUID

        Returns:
            Task dict with 'tests' array and 'epic_name' field, or None if not found
        """
        async with self.acquire() as conn:
            # Get task with epic name
            task_row = await conn.fetchrow(
                """
                SELECT t.*, e.name as epic_name, e.description as epic_description
                FROM tasks t
                JOIN epics e ON t.epic_id = e.id
                WHERE t.id = $1 AND t.project_id = $2
                """,
                task_id, project_id
            )

            if not task_row:
                return None

            task = dict(task_row)

            # Get tests for this task
            tests = await conn.fetch(
                """
                SELECT *
                FROM tests
                WHERE task_id = $1
                ORDER BY category, id
                """,
                task_id
            )
            task['tests'] = [dict(test) for test in tests]

            return task

    async def get_epic_with_tasks(
        self,
        epic_id: int,
        project_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """
        Get epic with all tasks and their test counts.

        Args:
            epic_id: Epic ID
            project_id: Project UUID

        Returns:
            Epic dict with 'tasks' array (including test_count per task), or None if not found
        """
        async with self.acquire() as conn:
            # Get epic
            epic_row = await conn.fetchrow(
                """
                SELECT *
                FROM epics
                WHERE id = $1 AND project_id = $2
                """,
                epic_id, project_id
            )

            if not epic_row:
                return None

            epic = dict(epic_row)

            # Get tasks with test counts
            tasks = await conn.fetch(
                """
                SELECT
                    t.*,
                    COUNT(ts.id) as test_count,
                    SUM(CASE WHEN ts.passes = true THEN 1 ELSE 0 END) as passing_test_count
                FROM tasks t
                LEFT JOIN tests ts ON t.id = ts.task_id
                WHERE t.epic_id = $1
                GROUP BY t.id
                ORDER BY t.priority, t.id
                """,
                epic_id
            )
            epic['tasks'] = [dict(task) for task in tasks]

            return epic

    # =========================================================================
    # Review Operations
    # =========================================================================

    async def create_review(
        self,
        project_id: UUID,
        session_id: UUID,
        review_type: str,
        metrics: Dict[str, Any],
        issues: Optional[List[Dict]] = None,
        reviewed_by: str = "automated"
    ) -> Dict[str, Any]:
        """
        Create a review record.

        Args:
            project_id: Project UUID
            session_id: Session UUID
            review_type: 'quick', 'full', or 'final'
            metrics: Review metrics dictionary
            issues: List of issues found
            reviewed_by: Who performed the review

        Returns:
            Created review record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO reviews
                (project_id, session_id, type, metrics, issues, reviewed_by)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                project_id, session_id, review_type,
                json.dumps(metrics),
                json.dumps(issues) if issues else '[]',
                reviewed_by
            )
            return dict(row)

    # =========================================================================
    # GitHub Operations
    # =========================================================================

    async def record_github_commit(
        self,
        project_id: UUID,
        commit_sha: str,
        branch: str,
        message: str,
        task_ids: Optional[List[int]] = None,
        session_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Record a GitHub commit.

        Args:
            project_id: Project UUID
            commit_sha: Git commit SHA
            branch: Branch name
            message: Commit message
            task_ids: List of related task IDs
            session_id: Session that created the commit

        Returns:
            Created commit record
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO github_commits
                (project_id, commit_sha, branch, message, task_ids, session_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (project_id, commit_sha) DO UPDATE
                SET message = EXCLUDED.message,
                    task_ids = EXCLUDED.task_ids
                RETURNING *
                """,
                project_id, commit_sha, branch, message,
                task_ids or [], session_id
            )
            return dict(row)

    # =========================================================================
    # Preferences Operations
    # =========================================================================

    async def get_project_preferences(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get project preferences.

        Args:
            project_id: Project UUID

        Returns:
            Preferences dictionary
        """
        async with self.acquire() as conn:
            result = await conn.fetchval(
                """
                SELECT preferences FROM project_preferences
                WHERE project_id = $1
                """,
                project_id
            )

            if result:
                # Parse JSON if it's a string
                if isinstance(result, str):
                    return json.loads(result)
                return result
            else:
                # Return defaults if not set
                return {
                    "preferred_model": None,
                    "preferred_coding_model": None,
                    "preferred_review_model": None,
                    "max_iterations": None,
                    "auto_continue": True,
                    "review_frequency": 5,
                    "auto_review": False,
                    "git_auto_commit": True,
                    "browser_verification_required": True
                }

    async def update_project_preferences(
        self,
        project_id: UUID,
        preferences: Dict[str, Any]
    ) -> None:
        """
        Update project preferences (merges with existing).

        Args:
            project_id: Project UUID
            preferences: Preferences to update
        """
        async with self.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO project_preferences (project_id, preferences)
                VALUES ($1, $2)
                ON CONFLICT (project_id) DO UPDATE
                SET preferences = project_preferences.preferences || $2::jsonb,
                    updated_at = NOW()
                """,
                project_id, json.dumps(preferences)
            )
    # =========================================================================
    # Session Quality Checks (Phase 1 Review System Integration)
    # =========================================================================

    async def store_quality_check(
        self,
        session_id: UUID,
        check_type: str,
        metrics: Dict[str, Any],
        critical_issues: List[str],
        warnings: List[str],
        overall_rating: Optional[int] = None,
        check_version: str = "1.0"
    ) -> UUID:
        """
        Store quality check results for a session.

        Args:
            session_id: Session UUID
            check_type: Type of check ('quick', 'deep', 'final')
            metrics: Full metrics dict from review_metrics.analyze_session_logs()
            critical_issues: List of critical issue strings
            warnings: List of warning strings
            overall_rating: Optional 1-10 quality score
            check_version: Version of quality check logic

        Returns:
            UUID of created quality check record
        """
        async with self.acquire() as conn:
            # Extract key metrics for indexed columns
            playwright_count = metrics.get('playwright_count', 0)
            playwright_screenshot_count = metrics.get('playwright_screenshot_count', 0)
            total_tool_uses = metrics.get('total_tool_uses', 0)
            error_count = metrics.get('error_count', 0)
            error_rate = metrics.get('error_rate', 0.0)

            check_id = await conn.fetchval(
                """
                INSERT INTO session_quality_checks (
                    session_id,
                    check_type,
                    check_version,
                    overall_rating,
                    playwright_count,
                    playwright_screenshot_count,
                    total_tool_uses,
                    error_count,
                    error_rate,
                    critical_issues,
                    warnings,
                    metrics
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                RETURNING id
                """,
                session_id, check_type, check_version, overall_rating,
                playwright_count, playwright_screenshot_count, total_tool_uses,
                error_count, error_rate,
                json.dumps(critical_issues), json.dumps(warnings), json.dumps(metrics)
            )
            return check_id

    async def store_deep_review(
        self,
        session_id: UUID,
        metrics: Dict[str, Any],
        critical_issues: List[str],
        warnings: List[str],
        overall_rating: int,
        review_text: str,
        prompt_improvements: List[str],
        check_version: str = "2.0"
    ) -> UUID:
        """
        Store deep review results for a session (Phase 2 Review System).

        This extends store_quality_check with Claude-powered review analysis.

        Args:
            session_id: Session UUID
            metrics: Full metrics dict from review_metrics.analyze_session_logs()
            critical_issues: List of critical issue strings
            warnings: List of warning strings
            overall_rating: 1-10 quality score
            review_text: Full review report (markdown)
            prompt_improvements: List of prompt improvement recommendations
            check_version: Version of review logic (default: "2.0" for Phase 2)

        Returns:
            UUID of created quality check record
        """
        async with self.acquire() as conn:
            # Extract key metrics for indexed columns
            playwright_count = metrics.get('playwright_count', 0)
            playwright_screenshot_count = metrics.get('playwright_screenshot_count', 0)
            total_tool_uses = metrics.get('total_tool_uses', 0)
            error_count = metrics.get('error_count', 0)
            error_rate = metrics.get('error_rate', 0.0)

            check_id = await conn.fetchval(
                """
                INSERT INTO session_quality_checks (
                    session_id,
                    check_type,
                    check_version,
                    overall_rating,
                    playwright_count,
                    playwright_screenshot_count,
                    total_tool_uses,
                    error_count,
                    error_rate,
                    critical_issues,
                    warnings,
                    metrics,
                    review_text,
                    prompt_improvements
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id
                """,
                session_id, 'deep', check_version, overall_rating,
                playwright_count, playwright_screenshot_count, total_tool_uses,
                error_count, error_rate,
                json.dumps(critical_issues), json.dumps(warnings), json.dumps(metrics),
                review_text, json.dumps(prompt_improvements)
            )
            return check_id

    async def get_session_quality(
        self,
        session_id: UUID,
        check_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get quality check results for a session.

        Args:
            session_id: Session UUID
            check_type: Optional filter by check type ('quick', 'deep', 'final')

        Returns:
            Quality check dict or None if not found
        """
        async with self.acquire() as conn:
            query = """
                SELECT
                    id,
                    session_id,
                    check_type,
                    check_version,
                    created_at,
                    overall_rating,
                    playwright_count,
                    playwright_screenshot_count,
                    total_tool_uses,
                    error_count,
                    error_rate,
                    critical_issues,
                    warnings,
                    metrics,
                    prompt_improvements,
                    review_text,
                    review_summary
                FROM session_quality_checks
                WHERE session_id = $1
            """

            params = [session_id]

            if check_type:
                query += " AND check_type = $2"
                params.append(check_type)

            query += " ORDER BY created_at DESC LIMIT 1"

            row = await conn.fetchrow(query, *params)
            if not row:
                return None

            # Convert to dict and parse JSONB fields
            result = dict(row)

            # Parse JSONB fields (asyncpg may return them as strings)
            jsonb_fields = ['critical_issues', 'warnings', 'metrics', 'prompt_improvements', 'review_summary']
            for field in jsonb_fields:
                if field in result and isinstance(result[field], str):
                    try:
                        result[field] = json.loads(result[field])
                    except (json.JSONDecodeError, TypeError):
                        result[field] = [] if field in ['critical_issues', 'warnings', 'prompt_improvements'] else {}

            return result

    async def get_project_quality_summary(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get overall quality summary for a project.

        Returns aggregate statistics across all sessions.

        Args:
            project_id: Project UUID

        Returns:
            Dict with quality summary stats
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_project_quality WHERE project_id = $1
                """,
                project_id
            )
            return dict(row) if row else {
                'project_id': str(project_id),
                'total_sessions': 0,
                'checked_sessions': 0,
                'avg_quality_rating': None,
                'sessions_without_browser_verification': 0,
                'avg_error_rate_percent': None,
                'avg_playwright_calls_per_session': None
            }

    async def get_sessions_with_quality_issues(
        self,
        project_id: Optional[UUID] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent sessions with quality issues.

        Args:
            project_id: Optional filter by project
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts with quality issues
        """
        async with self.acquire() as conn:
            query = "SELECT * FROM v_recent_quality_issues"

            if project_id:
                query += " WHERE project_id = $1"
                query += f" LIMIT {limit}"
                rows = await conn.fetch(query, project_id)
            else:
                query += f" LIMIT {limit}"
                rows = await conn.fetch(query)

            return [dict(row) for row in rows]

    async def get_browser_verification_compliance(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """
        Get browser verification compliance stats for a project.

        Returns breakdown of sessions by Playwright usage level.

        Args:
            project_id: Project UUID

        Returns:
            Dict with compliance statistics
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM v_browser_verification_compliance
                WHERE project_id = $1
                """,
                project_id
            )
            return dict(row) if row else {
                'project_id': str(project_id),
                'total_sessions': 0,
                'sessions_with_verification': 0,
                'sessions_excellent_verification': 0,
                'sessions_good_verification': 0,
                'sessions_minimal_verification': 0,
                'sessions_no_verification': 0,
                'verification_rate_percent': 0.0
            }

    # =========================================================================
    # Prompt Improvement Operations
    # =========================================================================

    async def create_prompt_analysis(
        self,
        project_ids: List[UUID],
        sandbox_type: str,
        triggered_by: str = "manual",
        user_id: Optional[UUID] = None
    ) -> UUID:
        """
        Create a new prompt improvement analysis record.

        Args:
            project_ids: List of project UUIDs to analyze
            sandbox_type: 'docker' or 'local'
            triggered_by: How analysis was triggered
            user_id: Optional user ID

        Returns:
            Analysis UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO prompt_improvement_analyses (
                    projects_analyzed,
                    sandbox_type,
                    triggered_by,
                    user_id,
                    status
                )
                VALUES ($1, $2, $3, $4, 'pending')
                RETURNING id
                """,
                project_ids, sandbox_type, triggered_by, user_id
            )
            return row['id']

    async def get_prompt_analysis(self, analysis_id: UUID) -> Optional[Dict[str, Any]]:
        """Get prompt analysis by ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prompt_improvement_analyses WHERE id = $1",
                analysis_id
            )
            return dict(row) if row else None

    async def list_prompt_analyses(
        self,
        limit: int = 20,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List prompt improvement analyses.

        Args:
            limit: Maximum number to return
            status: Optional filter by status

        Returns:
            List of analysis records
        """
        async with self.acquire() as conn:
            if status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_recent_analyses
                    WHERE status = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                    """,
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_recent_analyses
                    ORDER BY created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            return [dict(row) for row in rows]

    async def update_prompt_analysis_status(
        self,
        analysis_id: UUID,
        status: str,
        **kwargs
    ):
        """
        Update analysis status and optional fields.

        Args:
            analysis_id: Analysis UUID
            status: New status
            **kwargs: Additional fields to update
        """
        fields = ["status = $2"]
        params = [analysis_id, status]
        idx = 3

        for key, value in kwargs.items():
            fields.append(f"{key} = ${idx}")
            params.append(value)
            idx += 1

        query = f"""
            UPDATE prompt_improvement_analyses
            SET {', '.join(fields)}
            WHERE id = $1
        """

        async with self.acquire() as conn:
            await conn.execute(query, *params)

    async def delete_prompt_analysis(self, analysis_id: UUID) -> bool:
        """
        Delete a prompt improvement analysis.

        Cascades to delete all proposals associated with this analysis.

        Args:
            analysis_id: UUID of the analysis to delete

        Returns:
            True if deleted successfully
        """
        async with self.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM prompt_improvement_analyses
                WHERE id = $1
                """,
                analysis_id
            )
            # Return True if at least one row was deleted
            return result.split()[-1] != '0'

    async def create_prompt_proposal(
        self,
        analysis_id: UUID,
        prompt_file: str,
        section_name: str,
        change_type: str,
        original_text: str,
        proposed_text: str,
        rationale: str,
        evidence: List[Dict[str, Any]],
        confidence_level: int
    ) -> UUID:
        """
        Create a prompt change proposal.

        Args:
            analysis_id: Parent analysis UUID
            prompt_file: Name of prompt file
            section_name: Section to modify
            change_type: Type of change
            original_text: Current text
            proposed_text: Proposed new text
            rationale: Why this change is needed
            evidence: Supporting evidence
            confidence_level: 1-10 confidence score

        Returns:
            Proposal UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO prompt_proposals (
                    analysis_id,
                    prompt_file,
                    section_name,
                    change_type,
                    original_text,
                    proposed_text,
                    rationale,
                    evidence,
                    confidence_level
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                analysis_id,
                prompt_file,
                section_name,
                change_type,
                original_text,
                proposed_text,
                rationale,
                json.dumps(evidence),
                confidence_level
            )
            return row['id']

    async def get_prompt_proposal(self, proposal_id: UUID) -> Optional[Dict[str, Any]]:
        """Get prompt proposal by ID."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM prompt_proposals WHERE id = $1",
                proposal_id
            )
            return dict(row) if row else None

    async def list_prompt_proposals(
        self,
        analysis_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List prompt proposals.

        Args:
            analysis_id: Optional filter by analysis
            status: Optional filter by status
            limit: Maximum number to return

        Returns:
            List of proposal records
        """
        async with self.acquire() as conn:
            if analysis_id:
                if status:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM prompt_proposals
                        WHERE analysis_id = $1 AND status = $2
                        ORDER BY confidence_level DESC, created_at DESC
                        LIMIT $3
                        """,
                        analysis_id, status, limit
                    )
                else:
                    rows = await conn.fetch(
                        """
                        SELECT * FROM prompt_proposals
                        WHERE analysis_id = $1
                        ORDER BY confidence_level DESC, created_at DESC
                        LIMIT $2
                        """,
                        analysis_id, limit
                    )
            elif status:
                rows = await conn.fetch(
                    """
                    SELECT * FROM v_pending_proposals
                    WHERE status = $1
                    LIMIT $2
                    """,
                    status, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM prompt_proposals
                    ORDER BY confidence_level DESC, created_at DESC
                    LIMIT $1
                    """,
                    limit
                )
            return [dict(row) for row in rows]

    async def update_prompt_proposal_status(
        self,
        proposal_id: UUID,
        status: str,
        applied_by: Optional[str] = None,
        applied_to_version: Optional[str] = None
    ):
        """
        Update proposal status.

        Args:
            proposal_id: Proposal UUID
            status: New status ('accepted', 'rejected', 'implemented')
            applied_by: Who applied the change
            applied_to_version: Git commit hash
        """
        async with self.acquire() as conn:
            if status == 'implemented':
                await conn.execute(
                    """
                    UPDATE prompt_proposals
                    SET
                        status = $2,
                        applied_at = NOW(),
                        applied_by = $3,
                        applied_to_version = $4
                    WHERE id = $1
                    """,
                    proposal_id, status, applied_by, applied_to_version
                )
            else:
                await conn.execute(
                    """
                    UPDATE prompt_proposals
                    SET status = $2
                    WHERE id = $1
                    """,
                    proposal_id, status
                )

    async def create_prompt_version(
        self,
        prompt_file: str,
        version_name: str,
        content: str,
        git_commit_hash: Optional[str] = None,
        parent_version_id: Optional[UUID] = None,
        changes_summary: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> UUID:
        """
        Create a new prompt version record.

        Args:
            prompt_file: Name of prompt file
            version_name: Version identifier
            content: Full prompt content
            git_commit_hash: Optional git commit
            parent_version_id: Previous version UUID
            changes_summary: Description of changes
            created_by: Who created this version

        Returns:
            Version UUID
        """
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO prompt_versions (
                    prompt_file,
                    version_name,
                    content,
                    git_commit_hash,
                    parent_version_id,
                    changes_summary,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
                """,
                prompt_file,
                version_name,
                content,
                git_commit_hash,
                parent_version_id,
                changes_summary,
                created_by
            )
            return row['id']

    async def get_prompt_versions(
        self,
        prompt_file: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a prompt file.

        Args:
            prompt_file: Name of prompt file
            limit: Maximum number to return

        Returns:
            List of version records
        """
        async with self.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM v_version_performance
                WHERE prompt_file = $1
                ORDER BY created_at DESC
                LIMIT $2
                """,
                prompt_file, limit
            )
            return [dict(row) for row in rows]

    async def get_active_prompt_version(
        self,
        prompt_file: str
    ) -> Optional[Dict[str, Any]]:
        """Get the currently active version for a prompt file."""
        async with self.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM prompt_versions
                WHERE prompt_file = $1 AND is_active = true
                ORDER BY created_at DESC
                LIMIT 1
                """,
                prompt_file
            )
            return dict(row) if row else None

    async def set_active_prompt_version(
        self,
        version_id: UUID,
        prompt_file: str
    ):
        """
        Set a version as the active one for a prompt file.

        Deactivates all other versions of the same file.
        """
        async with self.transaction() as conn:
            # Deactivate all versions of this file
            await conn.execute(
                """
                UPDATE prompt_versions
                SET is_active = false
                WHERE prompt_file = $1
                """,
                prompt_file
            )

            # Activate the specified version
            await conn.execute(
                """
                UPDATE prompt_versions
                SET is_active = true
                WHERE id = $1
                """,
                version_id
            )


# =============================================================================
# Factory function for compatibility
# =============================================================================

async def get_database(connection_url: str) -> TaskDatabase:
    """
    Factory function to create and connect to database.

    Args:
        connection_url: PostgreSQL connection string

    Returns:
        Connected TaskDatabase instance
    """
    db = TaskDatabase(connection_url)
    await db.connect()
    return db