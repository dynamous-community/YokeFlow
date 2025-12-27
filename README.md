# YokeFlow - Autonomous AI Development Platform

[![License](https://img.shields.io/badge/License-YCL%20v1.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node-20%2B-green.svg)](https://nodejs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)](https://www.postgresql.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

Build complete applications using Claude across multiple autonomous sessions. Production-ready API-first architecture with modern Next.js web UI, database abstraction, and agent orchestration.

**Architecture:**
- 🏗️ **API-First Platform**: FastAPI REST API with WebSocket support
- 🎨 **Next.js Web UI**: Modern TypeScript/React interface with real-time updates
- 💾 **Database Abstraction**: Clean separation, PostgreSQL-ready
- 🎭 **Agent Orchestrator**: Decoupled session lifecycle management
- 🔌 **Dual Access**: Use via Web UI or CLI tools

**Key Features:**
- 🤖 Autonomous multi-session development
- 📊 Real-time progress monitoring via WebSocket
- 🔐 Secure blocklist approach for containerized deployment
- 📁 Hierarchical task management (epics → tasks → tests)
- 🎛️ Dual model strategy (Opus for planning, Sonnet for coding)
- 📝 Comprehensive session logging with human-readable durations
- ⚙️ YAML configuration file support
- 🛑 Graceful shutdown handling (Ctrl+C properly finalizes sessions)

**Originally forked from Anthropic's autonomous coding demo**, now evolved into YokeFlow with significant enhancements including API-first architecture, PostgreSQL database, agent orchestration, quality review system, and production-ready web interface.

## Upgrading from v1.0.0

**Important:** Version 1.1.0 includes database schema changes that are not backward compatible. If you are upgrading from v1.0.0:

1. **Export any projects you want to keep** (the generated code in `generations/` directory)
2. **Back up your database** if you want to preserve v1.0.0 data for reference
3. **Drop and recreate the database:**
   ```bash
   docker-compose down -v  # Remove volumes
   docker-compose up -d    # Start fresh PostgreSQL
   python scripts/init_database.py --docker  # Initialize schema
   ```
4. Start fresh with v1.1.0

**Why fresh install:** Several tables were modified or removed to improve the platform. Migration scripts have been removed as most users will start fresh with this wider release.

**Current Status: v1.1.0 - Production Ready (December 2025)**
- ✅ **PostgreSQL Migration**: 100% complete, production-ready async architecture
- ✅ **Docker Sandbox**: Full integration with 90+ sessions validated
- ✅ **API Foundation**: REST endpoints, WebSocket support, orchestrator, JWT authentication
- ✅ **Web UI v2.0**: **Production ready** - Complete and polished interface
  - ✅ Project creation with validation, initialization, and coding session control
  - ✅ Real-time session monitoring with WebSocket updates
  - ✅ Session logs viewer (Human/Events/Errors tabs) with download
  - ✅ Task detail views with epic/task/test hierarchy and drill-down
  - ✅ Quality dashboard with deep review recommendations
  - ✅ Project completion banner and celebration UI
  - ✅ JWT authentication with development mode
  - ✅ Toast notifications and confirmation dialogs (no more alert boxes)
  - ✅ Enhanced metrics (token breakdown, quality trends)
- ✅ **CLI Tools**: Fully functional for all operations
- ✅ **Review System** (4 Phases):
  - ✅ **Phase 1**: Quick quality checks (zero-cost, every session)
  - ✅ **Phase 2**: Automated deep reviews (every 5 sessions or quality < 7)
  - ✅ **Phase 3**: Quality dashboard with collapsible reviews and download
  - ✅ **Phase 4**: Prompt improvement analysis with single-project analysis
- 🎯 **Next Steps**: Complete pre-release testing, finalize documentation, make repository public

**Note:** This platform is production-ready. The Web UI provides full functionality for project management, monitoring, and quality analysis. Authentication, validation, and comprehensive testing ensure deployment readiness.

See [TODO-FUTURE.md](TODO-FUTURE.md) for post-release enhancements and [CLAUDE.md](CLAUDE.md) for comprehensive guide.

---

## Quick Start

### Prerequisites

**System Requirements:**
- **Node.js:** Version 20 LTS or newer ([Download](https://nodejs.org/))
- **Python:** Version 3.9 or newer
- **Docker:** For PostgreSQL database and sandboxing
- **Git:** For version control

```bash
# Verify Node.js version (must be 20+)
node --version  # Should show v20.x.x or newer

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Install Python dependencies
pip install -r requirements.txt

# Install Next.js web UI dependencies
cd web-ui
npm install
cp .env.local.example .env.local  # Configure web UI environment
cd ..

# Build MCP task manager server
cd mcp-task-manager
npm install
npm run build
cd ..

# Setup database
docker-compose up -d  # Start PostgreSQL
python scripts/init_database.py --docker  # Initialize schema

# Authenticate with Claude Code
claude setup-token

# Configure environment variables
cp .env.example .env
# Edit .env and set CLAUDE_CODE_OAUTH_TOKEN to your token from 'claude setup-token'
```

### Option 1: Web UI (Recommended)

**Use the production-ready web interface:**
```bash
# Terminal 1: Start the API server
python api/start_api.py
# Or: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# Runs on http://localhost:8000

# Terminal 2: Start the Next.js web UI
cd web-ui
npm run dev
# Open http://localhost:3000
```

**Authentication:**
- **Development Mode** (default): No password required, auto-bypasses login
- **Production Mode**: Set `UI_PASSWORD` in `.env` file to enable JWT authentication
- See [docs/authentication.md](docs/authentication.md) for details

**Features:**
- ✅ Create projects by uploading spec files with real-time validation
- ✅ Initialize projects (Session 0 - planning phase with Opus)
- ✅ Start/stop coding sessions with real-time monitoring
- ✅ View session logs (Human/Events/Errors tabs) with download
- ✅ WebSocket live updates for session progress
- ✅ Progress counters (epics/tasks/tests) with drill-down
- ✅ Task detail views with epic/task/test hierarchy
- ✅ Quality dashboard with collapsible deep reviews and markdown downloads
- ✅ **Screenshots gallery** - View all browser verification screenshots organized by task ID
- ✅ Project completion celebration banner
- ✅ JWT authentication (development mode enabled by default)
- ✅ Environment variable editor (inline .env editing)
- ✅ Enhanced metrics (token breakdown, quality trends)

**The Web UI is production-ready** with comprehensive features for project management and monitoring.

**macOS Sleep Prevention & Docker Stability (Important for Multi-Session Runs):**

When running autonomous sessions overnight or unattended, you need to prevent sleep AND ensure Docker stays running:

**Step 1: Prevent macOS Sleep (Complete Settings)**
```bash
# Mac Mini / iMac (Desktop): Disable ALL sleep-related features
sudo pmset -a disablesleep 1      # Disable system sleep
sudo pmset -a displaysleep 0       # Disable display sleep (CRITICAL for Docker!)
sudo pmset -a powernap 0           # Disable Power Nap
sudo pmset schedule cancelall      # Cancel scheduled sleep/wake events

# ALSO disable screen lock (prevents Docker throttling):
# System Settings → Lock Screen → "Require password after..." → Never
# Or via command line:
sysadminctl -screenLock off

# To re-enable all sleep features when done:
sudo pmset -a disablesleep 0
sudo pmset -a displaysleep 10
sudo pmset -a powernap 1
sysadminctl -screenLock on

# MacBook (Laptop): Use caffeinate (keeps lid open)
caffeinate -s uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Why display sleep matters:**
- Docker Desktop runs as a GUI app
- When display sleeps + screen locks, macOS throttles/suspends user-space processes
- This can suspend Docker's hypervisor/VM → PostgreSQL becomes unreachable
- Disabling display sleep AND screen lock prevents Docker throttling

**Step 2: Run Docker Watchdog (Recommended)**

Docker Desktop can crash even when the Mac doesn't sleep. The watchdog auto-restarts it:

```bash
# Terminal 3: Start Docker watchdog in background
./scripts/docker-watchdog.sh &

# It will:
# - Check Docker every 30 seconds
# - Auto-restart if Docker crashes
# - Restart PostgreSQL container
# - Log all events to docker-watchdog.log
```

**Why this matters:**
- Mac sleep stops Docker → PostgreSQL goes offline → sessions fail
- Docker Desktop can crash independently of sleep (especially on long runs)
- Watchdog ensures Docker recovers automatically without human intervention
- `pmset` is more reliable than System Preferences for desktop Macs

**Alternative to pmset:** Set System Preferences → Energy Saver → "Prevent computer from sleeping" (permanent setting)

See [docs/PREVENTING_MAC_SLEEP.md](docs/PREVENTING_MAC_SLEEP.md) for complete guide.

**Features:**
- ✅ **Create Projects**: Upload specification files (any .txt, .md format)
- ✅ **Start Sessions**: One-click session start with real-time progress
- ✅ **Monitor Progress**: Live updates via WebSocket (epics, tasks, tests)
- ✅ **Configure Environment**: Edit .env files directly in browser
- ✅ **View Logs**: Human-readable session logs with filtering
- ✅ **Manage Projects**: Browse, search, and delete projects

**The agent will:**
1. Read specification file(s)
2. Create complete roadmap (all epics, tasks, tests)
3. Generate .env.example with required environment variables
4. Stop after initialization for human review
5. Resume coding sessions with "Start Session" button

### Utility Scripts

Several utility scripts are available for development and debugging:

```bash
# View project progress (quick command-line check)
python scripts/task_status.py generations/my_project

# Reset stuck sessions (automatic cleanup also runs on session start)
python scripts/cleanup_sessions.py [--project my_project] [--force]

# Reset project to post-initialization state (for prompt iteration)
python scripts/reset_project.py --project my_project [--yes]

# Clean up Docker containers
python scripts/cleanup_containers.py
```

**Notes:**
- All project management is done via the Web UI (port 3000)
- Projects are stored in `generations/` directory
- Models are selected in the Web UI when creating/initializing projects
- Use Web UI for all normal operations (create, initialize, run sessions)

---

## How It Works

### Two-Phase Workflow

**Session 0 - Initialization (Opus):**
1. Reads `app_spec.txt` specification
2. Creates project in PostgreSQL database with hierarchical structure
3. Generates ALL epics (15-25 high-level features)
4. Expands ALL epics into tasks (100-300 tasks)
5. Adds tests for all tasks (200-1000 tests)
6. Creates project structure and `init.sh`
7. **Stops automatically** - complete roadmap ready

**Sessions 1+ - Coding (Sonnet):**
1. Gets next task from database
2. Implements feature
3. Verifies with browser automation
4. Updates database (marks tests pass/fail)
5. Commits to git
6. Auto-continues to next session (3s delay)

Press `Ctrl+C` to pause. Run the same command to resume.

### Hierarchical Task Management

```
📦 Epics (15-25)          "Core Chat Interface"
  └─ 📋 Tasks (8-15 each)    "Create message input component"
      └─ ✅ Tests (1-3 each)    "Verify textarea auto-resizes"
```

**Why?**
- Prevents token limit errors (was 60K, now ~5K per session)
- Complete visibility from day 1
- Accurate progress tracking
- MCP protocol-based (not shell scripts)

### Multiple Specification Files

For complex projects, you can upload multiple specification files:

**Best practices:**
1. **Name your main file** `main.md` or `spec.md`
2. **Reference other files** in your main spec:
   ```markdown
   ## API Design
   See `api-design.md` for detailed endpoint specifications.

   ## Database Schema
   See `database-schema.sql` for the complete schema.

   ## Code Examples
   See `example-auth.py` for authentication implementation patterns.
   ```

3. **Include supporting files**: API docs, schemas, code examples, wireframes, etc.

**Supported file types:**
- **Spec files**: `.txt`, `.md` (primary specification files)
- **Code examples**: `.py`, `.ts`, `.js`, `.tsx`, `.jsx` (reference implementations)
- **Config files**: `.json`, `.yaml`, `.yml`, `.sql`, `.sh` (schemas, scripts)
- **Styling**: `.css`, `.html` (design references)

**Example structure:**
```
main.md              # Main specification (read first)
api-design.md        # API endpoint definitions
database-schema.sql  # Database design
example-auth.py      # Authentication code example
example-api.ts       # API endpoint example
config-example.json  # Configuration template
wireframes.md        # UI mockups description
```

**How it works:**
- Files are saved to a `spec/` directory in your project
- The agent auto-detects the primary file (main.md, spec.md, or largest file)
- The agent reads the primary file first, then lazy-loads other files as needed
- This saves tokens and improves performance for large specifications

**See** [docs/example-specs.md](docs/example-specs.md) for detailed examples and `example-specs/multi-file-spec/` for a complete working example.

### Security Model

Designed for containerized deployment with blocklist approach:
- ✅ **Allows**: All development tools (npm, git, curl, etc.)
- ❌ **Blocks**: Dangerous system commands (rm, sudo, package managers)

Philosophy: Enable autonomous operation while maintaining safety.

---

## Configuration

### Configuration File (Recommended)

Create `.yokeflow.yaml` in your project directory or `~/.yokeflow.yaml` for global defaults:

```yaml
models:
  initializer: claude-opus-4-5-20251101
  coding: claude-sonnet-4-5-20250929

timing:
  auto_continue_delay: 3
  web_ui_poll_interval: 5
  web_ui_port: 5001

project:
  default_generations_dir: generations
  max_iterations: null  # unlimited
```

See [docs/configuration.md](docs/configuration.md) for complete guide and `.yokeflow.yaml.example` for all options.

### Environment Variables

The system uses a `.env` file for sensitive configuration. Copy `.env.example` to `.env` and update values:

```bash
# Required: Claude API Token (get from 'claude setup-token')
CLAUDE_CODE_OAUTH_TOKEN=your_actual_token_here

# Required: PostgreSQL Database URL
DATABASE_URL=postgresql://agent:agent_dev_password@localhost:5432/yokeflow

# Optional: Default models (can also set in .yokeflow.yaml)
DEFAULT_INITIALIZER_MODEL=claude-opus-4-5-20251101
DEFAULT_CODING_MODEL=claude-sonnet-4-5-20250929
DEFAULT_REVIEW_MODEL=claude-opus-4-5-20251101
DEFAULT_PROMPT_IMPROVEMENT_MODEL=claude-opus-4-5-20251101

# Optional: API Server settings
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

**Important:**
- The `.env` file is loaded automatically by the API server and CLI
- Never commit `.env` to git (it's in `.gitignore`)
- Use `.env.example` as a template for required variables

### Model Selection

**For Web UI:** Select models when creating/initializing projects via the UI

**For CLI:** Configure models in `.yokeflow.yaml`:
```yaml
models:
  initializer: claude-opus-4-5-20251101   # For Session 0 (planning)
  coding: claude-sonnet-4-5-20250929      # For Sessions 1+ (coding)
```

Models can also be set via environment variables in `.env`:
```bash
DEFAULT_INITIALIZER_MODEL=claude-opus-4-5-20251101
DEFAULT_CODING_MODEL=claude-sonnet-4-5-20250929
DEFAULT_REVIEW_MODEL=claude-opus-4-5-20251101
DEFAULT_PROMPT_IMPROVEMENT_MODEL=claude-opus-4-5-20251101
```

**Priority:** Web UI selection > `.yokeflow.yaml` > `.env` > Built-in defaults

---

## Project Structure

```
yokeflow/
├── api/                      # FastAPI REST API
│   ├── main.py              # API server with WebSocket
│   ├── start_api.py         # API server launcher
│   └── README.md            # API documentation
├── web-ui/                  # Next.js Web UI (TypeScript/React)
│   ├── src/                 # Application source
│   │   ├── app/            # Next.js pages
│   │   ├── components/     # React components
│   │   └── lib/            # API client, types, utils
│   └── package.json         # Dependencies
├── core/                    # Core platform modules
│   ├── orchestrator.py      # Session lifecycle management
│   ├── agent.py             # Agent loop and session logic
│   ├── database.py          # PostgreSQL abstraction (async)
│   ├── database_connection.py  # Connection pooling
│   ├── client.py            # Claude SDK client setup
│   ├── config.py            # Configuration management
│   ├── observability.py     # Session logging (JSONL + TXT)
│   ├── security.py          # Blocklist validation
│   ├── progress.py          # Progress tracking
│   ├── prompts.py           # Prompt loading
│   ├── reset.py             # Project reset logic
│   ├── sandbox_manager.py   # Docker sandbox management
│   └── sandbox_hooks.py     # Sandbox hooks
├── review/                  # Review system modules
│   ├── review_client.py     # Automated deep reviews (Phase 2)
│   ├── review_metrics.py    # Quality metrics (Phase 1)
│   └── prompt_improvement_analyzer.py  # Prompt optimization (Phase 4)
├── scripts/                 # Utility tools (debugging/development)
│   ├── task_status.py       # View task status and progress
│   ├── reset_project.py     # Reset project to post-init state
│   ├── analyze_sessions.py  # Analyze session metrics
│   ├── cleanup_sessions.py  # Clean up stuck sessions
│   ├── cleanup_containers.py  # Clean up Docker containers
│   ├── init_database.py     # Initialize PostgreSQL schema
│   ├── check_deep_reviews.py  # Inspect review data
│   ├── show_review_recommendations.py  # Show review suggestions
│   ├── docker-watchdog.sh   # Auto-restart Docker daemon
│   ├── setup-macos-for-long-runs.sh  # Prevent sleep on macOS
│   └── README.md            # Scripts documentation
├── prompts/                 # Agent instructions
│   ├── initializer_prompt.md  # Session 0 instructions (Opus)
│   ├── coding_prompt.md       # Sessions 1+ instructions (Sonnet)
│   └── review_prompt.md       # Deep review instructions
├── schema/
│   └── postgresql/          # PostgreSQL database schema
│       ├── 001_initial_schema.sql
│       └── 002_session_quality.sql
├── mcp-task-manager/        # MCP server (TypeScript)
│   ├── src/index.ts        # Server implementation
│   └── dist/               # Compiled JavaScript
├── tests/                   # Test scripts
├── docs/                    # Documentation
│   ├── developer-guide.md   # Technical deep-dive
│   ├── mcp-usage.md         # MCP integration details
│   ├── configuration.md     # Config file guide
│   └── review-system.md     # Complete review system documentation
└── generations/             # Generated projects (created at runtime)
```

### Generated Project Structure

```
generations/my_project/
├── app_spec.txt              # Your specification
├── init.sh                   # Generated setup script
├── claude-progress.md        # Session notes
├── logs/                     # Session logs (JSONL + TXT)
└── [application files]       # Generated code
```

---

## Running the Generated Application

```bash
cd generations/my_project

# Use the agent-generated setup script
./init.sh

# Or manually
npm install
npm run dev
```

Check `init.sh` or the agent's output for the exact URL (typically http://localhost:3000).

---

## Resetting Projects

**Problem:** Initialization takes 10-20 minutes. If coding sessions have issues, you don't want to re-run full initialization.

**Solution:** Reset to post-initialization state while preserving the complete roadmap:

```bash
# Preview what will be reset (dry run)
python reset_project.py --project-dir my_project --dry-run

# Reset with confirmation prompt
python reset_project.py --project-dir my_project

# Reset without confirmation
python reset_project.py --project-dir my_project --yes
```

**What gets reset:**
- Database: All task/test completion status (keeps roadmap intact)
- Git: Resets to commit after initialization session
- Logs: Archives coding session logs to `logs/old_attempts/TIMESTAMP/`
- Progress: Backs up and resets `claude-progress.md`

**What is preserved:**
- Complete project roadmap (all epics, tasks, tests)
- Initialization session (commit and log)
- Project structure and `init.sh`
- Configuration files (`.env.example`, etc.)

**Use cases:**
- Testing prompt improvements (v3 → v4 → v5)
- Debugging agent behavior during coding sessions
- A/B testing different models on same initialization
- Recovering from early-stage issues without full restart

**Benefits:** Saves 10-20 minutes per iteration, enabling faster prompt engineering and testing.

---

## Customization

**Change the application:**
Upload your specification files via the Web UI when creating a new project.

**Modify security rules:**
Edit `security.py` - add/remove commands from `BLOCKED_COMMANDS`.

**Customize prompts:**
Edit files in `prompts/` directory.

---

## Documentation

### For Users
- **This README** - Quick start and basic usage
- [CLAUDE.md](CLAUDE.md) - Comprehensive quick reference guide
- [docs/configuration.md](docs/configuration.md) - Config file documentation
- [docs/example-specs.md](docs/example-specs.md) - Example specification files and best practices

### For Developers
- [docs/developer-guide.md](docs/developer-guide.md) - Technical deep-dive
- [docs/mcp-usage.md](docs/mcp-usage.md) - MCP integration
- [docs/review-system.md](docs/review-system.md) - Complete review system documentation (4 phases)
- [TODO-FUTURE.md](TODO-FUTURE.md) - Post-release enhancements

---

## Troubleshooting

**Initialization takes a long time**
- Creating complete roadmap takes 3-5 minutes
- Agent stops automatically when done
- Then set Environment variables and start Coding session manually

**Command blocked**
- Security system working as intended
- Check `security.py` for blocked commands
- Modify blocklist if needed (use caution)

**Database errors**
- Ensure PostgreSQL is running: `docker-compose up -d`
- Check DATABASE_URL in `.env` file
- Initialize schema: `python scripts/init_database.py`

**Web UI shows no projects**
- Ensure PostgreSQL database is running
- Check projects in database: `psql $DATABASE_URL -c "SELECT * FROM projects;"`
- Run initialization session to create first project

**Generated applications don't work on different operating systems**
- Projects built in Docker sandbox use the Linux environment specified in `Dockerfile.agent-sandbox`
- Applications may require changes when moved to Windows or macOS
- Node native modules, system dependencies, and OS-specific code may need adjustment
- For production deployment, rebuild or test in target environment
- Consider using Docker for consistent cross-platform deployment

---

## License

YokeFlow Community License (YCL) v1.0 - See [LICENSE](LICENSE) for details.

---

