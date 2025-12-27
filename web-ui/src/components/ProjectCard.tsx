/**
 * Project Card Component
 * Displays a project summary with progress and stats
 */

import Link from 'next/link';
import { ProgressBar } from './ProgressBar';
import { truncate, formatDuration } from '@/lib/utils';
import type { Project } from '@/lib/types';

interface ProjectCardProps {
  project: Project;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const { id, name, progress, next_task, active_sessions } = project;
  const has_active_session = active_sessions && active_sessions.length > 0;

  // Determine project status
  const isComplete = progress.completed_tasks === progress.total_tasks && progress.total_tasks > 0;
  const isRunning = has_active_session;
  const isReady = !isComplete && next_task && !isRunning;
  const isNotStarted = !next_task && !isComplete;

  return (
    <Link
      href={`/projects/${id}`}
      className="block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-6 hover:border-gray-300 dark:hover:border-gray-700 hover:shadow-md transition-all"
    >
      <div className="flex items-start justify-between mb-4">
        <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">{name}</h3>
        <div className="flex items-center gap-2 text-sm">
          {isComplete ? (
            <span style={{ paddingLeft: '0.75rem', paddingRight: '0.75rem' }} className="py-1 rounded-full bg-green-100 dark:bg-green-500/20 text-green-700 dark:text-green-400 border border-green-300 dark:border-green-500/30">
              Complete
            </span>
          ) : isRunning ? (
            <span style={{ paddingLeft: '0.75rem', paddingRight: '0.75rem' }} className="py-1 rounded-full bg-purple-100 dark:bg-purple-500/20 text-purple-700 dark:text-purple-400 border border-purple-300 dark:border-purple-500/30">
              Running
            </span>
          ) : isReady ? (
            <span style={{ paddingLeft: '0.75rem', paddingRight: '0.75rem' }} className="py-1 rounded-full bg-blue-100 dark:bg-blue-500/20 text-blue-700 dark:text-blue-400 border border-blue-300 dark:border-blue-500/30">
              Ready
            </span>
          ) : (
            <span style={{ paddingLeft: '0.75rem', paddingRight: '0.75rem' }} className="py-1 rounded-full bg-gray-100 dark:bg-gray-500/20 text-gray-700 dark:text-gray-400 border border-gray-300 dark:border-gray-500/30">
              Not Started
            </span>
          )}
        </div>
      </div>

      <div className="space-y-4">
        {/* Task Progress */}
        <ProgressBar
          value={progress.task_completion_pct}
          label="Tasks"
          color={progress.task_completion_pct === 100 ? 'green' : 'blue'}
        />

        {/* Test Progress */}
        <ProgressBar
          value={progress.test_pass_pct}
          label="Tests"
          color={progress.test_pass_pct === 100 ? 'green' : progress.test_pass_pct > 0 ? 'yellow' : 'blue'}
        />

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4 pt-2">
          <div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              {progress.completed_epics}/{progress.total_epics}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Epics</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              {progress.completed_tasks}/{progress.total_tasks}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Tasks</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-gray-900 dark:text-gray-100">
              {progress.passing_tests}/{progress.total_tests}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Tests</div>
          </div>
        </div>

        {/* Next Task */}
        {next_task && (
          <div className="pt-4 border-t border-gray-200 dark:border-gray-800">
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Next Task:</div>
            <div className="text-sm text-gray-700 dark:text-gray-300">
              {truncate(next_task.description, 80)}
            </div>
          </div>
        )}

        {/* Completion Stats (for completed projects) */}
        {isComplete && project.total_time_seconds > 0 && (
          <div className="pt-4 border-t border-gray-200 dark:border-gray-800">
            <div className="flex items-center justify-between text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Time: </span>
                <span className="text-gray-900 dark:text-gray-100 font-medium">
                  {formatDuration(project.total_time_seconds)}
                </span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Cost: </span>
                <span className="text-gray-900 dark:text-gray-100 font-medium">
                  ${project.total_cost_usd.toFixed(2)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </Link>
  );
}
