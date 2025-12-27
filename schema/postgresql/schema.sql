-- =============================================================================
-- YokeFlow (Autonomous Coding Agent) - Complete PostgreSQL Schema
-- =============================================================================
-- Version: 2.2.0
-- Date: December 25, 2025
--
-- This is the consolidated schema file that reflects the current database state.
-- All migrations have been applied and consolidated into this single file.
--
-- Changelog:
--   2.2.0 (Dec 25, 2025): Added total_time_seconds, removed budget_usd, updated trigger
--   2.1.0 (Dec 23, 2025): Added session heartbeat tracking
--   2.0.0 (Dec 2025): Initial consolidated schema
--
-- To initialize a fresh database, run:
--   python scripts/init_database.py
-- =============================================================================

-- =============================================================================
-- EXTENSIONS
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- For UUID generation

-- =============================================================================
-- CUSTOM TYPES
-- =============================================================================

-- Project status enum
CREATE TYPE project_status AS ENUM (
    'active',
    'paused',
    'completed',
    'archived'
);

-- Session types
CREATE TYPE session_type AS ENUM (
    'initializer',
    'coding',
    'review'
);

-- Session status
CREATE TYPE session_status AS ENUM (
    'pending',
    'running',
    'completed',
    'error',
    'interrupted'
);

-- Deployment status
CREATE TYPE deployment_status AS ENUM (
    'local',
    'sandbox',
    'production'
);

-- Task status
CREATE TYPE task_status AS ENUM (
    'pending',
    'in_progress',
    'completed',
    'blocked'
);

-- =============================================================================
-- MAIN TABLES
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Projects Table - Central metadata for all projects
-- -----------------------------------------------------------------------------
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) UNIQUE NOT NULL,
    user_id UUID,  -- Ready for multi-user support

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,  -- Project completion tracking

    -- Environment configuration
    env_configured BOOLEAN DEFAULT FALSE,
    env_configured_at TIMESTAMPTZ,

    -- Specification tracking
    spec_file_path TEXT,
    spec_hash VARCHAR(64),  -- SHA256 hash to detect changes

    -- GitHub integration
    github_repo_url TEXT,
    github_branch VARCHAR(100) DEFAULT 'main',
    github_default_branch VARCHAR(100) DEFAULT 'main',

    -- Deployment configuration
    deployment_status deployment_status DEFAULT 'local',
    sandbox_config JSONB DEFAULT '{}',
    api_endpoint TEXT,

    -- Project status and metrics
    status project_status DEFAULT 'active',
    total_cost_usd DECIMAL(10,4) DEFAULT 0,
    total_time_seconds INTEGER DEFAULT 0,

    -- Flexible metadata storage
    metadata JSONB DEFAULT '{}',

    -- Constraints
    CONSTRAINT valid_total_cost CHECK (total_cost_usd >= 0),
    CONSTRAINT valid_total_time CHECK (total_time_seconds >= 0)
);

CREATE INDEX idx_projects_user_id ON projects(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_metadata ON projects USING GIN (metadata);
CREATE INDEX idx_projects_completed_at ON projects(completed_at);
CREATE INDEX idx_projects_total_time ON projects(total_time_seconds);

COMMENT ON COLUMN projects.completed_at IS 'Timestamp when all epics/tasks/tests were completed. NULL means project is still in progress.';
COMMENT ON COLUMN projects.total_time_seconds IS 'Total time spent on project in seconds, automatically aggregated from session durations';

-- -----------------------------------------------------------------------------
-- Sessions Table - Track all agent sessions
-- -----------------------------------------------------------------------------
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    session_number INTEGER NOT NULL,
    type session_type NOT NULL,

    -- Model configuration
    model TEXT NOT NULL,
    max_iterations INTEGER,

    -- Session status
    status session_status DEFAULT 'pending',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    last_heartbeat TIMESTAMPTZ,  -- Track active sessions to prevent false-positive stale detection

    -- Session outcome
    error_message TEXT,
    interruption_reason TEXT,

    -- Session metrics stored as JSONB for flexibility
    metrics JSONB DEFAULT '{
        "duration_seconds": 0,
        "tool_calls_count": 0,
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_usd": 0,
        "tasks_completed": 0,
        "tests_passed": 0,
        "errors_count": 0,
        "browser_verifications": 0
    }',

    -- Log file references
    log_path TEXT,

    UNIQUE(project_id, session_number)
);

CREATE INDEX idx_sessions_project_status ON sessions(project_id, status);
CREATE INDEX idx_sessions_type ON sessions(type);
CREATE INDEX idx_sessions_created_at ON sessions(created_at DESC);
CREATE INDEX idx_sessions_metrics ON sessions USING GIN (metrics);
CREATE INDEX idx_sessions_stale_detection ON sessions (status, last_heartbeat) WHERE status = 'running';

COMMENT ON COLUMN sessions.last_heartbeat IS 'Timestamp of last heartbeat update during session execution. Used to detect truly stale sessions vs. long-running active sessions.';

-- -----------------------------------------------------------------------------
-- Hierarchical Task Management Tables
-- -----------------------------------------------------------------------------

-- Epics Table - High-level feature areas
CREATE TABLE epics (
    id SERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    priority INTEGER DEFAULT 0,
    status task_status DEFAULT 'pending',

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    UNIQUE(project_id, name)
);

CREATE INDEX idx_epics_project_id ON epics(project_id);
CREATE INDEX idx_epics_status ON epics(status);
CREATE INDEX idx_epics_priority ON epics(priority);

-- Tasks Table - Individual implementation steps
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    epic_id INTEGER NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    description TEXT NOT NULL,
    action TEXT,
    priority INTEGER DEFAULT 0,
    done BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,

    -- Session tracking
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,
    session_notes TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_tasks_epic_id ON tasks(epic_id);
CREATE INDEX idx_tasks_project_id ON tasks(project_id);
CREATE INDEX idx_tasks_done ON tasks(done);
CREATE INDEX idx_tasks_priority ON tasks(priority);
CREATE INDEX idx_tasks_session_id ON tasks(session_id);

-- Tests Table - Verification steps for tasks
CREATE TABLE tests (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    category VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    steps JSONB DEFAULT '[]',
    passes BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    verified_at TIMESTAMPTZ,

    -- Session tracking
    session_id UUID REFERENCES sessions(id) ON DELETE SET NULL,

    -- Test results
    result JSONB DEFAULT '{}',

    CONSTRAINT valid_category CHECK (category IN ('functional', 'style', 'accessibility', 'performance', 'security'))
);

CREATE INDEX idx_tests_task_id ON tests(task_id);
CREATE INDEX idx_tests_project_id ON tests(project_id);
CREATE INDEX idx_tests_passes ON tests(passes);
CREATE INDEX idx_tests_category ON tests(category);

-- -----------------------------------------------------------------------------
-- Session Quality Checks Table - Phase 1 & 2 Review System
-- -----------------------------------------------------------------------------
-- Note: The old 'reviews' table was removed in Migration 007 (never used)
CREATE TABLE session_quality_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

    -- Check type and timing
    check_type VARCHAR(50) NOT NULL,  -- 'quick', 'deep', 'final'
    check_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Overall scores
    overall_rating INTEGER,  -- 1-10 quality score

    -- Critical quality metrics (from quick check)
    playwright_count INTEGER DEFAULT 0,
    playwright_screenshot_count INTEGER DEFAULT 0,
    total_tool_uses INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    error_rate DECIMAL(5,4),

    -- Issue tracking
    critical_issues JSONB DEFAULT '[]',
    warnings JSONB DEFAULT '[]',

    -- Full metrics (from review_metrics.analyze_session_logs)
    metrics JSONB DEFAULT '{}',

    -- Deep review results (Phase 2)
    review_text TEXT,
    review_summary JSONB,
    prompt_improvements JSONB DEFAULT '[]',

    -- Constraints
    CONSTRAINT valid_rating CHECK (overall_rating IS NULL OR (overall_rating >= 1 AND overall_rating <= 10)),
    CONSTRAINT valid_check_type CHECK (check_type IN ('quick', 'deep', 'final'))
);

CREATE INDEX idx_quality_checks_session ON session_quality_checks(session_id);
CREATE INDEX idx_quality_checks_rating ON session_quality_checks(overall_rating) WHERE overall_rating IS NOT NULL;
CREATE INDEX idx_quality_checks_playwright ON session_quality_checks(playwright_count);
CREATE INDEX idx_quality_checks_created ON session_quality_checks(created_at DESC);
CREATE INDEX idx_quality_checks_critical_issues ON session_quality_checks USING GIN (critical_issues);
CREATE INDEX idx_quality_checks_metrics ON session_quality_checks USING GIN (metrics);

COMMENT ON TABLE session_quality_checks IS 'Automated quality check results for coding sessions. Supports quick metrics-only checks (Phase 1) and deep Claude-powered reviews (Phase 2).';
COMMENT ON COLUMN session_quality_checks.check_type IS 'Type of quality check: quick (metrics only, $0), deep (Claude analysis, ~$0.10), final (comprehensive project review)';
COMMENT ON COLUMN session_quality_checks.playwright_count IS 'Total Playwright browser automation calls. Critical quality metric with r=0.98 correlation to session quality. 0 = critical issue, 1-9 = minimal, 10-49 = good, 50+ = excellent';
COMMENT ON COLUMN session_quality_checks.overall_rating IS '1-10 quality score. Based on browser verification, error rate, and critical issues. NULL for checks that do not calculate ratings.';

-- -----------------------------------------------------------------------------
-- Deep Review Results (Phase 2 Review System)
-- -----------------------------------------------------------------------------
-- Note: Added via Migration 003 (separate_deep_reviews.sql)
-- Separated from session_quality_checks for cleaner architecture

CREATE TABLE session_deep_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,

    -- Review version and timing
    review_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Overall score (1-10)
    overall_rating INTEGER,

    -- Deep review results
    review_text TEXT,
    review_summary JSONB DEFAULT '{}',
    prompt_improvements JSONB DEFAULT '[]',

    -- Model used for review
    model VARCHAR(100),

    -- Constraints
    CONSTRAINT valid_deep_review_rating CHECK (overall_rating IS NULL OR (overall_rating >= 1 AND overall_rating <= 10)),
    CONSTRAINT unique_session_deep_review UNIQUE (session_id)  -- Each session can have at most one deep review
);

CREATE INDEX idx_deep_reviews_session ON session_deep_reviews(session_id);
CREATE INDEX idx_deep_reviews_created ON session_deep_reviews(created_at DESC);
CREATE INDEX idx_deep_reviews_rating ON session_deep_reviews(overall_rating) WHERE overall_rating IS NOT NULL;
CREATE INDEX idx_deep_reviews_improvements ON session_deep_reviews USING GIN (prompt_improvements);

COMMENT ON TABLE session_deep_reviews IS 'Deep review results for coding sessions. Automated or on-demand Claude-powered reviews for prompt improvement analysis.';
COMMENT ON COLUMN session_deep_reviews.overall_rating IS '1-10 quality score from deep review analysis. May differ from quick check rating.';
COMMENT ON COLUMN session_deep_reviews.review_text IS 'Full markdown review text from Claude, including analysis and recommendations.';
COMMENT ON COLUMN session_deep_reviews.prompt_improvements IS 'Structured list of recommendation strings extracted from review text for aggregation across sessions.';
COMMENT ON CONSTRAINT unique_session_deep_review ON session_deep_reviews IS 'Ensures each session has at most one deep review. If a session needs to be re-reviewed, the existing review should be updated rather than creating a new one.';

-- -----------------------------------------------------------------------------
-- Prompt Improvement System Tables (Phase 4)
-- -----------------------------------------------------------------------------

-- Prompt Improvement Analyses
CREATE TABLE prompt_improvement_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',

    -- Analysis scope
    projects_analyzed UUID[] NOT NULL,
    sessions_analyzed INTEGER NOT NULL DEFAULT 0,
    date_range_start TIMESTAMPTZ,
    date_range_end TIMESTAMPTZ,

    -- Configuration
    analysis_model VARCHAR(100) DEFAULT 'claude-sonnet-4-5-20250929',
    sandbox_type VARCHAR(20),

    -- Results
    overall_findings TEXT,
    patterns_identified JSONB DEFAULT '{}',
    proposed_changes JSONB DEFAULT '[]',
    quality_impact_estimate DECIMAL(3,1),

    -- Metadata
    triggered_by VARCHAR(50),
    user_id UUID,
    notes TEXT,

    CONSTRAINT status_valid CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    CONSTRAINT sandbox_type_valid CHECK (sandbox_type IN ('docker', 'local'))
);

CREATE INDEX idx_prompt_analyses_status ON prompt_improvement_analyses(status);
CREATE INDEX idx_prompt_analyses_created ON prompt_improvement_analyses(created_at DESC);
CREATE INDEX idx_prompt_analyses_sandbox ON prompt_improvement_analyses(sandbox_type);

-- Prompt Proposals
CREATE TABLE prompt_proposals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    analysis_id UUID REFERENCES prompt_improvement_analyses(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Change details
    prompt_file VARCHAR(100) NOT NULL,
    section_name VARCHAR(200),
    line_start INTEGER,
    line_end INTEGER,

    -- The actual change
    original_text TEXT NOT NULL,
    proposed_text TEXT NOT NULL,
    change_type VARCHAR(50),

    -- Justification
    rationale TEXT NOT NULL,
    evidence JSONB DEFAULT '[]',
    confidence_level INTEGER,

    -- Implementation status
    status VARCHAR(20) DEFAULT 'proposed',
    applied_at TIMESTAMPTZ,
    applied_to_version VARCHAR(50),
    applied_by VARCHAR(100),

    -- Impact tracking
    sessions_before_change INTEGER,
    quality_before DECIMAL(3,1),
    sessions_after_change INTEGER,
    quality_after DECIMAL(3,1),

    CONSTRAINT change_type_valid CHECK (change_type IN ('addition', 'modification', 'deletion', 'reorganization')),
    CONSTRAINT status_valid CHECK (status IN ('proposed', 'accepted', 'rejected', 'implemented')),
    CONSTRAINT confidence_valid CHECK (confidence_level BETWEEN 1 AND 10)
);

CREATE INDEX idx_proposals_analysis ON prompt_proposals(analysis_id);
CREATE INDEX idx_proposals_status ON prompt_proposals(status);
CREATE INDEX idx_proposals_file ON prompt_proposals(prompt_file);

COMMENT ON TABLE prompt_improvement_analyses IS 'Stores cross-project prompt improvement analyses';
COMMENT ON TABLE prompt_proposals IS 'Individual prompt change proposals from analyses';

-- Note: github_commits and project_preferences tables removed in Migration 007
-- (GitHub integration never implemented, preferences handled by config files)

-- =============================================================================
-- VIEWS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Progress View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_progress AS
SELECT
    p.id as project_id,
    p.name as project_name,
    COUNT(DISTINCT e.id) as total_epics,
    COUNT(DISTINCT CASE WHEN e.status = 'completed' THEN e.id END) as completed_epics,
    COUNT(DISTINCT t.id) as total_tasks,
    COUNT(DISTINCT CASE WHEN t.done = true THEN t.id END) as completed_tasks,
    COUNT(DISTINCT test.id) as total_tests,
    COUNT(DISTINCT CASE WHEN test.passes = true THEN test.id END) as passing_tests,
    ROUND(
        CASE
            WHEN COUNT(DISTINCT t.id) > 0
            THEN (COUNT(DISTINCT CASE WHEN t.done = true THEN t.id END)::DECIMAL / COUNT(DISTINCT t.id) * 100)
            ELSE 0
        END, 2
    ) as task_completion_pct,
    ROUND(
        CASE
            WHEN COUNT(DISTINCT test.id) > 0
            THEN (COUNT(DISTINCT CASE WHEN test.passes = true THEN test.id END)::DECIMAL / COUNT(DISTINCT test.id) * 100)
            ELSE 0
        END, 2
    ) as test_pass_pct
FROM projects p
LEFT JOIN epics e ON p.id = e.project_id
LEFT JOIN tasks t ON p.id = t.project_id
LEFT JOIN tests test ON p.id = test.project_id
GROUP BY p.id, p.name;

-- -----------------------------------------------------------------------------
-- Next Task View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_next_task AS
SELECT DISTINCT ON (p.id)
    t.id as task_id,
    t.description,
    t.action,
    e.id as epic_id,
    e.name as epic_name,
    e.description as epic_description,
    p.id as project_id,
    p.name as project_name
FROM projects p
JOIN epics e ON p.id = e.project_id
JOIN tasks t ON e.id = t.epic_id
WHERE t.done = false
    AND e.status != 'completed'
    AND p.status = 'active'
ORDER BY p.id, e.priority, t.priority, t.id;

-- -----------------------------------------------------------------------------
-- Epic Progress View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_epic_progress AS
SELECT
    e.id as epic_id,
    e.project_id,
    e.name,
    e.status,
    COUNT(t.id) as total_tasks,
    SUM(CASE WHEN t.done = true THEN 1 ELSE 0 END) as completed_tasks,
    ROUND(
        CASE
            WHEN COUNT(t.id) > 0
            THEN (SUM(CASE WHEN t.done = true THEN 1 ELSE 0 END)::DECIMAL / COUNT(t.id) * 100)
            ELSE 0
        END, 2
    ) as completion_percentage
FROM epics e
LEFT JOIN tasks t ON e.id = t.epic_id
GROUP BY e.id;

-- -----------------------------------------------------------------------------
-- Active Sessions View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_active_sessions AS
SELECT
    s.id,
    s.project_id,
    p.name as project_name,
    s.session_number,
    s.type,
    s.model,
    s.status,
    s.started_at,
    EXTRACT(EPOCH FROM (NOW() - s.started_at)) as duration_seconds
FROM sessions s
JOIN projects p ON s.project_id = p.id
WHERE s.status = 'running';

-- -----------------------------------------------------------------------------
-- Project Quality View (excludes Session 0/initializer)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_project_quality AS
SELECT
    s.project_id,
    p.name as project_name,
    COUNT(DISTINCT s.id) as total_sessions,
    COUNT(DISTINCT q.id) as checked_sessions,
    ROUND(AVG(q.overall_rating), 1) as avg_quality_rating,
    SUM(CASE WHEN q.playwright_count = 0 THEN 1 ELSE 0 END) as sessions_without_browser_verification,
    ROUND(AVG(q.error_rate) * 100, 1) as avg_error_rate_percent,
    ROUND(AVG(q.playwright_count), 1) as avg_playwright_calls_per_session
FROM sessions s
LEFT JOIN session_quality_checks q ON s.id = q.session_id AND q.check_type = 'quick'
LEFT JOIN projects p ON s.project_id = p.id
WHERE s.type = 'coding'  -- Only coding sessions (excludes Session 0/initializer)
GROUP BY s.project_id, p.name;

COMMENT ON VIEW v_project_quality IS 'Project-level quality summary with average ratings, error rates, and browser verification statistics (coding sessions only, excludes Session 0)';

-- -----------------------------------------------------------------------------
-- Recent Quality Issues View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_recent_quality_issues AS
SELECT
    q.id as check_id,
    s.id as session_id,
    s.session_number,
    s.type as session_type,
    s.project_id,
    p.name as project_name,
    q.check_type,
    q.overall_rating,
    q.playwright_count,
    q.error_rate,
    q.critical_issues,
    q.warnings,
    q.created_at
FROM session_quality_checks q
JOIN sessions s ON q.session_id = s.id
JOIN projects p ON s.project_id = p.id
WHERE
    s.type != 'initializer'  -- Exclude initializer sessions
    AND (
        jsonb_array_length(q.critical_issues) > 0
        OR q.overall_rating < 6
    )
ORDER BY q.created_at DESC;

-- -----------------------------------------------------------------------------
-- Browser Verification Compliance View
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_browser_verification_compliance AS
SELECT
    s.project_id,
    p.name as project_name,
    COUNT(*) as total_sessions,
    SUM(CASE WHEN q.playwright_count > 0 THEN 1 ELSE 0 END) as sessions_with_verification,
    SUM(CASE WHEN q.playwright_count >= 50 THEN 1 ELSE 0 END) as sessions_excellent_verification,
    SUM(CASE WHEN q.playwright_count BETWEEN 10 AND 49 THEN 1 ELSE 0 END) as sessions_good_verification,
    SUM(CASE WHEN q.playwright_count BETWEEN 1 AND 9 THEN 1 ELSE 0 END) as sessions_minimal_verification,
    SUM(CASE WHEN q.playwright_count = 0 THEN 1 ELSE 0 END) as sessions_no_verification,
    ROUND(100.0 * SUM(CASE WHEN q.playwright_count > 0 THEN 1 ELSE 0 END) / COUNT(*), 1) as verification_rate_percent
FROM sessions s
JOIN projects p ON s.project_id = p.id
LEFT JOIN session_quality_checks q ON s.id = q.session_id AND q.check_type = 'quick'
WHERE s.type = 'coding'  -- Only coding sessions
GROUP BY s.project_id, p.name;

COMMENT ON VIEW v_browser_verification_compliance IS 'Browser verification compliance tracking. Shows % of coding sessions with Playwright usage (target: 100%)';

-- -----------------------------------------------------------------------------
-- Prompt Improvement Views
-- -----------------------------------------------------------------------------

-- Recent Analyses with Summary Stats
CREATE OR REPLACE VIEW v_recent_analyses AS
SELECT
    a.id,
    a.created_at,
    a.completed_at,
    a.status,
    a.sandbox_type,
    CARDINALITY(a.projects_analyzed) as num_projects,
    a.sessions_analyzed,
    a.quality_impact_estimate,
    COUNT(p.id) as total_proposals,
    COUNT(CASE WHEN p.status = 'proposed' THEN 1 END) as pending_proposals,
    COUNT(CASE WHEN p.status = 'accepted' THEN 1 END) as accepted_proposals,
    COUNT(CASE WHEN p.status = 'implemented' THEN 1 END) as implemented_proposals
FROM prompt_improvement_analyses a
LEFT JOIN prompt_proposals p ON a.id = p.analysis_id
GROUP BY a.id
ORDER BY a.created_at DESC;

-- Pending Proposals with Analysis Info
CREATE OR REPLACE VIEW v_pending_proposals AS
SELECT
    p.id,
    p.created_at,
    p.prompt_file,
    p.section_name,
    p.change_type,
    p.confidence_level,
    p.rationale,
    a.sandbox_type,
    a.sessions_analyzed,
    CARDINALITY(a.projects_analyzed) as num_projects_analyzed
FROM prompt_proposals p
JOIN prompt_improvement_analyses a ON p.analysis_id = a.id
WHERE p.status = 'proposed'
ORDER BY p.confidence_level DESC, p.created_at DESC;

-- =============================================================================
-- FUNCTIONS AND TRIGGERS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Update updated_at Timestamp
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_project_preferences_updated_at
    BEFORE UPDATE ON project_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- -----------------------------------------------------------------------------
-- Update Project Metrics (Cost and Time) on Session Complete
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_project_metrics()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        UPDATE projects
        SET
            total_cost_usd = total_cost_usd + COALESCE((NEW.metrics->>'cost_usd')::DECIMAL, 0),
            total_time_seconds = total_time_seconds + COALESCE(ROUND((NEW.metrics->>'duration_seconds')::NUMERIC)::INTEGER, 0)
        WHERE id = NEW.project_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_project_metrics_on_session_complete
    AFTER UPDATE ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_project_metrics();

-- -----------------------------------------------------------------------------
-- Validate Session Type Consistency (0-based session numbering)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION validate_session_type()
RETURNS TRIGGER AS $$
DECLARE
    epic_count INTEGER;
BEGIN
    -- Count existing epics for the project
    SELECT COUNT(*) INTO epic_count
    FROM epics
    WHERE project_id = NEW.project_id;

    -- First session (session_number = 0) must be initializer if no epics exist
    IF NEW.session_number = 0 AND epic_count = 0 AND NEW.type != 'initializer' THEN
        RAISE EXCEPTION 'First session (session_number = 0) must be initializer type when no epics exist';
    END IF;

    -- Can't run initializer if epics already exist
    IF NEW.type = 'initializer' AND epic_count > 0 THEN
        RAISE EXCEPTION 'Cannot run initializer session when epics already exist (% epics found)', epic_count;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_session_type_consistency
    BEFORE INSERT ON sessions
    FOR EACH ROW
    EXECUTE FUNCTION validate_session_type();

COMMENT ON FUNCTION validate_session_type() IS 'Validates session type consistency: First session (session_number=0) must be initializer when no epics exist, and initializer cannot run when epics exist';

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
