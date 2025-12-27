# YokeFlow Database Access Patterns

**Last Updated:** December 25, 2025
**Authors:** YokeFlow Development Team

---

## Table of Contents

1. [Overview](#overview)
2. [Module Architecture](#module-architecture)
3. [Pattern Analysis](#pattern-analysis)
4. [When to Use Each Pattern](#when-to-use-each-pattern)
5. [Complexity Decision Tree](#complexity-decision-tree)
6. [Best Practices](#best-practices)
7. [Common Scenarios](#common-scenarios)
8. [Migration Guide](#migration-guide)

---

## Overview

YokeFlow uses PostgreSQL for all persistence, with two primary modules providing database access:

1. **`core/database.py`** - The `TaskDatabase` class with high-level helper methods
2. **`core/database_connection.py`** - Connection management utilities (`get_db()`, `DatabaseManager`)

This document provides clear guidelines on when and how to use each pattern for optimal code organization and maintainability.

### Key Design Principles

- **Async-first**: All database operations use `asyncpg` for high-performance async I/O
- **Connection pooling**: Global singleton pool managed by `get_db()`
- **Abstraction layers**: Helper methods for common operations, raw SQL for complex queries
- **Type safety**: Uses UUID for primary keys, JSONB for flexible metadata

---

## Module Architecture

### `core/database.py` - TaskDatabase Class

**Purpose:** High-level abstraction layer providing helper methods for common database operations.

**Key Features:**
- 100+ helper methods organized by domain (projects, sessions, epics, tasks, tests, reviews, etc.)
- Handles common query patterns (CRUD operations, filtering, sorting)
- Manages JSONB parsing and UUID conversions
- Built-in connection pool management
- Context managers for transactions (`async with db.transaction()`)

**Typical Usage:**
```python
from core.database_connection import DatabaseManager

async with DatabaseManager() as db:
    # Use helper methods
    project = await db.get_project(project_id)
    tasks = await db.list_tasks(project_id, only_pending=True)
    await db.update_task_status(task_id, done=True)
```

### `core/database_connection.py` - Connection Utilities

**Purpose:** Low-level connection management and global pool access.

**Key Components:**

1. **`get_db()` - Global Pool Access**
   ```python
   from core.database_connection import get_db

   db = await get_db()  # Returns singleton TaskDatabase with active pool
   # Use db... (pool remains open after function returns)
   ```

2. **`DatabaseManager` - Context Manager**
   ```python
   from core.database_connection import DatabaseManager

   async with DatabaseManager() as db:
       # Use db for multiple operations
       # Pool remains open after context exits (shared globally)
   ```

3. **`create_database()` - Factory Function**
   ```python
   from core.database_connection import create_database

   db = create_database()  # Create new instance (not recommended - use get_db())
   await db.connect()
   ```

---

## Pattern Analysis

We identified three primary patterns across the codebase:

### Pattern 1: DatabaseManager Context (Recommended)

**Who Uses It:**
- `api/main.py` - All API endpoints
- `core/orchestrator.py` - Session management
- `core/quality_integration.py` - Quality checks
- `scripts/task_status.py` - Utility scripts

**Example:**
```python
async with DatabaseManager() as db:
    project = await db.get_project(project_id)
    await db.update_project_settings(project_id, settings)
```

**Characteristics:**
- ✅ Clean, self-documenting code
- ✅ Automatic pool management
- ✅ Ideal for multi-operation transactions
- ✅ No manual cleanup required
- ⚠️ Pool remains open globally (by design)

**When to Use:**
- API endpoints
- Orchestrator operations
- Scripts that need multiple queries
- Any code that needs clean scoping

### Pattern 2: get_db() Direct Access

**Who Uses It:**
- `api/main.py` - Some isolated queries
- `review/prompt_improvement_analyzer.py` - Complex cross-project analysis

**Example:**
```python
db = await get_db()
# Use db for operations
# No disconnect needed - pool is shared
```

**Characteristics:**
- ✅ Minimal boilerplate
- ✅ Fast for single operations
- ✅ Access to shared pool
- ⚠️ Less explicit lifecycle
- ⚠️ No automatic scoping

**When to Use:**
- Single query operations
- Performance-critical paths
- Helper functions that don't need scoping

### Pattern 3: Raw SQL with db.acquire()

**Who Uses It:**
- `api/main.py` - Complex queries (orphaned sessions, custom aggregations)
- `api/prompt_improvements_routes.py` - Complex joins and filtering
- `review/prompt_improvement_analyzer.py` - Custom aggregations with JSONB queries
- `core/orchestrator.py` - Direct session lookups

**Example:**
```python
async with db.acquire() as conn:
    row = await conn.fetchrow(
        """
        SELECT s.*, p.name as project_name
        FROM sessions s
        JOIN projects p ON s.project_id = p.id
        WHERE s.id = $1 AND s.status = 'running'
        """,
        session_id
    )
    return dict(row) if row else None
```

**Characteristics:**
- ✅ Maximum flexibility
- ✅ Optimal performance for complex queries
- ✅ Full PostgreSQL feature access (CTEs, window functions, etc.)
- ⚠️ More verbose
- ⚠️ Requires JSONB parsing
- ⚠️ Manual result conversion

**When to Use:**
- Complex joins across multiple tables
- Custom aggregations not covered by helpers
- JSONB queries with operators (`||`, `->`, `->>`)
- Performance-critical queries needing optimization
- Queries that don't fit helper method patterns

---

## When to Use Each Pattern

### Decision Matrix

| Scenario | Pattern | Rationale |
|----------|---------|-----------|
| API endpoint with 1-3 simple queries | `DatabaseManager` | Clean scoping, multiple operations |
| API endpoint with complex join | `DatabaseManager` + `db.acquire()` | Context for scope, raw SQL for complexity |
| Orchestrator session management | `DatabaseManager` | Transaction safety, clean lifecycle |
| Utility script | `DatabaseManager` | Explicit resource management |
| Helper function (single query) | `get_db()` | Minimal overhead |
| Cross-project analysis | `get_db()` + `db.acquire()` | Long-running, complex queries |
| Simple CRUD operation | `DatabaseManager` + helper method | Use existing abstraction |
| Custom aggregation | `DatabaseManager` + `db.acquire()` | Need raw SQL power |

### Pattern Selection Guidelines

#### Use **DatabaseManager** When:
- ✅ Writing API endpoints
- ✅ Need multiple related operations
- ✅ Want explicit resource scoping
- ✅ Transaction safety is important
- ✅ Code clarity is a priority

#### Use **get_db()** When:
- ✅ Single helper method call
- ✅ Performance-critical path
- ✅ Helper function that doesn't need scoping
- ✅ Already inside an async context

#### Use **db.acquire() + Raw SQL** When:
- ✅ Complex joins (3+ tables)
- ✅ Custom aggregations
- ✅ JSONB operators needed (`->`, `->>`, `||`, `@>`)
- ✅ PostgreSQL-specific features (CTEs, window functions, ARRAY operations)
- ✅ Query optimization is critical
- ✅ No suitable helper method exists

---

## Complexity Decision Tree

```
┌─────────────────────────────────┐
│ Need database access?           │
└──────────┬──────────────────────┘
           │
           ▼
    ┌──────────────┐
    │ Simple CRUD? │────Yes────▶ Use DatabaseManager + helper method
    └──────┬───────┘              (e.g., db.get_project(), db.update_task_status())
           │
          No
           │
           ▼
    ┌─────────────────────┐
    │ Complex query?      │
    │ (joins/aggregates)  │────Yes────▶ Use DatabaseManager + db.acquire()
    └──────┬──────────────┘              Write custom SQL
           │
          No
           │
           ▼
    ┌──────────────────────┐
    │ Need transactions or │
    │ multiple operations? │────Yes────▶ Use DatabaseManager
    └──────┬───────────────┘
           │
          No
           │
           ▼
    ┌──────────────────────┐
    │ Single helper call   │
    │ in isolated context? │────Yes────▶ Use get_db()
    └──────────────────────┘
```

### Query Complexity Indicators

**Simple (Use Helper Methods):**
- Single table lookup by ID
- List all records with basic filtering
- Update single field
- Delete by ID
- Standard CRUD operations

**Complex (Use Raw SQL):**
- Joins across 3+ tables
- JSONB field queries with operators
- Custom aggregations (GROUP BY, HAVING)
- Window functions
- CTEs (Common Table Expressions)
- Subqueries
- PostgreSQL-specific features (ARRAY, JSONB operators)

---

## Best Practices

### 1. Prefer Helper Methods Over Raw SQL

**Good:**
```python
async with DatabaseManager() as db:
    project = await db.get_project(project_id)
    tasks = await db.list_tasks(project_id, only_pending=True)
```

**Avoid:**
```python
async with DatabaseManager() as db:
    async with db.acquire() as conn:
        # Don't write raw SQL for operations that have helpers
        project = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
```

### 2. Use DatabaseManager for Scoped Operations

**Good:**
```python
async def my_api_endpoint(project_id: str):
    async with DatabaseManager() as db:
        project = await db.get_project(UUID(project_id))
        tasks = await db.list_tasks(UUID(project_id))
        return {"project": project, "tasks": tasks}
```

**Avoid:**
```python
async def my_api_endpoint(project_id: str):
    db = await get_db()
    # No clear lifecycle boundary
    project = await db.get_project(UUID(project_id))
    tasks = await db.list_tasks(UUID(project_id))
    # Pool never closed (acceptable for long-running services, but less clear)
    return {"project": project, "tasks": tasks}
```

### 3. Parse JSONB Fields Explicitly

**Good:**
```python
async with db.acquire() as conn:
    row = await conn.fetchrow("SELECT metadata FROM projects WHERE id = $1", project_id)
    metadata = row['metadata']
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    # Now use metadata dict
```

**Avoid:**
```python
# Assuming JSONB is always a dict (asyncpg behavior varies)
metadata = row['metadata']
settings = metadata['settings']  # May fail if metadata is a string
```

### 4. Use Context Managers for Transactions

**Good:**
```python
async with db.transaction() as conn:
    # Multiple operations in a transaction
    await conn.execute("UPDATE projects SET status = $1 WHERE id = $2", "active", project_id)
    await conn.execute("INSERT INTO sessions (...) VALUES (...)")
    # Automatically commits on success, rolls back on exception
```

**Avoid:**
```python
# Manual transaction management (error-prone)
async with db.acquire() as conn:
    await conn.execute("BEGIN")
    try:
        await conn.execute("UPDATE ...")
        await conn.execute("INSERT ...")
        await conn.execute("COMMIT")
    except:
        await conn.execute("ROLLBACK")
        raise
```

### 5. Convert Results to Dicts for Consistency

**Good:**
```python
async with db.acquire() as conn:
    row = await conn.fetchrow("SELECT * FROM projects WHERE id = $1", project_id)
    return dict(row) if row else None
```

**Consistent:**
```python
# Helper methods always return dicts
project = await db.get_project(project_id)  # Returns dict or None
```

### 6. Don't Call disconnect() on Shared Pool

**Good:**
```python
async with DatabaseManager() as db:
    # Use db...
    pass
# Pool remains open (shared globally)
```

**Avoid:**
```python
db = await get_db()
# ... use db ...
await db.disconnect()  # DON'T - this closes the shared pool for all users!
```

The pool is closed only on application shutdown:
```python
# In api/main.py shutdown event:
@app.on_event("shutdown")
async def shutdown_event():
    from core.database_connection import close_db
    await close_db()  # Close shared pool
```

### 7. Use Type Hints for UUIDs

**Good:**
```python
async def get_project_info(project_id: UUID) -> Dict[str, Any]:
    async with DatabaseManager() as db:
        return await db.get_project(project_id)
```

**Avoid:**
```python
async def get_project_info(project_id: str) -> Dict[str, Any]:
    # String to UUID conversion happens elsewhere (less clear)
    async with DatabaseManager() as db:
        return await db.get_project(UUID(project_id))
```

---

## Common Scenarios

### Scenario 1: Simple API Endpoint

**Task:** Get project details

**Pattern:** DatabaseManager + helper method

```python
@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    try:
        project_uuid = UUID(project_id)
        async with DatabaseManager() as db:
            project = await db.get_project(project_uuid)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID")
```

### Scenario 2: Complex Query with Joins

**Task:** Get sessions with quality issues

**Pattern:** DatabaseManager + db.acquire()

```python
@app.get("/api/quality/issues")
async def get_quality_issues(limit: int = 10):
    async with DatabaseManager() as db:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    s.id,
                    s.session_number,
                    p.name as project_name,
                    q.overall_rating,
                    q.critical_issues
                FROM sessions s
                JOIN projects p ON s.project_id = p.id
                JOIN session_quality_checks q ON s.id = q.session_id
                WHERE q.overall_rating < 7
                ORDER BY q.created_at DESC
                LIMIT $1
                """,
                limit
            )
            return [dict(row) for row in rows]
```

### Scenario 3: Multi-Operation Transaction

**Task:** Create project with initial settings

**Pattern:** DatabaseManager + transaction + helper methods

```python
async def create_project_with_settings(name: str, settings: Dict[str, Any]) -> UUID:
    async with DatabaseManager() as db:
        async with db.transaction() as conn:
            # Create project
            project = await db.create_project(name=name, spec_file_path="")
            project_id = project['id']

            # Set initial settings
            await db.update_project_settings(project_id, settings)

            # Create default epics
            await db.create_epic(project_id, name="Setup", priority=0)

            return project_id
```

### Scenario 4: Cross-Project Analysis

**Task:** Analyze prompt improvements across multiple projects

**Pattern:** get_db() + db.acquire() for long-running analysis

```python
class PromptImprovementAnalyzer:
    def __init__(self, db: TaskDatabase):
        self.db = db

    async def analyze_projects(self, project_ids: List[UUID]) -> Dict[str, Any]:
        async with self.db.acquire() as conn:
            # Complex query with JSONB operations
            rows = await conn.fetch(
                """
                SELECT
                    dr.session_id,
                    s.session_number,
                    dr.overall_rating,
                    dr.review_text,
                    dr.prompt_improvements
                FROM session_deep_reviews dr
                JOIN sessions s ON dr.session_id = s.id
                WHERE s.project_id = ANY($1::uuid[])
                  AND jsonb_array_length(dr.prompt_improvements) > 0
                ORDER BY s.session_number ASC
                """,
                project_ids
            )

            results = []
            for row in rows:
                result = dict(row)
                # Parse JSONB
                if isinstance(result['prompt_improvements'], str):
                    result['prompt_improvements'] = json.loads(result['prompt_improvements'])
                results.append(result)

            return {"reviews": results, "count": len(results)}

# Usage:
db = await get_db()
analyzer = PromptImprovementAnalyzer(db)
results = await analyzer.analyze_projects([project1_id, project2_id])
```

### Scenario 5: Utility Script

**Task:** Display task status

**Pattern:** DatabaseManager for clear lifecycle

```python
async def show_project_status(project_name: str):
    async with DatabaseManager() as db:
        # Get project
        project = await db.get_project_by_name(project_name)
        if not project:
            print(f"Project not found: {project_name}")
            return

        # Get progress
        progress = await db.get_progress(project['id'])

        # Display
        print(f"Tasks: {progress['completed_tasks']}/{progress['total_tasks']}")
        print(f"Tests: {progress['passing_tests']}/{progress['total_tests']}")

# Clean entry/exit
asyncio.run(show_project_status("my-project"))
```

### Scenario 6: Session Management

**Task:** Start a new coding session

**Pattern:** DatabaseManager for transaction safety

```python
async def start_session(project_id: UUID, model: str) -> SessionInfo:
    async with DatabaseManager() as db:
        # Check for active sessions (race condition prevention)
        active = await db.get_active_session(project_id)
        if active:
            raise ValueError("Session already running")

        # Get next session number
        session_number = await db.get_next_session_number(project_id)

        # Create session atomically
        try:
            session = await db.create_session(
                project_id=project_id,
                session_number=session_number,
                session_type="coding",
                model=model
            )
        except asyncpg.UniqueViolationError:
            raise ValueError("Concurrent session creation detected")

        return SessionInfo(**session)
```

---

## Migration Guide

### From Direct get_db() to DatabaseManager

**Before:**
```python
async def my_function(project_id: UUID):
    db = await get_db()
    project = await db.get_project(project_id)
    tasks = await db.list_tasks(project_id)
    # No explicit cleanup
    return {"project": project, "tasks": tasks}
```

**After:**
```python
async def my_function(project_id: UUID):
    async with DatabaseManager() as db:
        project = await db.get_project(project_id)
        tasks = await db.list_tasks(project_id)
        return {"project": project, "tasks": tasks}
```

### From Raw SQL to Helper Methods

**Before:**
```python
async with db.acquire() as conn:
    row = await conn.fetchrow(
        "SELECT * FROM projects WHERE name = $1",
        project_name
    )
    return dict(row) if row else None
```

**After:**
```python
return await db.get_project_by_name(project_name)
```

### From Manual JSONB Parsing to Consistent Pattern

**Before:**
```python
metadata = project['metadata']
# Might fail if string
settings = metadata.get('settings', {})
```

**After:**
```python
metadata = project.get('metadata', {})
if isinstance(metadata, str):
    import json
    metadata = json.loads(metadata)
settings = metadata.get('settings', {})
```

### Adding Helper Methods to TaskDatabase

If you find yourself writing the same raw SQL query multiple times, add a helper method:

```python
# In core/database.py
async def get_sessions_by_status(
    self,
    project_id: UUID,
    status: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Get sessions filtered by status."""
    async with self.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM sessions
            WHERE project_id = $1 AND status = $2
            ORDER BY session_number DESC
            LIMIT $3
            """,
            project_id, status, limit
        )
        return [dict(row) for row in rows]
```

Then use it:
```python
async with DatabaseManager() as db:
    running_sessions = await db.get_sessions_by_status(project_id, "running")
```

---

## Summary Checklist

When writing database code, ask yourself:

- [ ] Is there a helper method for this operation? → **Use it**
- [ ] Is this a simple CRUD operation? → **DatabaseManager + helper**
- [ ] Do I need a complex join or aggregation? → **DatabaseManager + db.acquire()**
- [ ] Am I in an API endpoint? → **DatabaseManager**
- [ ] Do I need multiple operations? → **DatabaseManager**
- [ ] Do I need transaction safety? → **db.transaction()**
- [ ] Am I parsing JSONB fields? → **Check for string, parse if needed**
- [ ] Am I using UUIDs? → **Type hints and explicit conversion**
- [ ] Should I call disconnect()? → **NO (pool is shared)**

**Golden Rules:**
1. **DatabaseManager** for 90% of use cases
2. **Helper methods** whenever they exist
3. **Raw SQL** only when necessary for complexity
4. **Never disconnect()** the shared pool manually
5. **Always parse JSONB** fields explicitly
6. **Transaction context** for multi-operation atomicity

---

**Questions or Improvements?**

This is a living document. If you encounter patterns not covered here or have suggestions for improvement, please update this guide or discuss with the team.
