# Quick Start Guide

This guide will get you up and running with YokeFlow in 5 minutes.

## Prerequisites

1. **PostgreSQL Database** (via Docker)
   ```bash
   docker-compose up -d
   python scripts/init_database.py --docker
   ```

2. **Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **MCP Task Manager** (TypeScript)
   ```bash
   cd mcp-task-manager
   npm install
   npm run build
   cd ..
   ```

4. **Next.js Web UI**
   ```bash
   cd web-ui
   cp .env.local.example .env.local
   npm install
   cd ..
   ```

5. **Authentication Token**
   ```bash
   # Set up Claude Code token
   claude setup-token

   # Add to .env file
   echo "CLAUDE_CODE_OAUTH_TOKEN=your_token_here" >> .env
   ```

## Starting the Platform

**Terminal 1 - Start API Server:**
```bash
# Using wrapper script (recommended)
python api/start_api.py

# OR using uvicorn directly (add --reload only if developing API code)
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Terminal 2 - Start Web UI:**
```bash
cd web-ui
npm run dev
```

**Terminal 3 - Start Docker Watchdog (Recommended):**
```bash
# Prevents Docker crashes from stopping your sessions
./scripts/docker-watchdog.sh &

# It will:
# - Check Docker every 30 seconds
# - Auto-restart if Docker crashes
# - Restart PostgreSQL container
# - Log all events to docker-watchdog.log
```

**Why run the watchdog?**
- Docker Desktop can crash even when Mac doesn't sleep
- Prevents "Database connection error" mid-session
- Auto-recovers without human intervention
- Essential for long-running coding sessions

Then open http://localhost:3000 in your browser.

## Common Issues

### Issue: "API server not responding at localhost:8000"

**Problem:** You ran `python api/main.py` directly (this doesn't work)

**Solution:** Use uvicorn instead:
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Issue: "Database connection error"

**Problem:** PostgreSQL not running

**Solution:**
```bash
# Start PostgreSQL
docker-compose up -d

# Verify it's running
docker ps | grep postgres

# Initialize schema
python scripts/init_database.py --docker
```

### Issue: "No API authentication configured"

**Problem:** Missing CLAUDE_CODE_OAUTH_TOKEN in .env

**Solution:**
```bash
# Get your token
claude setup-token

# Add to .env
cp .env.example .env
# Edit .env and add your token
```

## Verifying Everything Works

1. **Check API Server:**
   ```bash
   curl http://localhost:8000/api/health
   # Should return: {"status":"healthy",...}
   ```

2. **Check Database:**
   ```bash
   psql postgresql://agent:agent_dev_password@localhost:5432/yokeflow -c "SELECT 1;"
   # Should return: 1
   ```

3. **Check Web UI:**
   Open http://localhost:3000 - you should see the project list page

## Next Steps

1. **Create Your First Project:**
   - Click "Create New Project" in the Web UI
   - Upload a spec file (or use specs/app_spec.txt as example)
   - Click "Initialize Project" to create the roadmap

2. **Start Coding:**
   - After initialization completes, click "Start Coding Sessions"
   - Watch real-time progress in the UI
   - Sessions will auto-continue until all tasks are complete

3. **Monitor Progress:**
   - View session logs in the "Logs" tab
   - Check progress cards for completion stats
   - Stop sessions anytime with "Stop Sessions" button

## Documentation

- [README.md](README.md) - Full platform overview
- [CLAUDE.md](CLAUDE.md) - Quick reference guide
- [docs/developer-guide.md](docs/developer-guide.md) - Comprehensive technical guide
- [docs/api-usage.md](docs/api-usage.md) - API documentation
- [TODO-FUTURE.md](TODO-FUTURE.md) - Post-release enhancements

## Getting Help

- Check [CLAUDE.md](CLAUDE.md) Troubleshooting section
- Review logs in `generations/[project]/logs/`
- Open an issue on GitHub

## Pro Tips

1. **Use Opus for initialization, Sonnet for coding** (default behavior)
2. **Reset projects without re-initializing:**
   ```bash
   python scripts/reset_project.py --project my_project
   ```
   - Resets to state after initialization but before coding started
   - Saves 10-20 minutes by preserving the complete roadmap
3. **Monitor with utility scripts:**
   ```bash
   python scripts/task_status.py my_project
   ```
4. **Clean up stuck sessions:**
   ```bash
   python scripts/cleanup_sessions.py --project my_project
   ```
5. **Review session quality:**
   - Use the Web UI Quality Dashboard (automatic deep reviews)
   - Access via project detail page → Quality tab

---

**Ready to build!** 🚀
