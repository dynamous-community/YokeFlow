/**
 * Type definitions for the Task Management MCP Server
 */

// ID can be number (legacy compatibility) or string (PostgreSQL UUID)
export type EntityId = number | string;

export interface Epic {
  id: EntityId;
  name: string;
  description: string | null;
  priority: number;
  status: 'pending' | 'in_progress' | 'complete';
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface Task {
  id: EntityId;
  epic_id: EntityId;
  description: string;
  action: string;
  priority: number;
  done: 0 | 1;
  created_at: string;
  completed_at: string | null;
  session_notes: string | null;
}

export interface Test {
  id: EntityId;
  task_id: EntityId;
  category: 'functional' | 'style' | 'accessibility' | 'performance';
  description: string;
  steps: string; // JSON array as string
  passes: 0 | 1 | boolean; // PostgreSQL uses boolean, legacy compatibility for 0/1
  created_at: string;
  verified_at: string | null;
}

export interface ProjectStatus {
  total_epics: number;
  completed_epics: number;
  total_tasks: number;
  completed_tasks: number;
  total_tests: number;
  passing_tests: number;
  task_completion_pct: number;
  test_pass_pct: number;
}

export interface EpicProgress {
  id: EntityId;
  name: string;
  priority: number;
  status: string;
  total_tasks: number;
  completed_tasks: number;
  total_tests: number;
  passing_tests: number;
}

export interface TaskWithEpic extends Task {
  epic_name: string;
}

export interface TaskDetail extends Task {
  epic_name: string;
  tests: Test[];
}

export interface Session {
  id: EntityId;
  session_number: number;
  type: string;
  model: string;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  metrics: {
    tasks_completed?: number;
    tests_passed?: number;
    notes?: string | null;
    duration_seconds?: number;
    tool_calls_count?: number;
    tokens_input?: number;
    tokens_output?: number;
    cost_usd?: number;
    browser_verifications?: number;
    errors_count?: number;
  };
}

// Input types for creating/updating entities
export interface NewEpic {
  name: string;
  description?: string;
  priority: number;
}

export interface NewTask {
  epic_id: EntityId;
  description: string;
  action: string;
  priority?: number;
}

export interface NewTest {
  task_id: EntityId;
  category: Test['category'];
  description: string;
  steps: string[];
}

export type TaskStatus = 'pending' | 'in_progress' | 'completed';
export type EpicStatus = 'pending' | 'in_progress' | 'complete';

// Filter types for queries
export interface TaskFilter {
  epic_id?: EntityId;
  done?: boolean;
  limit?: number;
}

export interface EpicFilter {
  status?: EpicStatus;
  needs_expansion?: boolean;
}