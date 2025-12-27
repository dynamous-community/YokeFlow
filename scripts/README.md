# Scripts Directory

Utility tools for development, debugging, and system maintenance of YokeFlow projects.

## Overview

This directory contains command-line tools for managing YokeFlow projects, debugging sessions, and maintaining system health. These tools complement the Web UI and provide direct access to the database and Docker infrastructure.

---

## Development & Debugging Tools

### [task_status.py](task_status.py)
View real-time task progress and status for any project.

**Usage:**
```bash
python scripts/task_status.py [project_name_or_id]
python scripts/task_status.py --list          # List all projects
```

**Features:**
- Overall progress (epics, tasks, tests)
- Per-epic breakdown with completion percentages
- Task details with pass/fail test counts
- Rich terminal UI with progress bars

**Use when:**
- Monitoring agent progress from command line
- Debugging task completion issues
- Quick status checks without opening Web UI

---

### [analyze_sessions.py](analyze_sessions.py)
Analyze agent sessions from the database with detailed metrics.

**Usage:**
```bash
python scripts/analyze_sessions.py <project_name_or_id>
python scripts/analyze_sessions.py --list     # List all projects
python scripts/analyze_sessions.py --all      # Analyze all projects
```

**Features:**
- Session-by-session breakdown
- Token usage and duration metrics
- Quality ratings and trends
- Task completion statistics

**Use when:**
- Reviewing agent performance
- Identifying session patterns
- Analyzing token usage across projects
- Debugging session failures

---

### [reset_project.py](reset_project.py)
Reset a project to post-initialization state without re-running the time-consuming initialization.

**Usage:**
```bash
python scripts/reset_project.py --project-dir my-project
python scripts/reset_project.py --project-dir my-project --yes     # Skip confirmation
python scripts/reset_project.py --project-dir my-project --dry-run # Preview changes
```

**What gets reset:**
- Database: Task/test completion status, session records
- Git: Resets to commit after initialization
- Logs: Archives to `logs/old_attempts/TIMESTAMP/`

**What is preserved:**
- Complete roadmap (epics, tasks, tests)
- Initialization session and setup
- Project structure and configuration

**Use when:**
- Testing prompt improvements (faster iteration)
- Debugging coding session behavior
- A/B testing different models
- Recovering from early-stage issues

**Benefits:** Saves 10-20 minutes per iteration vs. full reinitialization

---

## System Maintenance Tools

### [cleanup_sessions.py](cleanup_sessions.py)
Clean up stuck sessions that are marked as 'running' but are no longer active.

**Usage:**
```bash
python scripts/cleanup_sessions.py
python scripts/cleanup_sessions.py --project my-project
python scripts/cleanup_sessions.py --force    # Skip confirmation
```

**Features:**
- Detects stale 'running' sessions
- Shows session age and project info
- Safe cleanup with confirmation prompts

**Use when:**
- System was put to sleep/hibernated
- Process was killed ungracefully
- Sessions appear stuck in Web UI
- Database shows incorrect 'running' status

**Note:** Automatic cleanup also runs when starting new sessions via Web UI

---

### [cleanup_containers.py](cleanup_containers.py)
Clean up Docker containers for YokeFlow projects.

**Usage:**
```bash
python scripts/cleanup_containers.py              # Remove containers for deleted projects
python scripts/cleanup_containers.py --all        # List all containers
python scripts/cleanup_containers.py --stopped    # Remove stopped containers
python scripts/cleanup_containers.py --force      # Force remove ALL (including running)
```

**Features:**
- Lists all yokeflow containers
- Removes containers for deleted projects
- Shows container status and disk usage
- Safe removal with confirmation

**Use when:**
- Docker disk space is low
- Cleaning up after deleted projects
- Removing orphaned containers
- Preparing for fresh project runs

---

### [docker-watchdog.sh](docker-watchdog.sh)
Monitors Docker daemon and auto-restarts if it crashes during long-running sessions.

**Usage:**
```bash
./scripts/docker-watchdog.sh &               # Run in background
LOGFILE=my.log ./scripts/docker-watchdog.sh  # Custom log file
```

**Features:**
- Checks Docker every 30 seconds
- Auto-restarts Docker Desktop if crashed
- Restarts PostgreSQL container after recovery
- Logs all events to `docker-watchdog.log`

**Use when:**
- Running overnight or unattended sessions
- macOS systems where Docker Desktop can crash
- Long multi-session runs (50+ sessions)
- Preventing database connection failures

**Important:** Works with [setup-macos-for-long-runs.sh](#setup-macos-for-long-runssh) for complete system reliability

---

### [setup-macos-for-long-runs.sh](setup-macos-for-long-runs.sh)
Configure macOS to prevent sleep and Docker throttling during long autonomous sessions.

**Usage:**
```bash
./scripts/setup-macos-for-long-runs.sh
```

**What it configures:**
- Disables system sleep
- Disables display sleep (CRITICAL for Docker!)
- Disables Power Nap
- Disables screen lock
- Cancels scheduled sleep/wake events

**Features:**
- Interactive prompts with confirmation
- Shows before/after settings
- Provides restore instructions

**Use when:**
- Running overnight sessions
- Unattended multi-hour builds
- Preventing Docker Desktop throttling
- Ensuring continuous operation

**Why this matters:**
- Display sleep + screen lock can throttle Docker Desktop
- Docker throttling → PostgreSQL becomes unreachable → sessions fail
- macOS treats Docker Desktop as a GUI app, subject to app suspension policies

**Note:** Use `pmset` commands or System Preferences to restore normal sleep settings when done

---

## Quality & Review Tools

### [check_deep_reviews.py](check_deep_reviews.py)
Check if deep reviews exist in the database and inspect their contents.

**Usage:**
```bash
python scripts/check_deep_reviews.py
```

**Features:**
- Counts total deep reviews
- Shows latest 5 reviews with ratings
- Displays prompt improvements
- Verifies review text presence

**Use when:**
- Debugging review system
- Verifying deep reviews are being created
- Inspecting review quality and recommendations
- Troubleshooting quality dashboard issues

---

### [show_review_recommendations.py](show_review_recommendations.py)
Extract and display the RECOMMENDATIONS section from the latest deep review.

**Usage:**
```bash
python scripts/show_review_recommendations.py
```

**Features:**
- Shows latest deep review recommendations
- Extracts actionable improvements
- Displays project and session context
- Formats for easy reading

**Use when:**
- Quick access to latest recommendations
- Reviewing prompt improvement suggestions
- Debugging review content
- Verifying recommendation quality

---

## Database Tools

### [init_database.py](init_database.py)
Initialize PostgreSQL database for YokeFlow with schema and configuration.

**Usage:**
```bash
python scripts/init_database.py --docker                    # Docker default
python scripts/init_database.py --url postgresql://...      # Custom URL
```

**Features:**
- Creates database if not exists
- Runs initial schema setup
- Sets up tables, views, indexes
- Validates schema after creation

**Use when:**
- First-time setup
- Resetting database to clean state
- Testing schema changes
- Recovering from database corruption

**Important:** Always run after `docker-compose up -d` for fresh installations

---

## Quick Reference

### Common Workflows

**Monitor a running session:**
```bash
python scripts/task_status.py my-project
```

**Clean up after system sleep:**
```bash
python scripts/cleanup_sessions.py
```

**Iterate on prompts without full reinitialization:**
```bash
python scripts/reset_project.py --project-dir my-project
```

**Prepare for overnight run:**
```bash
./scripts/setup-macos-for-long-runs.sh
./scripts/docker-watchdog.sh &
```

**Review latest agent recommendations:**
```bash
python scripts/show_review_recommendations.py
```

---

## Notes

- **All Python scripts** require PostgreSQL running (`docker-compose up -d`)
- **Database URL** is loaded from `.env` file automatically
- **Rich terminal UI** requires `rich` package (in `requirements.txt`)
- **Docker tools** require Docker Desktop running
- **Bash scripts** are macOS-specific (Linux users should adapt)

---

## See Also

- [Web UI](../web-ui/README.md) - Primary interface for project management
- [API Documentation](../api/README.md) - REST API and WebSocket endpoints
- [Developer Guide](../docs/developer-guide.md) - Technical deep-dive
- [CLAUDE.md](../CLAUDE.md) - Quick reference for the entire platform
