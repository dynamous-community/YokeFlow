/**
 * TypeScript types for the YokeFlow API
 * These match the Pydantic models in the FastAPI backend
 */

export interface Progress {
  total_epics: number;
  completed_epics: number;
  total_tasks: number;
  completed_tasks: number;
  total_tests: number;
  passing_tests: number;
  task_completion_pct: number;
  test_pass_pct: number;
}

export interface Task {
  id: number;
  epic_id: number;
  description: string;
  action: string;
  priority: number;
  done: boolean;
  created_at: string;
  completed_at: string | null;
  session_notes: string | null;
  session_id?: string | null;
  epic_name?: string;
}

export interface Test {
  id: number;
  task_id: number;
  category: string;
  description: string;
  steps: any; // JSONB array of steps
  passes: boolean | null;
  created_at: string;
  verified_at: string | null;
  result?: any; // JSONB test result data
}

export interface Epic {
  id: number;
  name: string;
  description: string;
  priority: number;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TaskWithTestCount extends Task {
  test_count: number;
  passing_test_count: number;
}

export interface TaskWithTests extends Task {
  tests: Test[];
  epic_name: string;
  epic_description: string;
}

export interface EpicWithTasks extends Epic {
  tasks: TaskWithTestCount[];
}

export interface Project {
  id: string;  // UUID from PostgreSQL
  name: string;  // Project name
  created_at: string;
  updated_at: string;
  status: string;
  sandbox_type?: string;  // Sandbox type: 'docker', 'local', etc.
  is_initialized: boolean;  // NEW: Whether initialization (Session 1) is complete
  completed_at: string | null;  // Timestamp when all tasks completed
  total_cost_usd: number;  // Total cost across all sessions
  total_time_seconds: number;  // Total time in seconds across all sessions
  progress: Progress;
  next_task: Task | null;
  active_sessions: any[];  // TODO: define Session type
  has_env_file: boolean;
  has_env_example: boolean;
  needs_env_config: boolean;
  env_configured: boolean;
  spec_file_path: string;
  // Legacy fields for backwards compatibility
  project_id?: string;  // Deprecated: use 'id' instead
  project_path?: string;  // Deprecated
}

export type SessionType = 'initializer' | 'coding';
export type SessionStatus = 'pending' | 'running' | 'completed' | 'error' | 'interrupted';

export interface SessionMetrics {
  duration_seconds?: number;
  tool_calls_count?: number;
  tokens_input?: number;
  tokens_output?: number;
  cost_usd?: number;
  tasks_completed?: number;
  tests_passed?: number;
  errors_count?: number;  // Used in some contexts
  tool_errors?: number;  // Actual field name in database
  browser_verifications?: number;
  epics_created?: number;
  tasks_created?: number;
  tests_created?: number;
}

export interface Session {
  session_id: string;
  project_id: string;
  session_number: number;
  session_type: SessionType;
  type: SessionType; // Alias for session_type (used in UI)
  model: string;
  status: SessionStatus;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  error_message: string | null;
  interruption_reason: string | null;
  metrics?: SessionMetrics; // Session metrics from database
}

export interface SessionConfig {
  initializer_model?: string;
  coding_model?: string;
  max_iterations?: number | null;
}

export interface CreateProjectRequest {
  name: string;
  force?: boolean;
}

// CreateProjectResponse is the same as ProjectResponse
// The create endpoint returns a full project object
export interface CreateProjectResponse extends Project {}

export interface StartSessionResponse extends Session {}

export interface StopSessionRequest {
  session_id: string;
}

export interface StopSessionResponse {
  success: boolean;
  message: string;
}

export interface WebSocketMessage {
  type:
    | 'initial_state'
    | 'progress_update'
    | 'progress'  // Real-time progress events from agent
    | 'session_started'
    | 'session_complete'
    | 'initialization_complete'  // Initialization (Session 0) completed
    | 'coding_sessions_complete'  // All coding sessions complete (stop-after-current or all tasks done)
    | 'session_error'
    | 'api_key_warning'  // Warning: Using ANTHROPIC_API_KEY instead of OAuth
    | 'assistant_message'
    | 'tool_use'
    | 'task_updated'  // Task status changed
    | 'test_updated'  // Test result changed
    | 'all_epics_complete'  // All epics finished
    | 'project_complete'  // Project fully complete
    | 'prompt_improvement_complete'  // Prompt improvement analysis completed
    | 'prompt_improvement_failed';  // Prompt improvement analysis failed
  progress?: Progress;
  session_id?: string;
  status?: SessionStatus;
  error?: string;
  message?: string;  // For api_key_warning and other text messages
  // NEW Phase 1.3 fields
  session?: Session;  // For session_started event
  session_number?: number;  // For assistant_message and tool_use events
  message_number?: number;  // For assistant_message event
  // Task/test update fields
  task_id?: number;  // For task_updated event
  test_id?: number;  // For test_updated event
  done?: boolean;    // For task_updated event
  passes?: boolean;  // For test_updated event
  text?: string;  // For assistant_message event
  tool_name?: string;  // For tool_use event
  tool_count?: number;  // For tool_use event (cumulative)
  timestamp?: string;  // For all events
  // Prompt improvement event fields
  analysis_id?: string;  // For prompt_improvement_complete/failed events
  proposals_count?: number;  // For prompt_improvement_complete event
  // Real-time progress event data
  event?: {
    type: 'tool_use' | 'tool_result';
    tool_name?: string;
    tool_id?: string;
    timestamp?: string;
    is_error?: boolean;
  };
  project_id?: string;  // For all events
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  version: string;
}

export interface InfoResponse {
  generations_dir: string;
  default_models: {
    initializer: string;
    coding: string;
  };
  version: string;
}

export interface ProjectSettings {
  sandbox_type: 'docker' | 'local';
  coding_model: string;
  initializer_model: string;
  max_iterations: number | null;
}

export interface UpdateSettingsRequest {
  sandbox_type?: 'docker' | 'local';
  coding_model?: string;
  initializer_model?: string;
  max_iterations?: number | null;
}

export interface ResetProjectResponse {
  success: boolean;
  error: string | null;
  state_before: {
    completed_tasks: number;
    passing_tests: number;
    total_tasks: number;
    total_tests: number;
    coding_sessions: number;
    git_commits: number;
    coding_logs: number;
  };
  state_after: {
    completed_tasks: number;
    passing_tests: number;
    total_tasks: number;
    total_tests: number;
    coding_sessions: number;
    git_commits: number;
    coding_logs: number;
  };
  archive_path: string | null;
  steps: {
    validation?: { success: boolean; error: string | null };
    docker?: { success: boolean; message: string | null };
    database?: { success: boolean; error: string | null };
    git?: { success: boolean; error: string | null };
    logs?: { success: boolean; error: string | null };
    progress?: { success: boolean; error: string | null };
  };
}

// Test Coverage Analysis Types
export interface TestCoverageOverall {
  total_epics: number;
  total_tasks: number;
  total_tests: number;
  tasks_with_tests: number;
  tasks_without_tests: number;
  avg_tests_per_task: number;
  coverage_percentage: number;
}

export interface TestCoverageEpic {
  epic_id: number;
  epic_name: string;
  total_tasks: number;
  tasks_with_tests: number;
  tasks_without_tests: number;
  total_tests: number;
  coverage_percentage: number;
  tasks_0_tests: Task[];
  tasks_1_test: Task[];
  tasks_2plus_tests: Task[];
}

export interface PoorCoverageEpic {
  epic_id: number;
  epic_name: string;
  tasks_without_tests: number;
  total_tasks: number;
  coverage_percentage: number;
  tasks: Task[];
}

export interface TestCoverageData {
  overall: TestCoverageOverall;
  by_epic: TestCoverageEpic[];
  poor_coverage_epics: PoorCoverageEpic[];
  warnings: string[];
}

export interface TestCoverageResponse {
  analyzed_at: string;
  data: TestCoverageData;
}

// ============================================================================
// Prompt Improvement System Types
// ============================================================================

export type AnalysisStatus = 'pending' | 'running' | 'completed' | 'failed';
export type ProposalStatus = 'proposed' | 'accepted' | 'rejected' | 'implemented';
export type ChangeType = 'addition' | 'modification' | 'deletion' | 'reorganization';

/**
 * Pattern identified across multiple sessions
 */
export interface IdentifiedPattern {
  frequency: number;  // Percentage of sessions affected (0.0 to 1.0)
  sessions_affected: number;
  severity: 'low' | 'medium' | 'high' | 'critical';
  recommendation: string;
  evidence?: string[];  // Session IDs or log references
}

/**
 * Collection of patterns from an analysis
 */
export interface PatternsIdentified {
  missing_browser_verification?: IdentifiedPattern;
  high_error_rate?: IdentifiedPattern;
  low_quality_sessions?: IdentifiedPattern;
  [key: string]: IdentifiedPattern | undefined;  // Allow additional patterns
}

/**
 * Evidence supporting a proposal
 */
export interface ProposalEvidence {
  session_ids?: string[];
  error_messages?: string[];
  quality_scores?: number[];
  pattern_frequency?: number;
}

/**
 * Individual prompt change proposal
 */
export interface PromptProposal {
  id: string;  // UUID
  analysis_id: string;  // UUID reference to analysis
  created_at: string;

  // Change details
  prompt_file: string;  // 'coding_prompt_docker.md' or 'coding_prompt_local.md'
  section_name: string | null;
  line_start: number | null;
  line_end: number | null;

  // The actual change
  original_text: string;
  proposed_text: string;
  change_type: ChangeType;

  // Justification
  rationale: string;
  evidence: ProposalEvidence;
  confidence_level: number;  // 1-10

  // Implementation status
  status: ProposalStatus;
  applied_at: string | null;
  applied_to_version: string | null;

  // Impact tracking (nullable until measured)
  sessions_before_change: number | null;
  quality_before: number | null;
  sessions_after_change: number | null;
  quality_after: number | null;
}

/**
 * Summary of a prompt improvement analysis
 */
export interface PromptAnalysisSummary {
  id: string;  // UUID
  created_at: string;
  completed_at: string | null;
  status: AnalysisStatus;

  // Scope
  sandbox_type: string;  // 'docker' or 'local'
  num_projects: number;  // Number of projects analyzed
  sessions_analyzed: number;

  // Results summary
  quality_impact_estimate: number | null;
  total_proposals: number;
  pending_proposals: number;
  accepted_proposals: number;
  implemented_proposals: number;
}

/**
 * Detailed analysis with all findings
 */
export interface PromptAnalysisDetail extends PromptAnalysisSummary {
  date_range_start: string | null;
  date_range_end: string | null;
  analysis_model: string;
  overall_findings: string | null;
  patterns_identified: PatternsIdentified;
  proposed_changes: any;  // Legacy JSONB field
  notes: string | null;

  // Related data (loaded separately)
  proposals?: PromptProposal[];
}

/**
 * Request to trigger a new analysis
 */
export interface TriggerAnalysisRequest {
  project_ids?: string[];  // Optional: specific projects to analyze
  sandbox_type?: string;  // 'docker' or 'local'
  last_n_days?: number;  // Time window (default: 7)
}

/**
 * Response from triggering analysis
 */
export interface TriggerAnalysisResponse {
  analysis_id: string;
  projects_analyzed: number;
  sessions_analyzed: number;
  proposals_generated: number;
  patterns_found: PatternsIdentified;
  message?: string;
}

/**
 * Request to update proposal status
 */
export interface UpdateProposalRequest {
  status: ProposalStatus;
  notes?: string;
}

/**
 * Response from applying a proposal
 */
export interface ApplyProposalResponse {
  success: boolean;
  message: string;
  file_path?: string;
  backup_path?: string;
  git_commit?: string;
}

/**
 * Project review statistics
 */
export interface ProjectReviewStats {
  total_sessions: number;
  sessions_with_reviews: number;
  sessions_without_reviews: number;
  coverage_percent: number;
  unreviewed_session_numbers: number[];
}

/**
 * Request to trigger bulk reviews
 */
export interface TriggerBulkReviewsRequest {
  mode: 'all' | 'unreviewed' | 'last_n' | 'range' | 'single';
  last_n?: number;  // For 'last_n' mode
  session_ids?: string[];  // For 'range' mode
  session_number?: number;  // For 'single' mode
}

/**
 * Response from triggering bulk reviews
 */
export interface TriggerBulkReviewsResponse {
  message: string;
  project_id: string;
  mode: string;
  sessions_triggered: number;
  status: string;
}

/**
 * Overall improvement metrics
 */
export interface ImprovementMetrics {
  total_analyses: number;
  total_proposals: number;
  accepted_proposals: number;
  implemented_proposals: number;
  rejected_proposals: number;
  avg_quality_improvement: number | null;
  last_analysis_at: string | null;
}

/**
 * Screenshot metadata
 */
export interface Screenshot {
  filename: string;
  size: number;
  modified_at: string;
  task_id: number | null;
  url: string;
}

/**
 * Docker container status
 */
export interface ContainerStatus {
  container_exists: boolean;
  status?: string; // 'running', 'exited', 'paused', etc.
  container_id?: string;
  container_name?: string;
  ports?: Record<string, any>;
  sandbox_type: string;
  message?: string;
}

export interface ContainerActionResponse {
  message: string;
  started?: boolean;
  stopped?: boolean;
  deleted?: boolean;
}
