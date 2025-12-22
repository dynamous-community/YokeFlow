# Docker Sandbox Implementation

**Target Audience:** Developers who want to understand or extend the Docker sandbox functionality.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Container Lifecycle](#container-lifecycle)
4. [How It Works](#how-it-works)
5. [Implementation Details](#implementation-details)
6. [Agent Integration](#agent-integration)
7. [Performance Considerations](#performance-considerations)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)
10. [Extending the System](#extending-the-system)

---

## Overview

### Problem Statement

When the autonomous agent generates applications that use API keys (e.g., Claude API integration), those environment variables can leak into the parent agent process during testing. This causes:

1. **Authentication conflicts**: Generated app's API keys override agent's credentials
2. **Session failures**: Subsequent agent sessions use wrong API key
3. **Security risk**: Secrets from generated apps persist in agent environment

**Example scenario:**
```
Session 1: Agent generates a chatbot app that uses ANTHROPIC_API_KEY
Session 2: Agent tests the chatbot by running it
Session 3: ANTHROPIC_API_KEY from chatbot is now in agent's environment
Session 4: Agent fails with "credit balance too low" (using chatbot's API key)
```

### Solution

Execute all agent commands inside isolated Docker containers with:
- **Separate filesystem** (no path conflicts)
- **Separate environment variables** (no leakage)
- **Volume mounts** (file persistence across sessions)
- **Resource limits** (CPU, memory control)
- **No session duration limits** (containers run indefinitely)

### Why Docker?

**Advantages for our use case:**
- ✅ **No session duration limits** - containers run as long as needed (hours, days)
- ✅ **Zero cloud costs** - runs on local hardware or your own server
- ✅ **Full control** - direct Docker access for debugging
- ✅ **Simple architecture** - standard Docker commands everyone knows
- ✅ **Instant file sync** - volume mounts = zero latency file operations
- ✅ **Network isolation options** - can restrict outbound access
- ✅ **Unlimited sessions** - only limited by host resources

**Compared to cloud alternatives:**
- E2B: Session limits (1hr free, 24hr pro), per-second billing, network latency
- Managed Kubernetes: Higher complexity, overhead for single-user development

Docker is optimal for long-running autonomous coding sessions where multi-hour unattended operation is required.

---

## Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                   Orchestrator                          │
│  - Manages agent session lifecycle                     │
│  - Creates/destroys Docker containers per session      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Sandbox Manager                         │
│  - Factory for sandbox instances                       │
│  - Types: LocalSandbox, DockerSandbox, E2BSandbox      │
└────────────────────┬────────────────────────────────────┘
                     │
                     ↓
┌─────────────────────────────────────────────────────────┐
│                 Docker Container                        │
│  - Image: node:20-slim (configurable)                  │
│  - Volume: /workspace → project directory               │
│  - Network: bridge (isolated)                           │
│  - Limits: 2GB RAM, 2.0 CPU (configurable)             │
└─────────────────────────────────────────────────────────┘
```

### Component Flow

```
1. Session Start
   └→ Orchestrator.start_session()
      └→ SandboxManager.create_sandbox(type="docker")
         └→ DockerSandbox.start()
            └→ docker run --name autonomous-agent-{project} \
                         --volume {project_dir}:/workspace \
                         node:20-slim

2. Agent Execution
   └→ create_client(docker_container="autonomous-agent-{project}")
      └→ MCP server receives DOCKER_CONTAINER_NAME env var
         └→ Agent sees bash_docker tool in system prompt
            └→ Agent uses bash_docker for all commands
               └→ docker exec autonomous-agent-{project} /bin/bash -c "{command}"

3. Session End
   └→ DockerSandbox.stop()
      └→ docker stop autonomous-agent-{project}
         └→ docker rm autonomous-agent-{project}
```

---

## Container Lifecycle

### Current Implementation

**Container Recreation Per Session:**

The current implementation creates a **fresh container for each session**:

1. **Session N starts:**
   - Create new `sandbox` object
   - Call `sandbox.start()`
   - Remove old container (if exists)
   - Create fresh container with `sleep infinity`
   - Run setup: `apt-get update`, install packages (~30-60s)
   - Mount project directory at `/workspace`

2. **During session:**
   - Execute commands via `docker exec`
   - Files sync via volume mount (bidirectional, instant)
   - Container stays running

3. **Session N ends:**
   - Container left running (`sleep infinity`)
   - Files persisted on host (volume mount)

4. **Session N+1 starts:**
   - **Destroy previous container completely**
   - Create brand new container
   - Re-run setup (apt-get, npm, etc.)
   - Mount same project directory

**Container naming:** `autonomous-agent-{project-name}` (unique per project)

### Why This Design?

- ✅ **Clean slate** - no stale processes, no leftover state
- ✅ **Reproducibility** - each session starts identically
- ✅ **No session limit** - containers run indefinitely during session
- ✅ **Simple lifecycle** - no complex state management

**Tradeoff:** ~30-60 seconds overhead per session for package installation (acceptable for clean environment guarantees)

### Initialization Overhead

From `sandbox_manager.py` - `_setup_container()`:

```bash
apt-get update -qq
apt-get install -y -qq git curl build-essential python3 python3-pip procps lsof jq sqlite3
npm install -g pnpm npm
```

**Time cost:** ~30-60 seconds per session

### Current Optimizations

**✅ Port Cleanup:**
```bash
# Kill stray processes from interrupted sessions
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
lsof -ti:3001 | xargs kill -9 2>/dev/null || true
```

**✅ Container Reuse (within session):**
- MCP `bash_docker` tool uses `docker exec` (not creating new containers)
- Same container for entire session = consistent state

**✅ Volume Mounting:**
- Project directory mounted at `/workspace`
- Read/Write/Edit tools work on host (no escaping issues)
- bash_docker runs in container (has all tools)

**✅ Resource Limits:**
```python
mem_limit=self.memory_limit,  # Default: 2g
nano_cpus=int(float(self.cpu_limit) * 1e9),  # Default: 2.0
```

### Future Optimization Opportunity

**Container Reuse Across Sessions:**

Instead of recreating containers, reuse them:

```python
# Try to reuse existing container
try:
    container = self.client.containers.get(self.container_name)
    if container.status == 'running':
        self.container_id = container.id
        self.is_running = True
        logger.info(f"Reusing existing container: {self.container_name}")
        return  # Exit early, don't recreate
except docker.errors.NotFound:
    pass  # Container doesn't exist, create below
```

**Benefits:**
- Eliminate 30-60s package installation overhead
- Sessions start instantly (just `docker exec`)
- Preserve installed packages, node_modules, etc.

**Tradeoffs:**
- Stale state could accumulate (orphaned processes, env vars)
- Need robust cleanup at session start
- Debugging harder (what's from this session vs previous?)

**Mitigation:**
```bash
# Enhanced cleanup at session start
docker exec $container pkill -9 node
docker exec $container pkill -9 npm
docker exec $container pkill -9 python
docker exec $container sh -c 'rm -rf /tmp/*'
```

**Verdict:** Worth implementing for significant time savings (~30-60s per session = 5-10 min/day saved).

---

## How It Works

### 1. Container Lifecycle Management

**File:** `sandbox_manager.py`

**DockerSandbox class:**
- **start()**: Creates container with project directory mounted as volume
- **stop()**: Stops and removes container
- **execute_command()**: Runs commands via `docker exec`

**Key features:**
- Container name: `autonomous-agent-{project-name}` (unique per project)
- Volume mount: `{host_path} → /workspace` (bidirectional sync)
- Working directory: `/workspace` (all commands run here)
- Auto-cleanup: Old containers removed before creating new ones

**Container configuration:**
```python
container = client.containers.run(
    image="node:20-slim",
    command="sleep infinity",  # Keep container alive
    name=f"autonomous-agent-{project_name}",
    detach=True,
    volumes={
        str(project_dir.resolve()): {
            "bind": "/workspace",
            "mode": "rw"
        }
    },
    working_dir="/workspace",
    mem_limit="2g",
    nano_cpus=2_000_000_000,  # 2.0 CPU
    environment={
        "HOME": "/root",
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    }
)
```

### 2. Custom MCP Tool Approach

**Why not use SDK hooks?**

Initial attempts to intercept the Bash tool via SDK hooks failed because:

1. **Two-process architecture**: Python agent spawns Node.js CLI subprocess
2. **Tool execution in CLI**: Bash commands run in Node.js process, not Python
3. **Hook limitations**: PreToolUse hooks can block but cannot override results
4. **No communication channel**: Python hooks can't pass results back from Docker

**See:** `SANDBOX_INVESTIGATION_SUMMARY.md` for full investigation details.

**Solution: bash_docker MCP tool**

Create a custom tool that explicitly executes commands in Docker:

```typescript
// mcp-task-manager/src/index.ts
{
  name: 'bash_docker',
  description: 'Execute a bash command in the Docker sandbox',
  inputSchema: {
    type: 'object',
    properties: {
      command: {
        type: 'string',
        description: 'The bash command to execute'
      }
    }
  }
}
```

**Implementation:**
```typescript
case 'bash_docker':
  const containerName = process.env.DOCKER_CONTAINER_NAME;
  const command = args?.command as string;

  // Execute via docker exec
  const dockerCommand = `docker exec ${containerName} /bin/bash -c ${JSON.stringify(command)}`;
  const { stdout, stderr } = await execAsync(dockerCommand);

  return {
    content: [{
      type: 'text',
      text: stdout + stderr
    }]
  };
```

**Key insight:** By making it a separate tool, the agent can explicitly choose when to use Docker execution. This is cleaner than trying to override the built-in Bash tool.

### 3. Agent Instruction via System Prompt

**File:** `client.py`

When Docker sandbox is active, the system prompt is enhanced with Docker-specific guidance:

```python
def create_client(project_dir: Path, model: str, docker_container: str = None):
    # Base system prompt
    base_prompt = "You are an expert full-stack developer..."

    # Append Docker guidance if sandbox active
    if docker_container:
        docker_prompt_path = Path("prompts/docker_prompt.md")
        docker_guidance = docker_prompt_path.read_text()
        system_prompt = f"{base_prompt}\n\n{docker_guidance}"

    # Pass container name to MCP server
    mcp_servers = {
        "task-manager": {
            "command": "node",
            "args": [str(mcp_server_path)],
            "env": {
                "DOCKER_CONTAINER_NAME": docker_container,
                # ...
            }
        }
    }
```

**Docker guidance content** (`prompts/docker_prompt.md`):
- **Use bash_docker tool** instead of regular Bash
- **Avoid heredocs** (they break in docker exec)
- **Use printf/echo** for file creation (not Write/Edit tools)
- **Missing utilities** (jq, lsof not in minimal images)

**Why this approach works:**
1. Agent sees bash_docker tool available
2. System prompt tells agent to use it
3. Agent automatically chooses bash_docker (tested in E2E tests)
4. No explicit prompting needed per command

### 4. Environment Variable Passing

**Container name propagation:**

```
Orchestrator (orchestrator.py)
  ↓ docker_container="autonomous-agent-myproject"
create_client (client.py)
  ↓ env={"DOCKER_CONTAINER_NAME": "autonomous-agent-myproject"}
MCP Server (mcp-task-manager/src/index.ts)
  ↓ process.env.DOCKER_CONTAINER_NAME
bash_docker tool
  ↓ docker exec autonomous-agent-myproject /bin/bash -c "..."
```

**Why environment variables?**
- MCP servers receive environment configuration
- Clean separation of concerns
- Easy to add E2B_SANDBOX_ID later for E2B support

### 5. Volume Mount Persistence

**How files persist:**

```
Session 1:
  1. Create container with volume mount
  2. Agent runs: npm init, npm install
  3. Files written to /workspace → synced to host
  4. Container destroyed

Session 2:
  1. Create NEW container with SAME volume mount
  2. /workspace contains files from Session 1
  3. node_modules/, package.json already exist
  4. Agent continues work

Session 3+:
  ... same pattern
```

**Benefits:**
- No manual file sync needed
- Near-instant bidirectional updates
- Works with any file size
- Survives container restarts

**Volume mount configuration:**
```python
volumes={
    str(project_dir.resolve()): {
        "bind": "/workspace",
        "mode": "rw"  # read-write
    }
}
```

---

## Implementation Details

### Files Modified/Created

**Core Implementation:**

| File | Purpose | Lines |
|------|---------|-------|
| `sandbox_manager.py` | Sandbox abstraction layer with Docker, Local, E2B backends | 423 |
| `mcp-task-manager/src/index.ts` | bash_docker tool implementation | 308-648 |
| `client.py` | Docker-aware client configuration, system prompt enhancement | 59-150 |
| `orchestrator.py` | Container lifecycle integration with sessions | 406-442 |
| `prompts/docker_prompt.md` | Agent guidance for Docker-specific workflow | 145 |

**Configuration:**

| File | Purpose |
|------|---------|
| `.autonomous-coding.yaml` | Sandbox type, image, resources configuration |
| `config.py` | Config loading and validation |

**Testing:**

| File | Purpose |
|------|---------|
| `tests/test_bash_docker.py` | Direct tool testing (3 commands) |
| `tests/test_e2e_sandbox.py` | End-to-end agent usage test |

### Configuration Options

**File:** `.autonomous-coding.yaml`

```yaml
sandbox:
  type: docker          # "none", "docker", or "e2b"
  docker_image: node:20-slim
  docker_network: bridge
  docker_memory_limit: 2g
  docker_cpu_limit: "2.0"
```

**Sandbox types:**

| Type | Description | Use Case |
|------|-------------|----------|
| `none` / `local` | No isolation, commands run on host | Local development, debugging |
| `docker` | Docker container isolation | Testing, single-user development |
| `e2b` | E2B cloud sandbox | Production, multi-tenant deployment |

**Docker image requirements:**
- Base: Any image with `/bin/bash` and volume mount support
- Recommended: `node:20-slim` (Node.js apps)
- Alternative: `python:3.11-slim` (Python apps)
- Custom: Build your own with required dependencies

**Resource limits:**
- Memory: Prevents OOM on host (default: 2GB)
- CPU: Prevents runaway processes (default: 2.0 cores)
- Adjustable based on project needs

### Docker Client Configuration

**Socket path detection:**

```python
# Auto-detect Docker socket from context
result = subprocess.run(['docker', 'context', 'inspect'],
                       capture_output=True, text=True)
context = json.loads(result.stdout)[0]
socket_path = context['Endpoints']['docker']['Host']

# Create client with custom socket
client = docker.DockerClient(base_url=socket_path)
```

**Why this matters:**
- Handles non-standard Docker setups (external SSD, custom paths)
- Works with Docker Desktop, Colima, or remote Docker
- Fallback to `docker.from_env()` if context fails

### Container Setup

**Automated dependency installation:**

```python
async def _setup_container(self):
    """Install basic dependencies in the container."""
    setup_commands = [
        "apt-get update -qq",
        "apt-get install -y -qq git curl build-essential python3 python3-pip",
        "npm install -g pnpm npm",
    ]

    for cmd in setup_commands:
        result = await self.execute_command(cmd, timeout=120)
        if result["returncode"] != 0:
            logger.warning(f"Setup command failed: {cmd}")
```

**Why this is needed:**
- Minimal images (node:20-slim) don't include git, curl, etc.
- Agent may need these for cloning, downloading, building
- Better to install once at startup than fail mid-session

**Tradeoffs:**
- ✅ Faster than custom image builds
- ✅ Flexible (works with any base image)
- ❌ Adds 30-60s to session startup
- ❌ Downloads repeated per session

**Alternative:** Build custom image with dependencies baked in:
```dockerfile
FROM node:20-slim
RUN apt-get update && apt-get install -y git curl build-essential
RUN npm install -g pnpm
```

---

## Agent Integration

### How Agent Learns to Use bash_docker

**Three mechanisms:**

1. **Tool availability** - MCP server registers bash_docker
2. **System prompt** - Explicit instruction to use bash_docker when Docker active
3. **Agent intelligence** - Claude chooses appropriate tool automatically

**Evidence from E2E testing:**

```python
# test_e2e_sandbox.py
async with client:
    await client.query("Run the command: pwd")

    async for msg in client.receive_response():
        if msg_type == "AssistantMessage":
            for block in msg.content:
                if block_type == "ToolUseBlock":
                    tool_name = block.name
                    # Agent chose bash_docker automatically!
                    assert tool_name == "mcp__task-manager__bash_docker"
```

**No explicit "use bash_docker" in the query** - agent inferred from system prompt.

### Prompt Engineering for Docker

**Key challenges solved by prompts/docker_prompt.md:**

1. **Heredoc syntax errors**
   - Problem: `cat << EOF` breaks in docker exec
   - Solution: Use `printf 'line\n' >> file` instead

2. **Write/Edit tool failures**
   - Problem: Tools run on host, can't access /workspace in container
   - Solution: Use bash_docker with printf/echo for file creation

3. **Missing utilities**
   - Problem: lsof, jq, fuser not in minimal images
   - Solution: Use alternatives (curl for port checks, grep for JSON)

**Example guidance:**

```markdown
### ✅ CORRECT: Use bash_docker with printf

printf 'const express = require("express");\n' > server.js
printf 'const app = express();\n' >> server.js

### ❌ AVOID: Heredocs

cat > server.js << 'EOF'
const express = require("express");
EOF
```

**Impact measurement:**
- **Before prompt**: 5-10 trial-and-error attempts per file creation
- **After prompt**: First attempt usually succeeds
- **Evidence**: Session 1-2 logs show immediate correct usage

### Error Handling

**Docker command failures:**

```typescript
try {
  const { stdout, stderr } = await execAsync(dockerCommand);
  return { content: [{ type: 'text', text: stdout + stderr }] };
} catch (error: any) {
  // Return error with stdout/stderr
  let errorOutput = error.stdout || error.stderr || error.message;
  return {
    content: [{ type: 'text', text: errorOutput }],
    isError: true
  };
}
```

**Agent receives errors and can retry:**
- Tool returns error flag
- Agent sees error message
- Agent can adjust command and retry
- Follows standard MCP error pattern

---

## Performance Considerations

### Startup Time Comparison

| Approach | Startup Time | Benefits | Tradeoffs |
|----------|--------------|----------|-----------|
| **Current (recreate)** | 30-60s | Clean state, reproducible | Overhead per session |
| **Container reuse** | <5s | Fast, preserves packages | Potential stale state |
| **Container pooling** | <2s | Instant, pre-warmed | Memory overhead, complexity |
| **Cloud sandboxes (E2B)** | ~150ms | Managed, scalable | Cost, session limits |

### Cost Comparison

**Scenario:** 20 sessions averaging 1.2 hours each (24-hour project)

| Solution | Setup Cost | Runtime Cost | Total |
|----------|-----------|--------------|-------|
| **Docker (current)** | $0 | $0 | **$0** |
| **Docker (optimized)** | 2-3 hours dev | $0 | **$0** |
| **E2B Pro** | $150/month | ~$80-100 | **$230-250/month** |

**Winner:** Docker - $0 cost, unlimited sessions, perfect for autonomous workflows.

### File Sync Performance

**Volume mounts (current):**
- Instant bidirectional updates
- Works with any file size
- Zero network latency
- Native filesystem performance

**Cloud alternatives:**
- Upload/download overhead
- Network latency considerations
- File size limitations

### Resource Isolation

**Docker provides:**
- Memory limits (default: 2GB)
- CPU limits (default: 2.0 cores)
- Network isolation options
- Filesystem separation

**Monitoring:**
```python
# Get container resource usage
docker stats autonomous-agent-{project}
```

---

## Testing

### Unit Tests

**File:** `tests/test_bash_docker.py`

**What it tests:**
1. Container name environment variable passing
2. Command execution in Docker (pwd, whoami, echo)
3. Output correctness (/workspace path)

**How to run:**
```bash
python tests/test_bash_docker.py
```

**Expected output:**
```
✅ Test 1: pwd
Output: /workspace

✅ Test 2: whoami
Output: root

✅ Test 3: echo
Output: Hello from Docker
```

### Integration Tests

**File:** `tests/test_e2e_sandbox.py`

**What it tests:**
1. Agent receives Docker system prompt
2. Agent automatically chooses bash_docker tool
3. Commands execute in container (not host)

**How to run:**
```bash
python tests/test_e2e_sandbox.py
```

**What to verify:**
- Agent uses `mcp__task-manager__bash_docker` (not `Bash`)
- Output shows `/workspace` (not host path)
- No manual prompting needed

### Real-World Validation

**Test project:** `specs/docker-sandbox-test.txt`

**What it tests:**
- Small 3-epic todo API project
- Multiple sessions (initialization + 3-6 coding sessions)
- File persistence across container restarts
- Volume mount correctness

**How to run:**
```bash
# Via CLI
python autonomous_agent.py --project-dir generations/docker-test \
                          --spec specs/docker-sandbox-test.txt

# Via API
# 1. Create project via Web UI with docker-sandbox-test.txt
# 2. Start initialization session
# 3. Start coding sessions
```

**What to monitor:**
```bash
# Watch containers
watch -n 1 'docker ps | grep autonomous-agent'

# Check container paths
docker exec autonomous-agent-docker-test pwd
# Should output: /workspace

# Watch logs
tail -f generations/docker-test/logs/session_*.txt
```

### Manual Testing Checklist

**Basic functionality:**
- [ ] Container created with correct name
- [ ] Volume mount working (files persist)
- [ ] Commands return Docker paths (/workspace)
- [ ] Container cleaned up after session

**Agent behavior:**
- [ ] Agent uses bash_docker tool automatically
- [ ] Agent avoids heredocs (uses printf)
- [ ] Agent handles missing utilities gracefully
- [ ] Sessions complete without Docker-related errors

**Error handling:**
- [ ] Container creation failures logged clearly
- [ ] Command failures returned to agent
- [ ] Cleanup happens even on errors
- [ ] Stale containers removed on restart

---

## Troubleshooting

### Common Issues

#### 1. "Docker daemon not running"

**Symptom:**
```
Failed to start Docker sandbox: Error while fetching server API version
```

**Solutions:**
- Start Docker Desktop / Colima
- Check `docker ps` works from terminal
- Verify DOCKER_HOST environment variable

#### 2. "Container already exists"

**Symptom:**
```
Conflict. The container name autonomous-agent-myproject is already in use
```

**Solution:**
```bash
# Remove old container
docker rm -f autonomous-agent-myproject

# Or let the code auto-cleanup (it tries to remove old containers)
```

**Root cause:** Previous session crashed without cleanup

#### 3. "Permission denied" on volume mount

**Symptom:**
```
docker: Error response from daemon: Mounts denied
```

**Solution:**
- Docker Desktop: Add project directory to File Sharing settings
- Linux: Check directory ownership and permissions
- SELinux: May need `:z` suffix on volume mount

#### 4. Agent uses Bash instead of bash_docker

**Symptom:**
- Commands execute on host (not in container)
- Paths show host directory (not /workspace)

**Debug steps:**
1. Check `docker_container` parameter passed to create_client()
2. Verify DOCKER_CONTAINER_NAME env var in MCP server
3. Check system prompt includes Docker guidance
4. Look for bash_docker in agent's tool list

**Solution:**
- Ensure DockerSandbox created and started
- Verify container name passed through orchestrator → client → MCP
- Check prompts/docker_prompt.md exists

#### 5. "Command not found" in container

**Symptom:**
```
/bin/sh: lsof: not found
/bin/sh: jq: not found
```

**Solution:**
- Install in container: `apt-get install -y lsof jq`
- Or use alternatives (see prompts/docker_prompt.md)
- Or build custom image with dependencies

**Best practice:** Add to `_setup_container()` if commonly needed

### Debug Logging

**Enable verbose logging:**

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Key log messages:**

```
INFO - DockerSandbox started: autonomous-agent-myproject (ID: abc123...)
INFO - [bash_docker] Executing in container: pwd
INFO - [bash_docker] Command executed successfully
INFO - DockerSandbox stopped: autonomous-agent-myproject
```

**MCP server logs:**

```bash
# Check stderr from task-manager MCP server
# Logged to Claude SDK output
[bash_docker] Executing in container autonomous-agent-myproject: npm install
```

### Inspecting Containers

**List running containers:**
```bash
docker ps | grep autonomous-agent
```

**Execute command in container:**
```bash
docker exec autonomous-agent-myproject pwd
docker exec autonomous-agent-myproject ls -la /workspace
```

**View container logs:**
```bash
docker logs autonomous-agent-myproject
```

**Inspect container configuration:**
```bash
docker inspect autonomous-agent-myproject | jq '.[0].Mounts'
docker inspect autonomous-agent-myproject | jq '.[0].HostConfig.Memory'
```

---

## Extending the System

### Adding E2B Support

**File:** `sandbox_manager.py`

**Current stub:**
```python
class E2BSandbox(Sandbox):
    async def start(self):
        raise NotImplementedError("E2B sandbox not yet implemented")
```

**Implementation steps:**

1. **Install E2B SDK:**
   ```bash
   pip install e2b
   ```

2. **Implement start():**
   ```python
   from e2b import Sandbox

   async def start(self):
       self.e2b_sandbox = Sandbox(
           template="nodejs",
           timeout=3600  # 1 hour
       )

       # Upload project files
       await self.sync_directory("to_sandbox")

       self.is_running = True
   ```

3. **Implement execute_command():**
   ```python
   async def execute_command(self, command, timeout=None):
       result = await self.e2b_sandbox.run(
           f"cd /workspace && {command}",
           timeout=timeout
       )
       return {
           "stdout": result.stdout,
           "stderr": result.stderr,
           "returncode": result.exit_code
       }
   ```

4. **Add MCP tool:**
   ```typescript
   // Similar to bash_docker but for E2B
   case 'bash_e2b':
       const sandboxId = process.env.E2B_SANDBOX_ID;
       // Call E2B API via SDK
   ```

5. **Update configuration:**
   ```yaml
   sandbox:
     type: e2b
     e2b_api_key: ${E2B_API_KEY}
     e2b_template: nodejs
   ```

**Challenges:**
- E2B has session limits (1 hour free, 24 hour pro)
- Need to handle pause/resume for long projects
- File upload/download instead of volume mounts
- Cost considerations ($0.0001 per second)

### Adding Custom Docker Images

**Why custom images?**
- Pre-install dependencies (faster startup)
- Include project-specific tools
- Optimize for specific stacks (Python, Go, Rust)

**Example: Python-focused image**

```dockerfile
# Dockerfile.python
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl build-essential \
    postgresql-client redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Install common Python tools
RUN pip install --no-cache-dir \
    poetry pytest black ruff mypy

WORKDIR /workspace
CMD ["sleep", "infinity"]
```

**Build and configure:**
```bash
docker build -f Dockerfile.python -t autonomous-agent-python:latest .
```

```yaml
# .autonomous-coding.yaml
sandbox:
  type: docker
  docker_image: autonomous-agent-python:latest
```

### Adding Resource Monitoring

**Goal:** Track resource usage per session

**Implementation:**

```python
class DockerSandbox(Sandbox):
    async def get_stats(self) -> Dict[str, Any]:
        """Get container resource usage statistics."""
        if not self.container_id:
            return {}

        container = self.client.containers.get(self.container_id)
        stats = container.stats(stream=False)

        return {
            "cpu_percent": self._calculate_cpu_percent(stats),
            "memory_usage_mb": stats['memory_stats']['usage'] / 1024 / 1024,
            "memory_limit_mb": stats['memory_stats']['limit'] / 1024 / 1024,
            "network_rx_bytes": stats['networks']['eth0']['rx_bytes'],
            "network_tx_bytes": stats['networks']['eth0']['tx_bytes'],
        }
```

**Track in database:**
```python
# orchestrator.py
async def start_session(...):
    # ... session execution ...

    # Get final stats
    stats = await sandbox.get_stats()
    metrics["resource_usage"] = stats

    await db.end_session(session_id, ..., metrics=metrics)
```

**Visualize in Web UI:**
- CPU usage graph per session
- Memory usage trends
- Network bandwidth tracking
- Alert on resource limit hits

### Adding Network Isolation

**Current:** Bridge network (containers can access internet)

**Options:**

1. **No network:**
   ```python
   container = client.containers.run(
       ...,
       network_mode="none"
   )
   ```
   - ✅ Complete isolation
   - ❌ Can't download dependencies

2. **Custom network with firewall:**
   ```bash
   docker network create --driver bridge \
       --subnet=172.20.0.0/16 \
       autonomous-agent-net
   ```
   ```python
   container = client.containers.run(
       ...,
       network="autonomous-agent-net"
   )
   ```
   - ✅ Control egress rules
   - ✅ Block specific domains
   - ⚠️ Requires Docker network setup

3. **HTTP proxy:**
   ```python
   environment={
       "HTTP_PROXY": "http://proxy:3128",
       "HTTPS_PROXY": "http://proxy:3128"
   }
   ```
   - ✅ Log all HTTP requests
   - ✅ Block malicious domains
   - ❌ Doesn't affect non-HTTP traffic

### Adding Snapshot/Restore

**Use case:** Save container state between sessions for faster restarts

**Implementation:**

```python
class DockerSandbox(Sandbox):
    async def snapshot(self, tag: str) -> str:
        """Create snapshot of current container state."""
        if not self.container_id:
            raise RuntimeError("No container running")

        container = self.client.containers.get(self.container_id)

        # Commit container to image
        image = container.commit(
            repository=f"autonomous-agent-snapshot",
            tag=tag
        )

        return image.id

    async def restore(self, snapshot_id: str) -> None:
        """Start container from snapshot."""
        container = self.client.containers.run(
            snapshot_id,
            command="sleep infinity",
            detach=True,
            volumes=self.volumes,
            # ... same config as start()
        )

        self.container_id = container.id
        self.is_running = True
```

**Use in orchestrator:**
```python
# After initialization session
snapshot_id = await sandbox.snapshot(tag="post-init")
await db.update_project(project_id, snapshot_id=snapshot_id)

# In coding sessions
if project.get('snapshot_id'):
    await sandbox.restore(project['snapshot_id'])
else:
    await sandbox.start()
```

**Benefits:**
- Skip npm install between sessions (15-60s saved)
- Preserve installed dependencies
- Faster session startup (2-5s vs 30-60s)

**Tradeoffs:**
- Disk usage (snapshots can be large)
- Requires cleanup policy
- Complexity in state management

---

## Future Enhancements

### Container Reuse Across Sessions

**Goal:** Eliminate 30-60s initialization overhead

**Benefits:**
- Sessions start instantly (just `docker exec`)
- Preserve installed packages, node_modules
- 5-10 minutes saved per day

**Implementation:** Modify `sandbox_manager.py` to check for existing running containers before recreating

**Effort:** 2-3 hours implementation + testing

### Resource Monitoring

**Goal:** Track CPU, memory, network usage per session

**Implementation:**
- Add `get_stats()` method to DockerSandbox
- Store metrics in sessions table
- Display in Web UI

**Effort:** 4-6 hours

### Snapshot/Restore

**Goal:** Save container state after initialization, restore for coding sessions

**Benefits:**
- Skip npm install between sessions (15-60s saved)
- Preserve development environment setup

**Implementation:**
- Use `container.commit()` after initialization
- Restore from image ID for coding sessions

**Effort:** 4-6 hours

### Network Isolation

**Goal:** Restrict outbound network access from containers

**Options:**
- Custom Docker network with firewall rules
- HTTP proxy for logging and filtering
- Whitelist for npm, github, etc.

**Effort:** 6-8 hours

---

## Related Documentation

- **Configuration**: [configuration.md](configuration.md) - Sandbox configuration options
- **MCP Tools**: [mcp-usage.md](mcp-usage.md) - MCP tool development
- **Docker Prompt**: [../prompts/docker_prompt.md](../prompts/docker_prompt.md) - Agent guidance for Docker
- **macOS Docker**: [macOS-docker-stability.md](macOS-docker-stability.md) - macOS-specific setup

---

**Questions or issues?** Open a GitHub issue or check the related documentation above.
