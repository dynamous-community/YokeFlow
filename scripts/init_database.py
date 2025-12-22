#!/usr/bin/env python3
"""
Database Initialization Script
==============================

Initialize PostgreSQL database for the autonomous coding agent.
Creates database, runs schema, and sets up initial configuration.

Usage:
    python scripts/init_database.py [--docker | --url DATABASE_URL]
"""

import asyncio
import asyncpg
import os
import sys
from pathlib import Path
import argparse
import logging

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from database import TaskDatabase

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def check_database_exists(connection_url: str) -> bool:
    """Check if database exists."""
    # Parse connection URL to get database name
    import urllib.parse
    parsed = urllib.parse.urlparse(connection_url)
    db_name = parsed.path.lstrip('/')

    # Connect to postgres database to check if our DB exists
    admin_url = connection_url.replace(f"/{db_name}", "/postgres")

    try:
        conn = await asyncpg.connect(admin_url)
        result = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name
        )
        await conn.close()
        return result is not None
    except Exception as e:
        logger.error(f"Error checking database: {e}")
        return False


async def create_database_if_not_exists(connection_url: str) -> None:
    """Create database if it doesn't exist."""
    import urllib.parse
    parsed = urllib.parse.urlparse(connection_url)
    db_name = parsed.path.lstrip('/')

    if await check_database_exists(connection_url):
        logger.info(f"Database '{db_name}' already exists")
        return

    # Connect to postgres database to create our DB
    admin_url = connection_url.replace(f"/{db_name}", "/postgres")

    try:
        conn = await asyncpg.connect(admin_url)
        await conn.execute(f'CREATE DATABASE "{db_name}"')
        await conn.close()
        logger.info(f"Created database '{db_name}'")
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        raise


async def run_schema(connection_url: str, schema_file: Path) -> None:
    """Run schema SQL file."""
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    logger.info(f"Running schema from {schema_file}")

    # Read schema
    schema_sql = schema_file.read_text()

    # Connect and run schema
    conn = await asyncpg.connect(connection_url)

    try:
        # Split by semicolons but be careful with functions/triggers
        statements = []
        current = []
        in_function = False

        for line in schema_sql.split('\n'):
            if '$$' in line:
                in_function = not in_function
            current.append(line)

            if ';' in line and not in_function:
                statements.append('\n'.join(current))
                current = []

        if current:
            statements.append('\n'.join(current))

        # Execute each statement
        for i, statement in enumerate(statements, 1):
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    await conn.execute(statement)
                    logger.debug(f"Executed statement {i}/{len(statements)}")
                except (asyncpg.exceptions.DuplicateObjectError,
                        asyncpg.exceptions.DuplicateTableError,
                        asyncpg.exceptions.DuplicateDatabaseError) as e:
                    # Ignore if object already exists (types, tables, indexes, etc)
                    logger.debug(f"Object already exists (statement {i}): {str(e)[:100]}")
                except Exception as e:
                    # Check if it's an index/constraint that already exists
                    error_msg = str(e).lower()
                    if any(phrase in error_msg for phrase in [
                        'already exists',
                        'duplicate key',
                        'already been defined'
                    ]):
                        logger.debug(f"Skipping existing object (statement {i}): {str(e)[:100]}")
                    else:
                        logger.error(f"Error in statement {i}: {e}")
                        logger.error(f"Statement: {statement[:200]}...")
                        raise

        logger.info("Schema executed successfully")

    finally:
        await conn.close()


async def verify_schema(connection_url: str) -> None:
    """Verify that schema was created correctly."""
    conn = await asyncpg.connect(connection_url)

    try:
        # Check tables
        tables = await conn.fetch("""
            SELECT tablename FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
        """)

        expected_tables = [
            'epics', 'github_commits', 'project_preferences',
            'projects', 'reviews', 'sessions', 'tasks', 'tests',
            'session_quality_checks', 'prompt_improvement_analyses',
            'prompt_proposals', 'prompt_versions'
        ]

        actual_tables = [row['tablename'] for row in tables]

        logger.info(f"Found {len(actual_tables)} tables: {', '.join(actual_tables)}")

        missing = set(expected_tables) - set(actual_tables)
        if missing:
            logger.warning(f"Missing tables: {', '.join(missing)}")

        # Check views
        views = await conn.fetch("""
            SELECT viewname FROM pg_views
            WHERE schemaname = 'public'
            ORDER BY viewname
        """)

        view_names = [row['viewname'] for row in views]
        logger.info(f"Found {len(view_names)} views: {', '.join(view_names)}")

        # Check custom types
        types = await conn.fetch("""
            SELECT typname FROM pg_type
            WHERE typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
            AND typtype = 'e'
            ORDER BY typname
        """)

        type_names = [row['typname'] for row in types]
        logger.info(f"Found {len(type_names)} custom types: {', '.join(type_names)}")

    finally:
        await conn.close()


async def drop_database(connection_url: str) -> None:
    """Drop the database (WARNING: destructive!)."""
    import urllib.parse
    parsed = urllib.parse.urlparse(connection_url)
    db_name = parsed.path.lstrip('/')

    # Connect to postgres database to drop our DB
    admin_url = connection_url.replace(f"/{db_name}", "/postgres")

    try:
        conn = await asyncpg.connect(admin_url)
        # Terminate existing connections
        await conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await conn.close()
        logger.info(f"Dropped database '{db_name}'")
    except Exception as e:
        logger.error(f"Error dropping database: {e}")
        raise


async def main():
    parser = argparse.ArgumentParser(description="Initialize PostgreSQL database")
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Use Docker Compose PostgreSQL (localhost:5432)"
    )
    parser.add_argument(
        "--url",
        help="PostgreSQL connection URL"
    )
    parser.add_argument(
        "--schema",
        default="schema/postgresql/schema.sql",
        help="Path to schema file"
    )
    parser.add_argument(
        "--skip-create",
        action="store_true",
        help="Skip database creation (assume it exists)"
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify schema, don't create anything"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop and recreate database (WARNING: destructive!)"
    )

    args = parser.parse_args()

    # Determine connection URL
    if args.docker:
        connection_url = "postgresql://agent:agent_dev_password@localhost:5432/autonomous_coding"
    elif args.url:
        connection_url = args.url
    elif os.getenv("DATABASE_URL"):
        connection_url = os.getenv("DATABASE_URL")
    else:
        logger.error("No database connection specified. Use --docker, --url, or set DATABASE_URL")
        sys.exit(1)

    logger.info(f"Connecting to: {connection_url.replace(':agent_dev_password', ':***')}")

    try:
        if args.verify_only:
            await verify_schema(connection_url)
        else:
            # Drop and recreate if requested
            if args.drop:
                response = input("⚠️  WARNING: This will DROP the database and all data. Continue? (yes/no): ")
                if response.lower() != 'yes':
                    logger.info("Aborted")
                    return
                await drop_database(connection_url)
                await create_database_if_not_exists(connection_url)
            elif not args.skip_create:
                # Create database if needed
                await create_database_if_not_exists(connection_url)

            # Run schema
            schema_file = Path(args.schema)
            await run_schema(connection_url, schema_file)

            # Verify
            await verify_schema(connection_url)

            logger.info("Database initialization complete!")

            # Test connection with our database class
            db = TaskDatabase(connection_url)
            await db.connect()
            logger.info("Successfully connected with TaskDatabase class")
            await db.disconnect()

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())