# YokeFlow API - Developer Documentation

RESTful API for managing YokeFlow projects and sessions with real-time WebSocket updates.

**For API usage examples and quick start, see [docs/api-usage.md](../docs/api-usage.md)**

---

## Overview

This document is for **developers** working on the API itself. For **users** wanting to call the API, see the [API Usage Guide](../docs/api-usage.md).

The API provides a complete backend for the YokeFlow platform, including:
- **JWT Authentication** - Secure token-based authentication with development mode
- **Project Management** - Create, list, and monitor projects with validation
- **Session Control** - Separate endpoints for initialization and coding
- **Real-Time Updates** - WebSocket events for live progress monitoring
- **PostgreSQL Database** - Production-ready async operations
- **Docker Sandbox** - Isolated execution environment support

## Quick Start

### Prerequisites

```bash
# PostgreSQL database (via Docker)
docker-compose up -d

# Install Python dependencies
pip install -r requirements.txt
```

### Start the Server

```bash
# From project root
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Server will start at http://localhost:8000
```

### View Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/api/health

## API Endpoints

### Health & Info

#### `GET /api/health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-10T12:00:00",
  "version": "1.0.0"
}
```

#### `GET /api/info`
Get API configuration information.

**Response:**
```json
{
  "generations_dir": "generations",
  "default_models": {
    "initializer": "claude-opus-4-5-20251101",
    "coding": "claude-sonnet-4-5-20250929"
  },
  "version": "1.0.0"
}
```

### Project Management

#### `GET /api/projects`
List all projects.

**Response:**
```json
[
  {
    "project_id": "my-project",
    "project_path": "generations/my-project",
    "progress": {
      "total_epics": 25,
      "completed_epics": 5,
      "total_tasks": 261,
      "completed_tasks": 64,
      "total_tests": 261,
      "passing_tests": 64,
      "task_completion_pct": 24.5,
      "test_pass_pct": 24.5
    },
    "next_task": {
      "id": 65,
      "description": "Build welcome screen...",
      "epic_name": "Core Chat Interface",
      "tests": [...]
    }
  }
]
```

#### `POST /api/projects`
Create a new project with specification file.

**Request (multipart/form-data):**
- `name` - Project name
- `spec_file` - Application specification file (required)
- `sandbox_type` - "docker" or "local" (default: "docker")
- `initializer_model` - Model for Session 0 (initialization, default: opus-4-5)
- `coding_model` - Model for Sessions 1+ (coding, default: sonnet-4-5)

**Example with curl:**
```bash
curl -X POST http://localhost:8000/api/projects \
  -F "name=my-project" \
  -F "spec_file=@app_spec.txt" \
  -F "sandbox_type=docker"
```

**Response:**
```json
{
  "project_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "my-project",
  "generations_path": "generations/my-project",
  "is_initialized": false,
  "metadata": {
    "sandbox_type": "docker",
    "initializer_model": "claude-opus-4-5-20251101",
    "coding_model": "claude-sonnet-4-5-20250929"
  }
}
```

**Errors:**
- `400 Bad Request` - Missing spec file or invalid parameters
- `409 Conflict` - Project with this name already exists
- `500 Internal Server Error` - Server error

#### `GET /api/projects/{project_id}`
Get project details.

**Response:**
```json
{
  "project_id": "my-project",
  "project_path": "generations/my-project",
  "progress": { ... },
  "next_task": { ... }
}
```

**Errors:**
- `404 Not Found` - Project doesn't exist

#### `GET /api/projects/{project_id}/progress`
Get project progress statistics only.

**Response:**
```json
{
  "total_epics": 25,
  "completed_epics": 5,
  "total_tasks": 261,
  "completed_tasks": 64,
  "total_tests": 261,
  "passing_tests": 64,
  "task_completion_pct": 24.5,
  "test_pass_pct": 24.5
}
```

#### `DELETE /api/projects/{project_id}`
Delete a project and all associated data.

**Deletes:**
- Project directory and all files
- Database records (cascades to epics, tasks, tests, sessions, reviews, commits)

**Response:**
```json
{
  "status": "deleted",
  "project_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Errors:**
- `404 Not Found` - Project doesn't exist
- `500 Internal Server Error` - Delete operation failed

**Note:** This operation is irreversible. All project data will be permanently deleted.

### Session Management

The API provides **separate endpoints** for initialization and coding sessions:

#### `POST /api/projects/{project_id}/initialize`
Run initialization session (Session 0) only. Creates project roadmap (epics, tasks, tests) and runs `init.sh`.

**Request Body:**
```json
{
  "initializer_model": "claude-opus-4-5-20251101"  // Optional
}
```

**Response:**
```json
{
  "session_id": "a1b2c3d4-...",
  "project_id": "550e8400-...",
  "session_number": 1,
  "session_type": "initializer",
  "model": "claude-opus-4-5-20251101",
  "status": "running",
  "created_at": "2025-12-16T12:00:00Z"
}
```

**Behavior:**
- Creates complete roadmap (epics → tasks → tests)
- Runs project setup script (`init.sh`)
- Sets `is_initialized: true` when complete
- **Never** auto-continues to coding
- Check status via WebSocket for completion

**Errors:**
- `400 Bad Request` - Project already initialized
- `404 Not Found` - Project doesn't exist
- `409 Conflict` - Session already running

---

#### `POST /api/projects/{project_id}/initialize/cancel`
Cancel running initialization session.

**Response:**
```json
{
  "status": "cancelled",
  "cleanup": {
    "epics_deleted": 15,
    "tasks_deleted": 143,
    "tests_deleted": 187
  }
}
```

**Behavior:**
- Stops the running initialization session
- Removes ALL epics, tasks, and tests from database
- Keeps project record (can re-initialize)
- Sets `is_initialized: false`

**Errors:**
- `404 Not Found` - No running initialization session
- `500 Internal Server Error` - Cancellation failed

---

#### `POST /api/projects/{project_id}/coding/start`
Run coding sessions (2+) with auto-continue loop.

**Request Body:**
```json
{
  "coding_model": "claude-sonnet-4-5-20250929",  // Optional
  "max_iterations": 0  // 0 = unlimited, N = run N sessions
}
```

**Response:**
```json
{
  "status": "started",
  "message": "Coding sessions started with auto-continue",
  "max_iterations": 0
}
```

**Behavior:**
- Verifies `is_initialized: true` (requires initialization first)
- Runs multiple sessions automatically
- Each session: get task → implement → verify → update database → commit
- Auto-continues until all tasks complete or `max_iterations` reached
- Use `/coding/stop` to stop between sessions

**Errors:**
- `400 Bad Request` - Project not initialized
- `409 Conflict` - Session already running

---

#### `POST /api/projects/{project_id}/coding/stop`
Stop auto-continue loop (graceful shutdown between sessions).

**Response:**
```json
{
  "status": "stopping",
  "message": "Will stop after current session completes"
}
```

**Behavior:**
- Waits for current session to finish
- Does not start next session
- Safe shutdown (no data loss)

---

#### `GET /api/projects/{project_id}/sessions`
List all sessions for a project.

**Response:**
```json
[
  {
    "session_id": "a1b2c3d4-...",
    "session_number": 1,
    "session_type": "initializer",
    "status": "completed",
    "created_at": "2025-12-16T12:00:00Z",
    "completed_at": "2025-12-16T12:15:00Z"
  },
  {
    "session_id": "b2c3d4e5-...",
    "session_number": 2,
    "session_type": "coding",
    "status": "running",
    "created_at": "2025-12-16T12:20:00Z"
  }
]
```

---

#### `GET /api/projects/{project_id}/sessions/{session_id}`
Get details for a specific session.

**Response:**
```json
{
  "session_id": "a1b2c3d4-...",
  "session_number": 1,
  "session_type": "initializer",
  "status": "completed",
  "model": "claude-opus-4-5-20251101",
  "sandbox_type": "docker",
  "created_at": "2025-12-16T12:00:00Z",
  "completed_at": "2025-12-16T12:15:00Z",
  "metadata": {
    "tool_use_count": 42,
    "tasks_completed": 0,
    "tests_passed": 0
  }
}
```

### WebSocket

#### `WS /api/ws/{project_id}`
WebSocket connection for real-time progress and session updates.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws/550e8400-...');
```

**Event Types:**

**1. Session Started**
```json
{
  "type": "session_started",
  "session_id": "a1b2c3d4-...",
  "session_number": 1,
  "session_type": "initializer"
}
```

**2. Tool Use** (incremental count)
```json
{
  "type": "tool_use",
  "tool_name": "Read",
  "count": 15
}
```

**3. Assistant Message** (streaming)
```json
{
  "type": "assistant_message",
  "content": "I'm implementing the authentication module...",
  "timestamp": "2025-12-16T12:30:45Z"
}
```

**4. Progress Update** (task/test completion)
```json
{
  "type": "progress_update",
  "progress": {
    "total_tasks": 143,
    "completed_tasks": 42,
    "total_tests": 187,
    "passing_tests": 42,
    "task_completion_pct": 29.4,
    "test_pass_pct": 22.5
  }
}
```

**5. Session Complete**
```json
{
  "type": "session_complete",
  "session_id": "a1b2c3d4-...",
  "status": "completed",
  "duration_seconds": 245
}
```

**6. Session Error**
```json
{
  "type": "session_error",
  "session_id": "a1b2c3d4-...",
  "error": "Error message",
  "details": "..."
}
```

**Example React Hook:**
```typescript
import { useWebSocket } from '@/lib/websocket';

function ProjectDetail({ projectId }) {
  const { events, isConnected } = useWebSocket(projectId);

  useEffect(() => {
    const latest = events[events.length - 1];
    if (latest?.type === 'tool_use') {
      console.log(`Tool count: ${latest.count}`);
    }
  }, [events]);

  return <div>Connected: {isConnected ? 'Yes' : 'No'}</div>;
}
```

## Architecture

```
┌─────────────────────────────────────────┐
│   Client Layer                          │
│   - Next.js Web UI (port 3000)         │
│   - Third-party API clients           │
│   - Third-party integrations           │
└─────────────────┬───────────────────────┘
                  │ HTTP / WebSocket
┌─────────────────▼───────────────────────┐
│   FastAPI Server (port 8000)            │
│   - REST endpoints                      │
│   - WebSocket event streaming           │
│   - CORS middleware                     │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│   AgentOrchestrator (orchestrator.py)   │
│   - Session lifecycle management        │
│   - Separate init/coding workflows      │
│   - WebSocket event broadcasting        │
│   - Stale session cleanup               │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│   Database Layer (database.py)          │
│   - Async operations                    │
│   - Connection pooling (10-20 conns)    │
│   - Type-aware thresholds               │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│   PostgreSQL Database                   │
│   - Projects, epics, tasks, tests       │
│   - Sessions, reviews, commits          │
│   - JSONB metadata                      │
│   - Views: v_progress, v_next_task      │
└─────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Separate Endpoints for Init/Coding
- `/initialize` - Session 0 only (initialization), never auto-continues
- `/coding/start` - Sessions 1+ (coding) with auto-continue loop
- Clear separation of concerns
- Better user control

### 2. Real-Time WebSocket Events
- Tool use counter updates live
- Assistant messages stream
- Progress updates immediate
- Low latency (<50ms)

### 3. Type-Aware Thresholds
- Initialization: 2+ hours before marked stale
- Coding: 20+ minutes before marked stale
- Automatic cleanup of abandoned sessions

### 4. PostgreSQL Migration Complete
- UUID-based project identification
- Async operations with connection pooling
- JSONB for flexible metadata
- Production-ready architecture

## Security

**Current Status:** Open API (development mode)

**Recommendations for Production:**
- Add JWT token authentication
- Implement API key system
- Enable rate limiting (slowapi)
- Restrict CORS origins
- Use HTTPS with reverse proxy

## Development

### Running Tests

```bash
# Start server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal
python api/test_api.py
```

### Adding New Endpoints

1. Add route handler to `api/main.py`
2. Define Pydantic models for request/response
3. Use `orchestrator` for business logic
4. Add error handling (HTTPException)
5. Update this documentation

### Example New Endpoint

```python
@app.get("/api/projects/{project_id}/tasks")
async def list_tasks(project_id: str):
    """List all tasks for a project."""
    try:
        project_path = generations_dir / project_id
        db = get_database(project_path)
        tasks = db.get_all_tasks()
        return tasks
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Project not found")
```

## Production Deployment

### Recommendations

1. **Use production ASGI server:**
   ```bash
   gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker
   ```

2. **Enable authentication:**
   - Add FastAPI security dependencies
   - Implement JWT or API key authentication
   - Restrict CORS origins

3. **Add rate limiting:**
   - Use slowapi or similar
   - Limit requests per IP/user

4. **Enable HTTPS:**
   - Use nginx or Caddy as reverse proxy
   - Obtain SSL certificate (Let's Encrypt)

5. **Monitor & Log:**
   - Add structured logging
   - Monitor endpoint performance
   - Track error rates

6. **Database:**
   - Consider PostgreSQL for multi-user scenarios
   - Use connection pooling
   - Implement backups

### Example Nginx Configuration

```nginx
server {
    listen 80;
    server_name api.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Troubleshooting

### "Connection refused"
**Cause:** API server not running or port in use

**Solution:**
```bash
# Check if server is running
lsof -i :8000

# Start server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Check logs (server logs to stdout)
```

### "Project not found" (404)
**Cause:** Invalid project_id or project doesn't exist

**Solution:**
```bash
# List all projects
curl http://localhost:8000/api/projects

# Check database
psql $DATABASE_URL -c "SELECT project_id, name FROM projects;"
```

### "Project already initialized" (400)
**Cause:** Trying to initialize an already initialized project

**Solution:**
- Use `/initialize/cancel` to reset
- Or create a new project

### "Session already running" (409)
**Cause:** Trying to start session while another is active

**Solution:**
```bash
# Check active sessions
curl http://localhost:8000/api/projects/{project_id}/sessions

# Stop coding sessions
curl -X POST http://localhost:8000/api/projects/{project_id}/coding/stop

# Cancel initialization
curl -X POST http://localhost:8000/api/projects/{project_id}/initialize/cancel
```

### WebSocket disconnects immediately
**Cause:** Invalid project_id or CORS issue

**Solution:**
- Verify project exists
- Check browser console for errors
- Ensure WebSocket URL uses `ws://` (not `wss://` in dev)

### "Database connection error"
**Cause:** PostgreSQL not running or wrong DATABASE_URL

**Solution:**
```bash
# Start PostgreSQL
docker-compose up -d

# Check connection
psql $DATABASE_URL -c "SELECT 1;"

# Verify environment variable
echo $DATABASE_URL
```

### Stale sessions not cleaning up
**Cause:** Background task not running or wrong thresholds

**Solution:**
- Check API logs for cleanup task errors
- Verify `cleanup_stale_sessions` is enabled
- Check thresholds in `orchestrator.py`

## Version History

**v2.1.0** (December 2025)
- ✅ JWT authentication with development mode
- ✅ Project name validation (lowercase, alphanumeric, hyphens, underscores)
- ✅ Protected endpoints with token-based auth
- ✅ Session logs API enhancements (JSONL raw content)
- ✅ Enhanced error handling and validation

**v2.0.0** (December 2025)
- ✅ Phase 2: Frontend integration complete
- ✅ Real-time WebSocket events (tool_use, assistant_message)
- ✅ Smart session controls (init vs coding)
- ✅ Three-tab session interface

**v1.5.0** (December 2025)
- ✅ Phase 1: Backend refactor complete
- ✅ Separate endpoints (/initialize, /coding/start)
- ✅ Type-aware stale session thresholds
- ✅ Enhanced WebSocket event types

**v1.0.0** (December 2025)
- ✅ PostgreSQL migration complete
- ✅ Async database operations
- ✅ WebSocket support
- ✅ API-first architecture

## Related Documentation

- [Main README](../README.md) - Platform overview
- [CLAUDE.md](../CLAUDE.md) - Developer guide
- [Developer Guide](../docs/developer-guide.md) - Technical deep-dive
- [MCP Task Manager](../mcp-task-manager/README.md) - Task management server
- [Web UI](../web-ui/README.md) - Next.js frontend

## License

Same as parent project.
