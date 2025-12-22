# Context Priming Command

Read these files to understand the autonomous coding agent system:

## Essential Context

1. **CLAUDE.md** - Quick reference overview (START HERE!)
   - What this project is and why it exists
   - Key features
   - Architecture overview
   - Common commands and workflows

2. **README.md** - User guide
   - Installation and setup
   - Usage examples (CLI and API/Web UI)
   - Project structure

3. **YOKEFLOW.md** - Transition guide
   - We are transitioning to a new codebase and re-branding
   - Part of this process is to improve the Prompt Improvement System
   
## After Reading

You should understand:

### Core System
- ✅ **Purpose**: Autonomous coding agent using Claude to build complete applications
- ✅ **Architecture**: API-first platform with CLI support
  - FastAPI REST API with WebSocket (port 8000)
  - Next.js Web UI (TypeScript/React, port 3000)
  - PostgreSQL database with async operations
  - Agent orchestrator (decoupled session management)
  - MCP (Model Context Protocol) for task operations

### Two-Phase Workflow
- ✅ **Session 0 (Initialization, Opus)**: Creates complete roadmap (epics → tasks → tests)
- ✅ **Sessions 1+ (Coding, Sonnet)**: Implements tasks with browser verification
- ✅ **Review System**: Production-ready quality monitoring (all 3 phases complete)

### Key Features (All Production Ready)
- ✅ **Observability**: Dual logging (JSONL + TXT)
- ✅ **Task Management**: PostgreSQL database with async operations, 15+ MCP tools
- ✅ **Quality System**: Automated reviews, quality dashboard, trend tracking
- ✅ **Project Management**: completion tracking, environment UI
- ✅ **Real-time Updates**: WebSocket live progress, session logs viewer

### Platform Capabilities
- ✅ **API Usage**: FastAPI server with REST endpoints + WebSocket (port 8000)
- ✅ **Web UI**: Next.js interface with 4 tabs (Overview/History/Quality/Logs, port 3000)
- ✅ **Quality Monitoring**: Automated deep reviews, quality dashboard, trend charts

### How to Extend
- ✅ Add API endpoints (api/main.py)
- ✅ Enhance Web UI (web-ui/src/)
- ✅ Improve prompts (prompts/ directory)
- ✅ Add tests (tests/ directory)
