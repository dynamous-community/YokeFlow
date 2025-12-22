# MCP-Based Task Management

## Overview

The autonomous coding agent uses MCP (Model Context Protocol) for all task management operations. This provides a structured, type-safe, protocol-based interface for managing tasks.

**Note:** MCP is the only supported mode. Shell-based task management (`task-helper.sh`) has been removed.

## Running the Agent

### Basic Usage

To run the autonomous agent:

```bash
python autonomous_agent.py --project-dir my_project
```

The MCP task manager is automatically enabled - no flags needed.

### Command-Line Options

- `--verbose` - Show detailed output
- `--max-iterations N` - Limit the number of iterations
- `--model MODEL` - Override both initializer and coding models
- `--initializer-model MODEL` - Specify model for initialization (default: claude-opus-4-5-20251101)
- `--coding-model MODEL` - Specify model for coding sessions (default: claude-sonnet-4-5-20250929)

**Example - Using defaults (Opus for init, Sonnet for coding)**:
```bash
python autonomous_agent.py --project-dir my_project
```

**Example - Override just the coding model**:
```bash
python autonomous_agent.py --project-dir my_project --coding-model claude-opus-4-5-20251101
```

## Testing MCP

Before running a full project, you can test the MCP integration:

```bash
python tests/test_mcp.py
```

This will:
1. Create a test database
2. Test basic MCP tools (status, create epic, expand epic)
3. Verify the MCP server is working correctly

## Why MCP?

### Advantages of Protocol-Based Tools

```python
# Agent uses MCP tools
mcp__task-manager__task_status
mcp__task-manager__get_next_task
mcp__task-manager__update_task_status(task_id=5, done=True)
```

**Benefits:**
- **Structured, type-safe interface** - Proper parameter validation
- **Better error handling** - Detailed error messages with context
- **No shell escaping issues** - JSON-based communication
- **Easier to extend** - Add new tools without shell script complexity
- **Foundation for real-time updates** - Could support subscriptions in future
- **Auto-initialization** - Database created before MCP server starts

## MCP Tools Available

All tools are prefixed with `mcp__task-manager__`:

### Query Tools
- `task_status` - Get overall project progress
- `get_next_task` - Get next task to work on
- `list_epics` - List all epics
- `get_epic` - Get epic details with tasks
- `list_tasks` - List tasks with filtering
- `get_task` - Get task details including tests
- `list_tests` - Get tests for a task
- `get_session_history` - View recent sessions

### Update Tools
- `update_task_status` - Mark task done/not done
- `start_task` - Mark task as started
- `update_test_result` - Mark test pass/fail

### Create Tools
- `create_epic` - Create new epic
- `create_task` - Create task in epic
- `create_test` - Add test to task
- `expand_epic` - Break epic into multiple tasks
- `log_session` - Log session completion

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│ Autonomous      │────▶│ Claude SDK      │
│ Agent           │     │ Client          │
└─────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ MCP Server          │
                    │ (task-manager)      │
                    └─────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ PostgreSQL Database │
                    │ (centralized)       │
                    └─────────────────────┘
```

## Database Connection

The task database is centralized in PostgreSQL:
- Connection via `DATABASE_URL` environment variable
- Project-specific queries use `PROJECT_ID` parameter
- Shared database for all projects with UUID-based isolation

## Troubleshooting

### MCP Server Not Found
If you get "MCP server not found" errors:
1. Ensure the MCP server is built: `cd mcp-task-manager && npm run build`
2. Check that `dist/index.js` exists
3. Verify the path in `client.py` is correct

### Database Connection Issues
If database connection fails:
1. Ensure PostgreSQL is running: `docker-compose up -d`
2. Check `DATABASE_URL` in `.env` file
3. Initialize database: `python scripts/init_database.py`
4. Verify connection: `psql $DATABASE_URL -c "SELECT version();"`

### Project Not Found
If project is not found:
1. Verify project exists in database: `psql $DATABASE_URL -c "SELECT * FROM projects;"`
2. Check that `PROJECT_ID` is being passed to MCP server
3. Ensure project was created via `orchestrator.create_project()`

## Development

To modify the MCP server:

1. Edit the TypeScript source:
   ```bash
   cd mcp-task-manager
   npm install
   # Edit src/*.ts files
   npm run build
   ```

2. Test your changes:
   ```bash
   python tests/test_mcp.py
   ```

3. Run with the agent:
   ```bash
   python autonomous_agent.py --project-dir test_project --max-iterations 1
   ```

## Future Enhancements

Planned improvements for MCP mode:
- WebSocket support for real-time UI updates
- Task dependencies and relationships
- Time tracking and estimates
- Multi-agent collaboration
- Web dashboard integration
- Skills system for complex operations

## Historical Note

Previously, the system supported both shell-based and MCP-based task management. Shell mode has been removed in favor of the superior MCP protocol. All projects now use MCP exclusively.