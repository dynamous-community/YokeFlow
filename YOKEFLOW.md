# YokeFlow Transition Checklist

This document provides a comprehensive checklist for transitioning from the autonomous-coding codebase to the new YokeFlow repository.

---

## Phase 1: Initial Setup

- [ ] Create new YokeFlow repository
- [ ] Copy codebase to new repo (decide: preserve git history or fresh start)
- [ ] Update `.git/config` to point to new remote
- [ ] Create initial commit in YokeFlow repo

---

## Phase 2: Rename & Rebrand

### Documentation Files

- [ ] `README.md` - Update project name, description, repo links
- [ ] `CLAUDE.md` - Update all references to project name
- [ ] `TODO.md` - Create fresh roadmap for YokeFlow
- [ ] `docs/*.md` - Update project references throughout

### Configuration Files

- [ ] `docker-compose.yml` - Rename services (autonomous_coding → yokeflow)
- [ ] `.env.example` - Update comments and variable names if needed
- [ ] `package.json` files - Update name, description, repository URL
- [ ] `.autonomous-coding.yaml.example` → `.yokeflow.yaml.example`
- [ ] Update config file references in `config.py`

### Database

- [ ] Database name in connection strings (`autonomous_coding` → `yokeflow`)
- [ ] Docker container name (`autonomous_coding_postgres` → `yokeflow_postgres`)
- [ ] Update `DATABASE_URL` in `.env.example` and documentation

### Python Code

- [ ] Comments and docstrings mentioning "autonomous-coding"
- [ ] Log messages and error messages
- [ ] Default paths in `config.py`
- [ ] MCP server references

### TypeScript/Next.js

- [ ] `web-ui/package.json` - name, description
- [ ] `web-ui/src/app/layout.tsx` - page titles, metadata
- [ ] Component comments and documentation
- [ ] API endpoint documentation

### MCP Task Manager

- [ ] `mcp-task-manager/package.json` - name, description
- [ ] Server name and metadata

---

## Phase 3: Path & Naming Updates

### Directory References

- [ ] Default generations directory name (if changing)
- [ ] Log file paths
- [ ] Schema file paths
- [ ] Prompt file paths

### CLI Scripts

- [ ] Help text in `cli/*.py` files
- [ ] Usage examples in docstrings
- [ ] Error messages

### API Server

- [ ] API documentation strings
- [ ] OpenAPI/Swagger metadata in `api/main.py`
- [ ] CORS origins (if domain-specific)

---

## Phase 4: Testing

### Verify Core Functionality

- [ ] Database initialization works
- [ ] API server starts correctly
- [ ] Web UI connects to API
- [ ] MCP server builds and runs
- [ ] CLI tools work with new paths

### Test Key Workflows

- [ ] Create new project via Web UI
- [ ] Run initialization session
- [ ] Run coding session
- [ ] View quality dashboard
- [ ] Download session logs

### Docker

- [ ] `docker-compose up -d` works
- [ ] PostgreSQL accessible with new database name
- [ ] Docker containers have correct names

---

## Phase 5: Enhancement Readiness

- [ ] Clean up old development artifacts
- [ ] Remove any temporary/experimental code
- [ ] Update dependencies to latest versions (if desired)
- [ ] Run test suites to ensure everything works
- [ ] Create fresh `.env` from `.env.example`

---

## Phase 6: Documentation for YokeFlow

- [ ] Update installation instructions
- [ ] Update quick start guide
- [ ] Update API documentation
- [ ] Document any changes from autonomous-coding
- [ ] Create migration guide (if needed for existing users)

---

## Phase 7: Archive Original Repo (Later)

- [ ] Add archive notice to autonomous-coding README.md
- [ ] Add link to YokeFlow in autonomous-coding README.md
- [ ] Consider GitHub's "Archive repository" feature
- [ ] Update repo description: "⚠️ ARCHIVED - Active development moved to YokeFlow"

---

## Quick Find & Replace List

Common strings to search and replace:

```
autonomous-coding  →  yokeflow
autonomous_coding  →  yokeflow
Autonomous Coding  →  YokeFlow
AUTONOMOUS_CODING  →  YOKEFLOW
.autonomous-coding.yaml  →  .yokeflow.yaml
autonomous_coding_postgres  →  yokeflow_postgres
```

**Note:** Be careful with case-sensitive replacements. Review each change before committing.

---

## Files Most Likely to Need Updates

### High Priority

- `README.md`
- `CLAUDE.md`
- `docker-compose.yml`
- `.env.example`
- `config.py`
- `web-ui/package.json`
- `web-ui/src/app/layout.tsx`
- `mcp-task-manager/package.json`

### Medium Priority

- All `docs/*.md` files
- `package.json` (root)
- CLI tool help text
- API server metadata

### Low Priority (cosmetic)

- Code comments
- Log messages
- Docstrings

---

## Notes

- **This checklist was created:** December 22, 2025
- **Source repository:** autonomous-coding (maintenance mode - bug fixes only)
- **Target repository:** YokeFlow (active development)
- **Strategy:** Complete transition checklist before making repo public
- **Archive timeline:** After YokeFlow is stable and public

---

## Recommended Approach

1. Work through checklist systematically (Phase 1 → Phase 7)
2. Test thoroughly at each phase before proceeding
3. Keep this checklist updated as you discover additional items
4. Don't rush - better to be thorough than fast
5. Make enhancements AFTER the transition is complete and tested

Good luck with YokeFlow! 🚀
