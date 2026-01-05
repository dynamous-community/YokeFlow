-- Session Checkpoints for Resume Capability
-- ============================================
-- Stores session state at key points for recovery and resumption

-- Checkpoint table - stores session state snapshots
CREATE TABLE IF NOT EXISTS session_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    -- Checkpoint metadata
    checkpoint_number INTEGER NOT NULL, -- Sequential within session (1, 2, 3...)
    checkpoint_type VARCHAR(50) NOT NULL, -- 'task_completion', 'epic_completion', 'manual', 'error'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Session state at checkpoint
    current_task_id INTEGER REFERENCES tasks(id),
    current_epic_id INTEGER REFERENCES epics(id),
    message_count INTEGER NOT NULL DEFAULT 0,
    iteration_count INTEGER NOT NULL DEFAULT 0,

    -- Agent conversation state
    conversation_history JSONB NOT NULL DEFAULT '[]', -- Array of messages
    tool_results_cache JSONB NOT NULL DEFAULT '{}', -- Recent tool results for context

    -- Task progress state
    completed_tasks INTEGER[] DEFAULT '{}', -- Array of completed task IDs
    in_progress_tasks INTEGER[] DEFAULT '{}', -- Array of in-progress task IDs
    blocked_tasks INTEGER[] DEFAULT '{}', -- Array of blocked task IDs

    -- Session metrics snapshot
    metrics_snapshot JSONB NOT NULL DEFAULT '{}',

    -- File system state (for verification)
    files_modified TEXT[], -- List of files modified in this session
    git_commit_sha VARCHAR(40), -- Last git commit at checkpoint

    -- Resumption info
    can_resume_from BOOLEAN DEFAULT TRUE,
    resume_notes TEXT, -- Notes about how to resume from this checkpoint
    invalidated BOOLEAN DEFAULT FALSE, -- Set to true if checkpoint is no longer valid
    invalidation_reason TEXT,

    -- Recovery metadata
    recovery_count INTEGER DEFAULT 0, -- How many times resumed from this checkpoint
    last_resumed_at TIMESTAMPTZ,

    CONSTRAINT unique_checkpoint_per_session UNIQUE (session_id, checkpoint_number),
    CONSTRAINT valid_checkpoint_number CHECK (checkpoint_number > 0),
    CONSTRAINT valid_message_count CHECK (message_count >= 0),
    CONSTRAINT valid_iteration_count CHECK (iteration_count >= 0)
);

-- Table for checkpoint recovery attempts
CREATE TABLE IF NOT EXISTS checkpoint_recoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checkpoint_id UUID NOT NULL REFERENCES session_checkpoints(id) ON DELETE CASCADE,

    -- Recovery attempt info
    recovery_initiated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recovery_completed_at TIMESTAMPTZ,
    recovery_status VARCHAR(20) NOT NULL, -- 'in_progress', 'success', 'failed'

    -- New session created for recovery
    new_session_id UUID REFERENCES sessions(id),

    -- Recovery details
    recovery_method VARCHAR(50) NOT NULL, -- 'automatic', 'manual', 'partial'
    recovery_notes TEXT,
    error_message TEXT,

    -- State comparison
    state_differences JSONB DEFAULT '{}', -- Differences between checkpoint and actual state

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_checkpoints_session ON session_checkpoints(session_id);
CREATE INDEX idx_checkpoints_project ON session_checkpoints(project_id);
CREATE INDEX idx_checkpoints_created_at ON session_checkpoints(created_at DESC);
CREATE INDEX idx_checkpoints_type ON session_checkpoints(checkpoint_type);
CREATE INDEX idx_checkpoints_can_resume ON session_checkpoints(can_resume_from) WHERE can_resume_from = TRUE;
CREATE INDEX idx_checkpoints_task ON session_checkpoints(current_task_id) WHERE current_task_id IS NOT NULL;

CREATE INDEX idx_recoveries_checkpoint ON checkpoint_recoveries(checkpoint_id);
CREATE INDEX idx_recoveries_status ON checkpoint_recoveries(recovery_status);
CREATE INDEX idx_recoveries_initiated_at ON checkpoint_recoveries(recovery_initiated_at DESC);

-- Views for checkpoint management

-- View: Latest checkpoint for each session
CREATE OR REPLACE VIEW v_latest_checkpoints AS
SELECT DISTINCT ON (session_id)
    cp.id,
    cp.session_id,
    cp.project_id,
    p.name as project_name,
    cp.checkpoint_number,
    cp.checkpoint_type,
    cp.created_at,
    cp.current_task_id,
    t.description as current_task_description,
    cp.message_count,
    cp.iteration_count,
    cp.can_resume_from,
    cp.invalidated,
    cp.recovery_count,
    cp.last_resumed_at,
    s.status as session_status,
    s.session_number
FROM session_checkpoints cp
JOIN sessions s ON cp.session_id = s.id
JOIN projects p ON cp.project_id = p.id
LEFT JOIN tasks t ON cp.current_task_id = t.id
ORDER BY session_id, checkpoint_number DESC;

-- View: Resumable checkpoints (valid and not invalidated)
CREATE OR REPLACE VIEW v_resumable_checkpoints AS
SELECT
    cp.id,
    cp.session_id,
    cp.project_id,
    p.name as project_name,
    cp.checkpoint_number,
    cp.checkpoint_type,
    cp.created_at,
    cp.current_task_id,
    t.description as current_task_description,
    cp.message_count,
    cp.recovery_count,
    cp.last_resumed_at,
    s.session_number,
    s.type as session_type,
    s.status as session_status,
    NOW() - cp.created_at as age
FROM session_checkpoints cp
JOIN sessions s ON cp.session_id = s.id
JOIN projects p ON cp.project_id = p.id
LEFT JOIN tasks t ON cp.current_task_id = t.id
WHERE cp.can_resume_from = TRUE
  AND cp.invalidated = FALSE
  AND s.status IN ('error', 'interrupted')
ORDER BY cp.created_at DESC;

-- View: Checkpoint recovery history
CREATE OR REPLACE VIEW v_checkpoint_recovery_history AS
SELECT
    cr.id,
    cr.checkpoint_id,
    cp.session_id as original_session_id,
    s1.session_number as original_session_number,
    cr.new_session_id,
    s2.session_number as new_session_number,
    cp.project_id,
    p.name as project_name,
    cr.recovery_initiated_at,
    cr.recovery_completed_at,
    cr.recovery_status,
    cr.recovery_method,
    cr.error_message,
    EXTRACT(EPOCH FROM (cr.recovery_completed_at - cr.recovery_initiated_at)) as recovery_duration_seconds,
    cp.checkpoint_type,
    cp.checkpoint_number
FROM checkpoint_recoveries cr
JOIN session_checkpoints cp ON cr.checkpoint_id = cp.id
JOIN sessions s1 ON cp.session_id = s1.id
LEFT JOIN sessions s2 ON cr.new_session_id = s2.id
JOIN projects p ON cp.project_id = p.id
ORDER BY cr.recovery_initiated_at DESC;

-- Function to create a checkpoint
CREATE OR REPLACE FUNCTION create_checkpoint(
    p_session_id UUID,
    p_project_id UUID,
    p_checkpoint_type VARCHAR(50),
    p_current_task_id INTEGER DEFAULT NULL,
    p_current_epic_id INTEGER DEFAULT NULL,
    p_message_count INTEGER DEFAULT 0,
    p_iteration_count INTEGER DEFAULT 0,
    p_conversation_history JSONB DEFAULT '[]',
    p_tool_results_cache JSONB DEFAULT '{}',
    p_completed_tasks INTEGER[] DEFAULT '{}',
    p_in_progress_tasks INTEGER[] DEFAULT '{}',
    p_blocked_tasks INTEGER[] DEFAULT '{}',
    p_metrics_snapshot JSONB DEFAULT '{}',
    p_files_modified TEXT[] DEFAULT '{}',
    p_git_commit_sha VARCHAR(40) DEFAULT NULL,
    p_resume_notes TEXT DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_checkpoint_id UUID;
    v_checkpoint_number INTEGER;
BEGIN
    -- Get next checkpoint number for this session
    SELECT COALESCE(MAX(checkpoint_number), 0) + 1
    INTO v_checkpoint_number
    FROM session_checkpoints
    WHERE session_id = p_session_id;

    -- Create the checkpoint
    INSERT INTO session_checkpoints (
        session_id,
        project_id,
        checkpoint_number,
        checkpoint_type,
        current_task_id,
        current_epic_id,
        message_count,
        iteration_count,
        conversation_history,
        tool_results_cache,
        completed_tasks,
        in_progress_tasks,
        blocked_tasks,
        metrics_snapshot,
        files_modified,
        git_commit_sha,
        resume_notes
    ) VALUES (
        p_session_id,
        p_project_id,
        v_checkpoint_number,
        p_checkpoint_type,
        p_current_task_id,
        p_current_epic_id,
        p_message_count,
        p_iteration_count,
        p_conversation_history,
        p_tool_results_cache,
        p_completed_tasks,
        p_in_progress_tasks,
        p_blocked_tasks,
        p_metrics_snapshot,
        p_files_modified,
        p_git_commit_sha,
        p_resume_notes
    )
    RETURNING id INTO v_checkpoint_id;

    RETURN v_checkpoint_id;
END;
$$ LANGUAGE plpgsql;

-- Function to invalidate checkpoints (when state has changed)
CREATE OR REPLACE FUNCTION invalidate_checkpoints(
    p_session_id UUID,
    p_reason TEXT
) RETURNS INTEGER AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE session_checkpoints
    SET invalidated = TRUE,
        invalidation_reason = p_reason
    WHERE session_id = p_session_id
      AND invalidated = FALSE
      AND can_resume_from = TRUE;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$ LANGUAGE plpgsql;

-- Function to start checkpoint recovery
CREATE OR REPLACE FUNCTION start_checkpoint_recovery(
    p_checkpoint_id UUID,
    p_recovery_method VARCHAR(50),
    p_new_session_id UUID DEFAULT NULL
) RETURNS UUID AS $$
DECLARE
    v_recovery_id UUID;
BEGIN
    -- Create recovery record
    INSERT INTO checkpoint_recoveries (
        checkpoint_id,
        recovery_status,
        recovery_method,
        new_session_id
    ) VALUES (
        p_checkpoint_id,
        'in_progress',
        p_recovery_method,
        p_new_session_id
    )
    RETURNING id INTO v_recovery_id;

    -- Update checkpoint recovery count
    UPDATE session_checkpoints
    SET recovery_count = recovery_count + 1,
        last_resumed_at = NOW()
    WHERE id = p_checkpoint_id;

    RETURN v_recovery_id;
END;
$$ LANGUAGE plpgsql;

-- Function to complete checkpoint recovery
CREATE OR REPLACE FUNCTION complete_checkpoint_recovery(
    p_recovery_id UUID,
    p_status VARCHAR(20),
    p_recovery_notes TEXT DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL,
    p_state_differences JSONB DEFAULT '{}'
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE checkpoint_recoveries
    SET recovery_status = p_status,
        recovery_completed_at = NOW(),
        recovery_notes = p_recovery_notes,
        error_message = p_error_message,
        state_differences = p_state_differences
    WHERE id = p_recovery_id;

    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- Function to get latest resumable checkpoint for a session
CREATE OR REPLACE FUNCTION get_latest_resumable_checkpoint(
    p_session_id UUID
) RETURNS UUID AS $$
DECLARE
    v_checkpoint_id UUID;
BEGIN
    SELECT id INTO v_checkpoint_id
    FROM session_checkpoints
    WHERE session_id = p_session_id
      AND can_resume_from = TRUE
      AND invalidated = FALSE
    ORDER BY checkpoint_number DESC
    LIMIT 1;

    RETURN v_checkpoint_id;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update session status enum to include checkpointing states
-- Note: We're adding 'paused' and 'resumed' to the session_status enum if needed
DO $$
BEGIN
    -- Add 'paused' status if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'paused' AND enumtypid = 'session_status'::regtype) THEN
        ALTER TYPE session_status ADD VALUE 'paused';
    END IF;

    -- Add 'resumed' status if it doesn't exist
    IF NOT EXISTS (SELECT 1 FROM pg_enum WHERE enumlabel = 'resumed' AND enumtypid = 'session_status'::regtype) THEN
        ALTER TYPE session_status ADD VALUE 'resumed';
    END IF;
EXCEPTION
    WHEN duplicate_object THEN
        -- Ignore if values already exist
        NULL;
END$$;

COMMENT ON TABLE session_checkpoints IS 'Stores session state snapshots at key points for recovery and resumption';
COMMENT ON TABLE checkpoint_recoveries IS 'Tracks attempts to recover sessions from checkpoints';
COMMENT ON COLUMN session_checkpoints.conversation_history IS 'Full conversation history at checkpoint for context restoration';
COMMENT ON COLUMN session_checkpoints.tool_results_cache IS 'Recent tool results to avoid re-execution';
COMMENT ON COLUMN session_checkpoints.invalidated IS 'Set to true if state has diverged and checkpoint is no longer safe to resume from';
COMMENT ON COLUMN checkpoint_recoveries.state_differences IS 'JSON object documenting differences between checkpoint state and actual state';
