/**
 * Session Timeline Component
 * Displays session history with status badges
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { formatRelativeTime, formatDuration, calculateDuration, getStatusColor, getSessionTypeDisplayName, getModelDisplayName } from '@/lib/utils';
import { api } from '@/lib/api';
import ConfirmDialog from '@/components/ConfirmDialog';
import type { Session, SessionMetrics } from '@/lib/types';

interface SessionTimelineProps {
  sessions: Session[];
  projectId: string;
  onSessionStopped?: () => void;
}

export function SessionTimeline({ sessions, projectId, onSessionStopped }: SessionTimelineProps) {
  const [stoppingSessionId, setStoppingSessionId] = useState<string | null>(null);
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set());
  const [showStopDialog, setShowStopDialog] = useState(false);
  const [sessionToStop, setSessionToStop] = useState<string | null>(null);

  /**
   * Get appropriate metrics to display based on session type
   * Initialization sessions show epics/tasks/tests created
   * Coding sessions show tasks completed, tests passed, screenshots taken
   */
  const getDisplayMetrics = (session: Session): { label: string; value: number | string; highlight?: boolean }[] => {
    const metrics = session.metrics || {};
    const isInitialization = session.session_number === 0 || session.session_type === 'initializer';

    const result: { label: string; value: number | string; highlight?: boolean }[] = [];

    if (isInitialization) {
      // Initialization session: show what was created
      if (metrics.epics_created) result.push({ label: 'Epics Created', value: metrics.epics_created });
      if (metrics.tasks_created) result.push({ label: 'Tasks Created', value: metrics.tasks_created });
      if (metrics.tests_created) result.push({ label: 'Tests Created', value: metrics.tests_created });
    } else {
      // Coding session: show what was completed
      if (metrics.tasks_completed) result.push({ label: 'Tasks Completed', value: metrics.tasks_completed });
      if (metrics.tests_passed) result.push({ label: 'Tests Passed', value: metrics.tests_passed });
      if (metrics.browser_verifications) result.push({ label: 'Screenshots', value: metrics.browser_verifications });
    }

    // Always show errors (highlight if > 0)
    // Note: Field name is 'tool_errors' in database, not 'errors_count'
    const errorCount = metrics.tool_errors || metrics.errors_count || 0;
    result.push({
      label: 'Errors',
      value: errorCount,
      highlight: errorCount > 0
    });

    // Always show tool calls for context
    if (metrics.tool_calls_count) {
      result.push({ label: 'Tool Calls', value: metrics.tool_calls_count });
    }

    // Show cost if available
    if (metrics.cost_usd && metrics.cost_usd > 0) {
      result.push({ label: 'Cost', value: `$${metrics.cost_usd.toFixed(4)}` });
    }

    // Show token usage if available
    if (metrics.tokens_input || metrics.tokens_output) {
      const totalTokens = (metrics.tokens_input || 0) + (metrics.tokens_output || 0);
      result.push({ label: 'Tokens', value: totalTokens.toLocaleString() });

      // Show token breakdown in separate fields
      if (metrics.tokens_input) {
        result.push({ label: 'Tokens In', value: metrics.tokens_input.toLocaleString() });
      }
      if (metrics.tokens_output) {
        result.push({ label: 'Tokens Out', value: metrics.tokens_output.toLocaleString() });
      }
    }

    return result;
  };

  const toggleSessionExpanded = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    e.stopPropagation();

    const newExpanded = new Set(expandedSessions);
    if (newExpanded.has(sessionId)) {
      newExpanded.delete(sessionId);
    } else {
      newExpanded.add(sessionId);
    }
    setExpandedSessions(newExpanded);
  };

  const handleStopSession = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault(); // Prevent navigation
    e.stopPropagation(); // Stop event bubbling
    setSessionToStop(sessionId);
    setShowStopDialog(true);
  };

  const confirmStopSession = async () => {
    if (!sessionToStop) return;

    setStoppingSessionId(sessionToStop);
    try {
      await api.stopSession(projectId, sessionToStop);
      // Callback to parent to reload sessions
      if (onSessionStopped) {
        onSessionStopped();
      }
      toast.success('Session stopped gracefully');
    } catch (err) {
      console.error('Failed to stop session:', err);
      toast.error('Failed to stop session', {
        description: 'Check console for details'
      });
    } finally {
      setStoppingSessionId(null);
      setSessionToStop(null);
    }
  };

  if (sessions.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        No sessions yet
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {sessions.map((session) => {
        const duration = calculateDuration(session.started_at, session.ended_at);
        const isRunning = session.status === 'running';
        const isStopping = stoppingSessionId === session.session_id;
        const isExpanded = expandedSessions.has(session.session_id);
        const displayMetrics = getDisplayMetrics(session);
        const metrics = session.metrics || {};

        return (
          <div
            key={session.session_id}
            className="block bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg overflow-hidden"
          >
            <Link
              href={`/projects/${projectId}/sessions/${session.session_id}`}
              className="block p-4 hover:bg-gray-50 dark:hover:bg-gray-900/80 transition-all"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className="text-lg font-semibold text-gray-900 dark:text-gray-100">
                    {session.session_number === 0 ? 'Initialization' : `Session #${session.session_number}`}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                      {getSessionTypeDisplayName(session.session_type)}
                    </span>
                    <span className="px-2 py-0.5 text-xs rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                      {getModelDisplayName(session.model)}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(session.status)} text-white`}>
                    {session.status}
                  </div>
                  {isRunning && (
                    <button
                      onClick={(e) => handleStopSession(e, session.session_id)}
                      disabled={isStopping}
                      className="px-3 py-1 bg-red-600/10 hover:bg-red-600/20 text-red-400 dark:text-red-400 border border-red-600/30 rounded text-xs font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isStopping ? 'Stopping...' : 'Stop'}
                    </button>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-4 text-sm text-gray-500">
                {session.created_at && (
                  <span>{formatRelativeTime(session.created_at)}</span>
                )}
                {duration !== null && (
                  <span>• Duration: {formatDuration(duration)}</span>
                )}
                {isRunning && session.started_at && (
                  <span>• Started {formatRelativeTime(session.started_at)}</span>
                )}
              </div>

              {session.error_message && (
                <div className="mt-2 text-sm text-red-400">
                  Error: {session.error_message}
                </div>
              )}
            </Link>

            {/* Expandable Metrics Section */}
            {!isRunning && session.status === 'completed' && displayMetrics.length > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-800">
                <button
                  onClick={(e) => toggleSessionExpanded(e, session.session_id)}
                  className="w-full px-4 py-2 text-sm text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800/50 text-left flex items-center justify-between transition-colors"
                >
                  <span>{isExpanded ? '▼' : '▶'} {isExpanded ? 'Hide' : 'Show'} Metrics</span>
                  {!isExpanded && displayMetrics.length > 0 && (
                    <span className="text-xs text-gray-500">
                      {displayMetrics.slice(0, 2).map(m => `${m.value} ${m.label.toLowerCase()}`).join(', ')}
                    </span>
                  )}
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 space-y-2 bg-gray-50 dark:bg-gray-800/30">
                    {/* Metrics Grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      {displayMetrics.map(metric => (
                        <div key={metric.label} className="bg-white dark:bg-gray-900 rounded p-2 border border-gray-200 dark:border-gray-700">
                          <div className="text-xs text-gray-500 dark:text-gray-400">{metric.label}</div>
                          <div className={`text-lg font-semibold ${
                            metric.highlight
                              ? 'text-red-500'
                              : metric.label === 'Errors'
                              ? 'text-green-500'
                              : 'text-gray-900 dark:text-gray-100'
                          }`}>
                            {metric.value}
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* More metrics coming soon note */}
                    <div className="text-xs text-gray-400 dark:text-gray-500 text-center pt-2 italic">
                      More metrics coming soon (tool breakdown, performance stats, efficiency scores)
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}

      {/* Stop Session Confirm Dialog */}
      <ConfirmDialog
        isOpen={showStopDialog}
        onClose={() => {
          setShowStopDialog(false);
          setSessionToStop(null);
        }}
        onConfirm={confirmStopSession}
        title="Stop Session?"
        message="Stop this session gracefully? Logs will be finalized."
        confirmText="Stop Session"
        variant="warning"
      />
    </div>
  );
}
