# Developer Guide

This guide provides technical details for developers who want to understand, customize, or extend YokeFlow.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Core Components](#core-components)
- [MCP Integration](#mcp-integration)
- [Database Schema](#database-schema)
- [Security System](#security-system)
- [Observability](#observability)
- [Extending the System](#extending-the-system)
- [Testing](#testing)

---

## Architecture Overview

### System Components

**API-First Architecture:**
```
┌─────────────────┐
│   Web Browser   │
└────────┬────────┘
         │ HTTP/WebSocket
         ▼
┌─────────────────────┐
│  Next.js Web UI     │  TypeScript/React (port 3000)
│  - Project mgmt     │
│  - Real-time updates│
│  - Env editor       │
└────────┬────────────┘
         │ REST API
         ▼
┌─────────────────────┐
│   FastAPI Server    │  Python (port 8000)
│   api/main.py       │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  orchestrator.py    │  Session lifecycle management
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│     agent.py        │  Agent loop, session management
└────────┬────────────┘
         │
         ├──────────────────┐
         │                  │
         ▼                  ▼
┌──────────────┐   ┌────────────────┐
│  client.py   │   │  prompts.py    │
│ (SDK setup)  │   │ (load prompts) │
└──────┬───────┘   └────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│   Claude SDK Client             │
│   - MCP servers loaded          │
│   - Security hooks active       │
│   - Observability logging       │
└─────────────────────────────────┘
       │
       ├────────────────┬─────────────┐
       │                │             │
       ▼                ▼             ▼
┌──────────────┐  ┌─────────┐  ┌──────────────┐
│ MCP Servers  │  │Security │  │Observability │
│ task-manager │  │Blocklist│  │Session Logs  │
│ playwright   │  │         │  │              │
└──────┬───────┘  └─────────┘  └──────────────┘
       │
       ▼
┌─────────────────────────┐
│ PostgreSQL Database     │
│ (centralized, all       │
│  projects)              │
└─────────────────────────┘
```


### Data Flow

**Initialization Flow:**
```
User → yokeflow.py → agent.py → orchestrator.py
  ↓
Create project in PostgreSQL database
  ↓
Copy app_spec.txt to project directory
  ↓
Create MCP client with task-manager server (PostgreSQL connection)
  ↓
Load initializer_prompt.md
  ↓
Agent creates epics → expands into tasks → adds tests (in PostgreSQL)
  ↓
Auto-stop (complete roadmap ready)
```

**Coding Flow:**
```
User → yokeflow.py → agent.py
  ↓
Load MCP client with task-manager server
  ↓
Load coding_prompt.md
  ↓
Agent loop:
  1. get_next_task (MCP call)
  2. Implement feature
  3. Browser automation verification
  4. update_test_result (MCP calls)
  5. update_task_status (MCP call)
  6. Git commit
  7. Auto-continue (3s delay)
```

---

## Core Components


### core/agent.py

**Purpose:** Core agent session logic

**Key Functions:**

`run_agent_session()` - Single agent session
- Creates client context
- Sends prompt
- Processes response stream
- Handles: AssistantMessage, UserMessage, SystemMessage
- Applies QuietOutputFilter for terminal display
- Logs everything via SessionLogger

`run_autonomous_agent()` - Main loop
- Detects first run vs continuation (checks for epics in PostgreSQL)
- Creates session logger
- Selects appropriate model (initializer vs coding)
- Loads appropriate prompt
- Calls run_agent_session()
- Auto-stops after initializer
- Auto-continues after coding sessions (3s delay)

**Session Type Detection:**
```python
# Check if project has epics in PostgreSQL
async with DatabaseManager() as db:
    epics = await db.list_epics(project_id)
    is_first_run = len(epics) == 0

if is_first_run:
    # Use initializer prompt + initializer model
    # Create project roadmap in PostgreSQL
    # Stop after completion
else:
    # Use coding prompt + coding model
    # Auto-continue with delay
```

### core/client.py

**Purpose:** Claude SDK client configuration

**Key Features:**
- Loads MCP servers (task-manager, puppeteer)
- Configures `bypassPermissions` mode for autonomous operation
- Sets up security hooks (Bash blocklist)
- Passes project-specific environment variables to MCP servers

**MCP Server Configuration:**
```python
mcp_servers = {
    "task-manager": {
        "command": "node",
        "args": [str(mcp_server_path)],
        "env": {
            "DATABASE_URL": os.getenv("DATABASE_URL"),
            "PROJECT_ID": str(project_id)
        }
    },
    "playwright": {
        "command": "npx",
        "args": ["playwright-mcp-server"]
    }
}
```

### core/prompts.py

**Purpose:** Prompt loading and project setup

**Key Functions:**

`get_initializer_prompt()` - Load initializer_prompt.md

`get_coding_prompt()` - Load coding_prompt.md

`copy_spec_to_project()` - Copy app_spec.txt to project

### core/security.py

**Purpose:** Bash command blocklist validation

**Blocked Command Categories:**
- File operations: rm, rmdir
- System modification: sudo, su, chown, chgrp
- Destructive operations: dd, mkfs, fdisk
- System control: reboot, shutdown, systemctl
- Package managers: apt, yum, dnf, brew
- Kernel modules: insmod, rmmod
- User management: useradd, passwd

**Special Cases:**
- `pkill` - Only allows development processes (node, npm, python, etc.)
- All other commands allowed by default

**Validation:**
```python
def validate_bash_command(command: str) -> tuple[bool, str]:
    """Returns (is_allowed, reason)"""
    # Check blocklist
    # Special handling for pkill
    # Return True/False + explanation
```

### core/observability.py

**Purpose:** Session logging and output filtering

**Classes:**

`SessionLogger`:
- Dual-format logging (JSONL + TXT)
- Tracks: prompts, messages, tool use/results, thinking, errors
- Auto-increments session numbers
- Session metrics stored in PostgreSQL database

`QuietOutputFilter`:
- Controls terminal verbosity
- Quiet mode: assistant text, Bash tools, errors only
- Verbose mode: everything (tool inputs, results, thinking, system messages)

**Log Structure:**
```
generations/[project]/logs/
├── session_001_20251209_140523.jsonl  # Machine-readable
└── session_001_20251209_140523.txt    # Human-readable

Note: Session metrics stored in PostgreSQL (sessions.metrics JSONB field)
```

### core/progress.py

**Purpose:** Progress tracking utilities

**Key Functions:**

`get_progress_from_db(project_dir)`:
- Queries v_progress view
- Returns dict with completion stats

`print_progress_summary(project_dir)`:
- Terminal output of current progress
- Called between sessions

### core/database.py

**Purpose:** PostgreSQL database abstraction layer with async operations

**Key Features:**
- Provides `TaskDatabase` class with 20+ async methods
- Clean separation between data access and business logic
- Production-ready with asyncpg and connection pooling
- Consistent API across all modules (CLI, API, Web UI)
- UUID-based project identification
- JSONB for flexible metadata

**Key Methods:**
- `get_progress(project_id)` - Overall statistics
- `get_next_task(project_id)` - Next task to work on
- `list_epics(project_id)` - Epic queries
- `list_tasks(project_id)` - Task queries
- `create_epic()`, `create_task()` - Create operations
- `update_task_status()`, `update_test_result()` - Update operations

**Usage Example:**
```python
from core.database_connection import DatabaseManager

async with DatabaseManager() as db:
    progress = await db.get_progress(project_id)
    next_task = await db.get_next_task(project_id)
    await db.update_task_status(task_id=5, done=True)
```

### core/orchestrator.py

**Purpose:** Agent orchestration service for API-driven control

**Key Features:**
- Decouples session management from CLI
- Enables API-driven control of agent sessions
- Foundation for job queue integration (Celery/Redis)
- Makes the system more modular and testable

**Classes:**

`AgentOrchestrator`:
- `create_project()` - Initialize new project
- `start_session()` - Begin agent session
- `get_session_info()` - Query session status
- `list_sessions()` - Get session history

`SessionInfo`:
- Dataclass containing session metadata
- Status, timestamps, model info, errors

**Usage Example:**
```python
from core.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator(verbose=False)
session_info = await orchestrator.start_session(
    project_dir=Path("generations/my-project"),
    model="claude-sonnet-4-5-20250929"
)
```

---

## MCP Integration

### MCP Server Location

```
mcp-task-manager/
├── src/
│   └── index.ts       # MCP server implementation
├── dist/
│   └── index.js       # Compiled (this is what runs)
├── package.json
└── tsconfig.json
```

### Building the MCP Server

```bash
cd mcp-task-manager
npm install
npm run build  # Compiles TypeScript to dist/index.js
```

### Available Tools

See [mcp-usage.md](mcp-usage.md) for complete tool reference.

**Query Tools:**
- task_status, get_next_task, list_epics, get_epic, list_tasks, list_tests, get_session_history

**Update Tools:**
- update_task_status, start_task, update_test_result

**Create Tools:**
- create_epic, create_task, create_test, expand_epic, log_session

### Tool Implementation Pattern

```typescript
// In index.ts
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: "task_status",
      description: "Get overall progress statistics",
      inputSchema: { type: "object", properties: {} }
    },
    // ... more tools
  ]
}));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "task_status":
      const stats = db.prepare(`SELECT * FROM v_progress`).get();
      return { content: [{ type: "text", text: JSON.stringify(stats) }] };

    // ... more cases
  }
});
```

### Adding a New MCP Tool

1. **Define tool in ListToolsRequestSchema handler:**
```typescript
{
  name: "my_new_tool",
  description: "What this tool does",
  inputSchema: {
    type: "object",
    properties: {
      param1: { type: "string", description: "..." },
      param2: { type: "number", description: "..." }
    },
    required: ["param1"]
  }
}
```

2. **Add case in CallToolRequestSchema handler:**
```typescript
case "my_new_tool":
  const { param1, param2 } = args;
  // Validate inputs
  // Query database
  // Return result
  return {
    content: [{
      type: "text",
      text: JSON.stringify(result)
    }]
  };
```

3. **Rebuild:**
```bash
npm run build
```

4. **Update prompts:**
Add usage instructions to `prompts/coding_prompt.md`

---

## Database Schema

### Tables

**epics:**
```sql
CREATE TABLE epics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at DATETIME,
    completed_at DATETIME
);
```

**tasks:**
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    epic_id INTEGER NOT NULL,
    description TEXT NOT NULL,
    action TEXT,                    -- Implementation details
    priority INTEGER DEFAULT 0,
    done BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    session_notes TEXT,
    FOREIGN KEY (epic_id) REFERENCES epics(id)
);
```

**tests:**
```sql
CREATE TABLE tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    category TEXT NOT NULL,        -- functional, style, accessibility, performance
    description TEXT NOT NULL,
    steps TEXT,                     -- JSON array of test steps
    passes BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    verified_at DATETIME,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

**sessions:**
```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_number INTEGER NOT NULL,
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME,
    notes TEXT
);
```

### Views

**v_progress:** Overall statistics
```sql
CREATE VIEW v_progress AS
SELECT
    COUNT(DISTINCT e.id) as total_epics,
    COUNT(DISTINCT CASE WHEN e.status = 'completed' THEN e.id END) as completed_epics,
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.done = 1 THEN t.id END) as completed_tasks,
    COUNT(test.id) as total_tests,
    COUNT(CASE WHEN test.passes = 1 THEN test.id END) as passing_tests
FROM epics e
LEFT JOIN tasks t ON e.id = t.epic_id
LEFT JOIN tests test ON t.id = test.task_id;
```

**v_next_task:** Next task to work on
```sql
CREATE VIEW v_next_task AS
SELECT
    t.*,
    e.name as epic_name,
    e.description as epic_description
FROM tasks t
JOIN epics e ON t.epic_id = e.id
WHERE t.done = 0
ORDER BY e.priority, t.priority
LIMIT 1;
```

**v_epic_progress:** Per-epic completion
```sql
CREATE VIEW v_epic_progress AS
SELECT
    e.*,
    COUNT(t.id) as total_tasks,
    SUM(CASE WHEN t.done = 1 THEN 1 ELSE 0 END) as completed_tasks,
    CAST(SUM(CASE WHEN t.done = 1 THEN 1 ELSE 0 END) AS FLOAT) /
        NULLIF(COUNT(t.id), 0) * 100 as completion_percentage
FROM epics e
LEFT JOIN tasks t ON e.id = t.epic_id
GROUP BY e.id;
```

**v_epics_need_expansion:** Epics with no tasks
```sql
CREATE VIEW v_epics_need_expansion AS
SELECT e.*
FROM epics e
LEFT JOIN tasks t ON e.id = t.epic_id
GROUP BY e.id
HAVING COUNT(t.id) = 0
ORDER BY e.priority;
```

### Modifying the Schema

1. Edit `schema/postgresql/schema.sql`
2. Test with a fresh database installation
3. Run `python scripts/init_database.py --docker` to apply schema

**Important:** Schema changes require a fresh database installation. Existing data cannot be migrated between versions.

---

## Security System

### Blocklist Approach

**Philosophy:** Allow everything except explicitly dangerous commands

**vs Allowlist:**
- Allowlist: Block everything, allow specific commands
- Blocklist: Allow everything, block specific commands

**Why Blocklist:**
- Development needs diverse tools
- Agent should work autonomously
- Safe in containers (primary deployment)
- Easier to maintain (fewer commands to list)

### Implementation

File: `security.py`

```python
BLOCKED_COMMANDS = {
    "rm", "rmdir",           # File deletion
    "sudo", "su",            # Privilege escalation
    "reboot", "shutdown",    # System control
    "apt", "yum", "brew",    # Package managers
    # ... etc
}

def validate_bash_command(command: str) -> tuple[bool, str]:
    # Parse command
    # Check against blocklist
    # Special handling for pkill
    return (is_allowed, reason)
```

### Testing Security

```bash
cd tests
python test_security.py
```

Tests cover:
- Blocked commands
- Allowed commands
- pkill validation
- Edge cases

### Adding/Removing Blocked Commands

Edit `security.py`:

```python
BLOCKED_COMMANDS = {
    "rm", "rmdir",
    # Add your blocked command:
    "mycmd",
}
```

**Warning:** Be cautious when removing blocks - test in container first.

---

## Observability

### Log Files

**JSONL Format** (machine-readable):
```json
{"type": "prompt", "content": "...", "timestamp": "2025-12-09T14:05:23Z"}
{"type": "assistant_text", "content": "...", "timestamp": "..."}
{"type": "tool_use", "name": "Bash", "input": {...}, "timestamp": "..."}
{"type": "tool_result", "content": "...", "is_error": false, "timestamp": "..."}
```

**TXT Format** (human-readable):
```
[14:05:23] === SESSION START ===
[14:05:23] PROMPT: (3245 chars)
[14:05:25] ASSISTANT: Let me start by...
[14:05:26] TOOL: Bash - pwd
[14:05:26] RESULT: /path/to/project
```

### QuietOutputFilter

**Quiet Mode (default):**
- Shows: Assistant text, Bash tool notifications, errors
- Hides: Tool inputs, results (unless error), thinking, system messages

**Verbose Mode (`--verbose`):**
- Shows: Everything

**Implementation:**
```python
class QuietOutputFilter:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def should_show_tool_use(self, tool_name: str) -> bool:
        if self.verbose:
            return True
        return tool_name == "Bash"  # Only Bash in quiet mode

    def should_show_tool_result(self, is_error: bool) -> bool:
        if self.verbose or is_error:
            return True
        return False
```

### Analyzing Logs

**Using analyze_logs.sh:**
```bash
./analyze_logs.sh generations/my_project

# Shows:
# - Session overview (duration, tools, errors)
# - Aggregate stats
# - Tool usage breakdown
# - Error summary
# - Blocked commands
# - Recent session preview
```

**Custom Analysis:**
```bash
# Count tool uses
jq -r 'select(.event == "tool_use") | .tool_name' logs/*.jsonl | sort | uniq -c

# Find errors
jq -r 'select(.event == "tool_result" and .is_error == true)' logs/*.jsonl

# Session durations (from individual session logs)
jq -r 'select(.event == "session_end") | .duration_seconds' logs/*.jsonl
```

**Note:** Session metrics are now stored in PostgreSQL database. Query the `sessions` table for aggregate analysis.

---

## Extending the System

### Adding Custom Prompts

1. Create new prompt file in `prompts/`
2. Add loader function to `prompts.py`:
```python
def get_my_prompt() -> str:
    return (PROMPTS_DIR / "my_prompt.md").read_text()
```
3. Call in `agent.py` when needed

### Custom MCP Server

See: [MCP Server Documentation](https://modelcontextprotocol.io/)

1. Create new MCP server (Node.js or Python)
2. Add to `client.py`:
```python
mcp_servers = {
    "task-manager": {...},
    "my-server": {
        "command": "node",
        "args": [str(my_server_path)],
        "env": {"MY_VAR": "value"}
    }
}
```
3. Use tools in prompts: `mcp__my-server__tool_name`

### Custom Security Rules

**Scenario:** Want to allow `curl` only to specific domains

```python
# In security.py
ALLOWED_DOMAINS = ["api.example.com", "cdn.example.com"]

def validate_bash_command(command: str) -> tuple[bool, str]:
    parts = shlex.split(command)
    cmd = parts[0]

    if cmd == "curl":
        # Check URL in args
        for arg in parts[1:]:
            if arg.startswith("http"):
                domain = urlparse(arg).netloc
                if domain not in ALLOWED_DOMAINS:
                    return (False, f"curl blocked: domain {domain} not in allowlist")
        return (True, "")

    # ... rest of validation
```

### Web UI Customization

**Architecture:** Next.js (TypeScript/React) → FastAPI REST API → Database Abstraction Layer

**Key Directories:**
- `web-ui/src/app/` - Next.js pages and routes
- `web-ui/src/components/` - React components
- `web-ui/src/lib/` - API client and utilities
- `api/` - FastAPI backend server

**Quick changes:**

**Add new API endpoint:**
```python
# api/main.py
@app.get("/api/projects/{project_id}/my-endpoint")
async def my_endpoint(project_id: str):
    db = get_database(generations_dir / project_id)
    results = db.custom_query()
    return results
```

**Add new React component:**
```typescript
// web-ui/src/components/MyComponent.tsx
export function MyComponent({ data }: { data: MyData }) {
  return <div>{/* component code */}</div>
}
```

---

## Testing

### Test Structure

```
tests/
├── test_security.py       # Security blocklist tests
├── test_mcp.py            # MCP integration tests
├── test_mcp_direct.py     # Direct MCP tool tests
├── test_initializer.sh    # End-to-end initializer test
└── test_coding.sh         # End-to-end coding test
```

### Running Tests

**Security tests:**
```bash
cd tests
python test_security.py
```

**MCP integration:**
```bash
python test_mcp.py
```

**End-to-end:**
```bash
./test_initializer.sh my-test-project
./test_coding.sh my-test-project
```

### Writing New Tests

**Security test pattern:**
```python
def test_my_command():
    is_allowed, reason = validate_bash_command("mycmd args")
    assert is_allowed == False
    assert "blocked" in reason.lower()
```

**MCP test pattern:**
```python
async def test_my_tool():
    # Create test database
    # Initialize MCP server
    # Call tool
    # Verify results
    # Cleanup
```

---

## Development Workflow

### Making Changes

1. **Create feature branch:**
```bash
git checkout -b feature/my-enhancement
```

2. **Make changes** to relevant files

3. **Test locally:**
```bash
# Run tests
python tests/test_security.py
python tests/test_mcp.py

# Test with real project
python yokeflow.py --project-dir test-proj --max-iterations 2
```

4. **Update documentation:**
- Update this guide if architecture changes
- Update PROPOSED_ENHANCEMENTS.md if adding features
- Update relevant docs in `docs/`

5. **Commit:**
```bash
git add .
git commit -m "Description of changes"
```

6. **Create PR or merge:**
```bash
git checkout main
git merge feature/my-enhancement
```

### Best Practices

**Code Style:**
- Python: Follow PEP 8
- TypeScript: Use ESLint
- Shell scripts: Use ShellCheck

**Documentation:**
- Update docs when changing APIs
- Add inline comments for complex logic
- Keep CLAUDE.md up to date for context restoration

**Testing:**
- Test security changes thoroughly
- Test MCP changes with real database
- End-to-end test for major changes

**Git Commits:**
- Descriptive commit messages
- Group related changes
- Reference issues if applicable

---

## Common Development Tasks

### Debugging MCP Server

**Enable debug logging:**
```typescript
// In mcp-task-manager/src/index.ts
console.error("DEBUG: tool called with args:", args);
```

**View stderr:**
```bash
# MCP server logs go to stderr, visible in agent logs
grep "MCP" generations/my_project/logs/session_*.txt
```

**Test MCP server directly:**
```bash
cd tests
python test_mcp_direct.py
```

### Debugging Security Issues

**See what command was blocked:**
```bash
# Check logs
./analyze_logs.sh generations/my_project

# Look for "blocked" in JSONL
jq -r 'select(.type == "tool_result" and .is_blocked == true)' logs/*.jsonl
```

**Temporarily allow command for testing:**
```python
# In security.py, comment out the block:
BLOCKED_COMMANDS = {
    # "mycmd",  # Temporarily allowed for testing
}
```

### Debugging Database Issues

**Inspect database:**
```bash
# Connect to PostgreSQL
psql $DATABASE_URL

# View schema
\d projects
\d epics
\d tasks
\d tests

# Query progress
SELECT * FROM v_progress;
SELECT * FROM v_epic_progress;

# Exit
\q
```

**Check database connection:**
```bash
# Test connection
psql $DATABASE_URL -c "SELECT version();"

# List all projects
psql $DATABASE_URL -c "SELECT id, name, created_at FROM projects;"
```

**Reset project data (keeps schema):**
```bash
# Use reset_project.py script
python reset_project.py --project-dir my_project --yes
```

---

## Performance Considerations

### Database Queries

**Use views for complex queries:**
- Views are pre-defined, optimized
- Better than ad-hoc queries from agent

**Add indexes if needed:**
```sql
CREATE INDEX idx_tasks_epic_id ON tasks(epic_id);
CREATE INDEX idx_tests_task_id ON tests(task_id);
```

### MCP Server

**Keep it lightweight:**
- Minimal dependencies
- Fast database queries
- No long-running operations

**Connection pooling:**
Currently uses single connection - fine for single-user.
For multi-user: implement connection pool.

### Web UI

**Status:** ✅ Production-ready (v2.0)

**Features:**
- JWT authentication with development mode
- Real-time WebSocket updates (session progress, tool uses)
- Task detail views with epic/task/test hierarchy
- Quality dashboard with session metrics
- Session logs viewer (TXT/JSONL)
- Project completion celebration banner
- Toast notifications and confirmation dialogs
- Environment variable editor

**Performance:**
- WebSocket for instant updates (no polling)
- Connection pooling implemented (10-20 connections)
- Async operations throughout

**Scaling:**
For high traffic: consider adding Redis cache for API responses.

---

## Deployment

### Local Development

Current state - works great for local development.

### Docker Deployment

**Recommended for production:**

```dockerfile
FROM python:3.11

# Install Node.js for MCP server
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
RUN apt-get install -y nodejs

# Install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code
COPY . /app
WORKDIR /app

# Build MCP server
RUN cd mcp-task-manager && npm install && npm run build

# Build Next.js web UI
RUN cd web-ui && npm install && npm run build

# Run API server (or agent CLI)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
# Alternative: CMD ["python", "yokeflow.py", "--project-dir", "/workspace"]
```

**Volume mounts:**
```bash
docker run -v $(pwd)/generations:/workspace yokeflow
```

### Cloud Deployment

**Current Status:** API-first architecture is complete and ready for deployment.

**Architecture:**
- FastAPI REST API server (port 8000)
- Next.js Web UI (port 3000, or static export)
- WebSocket for real-time updates
- Database abstraction layer (PostgreSQL-ready)

**Deployment Recommendations:**
- Use Digital Ocean, AWS, or similar for API server
- Deploy Next.js as static site or Node.js server
- Use Docker for sandboxed agent workspaces (built-in)
- ✅ JWT authentication implemented (production-ready)
- ✅ PostgreSQL in production (async operations, connection pooling)

See [TODO.md](../TODO.md) and [api/README.md](../api/README.md) for details.

---

## Additional Resources

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Claude SDK Documentation](https://docs.anthropic.com/claude/docs/claude-code)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)

---

See [CLAUDE.md](../CLAUDE.md) for context restoration.
