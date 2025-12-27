/**
 * CompletionBanner Component
 * Displays a celebration banner when a project completes all tasks
 */

'use client';

import { formatRelativeTime } from '@/lib/utils';

interface CompletionBannerProps {
  completedAt: string;
  totalEpics: number;
  totalTasks: number;
  totalTests: number;
}

export function CompletionBanner({
  completedAt,
  totalEpics,
  totalTasks,
  totalTests,
}: CompletionBannerProps) {
  return (
    <div className="bg-gradient-to-r from-green-500/10 via-blue-500/10 to-purple-500/10 border border-green-500/30 rounded-lg p-6 mb-6">
      <div className="flex items-center gap-4">
        <div className="text-5xl">🎉</div>
        <div className="flex-1">
          <h2 className="text-2xl font-bold text-green-400 mb-2">
            Project Complete!
          </h2>
          <p className="text-gray-300 mb-3">
            All tasks have been successfully completed. The agent finished working{' '}
            <span className="text-green-400 font-medium">
              {formatRelativeTime(completedAt)}
            </span>
            .
          </p>
          <div className="flex gap-6 text-sm">
            <div className="flex items-center gap-2">
              <span className="text-gray-600 dark:text-gray-400">Epics:</span>
              <span className="font-semibold text-green-400">{totalEpics}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-600 dark:text-gray-400">Tasks:</span>
              <span className="font-semibold text-blue-400">{totalTasks}</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-gray-600 dark:text-gray-400">Tests:</span>
              <span className="font-semibold text-purple-400">{totalTests}</span>
            </div>
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <div className="px-4 py-2 bg-green-500/20 text-green-400 rounded-md font-medium text-center">
            ✓ Complete
          </div>
        </div>
      </div>
    </div>
  );
}
