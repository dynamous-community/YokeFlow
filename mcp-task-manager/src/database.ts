/**
 * PostgreSQL database connection and query functions for task management
 * Uses the pg library for PostgreSQL connections
 */

import { Pool } from 'pg';
import type {
  Epic, Task, Test, ProjectStatus, EpicProgress,
  TaskWithEpic, TaskDetail, Session, NewEpic, NewTask, NewTest
} from './types.js';

export class TaskDatabase {
  private pool: Pool;
  private projectId: string;

  constructor() {
    // Get PostgreSQL connection from environment
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString) {
      throw new Error('DATABASE_URL environment variable is required');
    }

    // Get project ID from environment
    this.projectId = process.env.PROJECT_ID || '';
    if (!this.projectId) {
      throw new Error('PROJECT_ID environment variable is required');
    }

    // Create connection pool
    this.pool = new Pool({
      connectionString,
      max: 10, // Maximum number of connections in the pool
      idleTimeoutMillis: 30000, // Close idle clients after 30 seconds
      connectionTimeoutMillis: 2000, // Return an error after 2 seconds if connection could not be established
    });

    // Test connection on startup
    this.pool.query('SELECT NOW()').catch((err) => {
      throw new Error(`Failed to connect to PostgreSQL: ${err.message}`);
    });
  }

  // Execute a query and return results
  private async query<T>(sql: string, params: any[] = []): Promise<T[]> {
    try {
      const result = await this.pool.query(sql, params);
      return result.rows as T[];
    } catch (error: any) {
      throw new Error(`Database query failed: ${error.message}\nSQL: ${sql}`);
    }
  }

  // Execute a command without expecting results
  private async exec(sql: string, params: any[] = []): Promise<void> {
    try {
      await this.pool.query(sql, params);
    } catch (error: any) {
      throw new Error(`Database command failed: ${error.message}\nSQL: ${sql}`);
    }
  }

  // Query methods

  async getProjectStatus(): Promise<ProjectStatus> {
    const result = await this.query<ProjectStatus>(`
      SELECT
        (SELECT COUNT(*)::int FROM epics WHERE project_id = $1) as total_epics,
        (SELECT COUNT(*)::int FROM epics WHERE project_id = $1 AND status = 'completed') as completed_epics,
        (SELECT COUNT(*)::int FROM tasks WHERE project_id = $1) as total_tasks,
        (SELECT COUNT(*)::int FROM tasks WHERE project_id = $1 AND done = true) as completed_tasks,
        (SELECT COUNT(*)::int FROM tests t
         JOIN tasks tk ON t.task_id = tk.id
         WHERE tk.project_id = $1) as total_tests,
        (SELECT COUNT(*)::int FROM tests t
         JOIN tasks tk ON t.task_id = tk.id
         WHERE tk.project_id = $1 AND t.passes = true) as passing_tests,
        COALESCE(ROUND(100.0 * (SELECT COUNT(*) FROM tasks WHERE project_id = $1 AND done = true) /
              NULLIF((SELECT COUNT(*) FROM tasks WHERE project_id = $1), 0), 1), 0) as task_completion_pct,
        COALESCE(ROUND(100.0 * (SELECT COUNT(*) FROM tests t
         JOIN tasks tk ON t.task_id = tk.id
         WHERE tk.project_id = $1 AND t.passes = true) /
              NULLIF((SELECT COUNT(*) FROM tests t
         JOIN tasks tk ON t.task_id = tk.id
         WHERE tk.project_id = $1), 0), 1), 0) as test_pass_pct
    `, [this.projectId]);

    return result[0] || {
      total_epics: 0,
      completed_epics: 0,
      total_tasks: 0,
      completed_tasks: 0,
      total_tests: 0,
      passing_tests: 0,
      task_completion_pct: 0,
      test_pass_pct: 0
    };
  }

  async getNextTask(): Promise<TaskWithEpic | null> {
    const result = await this.query<TaskWithEpic>(`
      SELECT
        t.id::text,
        t.epic_id::text,
        t.description,
        t.action,
        'pending' as status,
        t.priority,
        t.created_at,
        t.completed_at,
        t.session_notes,
        CASE WHEN t.done = true THEN 1 ELSE 0 END as done,
        e.name as epic_name
      FROM tasks t
      JOIN epics e ON t.epic_id = e.id
      WHERE t.project_id = $1 AND t.done = false
      ORDER BY e.priority, t.priority
      LIMIT 1
    `, [this.projectId]);

    return result[0] || null;
  }

  async listEpics(needsExpansion = false): Promise<Epic[]> {
    let sql: string;
    let params: any[];

    if (needsExpansion) {
      sql = `
        SELECT
          e.id::text,
          e.name,
          e.description,
          e.priority,
          e.status,
          e.created_at,
          e.started_at,
          e.completed_at
        FROM epics e
        LEFT JOIN tasks t ON e.id = t.epic_id
        WHERE e.project_id = $1
        GROUP BY e.id, e.name, e.description, e.priority, e.status, e.created_at, e.started_at, e.completed_at
        HAVING COUNT(t.id) = 0
        ORDER BY e.priority
      `;
      params = [this.projectId];
    } else {
      sql = `
        SELECT
          id::text,
          name,
          description,
          priority,
          status,
          created_at,
          started_at,
          completed_at
        FROM epics
        WHERE project_id = $1
        ORDER BY priority
      `;
      params = [this.projectId];
    }

    const result = await this.query<Epic>(sql, params);
    return result || [];
  }

  async getEpic(id: string | number): Promise<Epic | null> {
    const result = await this.query<Epic>(`
      SELECT
        id::text,
        name,
        description,
        priority,
        status,
        created_at,
        started_at,
        completed_at
      FROM epics
      WHERE id = $1 AND project_id = $2
    `, [String(id), this.projectId]);

    return result[0] || null;
  }

  async getEpicProgress(id?: string | number): Promise<EpicProgress[]> {
    let sql = `
      SELECT
        e.id::text,
        e.name,
        e.priority,
        e.status,
        COUNT(t.id)::int as total_tasks,
        SUM(CASE WHEN t.done = true THEN 1 ELSE 0 END)::int as completed_tasks,
        (SELECT COUNT(*)::int FROM tests ts
         JOIN tasks tk ON ts.task_id = tk.id
         WHERE tk.epic_id = e.id) as total_tests,
        (SELECT COUNT(*)::int FROM tests ts
         JOIN tasks tk ON ts.task_id = tk.id
         WHERE tk.epic_id = e.id AND ts.passes = true) as passing_tests
      FROM epics e
      LEFT JOIN tasks t ON e.id = t.epic_id
      WHERE e.project_id = $1
    `;

    const params: any[] = [this.projectId];

    if (id !== undefined) {
      sql += ` AND e.id = $2`;
      params.push(String(id));
    }

    sql += ' GROUP BY e.id, e.name, e.priority, e.status ORDER BY e.priority';

    const result = await this.query<EpicProgress>(sql, params);
    return result || [];
  }

  async listTasks(epicId?: string | number, onlyPending = false): Promise<Task[]> {
    let sql = `
      SELECT
        id::text,
        epic_id::text,
        description,
        action,
        'pending' as status,
        priority,
        created_at,
        completed_at,
        session_notes,
        CASE WHEN done = true THEN 1 ELSE 0 END as done
      FROM tasks
      WHERE project_id = $1
    `;
    const params: any[] = [this.projectId];
    let paramCount = 1;

    if (epicId !== undefined) {
      sql += ` AND epic_id = $${++paramCount}`;
      params.push(String(epicId));
    }

    if (onlyPending) {
      sql += ` AND done = false`;
    }

    sql += ' ORDER BY priority';

    const result = await this.query<Task>(sql, params);
    return result || [];
  }

  async getTask(id: string | number): Promise<TaskDetail | null> {
    const taskResult = await this.query<any>(`
      SELECT
        t.id::text,
        t.epic_id::text,
        t.description,
        t.action,
        'pending' as status,
        t.priority,
        t.created_at,
        t.completed_at,
        t.session_notes,
        CASE WHEN t.done = true THEN 1 ELSE 0 END as done,
        e.name as epic_name
      FROM tasks t
      JOIN epics e ON t.epic_id = e.id
      WHERE t.id = $1 AND t.project_id = $2
    `, [String(id), this.projectId]);

    const task = taskResult[0];
    if (!task) return null;

    const tests = await this.query<Test>(`
      SELECT
        id::text,
        task_id::text,
        category,
        description,
        steps,
        passes,
        created_at,
        verified_at
      FROM tests
      WHERE task_id = $1
    `, [String(id)]) || [];

    return { ...task, tests };
  }

  async listTests(taskId: string | number): Promise<Test[]> {
    const result = await this.query<Test>(`
      SELECT
        id::text,
        task_id::text,
        category,
        description,
        steps,
        passes,
        created_at,
        verified_at
      FROM tests
      WHERE task_id = $1
      ORDER BY id
    `, [String(taskId)]);

    return result || [];
  }

  async getTest(id: string | number): Promise<Test | null> {
    const result = await this.query<Test>(`
      SELECT
        id::text,
        task_id::text,
        category,
        description,
        steps,
        passes,
        created_at,
        verified_at
      FROM tests
      WHERE id = $1
    `, [String(id)]);

    return result[0] || null;
  }

  // Mutation methods

  async createEpic(epic: NewEpic): Promise<Epic> {
    const result = await this.query<Epic>(`
      INSERT INTO epics (project_id, name, description, priority)
      VALUES ($1, $2, $3, $4)
      RETURNING
        id::text,
        name,
        description,
        priority,
        status,
        created_at,
        started_at,
        completed_at
    `, [this.projectId, epic.name, epic.description || null, epic.priority]);

    return result[0];
  }

  async createTask(task: NewTask): Promise<Task> {
    // Get next priority if not specified
    const priority = task.priority ?? await this.getNextTaskPriority(String(task.epic_id));

    const result = await this.query<Task>(`
      INSERT INTO tasks (epic_id, project_id, description, action, priority)
      VALUES ($1, $2, $3, $4, $5)
      RETURNING
        id::text,
        epic_id::text,
        description,
        action,
        'pending' as status,
        priority,
        created_at,
        completed_at,
        session_notes,
        CASE WHEN done = true THEN 1 ELSE 0 END as done
    `, [String(task.epic_id), this.projectId, task.description, task.action, priority]);

    return result[0];
  }

  async createTest(test: NewTest): Promise<Test> {
    const result = await this.query<Test>(`
      INSERT INTO tests (task_id, project_id, category, description, steps)
      VALUES ($1, $2, $3, $4, $5)
      RETURNING
        id::text,
        task_id::text,
        category,
        description,
        steps,
        passes,
        created_at,
        verified_at
    `, [String(test.task_id), this.projectId, test.category, test.description, JSON.stringify(test.steps)]);

    return result[0];
  }

  async updateTaskStatus(taskId: string | number, done: boolean): Promise<Task | null> {
    // CRITICAL: If marking task as complete, validate all tests are passing
    if (done === true) {
      const tests = await this.listTests(taskId);

      if (tests.length > 0) {
        const failingTests = tests.filter(t => t.passes !== true);

        if (failingTests.length > 0) {
          throw new Error(
            `Cannot mark task ${taskId} as complete: ${failingTests.length} of ${tests.length} test(s) not passing.\n` +
            `Failing tests:\n${failingTests.map(t => `  - Test ${t.id}: ${t.description}`).join('\n')}\n\n` +
            `All tests must pass before marking task complete. Use update_test_result to mark tests as passing.`
          );
        }
      }
    }

    const completedAt = done ? 'NOW()' : 'NULL';

    await this.exec(`
      UPDATE tasks
      SET done = $1, completed_at = ${completedAt}
      WHERE id = $2 AND project_id = $3
    `, [done, String(taskId), this.projectId]);

    // Check if all tasks in epic are done and update epic status
    if (done) {
      const task = await this.getTask(taskId);
      if (task) {
        await this.checkEpicCompletion(task.epic_id);
      }
    }

    const result = await this.query<Task>(`
      SELECT
        id::text,
        epic_id::text,
        description,
        action,
        'pending' as status,
        priority,
        created_at,
        completed_at,
        session_notes,
        CASE WHEN done = true THEN 1 ELSE 0 END as done
      FROM tasks
      WHERE id = $1 AND project_id = $2
    `, [String(taskId), this.projectId]);

    return result[0] || null;
  }

  async updateTestResult(testId: string | number, passes: boolean): Promise<Test | null> {
    const verifiedAt = passes ? 'NOW()' : 'NULL';

    await this.exec(`
      UPDATE tests
      SET passes = $1, verified_at = ${verifiedAt}
      WHERE id = $2
    `, [passes, String(testId)]);

    return await this.getTest(testId);
  }

  async startTask(taskId: string | number): Promise<void> {
    await this.exec(`
      UPDATE tasks
      SET session_notes = 'Started at ' || NOW()::text
      WHERE id = $1 AND project_id = $2 AND session_notes IS NULL
    `, [String(taskId), this.projectId]);
  }

  // Helper methods

  private async getNextTaskPriority(epicId: string | number): Promise<number> {
    const result = await this.query<{next: number}>(`
      SELECT COALESCE(MAX(priority), 0) + 1 as next
      FROM tasks
      WHERE epic_id = $1
    `, [String(epicId)]);

    return result[0]?.next || 1;
  }

  private async checkEpicCompletion(epicId: string | number): Promise<void> {
    const result = await this.query<{pending: number}>(`
      SELECT COUNT(*)::int as pending
      FROM tasks
      WHERE epic_id = $1 AND done = false
    `, [String(epicId)]);

    if (result[0]?.pending === 0) {
      await this.exec(`
        UPDATE epics
        SET status = 'completed', completed_at = NOW()
        WHERE id = $1
      `, [String(epicId)]);
    }
  }

  async logSession(sessionNumber: number, notes?: string): Promise<Session> {
    // Calculate metrics
    const tasksCompleted = await this.query<{count: number}>(`
      SELECT COUNT(*)::int as count FROM tasks
      WHERE project_id = $1 AND completed_at >= NOW() - INTERVAL '1 hour'
    `, [this.projectId]);

    const testsPassed = await this.query<{count: number}>(`
      SELECT COUNT(*)::int as count FROM tests t
      JOIN tasks tk ON t.task_id = tk.id
      WHERE tk.project_id = $1 AND t.verified_at >= NOW() - INTERVAL '1 hour'
    `, [this.projectId]);

    const metrics = {
      tasks_completed: tasksCompleted[0]?.count || 0,
      tests_passed: testsPassed[0]?.count || 0,
      notes: notes || null
    };

    const result = await this.query<Session>(`
      INSERT INTO sessions (project_id, session_number, type, model, status, metrics)
      VALUES ($1, $2, 'coding', 'claude-sonnet', 'completed', $3)
      RETURNING
        id::text,
        session_number,
        metrics,
        created_at
    `, [this.projectId, sessionNumber, JSON.stringify(metrics)]);

    return result[0];
  }

  async getSessionHistory(limit = 10): Promise<Session[]> {
    const result = await this.query<Session>(`
      SELECT
        id::text,
        session_number,
        type,
        model,
        status,
        metrics,
        created_at,
        started_at,
        ended_at
      FROM sessions
      WHERE project_id = $1
      ORDER BY session_number DESC
      LIMIT $2
    `, [this.projectId, limit]);

    return result || [];
  }

  async expandEpic(epicId: string | number, tasks: NewTask[]): Promise<Task[]> {
    const id = String(epicId);
    await this.exec(`
      UPDATE epics
      SET status = 'in_progress', started_at = NOW()
      WHERE id = $1 AND status = 'pending'
    `, [id]);

    const createdTasks: Task[] = [];
    for (const task of tasks) {
      const created = await this.createTask({ ...task, epic_id: id });
      createdTasks.push(created);
    }
    return createdTasks;
  }

  async markProjectComplete(): Promise<void> {
    await this.exec(`
      UPDATE projects
      SET completed_at = COALESCE(completed_at, NOW())
      WHERE id = $1
    `, [this.projectId]);
  }

  async close(): Promise<void> {
    await this.pool.end();
  }
}