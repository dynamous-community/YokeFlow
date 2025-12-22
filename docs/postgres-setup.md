# PostgreSQL Setup Guide

This guide walks through setting up PostgreSQL for the autonomous coding agent platform.

## Quick Start (Local Development with Docker)

### 1. Start PostgreSQL with Docker Compose

```bash
# Start PostgreSQL container
docker-compose up -d

# Verify it's running
docker-compose ps

# Check logs if needed
docker-compose logs postgres
```

The database will be available at:
- **Host**: localhost
- **Port**: 5432
- **Database**: autonomous_coding
- **Username**: agent
- **Password**: agent_dev_password

### 2. Initialize the Database Schema

```bash
# Install Python dependencies first
pip install -r requirements.txt

# Initialize database with schema
python scripts/init_database.py --docker

# Or if you want to verify existing schema
python scripts/init_database.py --docker --verify-only
```

### 3. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# The default DATABASE_URL is already configured for Docker
```

### 4. Optional: Access pgAdmin

If you want a GUI to manage the database:

```bash
# Start pgAdmin (runs on http://localhost:5050)
docker-compose --profile tools up -d

# Login credentials:
# Email: admin@autonomous-coding.local
# Password: admin
```

## Production Setup (Digital Ocean)

### 1. Create Managed Database

1. Log into Digital Ocean
2. Create a new PostgreSQL database cluster
3. Note the connection parameters

### 2. Configure Connection

Update your `.env` file:

```bash
DATABASE_URL=postgresql://username:password@host:port/database?sslmode=require
```

### 3. Initialize Schema

```bash
# Run initialization with production URL
python scripts/init_database.py --url "$DATABASE_URL"
```

## Database Management

### Connect with psql

```bash
# Local Docker
docker exec -it autonomous_coding_postgres psql -U agent -d autonomous_coding

# Production
psql "$DATABASE_URL"
```

### Common SQL Commands

```sql
-- View all tables
\dt

-- View table structure
\d projects

-- View custom types
\dT

-- View all views
\dv

-- Check project progress
SELECT * FROM v_progress;

-- Get active sessions
SELECT * FROM v_active_sessions;

-- Exit psql
\q
```

### Backup and Restore

```bash
# Backup
docker exec autonomous_coding_postgres pg_dump -U agent autonomous_coding > backup.sql

# Restore
docker exec -i autonomous_coding_postgres psql -U agent autonomous_coding < backup.sql
```

## Troubleshooting

### Port 5432 Already in Use

If you have another PostgreSQL running:

```bash
# Change port in docker-compose.yml
ports:
  - "5433:5432"  # Use port 5433 instead

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://agent:agent_dev_password@localhost:5433/autonomous_coding
```

### Connection Refused

```bash
# Check if container is running
docker-compose ps

# Check logs
docker-compose logs postgres

# Restart container
docker-compose restart postgres
```

### Permission Denied

```bash
# Ensure schema files have correct permissions
chmod +r schema/postgresql/*.sql

# Rebuild container if needed
docker-compose down
docker-compose up -d
```

## Database Schema Overview

The PostgreSQL schema includes:

### Main Tables
- **projects**: Central project metadata
- **sessions**: Agent session tracking
- **epics**: High-level feature areas
- **tasks**: Implementation steps
- **tests**: Verification steps
- **reviews**: Quality tracking
- **github_commits**: Git integration
- **project_preferences**: Per-project settings

### Custom Types (ENUMs)
- `project_status`: active, paused, completed, archived
- `session_type`: initializer, coding, review
- `session_status`: pending, running, completed, error, interrupted
- `deployment_status`: local, sandbox, production
- `task_status`: pending, in_progress, completed, blocked

### Key Features
- UUID primary keys for distributed systems
- JSONB fields for flexible metadata
- PostgreSQL arrays for task lists
- Generated columns for computed values
- GIN indexes for JSON performance
- Triggers for auto-updating timestamps

## Migration Status

✅ **Migration Complete**

All phases have been completed:
1. ✅ PostgreSQL configuration and connection layer
2. ✅ Orchestrator migration with async/await
3. ✅ REST API migration with all endpoints
4. ✅ Project structure changes (prompts, MCP server, CLI)
5. ✅ Integration testing and validation
6. ✅ Code consolidation (removed all `_pg` duplicate files)

The codebase is now **PostgreSQL-only** with no SQLite dependencies remaining.

## Current Architecture

- `database.py` - PostgreSQL database layer (asyncpg)
- `database_connection.py` - Connection pooling and lifecycle
- `orchestrator.py` - Async session management
- `api/main.py` - FastAPI with PostgreSQL backend
- UUID-based project identification
- JSONB for flexible metadata
- Connection pooling (10-20 connections)

## Resources

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Digital Ocean Managed Databases](https://www.digitalocean.com/products/managed-databases)