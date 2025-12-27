'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { Tabs } from '@/components/Tabs';
import { formatDate, formatDuration, calculateDuration, getStatusColor, getSessionTypeDisplayName, getModelDisplayName } from '@/lib/utils';

// Note: These types should match what we'll get from the API
interface SessionLog {
  human_readable: string;
  events: LogEvent[];
  errors: LogEvent[];
}

interface LogEvent {
  timestamp: string;
  type: string;
  message: string;
  details?: any;
}

export default function SessionDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  const sessionId = params.sessionId as string;

  const [activeTab, setActiveTab] = useState('human');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sessionLog, setSessionLog] = useState<SessionLog | null>(null);

  // Extract session number from sessionId (format: "project_session_N")
  const sessionNumber = sessionId.split('_').pop() || '?';

  useEffect(() => {
    loadSessionLogs();
  }, [sessionId]);

  async function loadSessionLogs() {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/projects/${projectId}/sessions/${sessionId}/logs`
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setSessionLog(data);
      setError(null);
    } catch (err) {
      console.error('Failed to load session logs:', err);
      setError('Failed to load session logs');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading session logs...</p>
        </div>
      </div>
    );
  }

  if (error || !sessionLog) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-100 mb-2">Session Not Found</h2>
          <p className="text-gray-400 mb-4">{error || 'Session logs not available'}</p>
          <Link
            href={`/projects/${projectId}`}
            className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Back to Project
          </Link>
        </div>
      </div>
    );
  }

  const tabs = [
    {
      id: 'human',
      label: 'Human Readable',
      content: (
        <div className="bg-gray-950 rounded-lg p-6 font-mono text-sm overflow-x-auto">
          <pre className="text-gray-300 whitespace-pre-wrap">{sessionLog.human_readable}</pre>
        </div>
      ),
    },
    {
      id: 'events',
      label: 'Events',
      content: (
        <div className="space-y-3">
          {sessionLog.events.length === 0 ? (
            <div className="text-center py-8 text-gray-700 dark:text-gray-500">No events recorded</div>
          ) : (
            sessionLog.events.map((event, index) => (
              <div
                key={index}
                className="bg-gray-900 border border-gray-800 rounded-lg p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-xs rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                      {event.type}
                    </span>
                    <span className="text-sm text-gray-700 dark:text-gray-500">
                      {formatDate(event.timestamp)}
                    </span>
                  </div>
                </div>
                <div className="text-gray-300 text-sm">{event.message}</div>
                {event.details && (
                  <pre className="mt-2 text-xs text-gray-500 overflow-x-auto">
                    {JSON.stringify(event.details, null, 2)}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>
      ),
    },
    {
      id: 'errors',
      label: 'Errors',
      badge: sessionLog.errors.length,
      content: (
        <div className="space-y-3">
          {sessionLog.errors.length === 0 ? (
            <div className="text-center py-8 text-green-500">
              ✓ No errors in this session
            </div>
          ) : (
            sessionLog.errors.map((error, index) => (
              <div
                key={index}
                className="bg-red-950/30 border border-red-900/50 rounded-lg p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">
                      {error.type}
                    </span>
                    <span className="text-sm text-gray-700 dark:text-gray-500">
                      {formatDate(error.timestamp)}
                    </span>
                  </div>
                </div>
                <div className="text-red-300 text-sm">{error.message}</div>
                {error.details && (
                  <pre className="mt-2 text-xs text-red-400/70 overflow-x-auto">
                    {JSON.stringify(error.details, null, 2)}
                  </pre>
                )}
              </div>
            ))
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2 text-sm">
          <Link href="/" className="text-gray-500 hover:text-gray-300">
            Projects
          </Link>
          <span className="text-gray-600">/</span>
          <Link href={`/projects/${projectId}`} className="text-gray-500 hover:text-gray-300">
            {projectId}
          </Link>
          <span className="text-gray-600">/</span>
          <span className="text-gray-100">Session #{sessionNumber}</span>
        </div>

        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">Session #{sessionNumber}</h1>
            <div className="flex items-center gap-3 text-sm text-gray-600 dark:text-gray-400">
              <span>Session ID: {sessionId}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                // TODO: Implement download logs functionality
                toast.info('Download logs feature coming soon');
              }}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 rounded-lg transition-colors"
            >
              Download Logs
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <Tabs tabs={tabs} activeTab={activeTab} onTabChange={setActiveTab} />
      </div>
    </div>
  );
}
