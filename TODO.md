# TODO - Autonomous Coding Agent Platform

This document tracks planned improvements and development roadmap for the autonomous coding agent platform.

**Last Updated:** December 22, 2025

---

## 🎯 CURRENT PRIORITIES


### 1. REVIEW SYSTEM - ARCHITECTURE & ENHANCEMENTS
**Status:** In progress

- See PROMPT_IMPROVEMENT_SYSTEM.md
- See docs/review_system.md

### 2. Upload mutliple spec files

### 3. Session Logs Viewer in UI
**Status:** Backend complete ✅ - UI component needed

**Current State:**
- ✅ Session logs viewer exists with TXT/JSONL viewing and download
- ✅ API endpoints exist for log retrieval
- ❌ **Could enhance with syntax highlighting and search features**

**What's Available (Backend):**
- Full log content viewing (TXT and JSONL)
- Download capability
- Session naming consistency with History tab

**What Could Be Enhanced (Frontend):**
- Syntax highlighting for tool calls in JSONL
- Search/filter within logs
- Side-by-side view (TXT + JSONL)
- Keyboard shortcuts for navigation

**Why Important:**
- Improves debugging experience
- Makes log analysis faster
- Better developer experience

**Implementation:**
- Enhance `web-ui/src/components/SessionLogsViewer.tsx`
- Add syntax highlighting library (e.g., Prism.js or highlight.js)
- Add search input with filter logic
- Optional: split-pane view for simultaneous TXT/JSONL

**Files:**
- `web-ui/src/components/SessionLogsViewer.tsx` (UPDATE)
- Backend already complete (no changes needed)

**Priority:** LOW (current viewer meets needs, these are nice-to-haves)

---

## 🔮 FUTURE ENHANCEMENTS

### 1. Enhanced History Tab Metrics
**Status:** ✅ Completed (December 2025) - Additional enhancements considered for future

**Completed Enhancements:**
- ✅ **Extended Database Schema:**
  - Added `input_tokens`, `output_tokens`, `cache_creation_tokens`, `cache_read_tokens` to sessions table
  - Added `metrics` JSONB field for flexible metric storage
  - Capture model information and session metadata

- ✅ **History Tab Display:**
  - Session type, status, and duration
  - Tool usage count and error count
  - Passing tests count
  - Token usage breakdown (input, output, cache creation, cache read)
  - Total cost calculation based on token usage
  - Model information displayed per session

- ✅ **API Endpoints:**
  - Session list with full metrics
  - Individual session detail retrieval
  - Metrics exposed via REST API

**Potential Future Additions (To Be Considered, Not Planned):**
- **Message Breakdown:**
  - User messages vs assistant messages
  - Tool uses by category (Read, Write, Edit, Bash, MCP)
  - Error types breakdown (API errors, tool errors, validation errors)

- **Performance Metrics:**
  - Average tool execution time
  - Session efficiency score (tasks completed per hour)

- **Visual Timeline/Graph:**
  - Activity timeline showing tool usage over session duration
  - Error clustering (when did errors occur)
  - Comparison chart with previous sessions

- **Session Comparison:**
  - "Compare with Session N" button
  - Side-by-side metric comparison
  - Trend indicators (improving/degrading)

**Note:** Current implementation meets core requirements. Additional features listed above are potential enhancements to be considered if needed, but are not actively planned.

**Files:**
- ✅ `schema/postgresql/001_initial_schema.sql` - Extended sessions table
- ✅ `web-ui/src/components/SessionTimeline.tsx` - Displays enhanced metrics
- ✅ `api/main.py` - Endpoints serve new metrics
- ✅ `database.py` - Session storage with metrics

**Priority:** COMPLETE (additional enhancements: LOW - only if needed)

---


## 🔮 PROPOSED ENHANCEMENTS

### Cosmetic UI Improvements
- [ ] **Dark/Light Theme Improvements** - Verify dark mode and light mode are easy to read
- [ ] **Mobile-Responsive Improvements** - Enhanced mobile layout and navigation

### Brownfield Development Support (Future Major Feature)
**Proposed Enhancement:** Extend platform to work with existing codebases

**Current State:**
- Platform currently focuses on **greenfield development** (building new apps from scratch)
- No support for importing existing repositories
- Agent works best with clean slate projects

**Proposed Features:**
- [ ] **GitHub Repository Import**
  - Clone existing repos into project workspace
  - Analyze codebase structure automatically
  - Generate roadmap for improvements/features

- [ ] **Codebase Understanding**
  - Parse existing code to understand architecture
  - Identify patterns, dependencies, tech stack
  - Create context for agent to work within

- [ ] **Incremental Enhancement Mode**
  - Add features to existing apps
  - Refactor existing code
  - Fix bugs in existing codebase
  - Maintain existing patterns/style

- [ ] **Pull Request Workflow**
  - Create feature branches
  - Generate PRs with changes
  - Integration with GitHub/GitLab

**Why This Is Complex:**
- Agent must understand existing code (not just write new code)
- Must respect existing architecture and patterns
- More challenging to verify correctness (existing tests may not cover changes)
- Requires different prompting strategy

**Priority:** LOW (major feature requiring significant R&D)

### Deployment
- [ ] **Digital Ocean Deployment** - Production deployment guide - Complete, not fully tested


### Performance & Scaling
- [ ] **Job queue** (Celery + Redis) for long-running tasks
- [ ] **Caching layer** (Redis) for frequently accessed data
- [ ] **Rate limiting** for API endpoints
- [ ] **E2B Sandbox Integration** - Cloud sandboxes in addition Docker

### User Experience
- [ ] **User accounts and authentication**
- [ ] **Multi-tenant support**
- [ ] **Project sharing and collaboration**
- [ ] **Email notifications** for session completion

---

## 📋 Project Philosophy

**Current Focus: Greenfield Development** - This platform currently focuses on building new applications from scratch (greenfield projects). Support for existing codebases (brownfield development) is a proposed future enhancement.

**Workflow:**
1. **Specification Creation** - Human-led with LLM assistance
2. **Initialization (Session 0)** - Opus creates complete roadmap
3. **Human Review** - Review tasks, configure environment
4. **Autonomous Coding (Sessions 1+)** - Sonnet implements until done
5. **Quality Review** - Automated analysis and improvement suggestions

**Core Principle:** "Focus on improving the agent system rather than manually fixing generated apps."

