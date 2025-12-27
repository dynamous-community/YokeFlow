/**
 * TaskDetailModal - Display detailed task information in a modal dialog
 *
 * Shows:
 * - Task description and action
 * - Epic context
 * - Completion status
 * - All associated tests with pass/fail status
 * - Session info (which session completed it)
 */

'use client';

import React, { useEffect, useState } from 'react';
import { X, CheckCircle, XCircle, Circle, Clock, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import type { TaskWithTests, Test } from '@/lib/types';

interface TaskDetailModalProps {
  projectId: string;
  taskId: number;
  isOpen: boolean;
  onClose: () => void;
}

export function TaskDetailModal({ projectId, taskId, isOpen, onClose }: TaskDetailModalProps) {
  const [task, setTask] = useState<TaskWithTests | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && taskId) {
      loadTask();
    }
  }, [isOpen, taskId, projectId]);

  async function loadTask() {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTask(projectId, taskId);
      setTask(data);
    } catch (err: any) {
      console.error('Failed to load task:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  // Backdrop click handler
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  // Category badge colors
  const getCategoryColor = (category: string) => {
    switch (category.toLowerCase()) {
      case 'functional':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'accessibility':
        return 'bg-purple-500/20 text-purple-400 border-purple-500/30';
      case 'style':
        return 'bg-pink-500/20 text-pink-400 border-pink-500/30';
      case 'performance':
        return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
      case 'security':
        return 'bg-red-500/20 text-red-400 border-red-500/30';
      default:
        return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div className="bg-gray-900 border border-gray-800 rounded-lg max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-start justify-between p-6 border-b border-gray-800">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h2 className="text-xl font-semibold text-gray-100">
                Task #{taskId}
              </h2>
              {task?.done && (
                <span className="flex items-center gap-1 px-2 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 text-xs font-medium">
                  <CheckCircle className="w-3 h-3" />
                  Complete
                </span>
              )}
            </div>
            {task && (
              <p className="text-sm text-gray-600 dark:text-gray-400">
                from Epic: <span className="text-blue-400">{task.epic_name}</span>
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-300 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="text-center">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3"></div>
                <p className="text-gray-400 text-sm">Loading task details...</p>
              </div>
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
              <p className="font-medium mb-1">Error loading task</p>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {!loading && !error && task && (
            <div className="space-y-6">
              {/* Epic Context */}
              {task.epic_description && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                    <FileText className="w-4 h-4" />
                    Epic Context
                  </h3>
                  <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                    <p className="text-gray-300 text-sm">{task.epic_description}</p>
                  </div>
                </div>
              )}

              {/* Task Description */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Description</h3>
                <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                  <p className="text-gray-100 whitespace-pre-wrap">{task.description}</p>
                </div>
              </div>

              {/* Task Action */}
              {task.action && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Implementation Details</h3>
                  <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50">
                    <p className="text-gray-300 text-sm whitespace-pre-wrap">{task.action}</p>
                  </div>
                </div>
              )}

              {/* Completion Info */}
              {task.completed_at && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Completion Info
                  </h3>
                  <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50 space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600 dark:text-gray-400">Completed:</span>
                      <span className="text-gray-200">
                        {new Date(task.completed_at).toLocaleString()}
                      </span>
                    </div>
                    {task.session_id && (
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-600 dark:text-gray-400">Session:</span>
                        <span className="text-blue-400 font-mono">#{task.session_id.slice(0, 8)}</span>
                      </div>
                    )}
                    {task.session_notes && (
                      <div className="mt-3 pt-3 border-t border-gray-700">
                        <p className="text-sm text-gray-300">{task.session_notes}</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Tests */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-3">
                  Tests ({task.tests.length})
                </h3>
                {task.tests.length === 0 ? (
                  <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700/50 text-center">
                    <p className="text-gray-500 text-sm">No tests defined for this task</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {task.tests.map((test) => (
                      <TestItem key={test.id} test={test} getCategoryColor={getCategoryColor} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-100 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// Test item component
function TestItem({ test, getCategoryColor }: { test: Test; getCategoryColor: (category: string) => string }) {
  const [expanded, setExpanded] = useState(false);

  // Parse steps if they're a JSON string
  const steps = typeof test.steps === 'string' ? JSON.parse(test.steps || '[]') : test.steps || [];
  const hasSteps = Array.isArray(steps) && steps.length > 0;

  return (
    <div className="bg-gray-800/50 rounded-lg border border-gray-700/50 overflow-hidden">
      <div
        className={`p-4 ${hasSteps ? 'cursor-pointer hover:bg-gray-800/80' : ''}`}
        onClick={() => hasSteps && setExpanded(!expanded)}
      >
        <div className="flex items-start gap-3">
          {/* Status Icon */}
          <div className="mt-0.5 flex-shrink-0">
            {test.passes === true && (
              <CheckCircle className="w-5 h-5 text-green-400" />
            )}
            {test.passes === false && (
              <XCircle className="w-5 h-5 text-red-400" />
            )}
            {test.passes === null && (
              <Circle className="w-5 h-5 text-gray-700 dark:text-gray-500" />
            )}
          </div>

          {/* Test Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-xs font-medium border ${getCategoryColor(test.category)}`}>
                {test.category}
              </span>
              {test.passes === true && (
                <span className="text-xs text-green-400 font-medium">Passed</span>
              )}
              {test.passes === false && (
                <span className="text-xs text-red-400 font-medium">Failed</span>
              )}
              {test.passes === null && (
                <span className="text-xs text-gray-500 font-medium">Not Run</span>
              )}
            </div>
            <p className="text-sm text-gray-200">{test.description}</p>
            {hasSteps && (
              <p className="text-xs text-gray-500 mt-2">
                {expanded ? '▼' : '▶'} {steps.length} step{steps.length !== 1 ? 's' : ''} {expanded ? '(click to collapse)' : '(click to expand)'}
              </p>
            )}
          </div>
        </div>

        {/* Expanded Steps */}
        {expanded && hasSteps && (
          <div className="mt-4 pt-4 border-t border-gray-700">
            <h4 className="text-xs font-medium text-gray-400 mb-2">Test Steps:</h4>
            <ol className="space-y-2 list-decimal list-inside">
              {steps.map((step: string, idx: number) => (
                <li key={idx} className="text-sm text-gray-300">
                  {step}
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  );
}
