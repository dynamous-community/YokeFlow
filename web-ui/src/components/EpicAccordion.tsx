/**
 * EpicAccordion - Display epic with collapsible task list
 *
 * Shows:
 * - Epic name, description, progress
 * - Expandable task list
 * - Task completion status and test results
 * - Clickable tasks to open TaskDetailModal
 */

'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, Circle, XCircle, AlertCircle } from 'lucide-react';
import { ProgressBar } from './ProgressBar';
import type { Epic, TaskWithTestCount } from '@/lib/types';

interface EpicAccordionProps {
  epic: Epic;
  tasks: TaskWithTestCount[];
  onTaskClick: (taskId: number) => void;
}

export function EpicAccordion({ epic, tasks, onTaskClick }: EpicAccordionProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Calculate progress
  const completedTasks = tasks.filter(t => t.done).length;
  const totalTasks = tasks.length;
  const progressPercent = totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

  // Calculate test stats
  const totalTests = tasks.reduce((sum, t) => sum + (t.test_count || 0), 0);
  const passingTests = tasks.reduce((sum, t) => sum + (t.passing_test_count || 0), 0);

  // Epic status badge
  const getStatusBadge = () => {
    if (epic.status === 'completed' || completedTasks === totalTasks) {
      return (
        <span className="px-2 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 text-xs font-medium">
          Complete
        </span>
      );
    }
    if (epic.status === 'in_progress' || completedTasks > 0) {
      return (
        <span className="px-2 py-1 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-medium">
          In Progress
        </span>
      );
    }
    return (
      <span className="px-2 py-1 rounded-full bg-gray-500/20 text-gray-400 border border-gray-500/30 text-xs font-medium">
        Pending
      </span>
    );
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Epic Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full p-4 flex items-start gap-3 hover:bg-gray-800/50 transition-colors text-left"
      >
        {/* Expand Icon */}
        <div className="mt-1 flex-shrink-0">
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-600 dark:text-gray-400" />
          )}
        </div>

        {/* Epic Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className="text-lg font-semibold text-gray-100">{epic.name}</h3>
            {getStatusBadge()}
          </div>

          {epic.description && (
            <p className="text-sm text-gray-400 mb-3">{epic.description}</p>
          )}

          {/* Progress Stats */}
          <div className="space-y-2">
            <div className="flex items-center gap-4 text-sm">
              <span className="text-gray-600 dark:text-gray-400">
                Tasks: <span className="text-gray-200 font-medium">{completedTasks}/{totalTasks}</span>
              </span>
              <span className="text-gray-600 dark:text-gray-400">
                Tests: <span className="text-gray-200 font-medium">{passingTests}/{totalTests}</span>
              </span>
            </div>
            <ProgressBar
              value={progressPercent}
              className="h-2"
              color={progressPercent === 100 ? 'green' : progressPercent > 0 ? 'blue' : 'red'}
              showPercentage={false}
            />
          </div>
        </div>
      </button>

      {/* Task List */}
      {isExpanded && (
        <div className="border-t border-gray-800">
          {tasks.length === 0 ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              No tasks in this epic yet
            </div>
          ) : (
            <div className="divide-y divide-gray-800">
              {tasks.map((task) => (
                <TaskRow key={task.id} task={task} onTaskClick={onTaskClick} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Task row component
function TaskRow({ task, onTaskClick }: { task: TaskWithTestCount; onTaskClick: (taskId: number) => void }) {
  const hasTests = (task.test_count || 0) > 0;
  const passingTests = task.passing_test_count || 0;
  const totalTests = task.test_count || 0;
  const allTestsPassing = hasTests && passingTests === totalTests;
  const someTestsFailing = hasTests && passingTests < totalTests;

  return (
    <button
      onClick={() => onTaskClick(task.id)}
      className="w-full p-4 flex items-start gap-3 hover:bg-gray-800/50 transition-colors text-left group"
    >
      {/* Status Icon */}
      <div className="mt-0.5 flex-shrink-0">
        {task.done ? (
          <CheckCircle className="w-5 h-5 text-green-400" />
        ) : (
          <Circle className="w-5 h-5 text-gray-700 dark:text-gray-500" />
        )}
      </div>

      {/* Task Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-3 mb-1">
          <p className={`text-sm ${task.done ? 'text-gray-300' : 'text-gray-100'} group-hover:text-blue-400 transition-colors`}>
            {task.description}
          </p>
        </div>

        {/* Test Status */}
        {hasTests && (
          <div className="flex items-center gap-2 mt-2">
            <div className="flex items-center gap-1 text-xs">
              {allTestsPassing && (
                <>
                  <CheckCircle className="w-3 h-3 text-green-400" />
                  <span className="text-green-400 font-medium">
                    All tests passing ({totalTests})
                  </span>
                </>
              )}
              {someTestsFailing && (
                <>
                  <AlertCircle className="w-3 h-3 text-amber-400" />
                  <span className="text-amber-400 font-medium">
                    {passingTests}/{totalTests} tests passing
                  </span>
                </>
              )}
              {!task.done && passingTests === 0 && (
                <>
                  <XCircle className="w-3 h-3 text-gray-700 dark:text-gray-500" />
                  <span className="text-gray-500 font-medium">
                    {totalTests} test{totalTests !== 1 ? 's' : ''} not run
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {!hasTests && (
          <p className="text-xs text-gray-600 mt-2">No tests</p>
        )}
      </div>
    </button>
  );
}
