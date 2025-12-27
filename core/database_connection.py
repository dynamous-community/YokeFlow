"""
Database Connection Management
===============================

Centralized database connection utilities for YokeFlow.
Uses PostgreSQL exclusively for production-ready multi-tenant architecture.

Usage:
    from database_connection import get_db, DatabaseManager

    # Get PostgreSQL database (async)
    db = await get_db()
    await db.connect()

    # Or use context manager (recommended)
    async with DatabaseManager() as db:
        projects = await db.list_projects()
"""

import os
from pathlib import Path
from typing import Optional
import logging

# Load environment variables from .env file in agent root directory
# CRITICAL: Do NOT load from CWD, which might be a generated project directory
from dotenv import load_dotenv

# Get agent root directory (parent of core/ where this file is located)
_agent_root = Path(__file__).parent.parent
_agent_env_file = _agent_root / ".env"

# Load from agent's .env only, not from any project directory
load_dotenv(dotenv_path=_agent_env_file)

logger = logging.getLogger(__name__)

# Global database instance (singleton pattern)
_db_instance: Optional['TaskDatabase'] = None
_db_lock = None  # Will be set to asyncio.Lock() when needed


def get_database_url() -> str:
    """
    Get database connection URL from environment.

    Returns:
        Database connection URL

    Raises:
        ValueError: If DATABASE_URL not set
    """
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL environment variable not set. "
            "Please configure it in your .env file. "
            "Example: DATABASE_URL=postgresql://agent:password@localhost:5432/yokeflow"
        )

    return database_url


def create_database(connection_string: Optional[str] = None):
    """
    Create a PostgreSQL database instance.

    Args:
        connection_string: Database connection string (if None, reads from env)

    Returns:
        TaskDatabase instance connected to PostgreSQL

    Example:
        # Use environment variable
        db = create_database()

        # Use specific connection
        db = create_database("postgresql://localhost/mydb")
    """
    # Get connection string
    if connection_string is None:
        connection_string = get_database_url()

    # Validate it's PostgreSQL
    if not connection_string.startswith(("postgresql://", "postgres://")):
        raise ValueError(
            f"Invalid database URL. Must be PostgreSQL connection string. "
            f"Got: {connection_string[:20]}..."
        )

    # Import and create PostgreSQL database
    from core.database import TaskDatabase
    logger.info("Creating PostgreSQL database connection")
    return TaskDatabase(connection_string)


async def get_db(connection_string: Optional[str] = None):
    """
    Get and connect to PostgreSQL database (singleton pattern).

    This is the recommended way to get a database instance in async contexts.
    Uses a global singleton to avoid creating multiple connection pools.

    Args:
        connection_string: Optional connection string (uses env if not provided)

    Returns:
        Connected TaskDatabase instance (reuses existing pool if available)

    Example:
        db = await get_db()
        progress = await db.get_progress(project_id)
        # Note: Do NOT call disconnect() - pool is shared
    """
    global _db_instance, _db_lock

    # Initialize lock on first use
    if _db_lock is None:
        import asyncio
        _db_lock = asyncio.Lock()

    # Get or create singleton instance
    async with _db_lock:
        if _db_instance is None or _db_instance.pool is None:
            logger.info("Creating new global database connection pool")
            _db_instance = create_database(connection_string)
            await _db_instance.connect()

        return _db_instance


async def close_db():
    """
    Close the global database connection pool.

    This should be called on application shutdown to cleanly close
    the connection pool.

    Example:
        # On FastAPI shutdown
        @app.on_event("shutdown")
        async def shutdown():
            await close_db()
    """
    global _db_instance

    if _db_instance and _db_instance.pool:
        logger.info("Closing global database connection pool")
        await _db_instance.disconnect()
        _db_instance = None


class DatabaseManager:
    """
    Context manager for PostgreSQL database connections.

    Uses a shared global connection pool for efficiency.
    The pool is NOT closed when exiting the context (it's reused).

    Example:
        async with DatabaseManager() as db:
            projects = await db.list_projects()
            progress = await db.get_progress(project_id)
    """

    def __init__(self, connection_string: Optional[str] = None):
        """
        Initialize database manager.

        Args:
            connection_string: Optional PostgreSQL connection string
        """
        self.connection_string = connection_string
        self.db = None

    async def __aenter__(self):
        """Get database instance (reuses global pool)."""
        self.db = await get_db(self.connection_string)
        return self.db

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context (pool remains open for reuse)."""
        # Do NOT disconnect - the pool is shared globally
        pass


def is_postgresql_configured() -> bool:
    """
    Check if PostgreSQL is configured.

    Returns:
        True if DATABASE_URL is set and points to PostgreSQL
    """
    try:
        url = os.getenv("DATABASE_URL", "")
        return url.startswith(("postgresql://", "postgres://"))
    except Exception:
        return False


def get_connection_info() -> dict:
    """
    Get PostgreSQL connection information (for debugging).

    Returns:
        Dict with connection details (passwords redacted)
    """
    try:
        url = get_database_url()

        # Redact password
        if "@" in url and ":" in url:
            parts = url.split("@")
            before_at = parts[0]
            after_at = "@".join(parts[1:])

            if ":" in before_at:
                protocol_user = before_at.rsplit(":", 1)[0]
                safe_url = f"{protocol_user}:****@{after_at}"
            else:
                safe_url = url
        else:
            safe_url = url

        return {
            "type": "postgresql",
            "url": safe_url,
            "configured": True
        }
    except Exception as e:
        return {
            "type": "postgresql",
            "url": None,
            "configured": False,
            "error": str(e)
        }


if __name__ == "__main__":
    # Test PostgreSQL database connection
    import asyncio

    async def test():
        print("PostgreSQL Connection Configuration Test")
        print("=" * 50)

        info = get_connection_info()
        print(f"Database Type: {info['type']}")
        print(f"Connection URL: {info['url']}")
        print(f"Configured: {info['configured']}")

        if info['configured']:
            print("\nAttempting to connect to PostgreSQL...")
            try:
                db = await get_db()
                print("✅ Successfully connected to PostgreSQL!")

                # Test a simple query
                async with db.acquire() as conn:
                    version = await conn.fetchval("SELECT version()")
                    print(f"PostgreSQL version: {version[:50]}...")

                await db.disconnect()
                print("✅ Successfully disconnected")
            except Exception as e:
                print(f"❌ Connection failed: {e}")
        else:
            print(f"\n❌ Error: {info.get('error', 'Unknown error')}")

    asyncio.run(test())
