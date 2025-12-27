'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { FileText, Download } from 'lucide-react';

interface LogFile {
  filename: string;
  type: 'human' | 'events';
  sessionNumber: number;
  timestamp: string;
}

interface GroupedSession {
  sessionNumber: number;
  timestamp: string;
  humanLog?: LogFile;
  eventsLog?: LogFile;
}

interface SessionLogsViewerProps {
  projectId: string;
}

export function SessionLogsViewer({ projectId }: SessionLogsViewerProps) {
  const [logs, setLogs] = useState<LogFile[]>([]);
  const [groupedSessions, setGroupedSessions] = useState<GroupedSession[]>([]);
  const [selectedLog, setSelectedLog] = useState<LogFile | null>(null);
  const [logContent, setLogContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [loadingContent, setLoadingContent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadLogsList();
  }, [projectId]);

  async function loadLogsList() {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getSessionLogs(projectId);
      // Map backend response to frontend format
      const mappedLogs = response.map((log: any) => ({
        filename: log.filename,
        type: log.type,
        sessionNumber: log.session_number,
        timestamp: log.modified
      }));
      setLogs(mappedLogs);

      // Group logs by session number
      const sessionMap = new Map<number, GroupedSession>();
      mappedLogs.forEach((log: LogFile) => {
        if (!sessionMap.has(log.sessionNumber)) {
          sessionMap.set(log.sessionNumber, {
            sessionNumber: log.sessionNumber,
            timestamp: log.timestamp,
          });
        }
        const session = sessionMap.get(log.sessionNumber)!;
        if (log.type === 'human') {
          session.humanLog = log;
        } else {
          session.eventsLog = log;
        }
        // Use the most recent timestamp for the session
        if (new Date(log.timestamp) > new Date(session.timestamp)) {
          session.timestamp = log.timestamp;
        }
      });

      // Convert to array and sort by session number descending (newest first)
      const grouped = Array.from(sessionMap.values()).sort(
        (a, b) => b.sessionNumber - a.sessionNumber
      );
      setGroupedSessions(grouped);
    } catch (err: any) {
      console.error('Failed to load logs list:', err);
      setError(err.message || 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }

  async function loadLogContent(log: LogFile) {
    try {
      setLoadingContent(true);
      setSelectedLog(log);
      const content = await api.getSessionLogContent(projectId, log.type, log.filename);
      setLogContent(content);
    } catch (err: any) {
      console.error('Failed to load log content:', err);
      setLogContent(`Error loading log: ${err.message || 'Unknown error'}`);
    } finally {
      setLoadingContent(false);
    }
  }

  function downloadLog() {
    if (!selectedLog || !logContent) return;

    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedLog.filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center py-12">
        <div className="text-gray-600 dark:text-gray-400">Loading session logs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-800 rounded-lg p-4">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  if (groupedSessions.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
        <FileText className="w-12 h-12 mx-auto text-gray-600 mb-4" />
        <div className="text-gray-600 dark:text-gray-400">No session logs yet</div>
        <div className="text-gray-500 text-sm mt-2">Logs will appear here after sessions complete</div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Session List (Grouped) */}
      <div className="lg:col-span-1">
        <h3 className="text-lg font-semibold text-gray-200 mb-4">Session Logs</h3>
        <div className="space-y-3 overflow-y-auto max-h-[600px] pr-2">
          {groupedSessions.map((session) => (
            <div
              key={session.sessionNumber}
              className="bg-gray-900 border border-gray-800 rounded-lg p-3"
            >
              {/* Session Header */}
              <div className="font-medium text-gray-200 mb-2">
                {session.sessionNumber === 0 ? 'Initialization' : `Session #${session.sessionNumber}`}
              </div>
              <div className="text-xs text-gray-500 mb-3">
                {new Date(session.timestamp).toLocaleString()}
              </div>

              {/* Log File Buttons */}
              <div className="space-y-2">
                {session.humanLog && (
                  <button
                    onClick={() => loadLogContent(session.humanLog!)}
                    className={`w-full text-left px-3 py-2 rounded-lg border transition-colors text-sm ${
                      selectedLog?.filename === session.humanLog.filename
                        ? 'bg-green-900/30 border-green-700 text-green-300'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span>Human-readable (TXT)</span>
                      <FileText className="w-4 h-4" />
                    </div>
                  </button>
                )}
                {session.eventsLog && (
                  <button
                    onClick={() => loadLogContent(session.eventsLog!)}
                    className={`w-full text-left px-3 py-2 rounded-lg border transition-colors text-sm ${
                      selectedLog?.filename === session.eventsLog.filename
                        ? 'bg-purple-900/30 border-purple-700 text-purple-300'
                        : 'bg-gray-800 border-gray-700 text-gray-300 hover:bg-gray-700 hover:border-gray-600'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span>Structured events (JSONL)</span>
                      <FileText className="w-4 h-4" />
                    </div>
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Log Content Viewer */}
      <div className="lg:col-span-2">
        {selectedLog ? (
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            {/* Header */}
            <div className="px-4 py-3 bg-gray-800/50 border-b border-gray-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5 text-gray-600 dark:text-gray-400" />
                <div>
                  <div className="font-medium text-gray-200">{selectedLog.filename}</div>
                  <div className="text-xs text-gray-700 dark:text-gray-500">
                    {selectedLog.type === 'human' ? 'Human-readable log' : 'Structured events log'}
                  </div>
                </div>
              </div>
              <button
                onClick={downloadLog}
                className="px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-lg transition-colors text-sm flex items-center gap-2"
                title="Download log file"
              >
                <Download className="w-4 h-4" />
                Download
              </button>
            </div>

            {/* Content */}
            <div className="p-4 overflow-auto max-h-[600px]">
              {loadingContent ? (
                <div className="text-gray-400 text-center py-8">Loading log content...</div>
              ) : (
                <pre className={`text-xs font-mono text-gray-300 ${
                  selectedLog.type === 'events'
                    ? 'whitespace-pre overflow-x-auto'
                    : 'whitespace-pre-wrap break-words'
                }`}>
                  {logContent}
                </pre>
              )}
            </div>
          </div>
        ) : (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-12 text-center">
            <FileText className="w-16 h-16 mx-auto text-gray-600 mb-4" />
            <div className="text-gray-600 dark:text-gray-400">Select a log file to view its content</div>
            <div className="text-gray-500 text-sm mt-2">
              Click on a session log from the list to view details
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
