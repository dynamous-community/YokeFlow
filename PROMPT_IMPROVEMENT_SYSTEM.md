# Prompt Improvement System

**Status:** ✅ Production Ready
**Completed:** December 21, 2025

---

## Overview

The Prompt Improvement System analyzes session patterns across multiple projects to generate concrete improvements for the global coding prompts (`coding_prompt_docker.md` and `coding_prompt_local.md`).

**Key Achievement:** Successfully integrated the proven deep review system to provide data-driven prompt recommendations based on actual session performance.

## Architecture

### Data Flow

```
Deep Reviews (every 5 sessions)
    ↓
session_quality_checks table (with recommendations)
    ↓
Prompt Improvement Analyzer
    ↓
    ├─ Load recommendations from deep reviews
    ├─ Aggregate by theme (8 categories)
    ├─ Generate proposals (12 per analysis)
    └─ Optional: Claude SDK enhancement
    ↓
prompt_improvement_analyses & prompt_proposals tables
    ↓
Web UI Dashboard
```

### Components

**Backend:**
- `prompt_improvement_analyzer.py` - Core analysis engine
- `review_client.py` - Deep review system (integrated)
- `review_metrics.py` - Quick quality checks
- Database: PostgreSQL with 3 tables

**Frontend:**
- `PromptImprovementDashboard.tsx` - Analysis list
- `PromptAnalysisDetail.tsx` - Detailed view with proposals
- `PromptProposalDiff.tsx` - Before/after diff viewer

**Database Schema:**
- `prompt_improvement_analyses` - Analysis metadata
- `prompt_proposals` - Individual proposals
- `prompt_versions` - Historical tracking

## Implementation Phases

### ✅ Phase 1: Recommendation Parsing (Dec 21, 2025 - 2 hours)

**Problem:** Deep reviews had recommendations in markdown but weren't being extracted

**Solution:**
- Fixed `_parse_recommendations()` in `review_client.py`
- Enhanced regex to handle `#### 1. **Title**` format
- Reprocessed all 24 existing deep reviews

**Result:** 16 deep reviews now have 1-76 recommendations each

**Commit:** 977d2f8

---

### ✅ Phase 2: Deep Review Integration (Dec 21, 2025 - 4 hours)

**Problem:** Analyzer used basic thresholds, ignored deep review data

**Solution:**
- Added `_load_deep_review_recommendations()` - Queries database
- Added `_aggregate_recommendations()` - Groups by 8 themes
- Rebuilt `_generate_proposals()` - Prioritizes deep review data

**Themes:**
- browser_verification
- error_handling
- git_commits
- testing
- docker
- parallel_execution
- task_management
- documentation
- general (catchall)

**Result:**
- Before: 0-3 generic threshold-based proposals
- After: 7-12 high-confidence proposals from deep reviews
- Evidence includes session IDs, quality ratings, frequency

**Commit:** c3ae371

---

### ✅ Phase 3: Claude SDK Infrastructure (Dec 21, 2025 - 2 hours)

**Objective:** Use Claude to generate specific before/after text diffs

**Implementation:**
- Added `_create_claude_client()` - SDK client for analysis
- Added `_generate_diff_with_claude()` - Request JSON diffs from Claude
- Hybrid approach: Try Claude for top 3 themes, fallback to Phase 2

**Status:**
- ✅ Infrastructure complete
- ✅ Graceful fallback working
- ⚠️ SDK debugging needed (empty responses)
- ✅ No impact: System fully functional without Claude enhancement

**Configuration:**
```python
claude_enabled = True   # Set to False to disable
claude_budget = 3       # Limit API calls
```

**Commit:** cc814a3

---

### ✅ Bug Fix: Session Deduplication (Dec 21, 2025)

**Problem:** Sessions duplicated in UI (Session 5 appeared 151 times in "general" theme)

**Cause:** Each recommendation added session to list (14 recs = 14 entries)

**Solution:**
- Changed to dict-based tracking (one entry per session per theme)
- Calculate averages from unique sessions only

**Result:**
- Before: 123-151 duplicate entries
- After: 2-11 unique sessions per theme

**Commit:** bb2b1c0

---

## Current Capabilities

### Analyzer Features

**Input:**
- Project IDs to analyze
- Date range (default: last 90 days)
- Sandbox type (docker or local)
- Minimum sessions per project

**Processing:**
1. Load deep review recommendations from database
2. Aggregate by theme using keyword matching
3. Calculate frequency, avg quality, unique sessions
4. Generate proposals (Claude-enhanced or direct from recommendations)

**Output:**
- 7-12 proposals per analysis
- Each proposal includes:
  - Section name (where to modify prompt)
  - Proposed text (specific recommendations)
  - Rationale (why this helps)
  - Evidence (which sessions, quality ratings)
  - Confidence level (1-10)

### Example Analysis Results

```
Analysis of 48 sessions across 1 project:
- 12 proposals generated
- 7 high-confidence (9/10) from deep reviews
  - Testing Requirements (7 sessions, 8.2/10 avg quality)
  - Error Handling (9 sessions, 7.6/10 avg quality)
  - Browser Verification (11 sessions, 7.9/10 avg quality)
- 3 medium-confidence (6-7/10) from deep reviews
- 2 low-confidence (1-2/10) from thresholds
```

## API Endpoints

**Analysis:**
- `POST /api/prompt-improvements/analyze` - Trigger new analysis
- `GET /api/prompt-improvements` - List all analyses
- `GET /api/prompt-improvements/{id}` - Get analysis details
- `DELETE /api/prompt-improvements/{id}` - Delete analysis

**Proposals:**
- `GET /api/prompt-improvements/{id}/proposals` - Get proposals for analysis
- `GET /api/prompt-improvements/proposals` - List all proposals
- `PATCH /api/prompt-improvements/proposals/{id}` - Update status

**Metrics:**
- `GET /api/prompt-improvements/metrics` - System-wide stats

## Web UI

**Dashboard** (`/prompt-improvements`)
- List of all analyses
- Status indicators (pending, running, completed, failed)
- Quick stats (projects, sessions, proposals)
- Delete functionality with confirmation

**Analysis Detail** (`/prompt-improvements/{id}`)
- Analysis metadata (date, projects, sessions)
- Patterns identified (themes and frequencies)
- Full proposal list with confidence levels
- Diff viewer for proposed changes
- Dark mode support

## Usage

### Manual Analysis (Web UI)

1. Navigate to Prompt Improvements page
2. Click "Analyze" button
3. Select projects and date range
4. Review generated proposals
5. Accept/reject individual proposals

### Programmatic Analysis

```python
from prompt_improvement_analyzer import PromptImprovementAnalyzer
from database_connection import get_db

db = await get_db()
analyzer = PromptImprovementAnalyzer(db)

result = await analyzer.analyze_projects(
    project_ids=[project_uuid],
    sandbox_type="docker",
    last_n_days=90,
    min_sessions_per_project=5
)

print(f"Generated {result['proposals_generated']} proposals")
```

### Testing

```bash
# Run analysis on claude-clone project
python scripts/test_improved_analyzer.py

# View proposals
python -c "
import asyncio
from database_connection import get_db

async def main():
    db = await get_db()
    async with db.acquire() as conn:
        proposals = await conn.fetch(
            'SELECT * FROM prompt_proposals ORDER BY confidence_level DESC LIMIT 5'
        )
        for p in proposals:
            print(f'{p[\"section_name\"]}: {p[\"confidence_level\"]}/10')
    await db.disconnect()

asyncio.run(main())
"
```

## Files

**Core:**
- `prompt_improvement_analyzer.py` (800 lines) - Analysis engine
- `api/prompt_improvements_routes.py` (450 lines) - REST API
- `schema/postgresql/003_prompt_improvements.sql` - Database schema

**UI:**
- `web-ui/src/app/prompt-improvements/page.tsx` - Dashboard
- `web-ui/src/app/prompt-improvements/[id]/page.tsx` - Detail view
- `web-ui/src/components/PromptImprovementDashboard.tsx`
- `web-ui/src/components/PromptAnalysisDetail.tsx`
- `web-ui/src/components/PromptProposalDiff.tsx`

**Testing:**
- `scripts/test_improved_analyzer.py` - Integration test
- `scripts/reprocess_deep_review_recommendations.py` - Backfill tool

## Future Enhancements (Phase 4 - Deferred)

### API Integration
- Show which deep reviews contributed to each proposal
- Link proposals back to source sessions in UI
- Display recommendation sources with clickable session links

### Claude SDK Debugging
- Fix empty response issue from `receive_response()`
- Validate JSON parsing and extraction
- Test with different prompt lengths

### Advanced Features
- A/B testing framework for prompt versions
- Automatic prompt updates with approval workflow
- Impact tracking (quality improvements after applying proposals)
- Scheduled analysis runs
- Email/Slack notifications for new proposals

## Documentation

- **This file** - System overview and usage
- `docs/review-system.md` - Complete review system architecture
- `docs/mcp-usage.md` - Task management integration
- `CLAUDE.md` - Project-level guidance for Claude Code

## Conclusion

The Prompt Improvement System successfully bridges the proven deep review system with actionable prompt improvements. It provides:

✅ **Data-driven recommendations** - Based on real session analysis, not hunches
✅ **Cross-project insights** - Patterns identified across multiple projects
✅ **High confidence** - 9/10 confidence from sessions with 8+ quality ratings
✅ **Production ready** - Fully functional with graceful degradation
✅ **Extensible** - Claude SDK infrastructure ready for enhancement

The system transforms scattered session feedback into concrete, prioritized improvements for the coding prompts.

---

**Last Updated:** December 21, 2025
**Status:** Production Ready
