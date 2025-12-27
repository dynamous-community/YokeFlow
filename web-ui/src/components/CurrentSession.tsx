'use client';

import { useState } from 'react';
import { Session } from '@/lib/types';
import { Clock, CheckCircle, XCircle, AlertCircle, Activity, FileText, AlertTriangle, RefreshCw } from 'lucide-react';

interface CurrentSessionProps {
  session: Session | null;
  nextTask: {
    description: string;
    epic_name?: string;
  } | null;
  onStopSession?: () => void;
  onStopAfterCurrent?: () => void;
  onRefreshSessions?: () => void;
  isStopping?: boolean;
  isStoppingAfterCurrent?: boolean;
  isRefreshingSessions?: boolean;
  maxIterations?: number | null;
  // NEW Phase 2.2: Real-time session feedback
  toolCount?: number | null;
  assistantMessages?: string[];
  // Project initialization status
  isInitialized?: boolean;
  // Loading states for session startup
  isInitializing?: boolean;
  isStartingCoding?: boolean;
}

export function CurrentSession({
  session,
  nextTask,
  onStopSession,
  onStopAfterCurrent,
  onRefreshSessions,
  isStopping = false,
  isStoppingAfterCurrent = false,
  isRefreshingSessions = false,
  maxIterations = null,
  toolCount = null,
  assistantMessages = [],
  isInitialized = false,
  isInitializing = false,
  isStartingCoding = false
}: CurrentSessionProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'activity' | 'details'>('overview');

  if (!session && !nextTask) {
    // Show loading state when starting a session
    if (isInitializing || isStartingCoding) {
      return (
        <div className="text-center py-12">
          <div className="flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
            <div className="space-y-2">
              <p className="text-gray-300 font-medium">
                {isInitializing ? 'Starting Initializer...' : 'Starting Coding Session...'}
              </p>
              <p className="text-sm text-gray-700 dark:text-gray-500">
                This may take up to 60 seconds while the agent session starts
              </p>
            </div>
          </div>
        </div>
      );
    }

    // Default "no session" state
    return (
      <div className="text-center py-12 text-gray-700 dark:text-gray-500">
        <p>No active session</p>
        <p className="text-sm mt-2">
          {isInitialized
            ? 'Click "Start Coding Sessions" to begin autonomous development'
            : 'Click "Initialize Project" to create the project roadmap'}
        </p>
      </div>
    );
  }

  // Format duration
  const formatDuration = (start: string, end?: string) => {
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const diffMs = endTime - startTime;
    const diffSec = Math.floor(diffMs / 1000);
    const hours = Math.floor(diffSec / 3600);
    const minutes = Math.floor((diffSec % 3600) / 60);
    const seconds = diffSec % 60;

    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else if (minutes > 0) {
      return `${minutes}m ${seconds}s`;
    } else {
      return `${seconds}s`;
    }
  };

  // Status styling
  const statusConfig = {
    running: {
      icon: Clock,
      color: 'text-blue-400',
      bg: 'bg-blue-500/20',
      border: 'border-blue-500/30',
      label: 'Running',
    },
    completed: {
      icon: CheckCircle,
      color: 'text-green-400',
      bg: 'bg-green-500/20',
      border: 'border-green-500/30',
      label: 'Completed',
    },
    interrupted: {
      icon: AlertCircle,
      color: 'text-amber-400',
      bg: 'bg-amber-500/20',
      border: 'border-amber-500/30',
      label: 'Interrupted',
    },
    error: {
      icon: XCircle,
      color: 'text-red-400',
      bg: 'bg-red-500/20',
      border: 'border-red-500/30',
      label: 'Error',
    },
    pending: {
      icon: Clock,
      color: 'text-gray-400',
      bg: 'bg-gray-500/20',
      border: 'border-gray-500/30',
      label: 'Pending',
    },
  };

  const status = session?.status || 'pending';
  const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
  const StatusIcon = config.icon;

  // Format session number based on type
  const getSessionLabel = (session: Session) => {
    const sessionType = session.type || session.session_type;
    if (sessionType === 'initializer') {
      return 'Initialization';
    } else if (sessionType === 'coding') {
      // Session numbers: 0 = Initialization, 1+ = Coding 1, Coding 2, etc.
      return `Coding ${session.session_number}`;
    }
    return `Session ${session.session_number}`;
  };

  return (
    <div className="space-y-4">
      {/* Session Status Card */}
      {session && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
          {/* Tab Headers */}
          <div className="flex border-b border-gray-700">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex-1 px-4 py-3 font-medium transition-colors flex items-center justify-center gap-2 text-sm ${
                activeTab === 'overview'
                  ? 'bg-gray-700 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
              }`}
            >
              <FileText className="w-4 h-4" />
              Overview
            </button>
            <button
              onClick={() => setActiveTab('activity')}
              className={`flex-1 px-4 py-3 font-medium transition-colors flex items-center justify-center gap-2 text-sm ${
                activeTab === 'activity'
                  ? 'bg-gray-700 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
              }`}
            >
              <Activity className="w-4 h-4" />
              Activity
              {assistantMessages.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">
                  {assistantMessages.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('details')}
              className={`flex-1 px-4 py-3 font-medium transition-colors flex items-center justify-center gap-2 text-sm ${
                activeTab === 'details'
                  ? 'bg-gray-700 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-700/50'
              }`}
            >
              <AlertTriangle className="w-4 h-4" />
              Details
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {/* OVERVIEW TAB */}
            {activeTab === 'overview' && (
              <div>
                <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-100 mb-2">
                {getSessionLabel(session)}
              </h3>
              <div className="flex items-center gap-3">
                <span className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-sm ${config.bg} ${config.border} border`}>
                  <StatusIcon className={`w-4 h-4 ${config.color}`} />
                  <span className={config.color}>{config.label}</span>
                </span>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {session.type} • {session.model.includes('opus') ? 'Opus' : 'Sonnet'}
                </span>
              </div>
            </div>

            <div className="flex gap-2">
              {session.status === 'running' && (onStopSession || onStopAfterCurrent) && (
                <>
                  {isStopping ? (
                    <div className="px-4 py-2 bg-red-500/20 border border-red-500/30 rounded-lg text-sm text-red-400 flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-red-400 border-t-transparent rounded-full animate-spin"></div>
                      Stopping...
                    </div>
                  ) : isStoppingAfterCurrent ? (
                    <div className="px-4 py-2 bg-amber-500/20 border border-amber-500/30 rounded-lg text-sm text-amber-400">
                      Will stop after this session completes
                    </div>
                  ) : (
                    <>
                      {/* Only show "Stop After Current" for coding sessions with auto-continue enabled */}
                      {onStopAfterCurrent &&
                       (session.type === 'coding' || session.session_type === 'coding') &&
                       (maxIterations === 0 || maxIterations === null) && (
                        <button
                          onClick={onStopAfterCurrent}
                          className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors text-sm font-medium"
                          title="Let current session finish, then stop (prevents auto-continue)"
                        >
                          Stop After Current
                        </button>
                      )}
                      {/* Only show "Stop Now" for coding sessions */}
                      {onStopSession && (session.type === 'coding' || session.session_type === 'coding') && (
                        <button
                          onClick={onStopSession}
                          className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors text-sm font-medium"
                          title="Stop the running session immediately"
                        >
                          Stop Now
                        </button>
                      )}
                    </>
                  )}
                </>
              )}

              {/* Refresh button - show for any session status */}
              {onRefreshSessions && (
                <button
                  onClick={onRefreshSessions}
                  disabled={isRefreshingSessions}
                  className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm font-medium flex items-center gap-2"
                  title="Refresh session status (marks orphaned sessions as interrupted)"
                >
                  <RefreshCw className={`w-4 h-4 ${isRefreshingSessions ? 'animate-spin' : ''}`} />
                  {isRefreshingSessions ? 'Refreshing...' : 'Refresh Status'}
                </button>
              )}
            </div>
          </div>

          {/* Timing */}
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-gray-600 dark:text-gray-400">
              <Clock className="w-4 h-4" />
              <span>
                Started {new Date(session.started_at || session.created_at).toLocaleString()}
              </span>
            </div>
            {/* Only show duration after session completes (avoid showing stale static value) */}
            {session.started_at && session.status !== 'running' && (
              <div className="text-gray-600 dark:text-gray-400">
                Duration: {formatDuration(session.started_at, session.ended_at || undefined)}
              </div>
            )}
          </div>

          {/* Real-time Session Feedback (Phase 2.2) */}
          {session.status === 'running' && (
            <div className="mt-4 space-y-3">
              {/* Tool Use Counter */}
              {toolCount !== null && (
                <div className="flex items-center gap-2">
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 border border-blue-500/30 rounded-lg text-sm">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                    <span className="text-blue-300 font-medium">
                      {toolCount} tool{toolCount !== 1 ? 's' : ''} used
                    </span>
                  </div>
                </div>
              )}

              {/* Latest Assistant Message */}
              {assistantMessages.length > 0 && (
                <div className="p-3 bg-gray-700/50 border border-gray-600 rounded-lg">
                  <div className="text-xs text-gray-400 mb-1">Latest Activity:</div>
                  <div className="text-sm text-gray-300 line-clamp-2">
                    {assistantMessages[assistantMessages.length - 1]}
                  </div>
                </div>
              )}
            </div>
          )}

                {/* Error Message */}
                {session.error_message && (
                  <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-sm text-red-400 font-mono">{session.error_message}</p>
                  </div>
                )}

                {/* Interruption Reason */}
                {session.interruption_reason && (
                  <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                    <p className="text-sm text-amber-400">{session.interruption_reason}</p>
                  </div>
                )}
              </div>
            )}

            {/* ACTIVITY TAB */}
            {activeTab === 'activity' && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-100 mb-3">Assistant Messages</h3>

                {/* Tool Counter */}
                {session.status === 'running' && toolCount !== null && (
                  <div className="flex items-center gap-2 px-4 py-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse"></div>
                    <span className="text-blue-300 font-medium">
                      {toolCount} tool{toolCount !== 1 ? 's' : ''} used in this session
                    </span>
                  </div>
                )}

                {/* Assistant Messages List */}
                {assistantMessages.length > 0 ? (
                  <div className="space-y-3">
                    {assistantMessages.map((message, index) => (
                      <div key={index} className="p-3 bg-gray-700/50 border border-gray-600 rounded-lg">
                        <div className="text-xs text-gray-400 mb-1">Message #{index + 1}</div>
                        <div className="text-sm text-gray-300">{message}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-700 dark:text-gray-500">
                    <Activity className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>No activity messages yet</p>
                    <p className="text-sm mt-1">Messages will appear here as the session runs</p>
                  </div>
                )}
              </div>
            )}

            {/* DETAILS TAB */}
            {activeTab === 'details' && (
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-100 mb-3">Session Details</h3>

                <div className="space-y-3">
                  {/* Session Info */}
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 bg-gray-700/30 border border-gray-600 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Session Type</div>
                      <div className="text-sm text-gray-200 capitalize">{session.type || session.session_type}</div>
                    </div>
                    <div className="p-3 bg-gray-700/30 border border-gray-600 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Model</div>
                      <div className="text-sm text-gray-200">{session.model.includes('opus') ? 'Opus' : 'Sonnet'}</div>
                    </div>
                    <div className="p-3 bg-gray-700/30 border border-gray-600 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Status</div>
                      <div className={`text-sm ${config.color} capitalize`}>{config.label}</div>
                    </div>
                    <div className="p-3 bg-gray-700/30 border border-gray-600 rounded-lg">
                      <div className="text-xs text-gray-400 mb-1">Session ID</div>
                      <div className="text-sm text-gray-200 font-mono text-xs">{session.session_id.substring(0, 8)}...</div>
                    </div>
                  </div>

                  {/* Timestamps */}
                  <div className="p-4 bg-gray-700/30 border border-gray-600 rounded-lg">
                    <div className="text-xs text-gray-400 mb-2">Timestamps</div>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600 dark:text-gray-400">Created:</span>
                        <span className="text-gray-200">{new Date(session.created_at).toLocaleString()}</span>
                      </div>
                      {session.started_at && (
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Started:</span>
                          <span className="text-gray-200">{new Date(session.started_at).toLocaleString()}</span>
                        </div>
                      )}
                      {session.ended_at && (
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Ended:</span>
                          <span className="text-gray-200">{new Date(session.ended_at).toLocaleString()}</span>
                        </div>
                      )}
                      {session.started_at && (
                        <div className="flex justify-between pt-2 border-t border-gray-600">
                          <span className="text-gray-600 dark:text-gray-400">Duration:</span>
                          <span className="text-gray-200 font-medium">
                            {formatDuration(session.started_at, session.ended_at || undefined)}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Errors/Warnings */}
                  {(session.error_message || session.interruption_reason) && (
                    <div className="space-y-2">
                      {session.error_message && (
                        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                          <div className="text-xs text-red-400 mb-1 font-medium">Error Message</div>
                          <p className="text-sm text-red-300 font-mono">{session.error_message}</p>
                        </div>
                      )}
                      {session.interruption_reason && (
                        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg">
                          <div className="text-xs text-amber-400 mb-1 font-medium">Interruption Reason</div>
                          <p className="text-sm text-amber-300">{session.interruption_reason}</p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Next Task Card
      {nextTask && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-100 mb-3">Next Task</h3>
          <div className="text-gray-300 mb-2">{nextTask.description}</div>
          {nextTask.epic_name && (
            <div className="text-sm text-gray-700 dark:text-gray-500">Epic: {nextTask.epic_name}</div>
          )}
        </div>
      )}
      */}

      {/* No Session Message */}
      {!session && nextTask && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <p className="text-sm text-blue-400">
            Ready to start working on the next task. Click "Start Session" to begin.
          </p>
        </div>
      )}
    </div>
  );
}
