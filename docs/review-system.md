# Review System - Developer Guide

**Last Updated:** December 22, 2025
**Status:** Production Ready (All 4 Phases Complete)

> **Note:** This document provides a general overview of the review system for developers who want to learn from or fork this codebase. For detailed Phase 4 implementation notes, see [PROMPT_IMPROVEMENT_SYSTEM.md](../PROMPT_IMPROVEMENT_SYSTEM.md) (temporary development documentation that will be removed once fully tested).

---

## Overview

The review system provides automated quality analysis and continuous improvement for agent sessions with four integrated phases:

1. **Phase 1:** Quick checks (zero-cost, every session)
2. **Phase 2:** Deep reviews (AI-powered, ~$0.10 each, automated triggers)
3. **Phase 3:** Web UI dashboard (visual quality monitoring)
4. **Phase 4:** Prompt improvement analysis (data-driven prompt optimization)

This system helps identify issues early, suggests prompt improvements, tracks quality trends over time, and generates actionable recommendations to improve the global coding prompts.

---

## Architecture

```
┌─────────────────┐
│  Agent Session  │
│   Completes     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 1: Quick Quality Check       │
│  (orchestrator.py)                  │
│  - Parse JSONL logs                 │
│  - Extract metrics                  │
│  - Run quality checks               │
│  - Calculate rating (1-10)          │
│  - Store in database                │
│  Cost: $0 (zero API calls)          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 2: Trigger Check             │
│  (review_client.py)                 │
│  Should trigger if:                 │
│  - session_number % 5 == 0          │
│  - quality < 7/10                   │
│  - 5+ sessions since last review    │
└────────┬────────────────────────────┘
         │
         ▼ (if triggered)
┌─────────────────────────────────────┐
│  Phase 2: Deep Review               │
│  (review_client.py)                 │
│  - Load session logs                │
│  - Send to Claude via SDK           │
│  - Store in database                │
│  Cost: ~$0.10 per review            │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Phase 3: Web UI Display            │
│  (QualityDashboard.tsx)             │
│  - Fetch quality data via API       │
│  - Render charts and badges         │
│  - Display review.                  │
│  - Show quality trends              │
└────────┬────────────────────────────┘
         │
         ▼ (manual trigger or scheduled)
┌─────────────────────────────────────┐
│  Phase 4: Prompt Improvement        │
│  (prompt_improvement_analyzer.py)   │
│  - Aggregate deep review data       │
│  - Group by themes (8 categories)   │
│  - Generate proposals (7-12 each)   │
│  - Rank by confidence & evidence    │
│  - Display in Web UI                │
│  Cost: $0 (or ~$0.30 with Claude)   │
└─────────────────────────────────────┘
```

---

## How the Phases Work Together

The four phases form an integrated feedback loop:

**Real-Time Monitoring (Phase 1 → Phase 3):**
```
Session completes → Quick check runs → Store metrics → Display in dashboard
                                     ↓
                         If quality < 7 or session % 5 == 0
                                     ↓
                              Trigger deep review
```

**Pattern Analysis (Phase 2 → Phase 4):**
```
Multiple sessions run → Deep reviews accumulate recommendations
                                     ↓
                    Manual trigger: Analyze recommendations
                                     ↓
                    Group by theme → Calculate evidence
                                     ↓
                    Generate proposals → Display in UI
                                     ↓
                    Developer reviews → Apply to prompts
                                     ↓
                    New sessions run → Quality improves
```

**Data Flow:**
1. **Phase 1** stores metrics in `session_quality_checks` table
2. **Phase 2** adds full `review_text` (markdown) to same row
3. **Phase 3** displays complete review text with collapsible sections
4. **Phase 4** analyzes review text patterns across multiple sessions

**Key Insight:** Each phase builds on the previous one. You can use Phase 1 alone for basic monitoring, add Phase 2 for deeper insights, Phase 3 for visualization, and Phase 4 for systematic prompt improvement.

---

## Phase 1: Quick Quality Checks

**File:** [`review_metrics.py`](../review_metrics.py)
**Cost:** $0 (zero API calls)
**When:** After every session completes

### Metrics Extracted

From JSONL session logs:
- **Tool use count:** Total API calls made
- **Error count:** Failed tool calls or exceptions
- **Error rate:** Percentage of failed calls
- **Playwright usage:** Browser automation calls
- **Screenshot count:** Visual verification attempts

### Quality Checks

```python
def quick_quality_check(metrics: dict, is_initializer: bool = False) -> tuple[list, int]:
    """
    Returns: (issues, rating)
    - issues: List of warning/critical issue dicts
    - rating: 1-10 score
    """
```

**Checks performed:**
1. **Browser Verification** (CRITICAL for coding sessions)
   - Warns if `playwright_count == 0`
   - Initializer sessions are exempt

2. **High Error Rate** (WARNING if > 10%)
   - Indicates prompts may be unclear
   - Or environment issues

3. **No Tool Calls** (CRITICAL)
   - Session did nothing
   - Likely a prompt or API issue

### Database Storage

Stores in `session_quality_checks` table:
```sql
INSERT INTO session_quality_checks (
    session_id,
    check_type,        -- 'quick'
    overall_rating,    -- 1-10
    playwright_count,
    error_count,
    error_rate,
    critical_issues,   -- JSONB array
    warnings           -- JSONB array
)
```

---

## Phase 2: Deep Reviews

**File:** [`review_client.py`](../review_client.py)
**Cost:** ~$0.10 per review (~$0.40 per 20-session project)
**When:** Automated triggers (see below)

### Trigger Conditions

Deep reviews are triggered when:

1. **Every 5th session** (session_number % 5 == 0)
   - Sessions 5, 10, 15, 20, ...
   - Trend analysis across multiple sessions

2. **Quality drops below 7/10**
   - Immediate review when issues detected
   - Catch problems early

3. **5 sessions since last deep review**
   - Even if not at 5-session interval
   - Ensures regular coverage

**Implementation:**
```python
async def should_trigger_deep_review(
    project_id: UUID,
    session_number: int,
    last_session_quality: Optional[int] = None
) -> bool:
    # Check interval (skip session 1)
    if session_number > 1 and session_number % 5 == 0:
        return True

    # Check quality threshold
    if last_session_quality is not None and last_session_quality < 7:
        return True

    # Check gap since last review
    last_review = await db.get_last_deep_review(project_id)
    if last_review:
        gap = session_number - last_review['session_number']
        if gap >= 5:
            return True
    elif session_number >= 5:
        # First deep review
        return True

    return False
```

### Review Process

1. **Load Session Data**
   - Human-readable log (TXT file)
   - Machine-readable events (JSONL file)
   - Quick check metrics from Phase 1

2. **Send to Claude via SDK**
   ```python
   from claude_agent_sdk import ClaudeSDKClient

   client = create_review_client(model="claude-sonnet-4-5-20250929")
   async with client:
       await client.query(review_prompt)
       review_text = await collect_response(client)
   ```

3. **Extract Rating from Review**
   - Parse overall rating (1-10) from review text
   - Store complete review as markdown
   - No parsing of recommendations (kept in full review text)

4. **Store in Database**
   ```python
   await db.store_deep_review(
       session_id=session_id,
       review_text=review_text,      # Complete markdown review
       overall_rating=rating,
   )
   ```

### Review Prompt

**File:** [`prompts/review_prompt.md`](../prompts/review_prompt.md)

Instructs Claude to analyze:
- Browser verification usage
- Error patterns and recovery
- Task completion effectiveness
- Prompt clarity and specificity
- Agent behavior patterns

Returns structured feedback with:
- Overall rating (1-10)
- Specific prompt improvement suggestions
- Pattern observations
- Action items for improvement

### Non-Blocking Execution

Deep reviews run in background:
```python
# In orchestrator.py
async def _maybe_trigger_deep_review(self, session_id, project_path, quality):
    should_trigger = await should_trigger_deep_review(...)
    if should_trigger:
        # Spawn background task (doesn't block session completion)
        asyncio.create_task(
            self._run_deep_review_background(session_id, project_path)
        )
```

This ensures:
- Sessions complete immediately
- Reviews run in parallel
- No impact on auto-continue flow
- Database updates happen asynchronously

---

## Phase 3: Web UI Dashboard

**Files:**
- [`web-ui/src/components/QualityDashboard.tsx`](../web-ui/src/components/QualityDashboard.tsx)
- [`web-ui/src/components/SessionQualityBadge.tsx`](../web-ui/src/components/SessionQualityBadge.tsx)

### Features

**1. Summary Cards** (3-column layout)
- Average quality rating across all sessions
- Sessions checked (coverage percentage)
- Browser verification compliance

**2. Quality Trend Chart**
- Visual bars for last 10 sessions
- Color-coded by rating:
  - Green (9-10): Excellent
  - Blue (7-8): Good
  - Yellow (5-6): Fair
  - Red (1-4): Poor
- Shows browser verification usage ("nn Browser Checks")
- Session labels ("Session nn" instead of "Snn")

**3. Deep Review Reports** (December 2025 Update)
- Collapsible sections for each deep review
- Displays **full review text** as markdown (not parsed recommendations)
- Download button for each review (markdown file format)
- Expand/collapse individual reviews
- Shows session number and quality badge per review

### API Endpoints

All endpoints already implemented in [`api/main.py`](../api/main.py):

```python
# Overall quality summary
GET /api/projects/{id}/quality

# Session-specific quality
GET /api/projects/{id}/sessions/{session_id}/quality

# Recent issues
GET /api/projects/{id}/quality/issues?limit=5

# Browser verification stats
GET /api/projects/{id}/quality/browser-verification
```

### Usage

1. Navigate to project detail page
2. Click "Quality" tab (📊 icon)
3. View dashboard with:
   - Summary statistics
   - Quality trend over time
   - Deep review

---

## Phase 4: Prompt Improvement Analysis

**File:** [`prompt_improvement_analyzer.py`](../prompt_improvement_analyzer.py)
**Cost:** $0 (zero API calls, or ~$0.30 with optional Claude enhancement)
**When:** Manual trigger via Web UI or programmatic analysis

### Purpose

Phase 4 transforms scattered deep review recommendations into concrete, prioritized improvements for the global coding prompts. Instead of reading individual session reviews, developers get aggregated patterns and specific proposals.

### How It Works

**1. Load Deep Review Data**
```python
# Query database for all deep reviews with review text
reviews = await db.fetch("""
    SELECT
        sqc.session_id,
        sqc.review_text,          -- Full markdown review
        sqc.overall_rating,
        s.session_number,
        s.project_id
    FROM session_quality_checks sqc
    JOIN sessions s ON sqc.session_id = s.id
    WHERE sqc.check_type = 'deep'
      AND sqc.review_text IS NOT NULL
      AND LENGTH(sqc.review_text) > 0
""")
```

**2. Extract Recommendations from Review Text**

Parse the markdown review text to extract recommendations, then group into 8 categories using keyword matching:
- **browser_verification** - Playwright usage, screenshots, visual testing
- **error_handling** - Error recovery, retry logic, debugging
- **git_commits** - Commit messages, formatting, co-authorship
- **testing** - Test creation, verification, coverage
- **docker** - Sandbox usage, bash_docker commands
- **parallel_execution** - Tool parallelization, efficiency
- **task_management** - MCP tool usage, task workflow
- **documentation** - Code comments, clarity
- **general** - Everything else

**3. Calculate Evidence Metrics**

For each theme:
```python
{
    "theme": "browser_verification",
    "frequency": 11,              # Appeared in 11 recommendations
    "avg_quality": 7.9,           # Average rating of sessions with this issue
    "unique_sessions": 7,         # Number of unique sessions
    "session_ids": [...],         # Evidence: which sessions
    "session_numbers": [5, 10, 15, ...]
}
```

**4. Generate Proposals**

Each proposal includes:
- **prompt_file** - Which prompt to modify (`coding_prompt_docker.md`)
- **section_name** - Where to add/modify text
- **proposed_text** - Specific recommendation text
- **rationale** - Why this helps (based on session patterns)
- **evidence** - Session IDs, quality ratings, frequency
- **confidence_level** - 1-10 score based on evidence strength

**Confidence Scoring:**
```python
if frequency >= 5 and avg_quality >= 8:
    confidence = 9  # High confidence: frequent issue, high-quality sessions
elif frequency >= 3:
    confidence = 7  # Medium confidence: moderate frequency
else:
    confidence = 5  # Lower confidence: infrequent
```

### Example Analysis Results

**Input:** 48 sessions across 1 project with 16 deep reviews

**Output:** 12 proposals grouped by theme
```
Theme: browser_verification (11 recommendations, 7 unique sessions, 7.9/10 avg)
├─ Proposal: "Strengthen Browser Verification Requirements"
│  Section: Browser Verification
│  Confidence: 9/10
│  Evidence: Sessions 5, 10, 12, 15, 18, 20, 23 (avg quality 7.9)
│
Theme: error_handling (9 recommendations, 6 unique sessions, 7.6/10 avg)
├─ Proposal: "Enhanced Error Recovery Patterns"
│  Section: Error Handling
│  Confidence: 9/10
│  Evidence: Sessions 5, 8, 10, 15, 20, 25 (avg quality 7.6)
│
Theme: testing (7 recommendations, 5 unique sessions, 8.2/10 avg)
├─ Proposal: "Comprehensive Testing Requirements"
│  Section: Testing Standards
│  Confidence: 8/10
│  Evidence: Sessions 10, 15, 20, 25, 30 (avg quality 8.2)
```

### Optional: Claude Enhancement

For the top N themes (default: 3), the analyzer can optionally use Claude to generate more specific before/after diffs:

```python
# Hybrid approach: Claude for top themes, direct aggregation for others
if theme_rank <= claude_budget and claude_enabled:
    # Request Claude to generate specific text diffs
    diff = await _generate_diff_with_claude(theme, recommendations)
    # Returns: { "original_text": "...", "proposed_text": "...", "rationale": "..." }
else:
    # Direct aggregation (no API call)
    proposed_text = "\n".join([r['text'] for r in theme_recommendations])
```

**Status:** Infrastructure complete, currently uses direct aggregation (Claude feature gracefully disabled pending SDK debugging).

### Database Storage

**Analysis Metadata:**
```sql
CREATE TABLE prompt_improvement_analyses (
    id UUID PRIMARY KEY,
    projects_analyzed UUID[],           -- Which projects
    sandbox_type VARCHAR(20),           -- docker or local
    sessions_analyzed INTEGER,          -- Total sessions reviewed
    deep_reviews_processed INTEGER,     -- Reviews with recommendations
    proposals_generated INTEGER,        -- Number of proposals created
    status VARCHAR(20),                 -- pending/running/completed/failed
    triggered_by VARCHAR(50),           -- manual/scheduled/api
    created_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);
```

**Individual Proposals:**
```sql
CREATE TABLE prompt_proposals (
    id UUID PRIMARY KEY,
    analysis_id UUID REFERENCES prompt_improvement_analyses(id),
    prompt_file VARCHAR(100),           -- coding_prompt_docker.md
    section_name VARCHAR(200),          -- Where to modify
    change_type VARCHAR(50),            -- add/modify/remove
    original_text TEXT,                 -- Current prompt text (optional)
    proposed_text TEXT,                 -- Recommended text
    rationale TEXT,                     -- Why this helps
    evidence JSONB,                     -- Session IDs, metrics
    confidence_level INTEGER,           -- 1-10 score
    status VARCHAR(20),                 -- pending/accepted/rejected/implemented
    created_at TIMESTAMPTZ
);
```

### API Endpoints

**File:** [`api/prompt_improvements_routes.py`](../api/prompt_improvements_routes.py)

```python
# Trigger new analysis
POST /api/prompt-improvements/analyze
Body: {
    "project_ids": ["uuid1", "uuid2"],
    "sandbox_type": "docker",
    "last_n_days": 90
}

# List all analyses
GET /api/prompt-improvements?limit=20

# Get analysis details with proposals
GET /api/prompt-improvements/{analysis_id}

# Get proposals for analysis
GET /api/prompt-improvements/{analysis_id}/proposals

# Update proposal status
PATCH /api/prompt-improvements/proposals/{proposal_id}
Body: { "status": "accepted" }

# Delete analysis (cascades to proposals)
DELETE /api/prompt-improvements/{analysis_id}
```

### Web UI Components

**Dashboard** (`/prompt-improvements`):
- List of all analyses with status badges
- Quick stats: projects analyzed, sessions reviewed, proposals generated
- Delete functionality with confirmation dialogs
- Dark mode support

**Analysis Detail** (`/prompt-improvements/{id}`):
- Analysis metadata (date, projects, sessions)
- Patterns identified (themes with frequency, quality, unique sessions)
- Full proposal list with confidence levels
- Diff viewer showing before/after text
- Accept/reject buttons for individual proposals

**Key Features:**
- Real-time status updates during analysis
- Evidence display (session IDs, quality ratings)
- Grouped by confidence level (high/medium/low)
- Markdown rendering in proposal text
- Copy-to-clipboard for quick prompt editing

### Workflow

**Typical Usage:**

1. **Run projects** - Let agent complete 20-50 sessions
2. **Deep reviews trigger** - Every 5 sessions or quality < 7
3. **Accumulate data** - Wait for 10-15 deep reviews with recommendations
4. **Trigger analysis** - Manual via Web UI or API call
5. **Review proposals** - Check confidence levels and evidence
6. **Apply improvements** - Edit `coding_prompt_docker.md` based on proposals
7. **Track impact** - Monitor quality ratings in subsequent sessions

**Example Workflow:**
```bash
# 1. Check deep reviews available
psql $DATABASE_URL -c "
    SELECT COUNT(*) FROM session_quality_checks
    WHERE check_type = 'deep'
      AND jsonb_array_length(prompt_improvements) > 0
"
# Output: 16 reviews

# 2. Trigger analysis via API
curl -X POST http://localhost:8000/api/prompt-improvements/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "project_ids": ["550e8400-e29b-41d4-a716-446655440000"],
    "sandbox_type": "docker"
  }'

# 3. View proposals in Web UI
open http://localhost:3000/prompt-improvements

# 4. Apply high-confidence proposals to prompt files
# (Manual step: edit prompts/coding_prompt_docker.md)

# 5. Run new sessions and compare quality
# (Quality ratings should improve if proposals were on target)
```

### Design Decisions

**Why aggregate across sessions?**
- Single session feedback can be noisy
- Patterns emerge from multiple observations
- Higher confidence in frequent issues

**Why theme-based grouping?**
- Easier to organize prompt sections
- Related issues grouped together
- Clear categories for prompt engineering

**Why confidence scoring?**
- Prioritize high-frequency, high-quality recommendations
- Avoid chasing one-off issues
- Focus on impactful improvements

**Why manual trigger instead of automatic?**
- Analysis requires human judgment
- Prompts are global (affect all future sessions)
- Cost control (optional Claude calls)
- Allows accumulation of sufficient data (10+ reviews)

**Why store in database?**
- Track which proposals were implemented
- Measure impact over time (future: A/B testing)
- Historical record of prompt evolution
- Enables version tracking

### Extensibility

**Future Enhancements:**

1. **A/B Testing Framework**
   - Test prompt versions in parallel
   - Compare quality metrics
   - Automatic rollback if quality degrades

2. **Impact Tracking**
   - Link proposals to quality improvements
   - Show before/after metrics
   - Validate effectiveness of changes

3. **Scheduled Analysis**
   - Run weekly/monthly automatically
   - Email/Slack notifications for new proposals
   - Trend reports

4. **Claude SDK Enhancement**
   - Debug empty response issue
   - Generate more specific before/after diffs
   - Validate proposed text fits prompt structure

---

## Database Schema

**Table:** `session_quality_checks`

```sql
CREATE TABLE session_quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id),

    -- Check metadata
    check_type VARCHAR(10) NOT NULL,  -- 'quick' | 'deep' | 'final'
    check_version VARCHAR(20),         -- For tracking prompt versions
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Quality metrics (from Phase 1)
    overall_rating INTEGER,            -- 1-10
    playwright_count INTEGER DEFAULT 0,
    playwright_screenshot_count INTEGER DEFAULT 0,
    total_tool_uses INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_rate DECIMAL(5,2) DEFAULT 0,

    -- Issues (JSONB arrays)
    critical_issues JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',

    -- Deep review fields (Phase 2)
    review_text TEXT,                  -- Full markdown review from Claude
    prompt_improvements JSONB DEFAULT '[]',  -- Legacy field (now unused, kept for compatibility)

    -- Indexes
    CONSTRAINT check_type_valid CHECK (check_type IN ('quick', 'deep', 'final'))
);

CREATE INDEX idx_quality_session ON session_quality_checks(session_id);
CREATE INDEX idx_quality_type ON session_quality_checks(check_type);
CREATE INDEX idx_quality_rating ON session_quality_checks(overall_rating);
```

**Phase 4 Tables:**

```sql
-- Prompt improvement analyses
CREATE TABLE prompt_improvement_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    projects_analyzed UUID[] NOT NULL,
    sandbox_type VARCHAR(20) NOT NULL,
    sessions_analyzed INTEGER DEFAULT 0,
    deep_reviews_processed INTEGER DEFAULT 0,
    proposals_generated INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    triggered_by VARCHAR(50) DEFAULT 'manual',
    user_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    CONSTRAINT status_valid CHECK (status IN ('pending', 'running', 'completed', 'failed'))
);

-- Individual prompt proposals
CREATE TABLE prompt_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID NOT NULL REFERENCES prompt_improvement_analyses(id) ON DELETE CASCADE,
    prompt_file VARCHAR(100) NOT NULL,
    section_name VARCHAR(200) NOT NULL,
    change_type VARCHAR(50) NOT NULL,
    original_text TEXT,
    proposed_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence JSONB DEFAULT '[]',
    confidence_level INTEGER NOT NULL CHECK (confidence_level BETWEEN 1 AND 10),
    status VARCHAR(20) DEFAULT 'pending',
    applied_at TIMESTAMPTZ,
    applied_by VARCHAR(100),
    applied_to_version VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT status_valid CHECK (status IN ('pending', 'accepted', 'rejected', 'implemented'))
);

-- Prompt version tracking (optional, for future A/B testing)
CREATE TABLE prompt_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prompt_file VARCHAR(100) NOT NULL,
    version_name VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    git_commit_hash VARCHAR(100),
    parent_version_id UUID REFERENCES prompt_versions(id),
    changes_summary TEXT,
    is_active BOOLEAN DEFAULT false,
    created_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(prompt_file, version_name)
);

-- Indexes for Phase 4
CREATE INDEX idx_analyses_status ON prompt_improvement_analyses(status);
CREATE INDEX idx_analyses_created ON prompt_improvement_analyses(created_at);
CREATE INDEX idx_proposals_analysis ON prompt_proposals(analysis_id);
CREATE INDEX idx_proposals_confidence ON prompt_proposals(confidence_level DESC);
CREATE INDEX idx_proposals_status ON prompt_proposals(status);
CREATE INDEX idx_versions_file ON prompt_versions(prompt_file);
CREATE INDEX idx_versions_active ON prompt_versions(is_active) WHERE is_active = true;
```

**Database Views:**

```sql
-- Project-wide quality summary
CREATE VIEW v_project_quality AS
SELECT
    p.id as project_id,
    COUNT(DISTINCT s.id) as total_sessions,
    COUNT(DISTINCT q.session_id) as checked_sessions,
    AVG(q.overall_rating) as avg_quality_rating,
    COUNT(DISTINCT CASE WHEN q.playwright_count = 0 THEN s.id END)
        as sessions_without_browser_verification,
    AVG(q.error_rate) as avg_error_rate_percent,
    AVG(q.playwright_count) as avg_playwright_calls_per_session
FROM projects p
LEFT JOIN sessions s ON p.id = s.project_id
LEFT JOIN session_quality_checks q ON s.id = q.session_id
WHERE q.check_type = 'quick'
GROUP BY p.id;

-- Recent quality issues
CREATE VIEW v_recent_quality_issues AS
SELECT
    s.id as session_id,
    s.session_number,
    s.project_id,
    q.overall_rating,
    q.critical_issues,
    q.warnings,
    q.created_at
FROM session_quality_checks q
JOIN sessions s ON q.session_id = s.id
WHERE q.overall_rating < 7
   OR jsonb_array_length(q.critical_issues) > 0
ORDER BY q.created_at DESC;
```

---

## Key Design Decisions

### Why Three Phases?

1. **Phase 1 (Quick):** Catches obvious issues immediately at zero cost
2. **Phase 2 (Deep):** Provides AI-powered analysis for deeper insights
3. **Phase 3 (UI):** Makes data visible and actionable for users

### Why Automated Triggers?

- **Predictable costs:** Max ~$0.40 per 20-session project
- **Early detection:** Quality drops trigger immediate review
- **Regular coverage:** Every 5 sessions ensures trends are caught
- **No manual work:** Runs automatically in background

### Why claude_agent_sdk?

- **Consistency:** Same SDK as core agent (agent.py, client.py)
- **Better error handling:** Retry logic and graceful degradation
- **Unified auth:** Uses CLAUDE_CODE_OAUTH_TOKEN (no separate API keys)
- **Future-proof:** Easy to add MCP tools for advanced analysis

### Why session_number vs total_sessions?

**Bug fixed December 18, 2025:**
- Old code used `total_sessions` (count of all sessions)
- Problem: Includes initializer session, offset by 1
- New code uses `session_number` directly
- Result: Correct triggers at 5, 10, 15, 20, etc.

---

## Testing

**Test file:** [`tests/test_review_phase2.py`](../tests/test_review_phase2.py)

Run tests:
```bash
python tests/test_review_phase2.py
```

Tests cover:
- ✅ Trigger logic (interval, quality, gap)
- ✅ Metrics extraction from logs
- ✅ Review client functionality
- ✅ Database storage and retrieval
- ✅ Edge cases (no sessions, first review, etc.)

---

## Cost Analysis

**Per Project (20 sessions):**
- Phase 1 (quick checks): $0 (20 sessions × $0)
- Phase 2 (deep reviews): ~$0.40 (4 reviews × $0.10)
- Phase 3 (Web UI): $0 (data visualization only)
- Phase 4 (prompt analysis): $0 (or ~$0.30 if Claude enhancement enabled)
- **Total: ~$0.40-$0.70 per project**

**Triggers:**
- Session 5: Deep review ($0.10)
- Session 10: Deep review ($0.10)
- Session 15: Deep review ($0.10)
- Session 20: Deep review ($0.10)
- Manual: Prompt analysis ($0-$0.30)

If quality drops below 7/10, additional deep reviews may trigger. Prompt analysis is typically run once per 10-15 deep reviews (across multiple sessions/projects).

---

## Usage Example

### Viewing Quality in Web UI

1. Start project: `python autonomous_agent.py --project-dir ./my_project`
2. Let sessions run (auto-continues)
3. Open Web UI: http://localhost:3000
4. Click project name
5. Click "Quality" tab → "Session Quality" sub-tab
6. View dashboard:
   - Check average quality (should be 7+)
   - Review quality trend chart
   - Expand deep review reports to read full analysis
   - Download reviews as markdown files
   - Address quality issues if any

### Manual Deep Review (CLI)

```bash
# Review specific session
python review_client.py generations/my_project 5

# Output:
# Session 5 Deep Review:
# Rating: 8/10
#
# Full Review (Markdown):
# [Complete markdown review text from Claude including:]
# - Session quality rating with justification
# - Browser verification analysis
# - Error pattern analysis
# - Prompt adherence evaluation
# - Concrete prompt improvements recommendations
#
# Note: Recommendations are included in the full review text,
#       not parsed into separate fields
```

### Checking Trigger Status

```python
from review_client import should_trigger_deep_review
from uuid import UUID

project_id = UUID("...")
session_number = 15
quality = 8

should_trigger = await should_trigger_deep_review(
    project_id,
    session_number,
    quality
)
# Returns: True (session 15 is at 5-session interval)
```

---

## Troubleshooting

### Deep Reviews Not Triggering

**Check:**
1. Is `CLAUDE_CODE_OAUTH_TOKEN` set?
   ```bash
   echo $CLAUDE_CODE_OAUTH_TOKEN
   ```

2. Are sessions completing successfully?
   ```bash
   python task_status.py generations/my_project
   ```

3. Check database for reviews:
   ```sql
   SELECT s.session_number, q.check_type, q.overall_rating
   FROM session_quality_checks q
   JOIN sessions s ON q.session_id = s.id
   WHERE q.check_type = 'deep'
   ORDER BY s.session_number;
   ```

4. Check API logs for trigger messages:
   ```bash
   grep "Deep review trigger" logs/api.log
   ```

### Reviews Stored But Not Showing in UI

**Check:**
1. Is Web UI connected to correct database?
2. Refresh browser (hard refresh: Cmd+Shift+R)
3. Check browser console for API errors
4. Verify API endpoint:
   ```bash
   curl http://localhost:8000/api/projects/{id}/quality
   ```

### Quality Rating Always 10/10

**Possible causes:**
1. Agent is performing exceptionally well (good problem!)
2. Sessions are very short (not enough data)
3. Check if browser verification is being used:
   ```bash
   grep "playwright" generations/my_project/logs/*.jsonl
   ```

---

## Future Enhancements

**Phase 1-3 Enhancements:**
- Manual review trigger button in UI
- Quality filters and search
- PDF report export
- Email/Slack alerts for critical issues
- Cross-project comparative analysis

**Phase 4 Enhancements:**
- A/B testing framework for prompt versions
- Automatic impact tracking (quality before/after changes)
- Scheduled analysis runs (weekly/monthly)
- Claude SDK debugging for enhanced diff generation
- Direct prompt editing from Web UI with version control

See [TODO.md](../TODO.md) for complete roadmap.

---

## Related Documentation

**System Overview:**
- [CLAUDE.md](../CLAUDE.md) - Main project documentation
- [README.md](../README.md) - User guide and quick start
- [TODO.md](../TODO.md) - Development roadmap

**Technical Guides:**
- [docs/developer-guide.md](./developer-guide.md) - Technical deep-dive
- [docs/mcp-usage.md](./mcp-usage.md) - MCP integration details

**Review System:**
- [prompts/review_prompt.md](../prompts/review_prompt.md) - Deep review instructions for Phase 2
- [PROMPT_IMPROVEMENT_SYSTEM.md](../PROMPT_IMPROVEMENT_SYSTEM.md) - Phase 4 implementation details (temporary dev docs)

**Code Reference:**
- [review_metrics.py](../review_metrics.py) - Phase 1 implementation
- [review_client.py](../review_client.py) - Phase 2 implementation
- [prompt_improvement_analyzer.py](../prompt_improvement_analyzer.py) - Phase 4 implementation
- [web-ui/src/components/QualityDashboard.tsx](../web-ui/src/components/QualityDashboard.tsx) - Phase 3 UI
- [web-ui/src/components/PromptImprovementDashboard.tsx](../web-ui/src/components/PromptImprovementDashboard.tsx) - Phase 4 UI

---

## Summary

The review system is production-ready and provides a complete feedback loop for continuous improvement:

**Phase 1 - Quick Checks:**
- ✅ Zero-cost analysis on every session
- ✅ Instant quality ratings (1-10)
- ✅ Critical issue detection

**Phase 2 - Deep Reviews:**
- ✅ AI-powered analysis at critical points
- ✅ Automated triggers (every 5 sessions or quality < 7)
- ✅ Structured prompt improvement recommendations

**Phase 3 - Quality Dashboard:**
- ✅ Beautiful web UI for monitoring trends
- ✅ Visual quality charts and badges
- ✅ Deep review recommendations display

**Phase 4 - Prompt Optimization:**
- ✅ Aggregate patterns across sessions
- ✅ Theme-based grouping (8 categories)
- ✅ Confidence-scored proposals
- ✅ Evidence-backed recommendations
- ✅ Manual trigger with full control

**Total Cost:** ~$0.40-$0.70 per 20-session project

**The Complete Loop:**
1. Sessions run → Quick checks identify issues
2. Deep reviews analyze patterns → Store recommendations
3. Dashboard shows quality trends → Highlight problems
4. Prompt analysis aggregates data → Generate proposals
5. Apply improvements → Monitor impact in next sessions

Use this system to identify issues early, improve your prompts systematically, and track quality trends over time!
