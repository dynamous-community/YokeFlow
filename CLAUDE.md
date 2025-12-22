# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## What This Is

An autonomous coding agent that uses Claude to build complete applications over multiple sessions.

**Status**: Transitioning to **YokeFlow** - See `YOKEFLOW.md` for migration checklist

**Architecture**: API-first platform with FastAPI + Next.js Web UI + PostgreSQL + MCP task management

**Workflow**: Opus plans roadmap (Session 0) → Sonnet implements features (Sessions 1+)

## Core Workflow

**Session 0 (Initialization)**: Reads `app_spec.txt` → Creates epics/tasks/tests in PostgreSQL → Runs `init.sh`

**Sessions 1+ (Coding)**: Get next task → Implement → Browser verify → Update database → Git commit → Auto-continue

**Key Files**:
- `orchestrator.py` - Session lifecycle
- `agent.py` - Agent loop
- `database.py` - PostgreSQL abstraction (async)
- `api/main.py` - REST API + WebSocket
- `observability.py` - Session logging (JSONL + TXT)
- `security.py` - Blocklist validation
- `prompts/` - Agent instructions


## Database

**Schema**: PostgreSQL with 3-tier hierarchy: `epics` → `tasks` → `tests`

**Key tables**: `projects`, `epics`, `tasks`, `tests`, `sessions`, `session_quality_checks`

**Key views**: `v_next_task`, `v_progress`, `v_epic_progress`

**Access**: Use `database.py` abstraction (async/await). See `schema/postgresql/` for DDL.

## MCP Tools

The `mcp-task-manager/` provides 15+ tools (prefix: `mcp__task-manager__`):

**Query**: `task_status`, `get_next_task`, `list_epics`, `get_epic`, `list_tasks`, `get_task`, `list_tests`

**Update**: `update_task_status`, `start_task`, `update_test_result`

**Create**: `create_epic`, `create_task`, `create_test`, `expand_epic`, `log_session`

Must build before use: `cd mcp-task-manager && npm run build`

## Configuration

**Priority**: CLI args > Config file (`.autonomous-coding.yaml`) > Defaults

**Key settings**:
- `models.initializer` / `models.coding` - Override default Opus/Sonnet models
- `timing.auto_continue_delay` - Seconds between sessions (default 3)
- `project.max_iterations` - Limit session count (null = unlimited)

## Security

**Blocklist approach**: Allows dev tools (npm, git, curl), blocks dangerous commands (rm, sudo, apt)

Edit `security.py` `BLOCKED_COMMANDS` to modify. Safe in Docker containers.

## Project Structure

```
autonomous-coding/
├── api/                     # FastAPI REST API
├── web-ui/                  # Next.js Web UI
├── cli/                     # CLI tools (autonomous_agent, task_status, reset_project)
├── mcp-task-manager/        # MCP server (TypeScript)
├── prompts/                 # Agent instructions (initializer, coding, review)
├── schema/postgresql/       # Database DDL
├── tests/                   # Test suites
├── docs/                    # Documentation
├── orchestrator.py          # Session lifecycle
├── agent.py                 # Agent loop
├── database.py              # PostgreSQL abstraction
├── observability.py         # Logging (JSONL + TXT)
├── security.py              # Blocklist
├── review_*.py              # Review system (Phase 1-4)
└── generations/             # Generated projects
```

## Key Design Decisions

**PostgreSQL**: Production-ready, async operations, JSONB metadata, UUID-based IDs

**Orchestrator**: Decouples session management from CLI, enables API control, foundation for job queues

**MCP over Shell**: Protocol-based, structured I/O, no injection risks, language-agnostic

**Tasks Upfront**: Complete visibility from day 1, accurate progress tracking, user can review roadmap

**Dual Models**: Opus for planning (comprehensive), Sonnet for coding (fast + cheap)

**Blocklist Security**: Agent autonomy with safety, designed for containers

## Troubleshooting

**MCP server failed**: Run `cd mcp-task-manager && npm run build`

**Database error**: Ensure PostgreSQL running (`docker-compose up -d`), check DATABASE_URL in `.env`

**Command blocked**: Check `security.py` BLOCKED_COMMANDS list

**Agent stuck**: Check logs in `generations/[project]/logs/`, run with `--verbose`

**Web UI no projects**: Ensure PostgreSQL running, verify API connection

## Testing

```bash
python tests/test_security.py           # Security validation (64 tests)
python tests/test_mcp.py                 # MCP integration
python tests/test_database_abstraction.py # Database layer
python tests/test_orchestrator.py        # Orchestrator
```

## Important Files

**Core**: `orchestrator.py`, `agent.py`, `database.py`, `observability.py`, `security.py`

**Prompts**: `prompts/initializer_prompt.md`, `prompts/coding_prompt.md`, `prompts/review_prompt.md`

**API**: `api/main.py`, `web-ui/src/lib/api.ts`

**MCP**: `mcp-task-manager/src/index.ts`

**Schema**: `schema/postgresql/001_initial_schema.sql`

**Docs**: `docs/developer-guide.md`, `docs/review-system.md`, `README.md`, `TODO.md`

**Transition Docs**: `YOKEFLOW.md` (transition checklist), `PROMPT_IMPROVEMENT_SYSTEM.md` (Phase 4 refactoring status)

**Review System**:
- Phase 1: `review_metrics.py` - Quick checks (zero-cost) ✅ Production Ready
- Phase 2: `review_client.py` - Deep reviews (AI-powered) ✅ Production Ready
- Phase 3: `web-ui/src/components/QualityDashboard.tsx` - UI dashboard ✅ Production Ready
- Phase 4: `prompt_improvement_analyzer.py` - Prompt optimization ⚠️ Needs Refactoring (YokeFlow transition)

## Recent Changes

**December 2025**:
- ✅ Review system Phases 1-3 complete (quick checks, deep reviews, UI dashboard)
- ⚠️ Phase 4 (Prompt Improvement System) - Infrastructure complete, needs refactoring for YokeFlow
- ✅ PostgreSQL migration complete (UUID-based, async, connection pooling)
- ✅ API-first platform with Next.js Web UI
- ✅ Project completion tracking with celebration UI
- ✅ Coding prompt improvements (browser verification enforcement, bash_docker mandate)
- 🚀 **YokeFlow Transition**: Rebranding and repository migration in progress

**Key Evolution**:
- Shell scripts → MCP (protocol-based task management)
- JSONL + TXT dual logging (human + machine readable)
- Autonomous coding → **YokeFlow** (next-generation branding)

## Philosophy

**Greenfield Development**: Builds new applications from scratch, not modifying existing codebases.

**Workflow**: Create `app_spec.txt` → Initialize roadmap → Review → Autonomous coding → Completion verification

**Core Principle**: One-shot success. Improve the agent system itself rather than fixing generated apps.

## Transition Status

**Current State**: Maintenance mode - bug fixes only

**Next Steps**:
1. Complete Phase 4 refactoring (Prompt Improvement System)
2. Execute YokeFlow transition checklist (`YOKEFLOW.md`)
3. Rebrand and migrate to new repository
4. Archive this repository with migration notice

**Active Development**: Moving to YokeFlow repository

---

**For detailed documentation, see `docs/` directory. Forked from Anthropic's autonomous coding demo with extensive enhancements.**
