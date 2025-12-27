/**
 * WebSocket utilities for real-time project updates
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { Progress, WebSocketMessage, SessionStatus } from './types';

const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

interface UseProjectWebSocketReturn {
  progress: Progress | null;
  connected: boolean;
  error: string | null;
  reconnect: () => void;
  // NEW Phase 2.2: Real-time session feedback
  toolCount: number | null;  // Cumulative tool use count for current session
  assistantMessages: string[];  // Latest assistant messages (up to 10)
  apiKeyWarning: string | null;  // Warning message if using API key instead of OAuth
}

interface UseProjectWebSocketOptions {
  onSessionComplete?: (sessionId: string, status: SessionStatus) => void;
  onSessionStarted?: (session: any) => void;
  // NEW Phase 2.2: Real-time event callbacks
  onAssistantMessage?: (message: string, sessionNumber: number) => void;
  onToolUse?: (toolName: string, count: number, sessionNumber: number) => void;
  // Real-time task/test progress callbacks
  onTaskUpdated?: (taskId: number, done: boolean) => void;
  onTestUpdated?: (testId: number, passes: boolean) => void;
  // Prompt improvement callbacks
  onPromptImprovementComplete?: (analysisId: string, proposalsCount: number) => void;
  onPromptImprovementFailed?: (analysisId: string, error: string) => void;
}

export function useProjectWebSocket(
  projectId: string | null,
  options?: UseProjectWebSocketOptions
): UseProjectWebSocketReturn {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // NEW Phase 2.2: Real-time session feedback states
  const [toolCount, setToolCount] = useState<number | null>(null);
  const [assistantMessages, setAssistantMessages] = useState<string[]>([]);
  const [apiKeyWarning, setApiKeyWarning] = useState<string | null>(null);

  // Store callbacks in refs to avoid reconnection loops
  const onSessionCompleteRef = useRef(options?.onSessionComplete);
  const onSessionStartedRef = useRef(options?.onSessionStarted);
  const onAssistantMessageRef = useRef(options?.onAssistantMessage);
  const onToolUseRef = useRef(options?.onToolUse);
  const onTaskUpdatedRef = useRef(options?.onTaskUpdated);
  const onTestUpdatedRef = useRef(options?.onTestUpdated);
  const onPromptImprovementCompleteRef = useRef(options?.onPromptImprovementComplete);
  const onPromptImprovementFailedRef = useRef(options?.onPromptImprovementFailed);

  useEffect(() => {
    onSessionCompleteRef.current = options?.onSessionComplete;
    onSessionStartedRef.current = options?.onSessionStarted;
    onAssistantMessageRef.current = options?.onAssistantMessage;
    onToolUseRef.current = options?.onToolUse;
    onTaskUpdatedRef.current = options?.onTaskUpdated;
    onTestUpdatedRef.current = options?.onTestUpdated;
    onPromptImprovementCompleteRef.current = options?.onPromptImprovementComplete;
    onPromptImprovementFailedRef.current = options?.onPromptImprovementFailed;
  }, [options?.onSessionComplete, options?.onSessionStarted, options?.onAssistantMessage, options?.onToolUse, options?.onTaskUpdated, options?.onTestUpdated, options?.onPromptImprovementComplete, options?.onPromptImprovementFailed]);

  const connect = useCallback(() => {
    if (!projectId) return;

    // Clear any existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      const ws = new WebSocket(`${WS_BASE}/api/ws/${projectId}`);

      ws.onopen = () => {
        console.log(`[WebSocket] Connected to project ${projectId}`);
        setConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          console.log('[WebSocket] Message:', data.type);

          switch (data.type) {
            case 'initial_state':
            case 'progress_update':
              if (data.progress) {
                setProgress(data.progress);
              }
              break;

            case 'progress':
              // Handle real-time progress events from agent
              if (data.event) {
                const event = data.event;

                if (event.type === 'tool_use' && event.tool_name) {
                  // Increment tool count
                  setToolCount(prev => (prev || 0) + 1);

                  // Optionally trigger callback if provided
                  if (onToolUseRef.current) {
                    // We don't have session_number in the event, so pass 0
                    onToolUseRef.current(event.tool_name, (toolCount || 0) + 1, 0);
                  }
                } else if (event.type === 'tool_result') {
                  // Tool result received - could update UI if needed
                  console.log('[WebSocket] Tool result received:', event.tool_id);
                }
              }
              break;

            case 'session_started':
              console.log(`[WebSocket] New session started:`, data.session);
              // Reset real-time counters for new session
              setToolCount(0);
              setAssistantMessages([]);
              // Trigger callback if provided
              if (onSessionStartedRef.current && data.session) {
                onSessionStartedRef.current(data.session);
              }
              break;

            case 'session_complete':
            case 'initialization_complete':  // Treat initialization_complete same as session_complete
            case 'coding_sessions_complete':  // All coding sessions complete (stop-after-current)
              console.log(`[WebSocket] Session completed:`, data.type);
              // Clear real-time counters when session ends
              setToolCount(null);
              setAssistantMessages([]);
              // Trigger callback if provided
              if (onSessionCompleteRef.current) {
                // For initialization_complete, extract session_id and status from session object
                const sessionId = data.session_id || data.session?.session_id;
                const status = data.status || data.session?.status || 'completed';
                if (sessionId) {
                  onSessionCompleteRef.current(sessionId, status);
                } else {
                  // No session_id, just trigger reload
                  onSessionCompleteRef.current('unknown', 'completed');
                }
              }
              break;

            case 'all_epics_complete':
            case 'project_complete':
              console.log(`[WebSocket] Project complete! All epics/tasks done.`);
              // Clear real-time counters
              setToolCount(null);
              setAssistantMessages([]);
              // Trigger session complete callback to reload page
              if (onSessionCompleteRef.current) {
                onSessionCompleteRef.current('final', 'completed');
              }
              break;

            case 'session_error':
              console.error('[WebSocket] Session error:', data.error);
              setError(data.error || 'Unknown session error');
              // Clear real-time counters on error
              setToolCount(null);
              setAssistantMessages([]);
              break;

            case 'api_key_warning':
              console.warn('[WebSocket] API Key Warning:', data.message);
              setApiKeyWarning(data.message || 'Using ANTHROPIC_API_KEY (credit-based billing)');
              break;

            // NEW Phase 2.2: Real-time session feedback events
            case 'assistant_message':
              if (data.text) {
                console.log(`[WebSocket] Assistant message #${data.message_number}:`, data.text.substring(0, 50) + '...');
                // Keep only last 10 messages
                setAssistantMessages(prev => {
                  const updated = [...prev, data.text!];
                  return updated.slice(-10);
                });
                // Trigger callback if provided
                if (onAssistantMessageRef.current && data.session_number) {
                  onAssistantMessageRef.current(data.text, data.session_number);
                }
              }
              break;

            case 'tool_use':
              if (data.tool_count !== undefined) {
                console.log(`[WebSocket] Tool used: ${data.tool_name} (total: ${data.tool_count})`);
                setToolCount(data.tool_count);
                // Trigger callback if provided
                if (onToolUseRef.current && data.tool_name && data.session_number) {
                  onToolUseRef.current(data.tool_name, data.tool_count, data.session_number);
                }
              }
              break;

            // Real-time task/test progress updates
            case 'task_updated':
              console.log(`[WebSocket] Task ${data.task_id} updated: done=${data.done}`);
              // Trigger callback if provided
              if (onTaskUpdatedRef.current && data.task_id !== undefined && data.done !== undefined) {
                onTaskUpdatedRef.current(data.task_id, data.done);
              }
              break;

            case 'test_updated':
              console.log(`[WebSocket] Test ${data.test_id} updated: passes=${data.passes}`);
              // Trigger callback if provided
              if (onTestUpdatedRef.current && data.test_id !== undefined && data.passes !== undefined) {
                onTestUpdatedRef.current(data.test_id, data.passes);
              }
              break;

            // Prompt improvement events
            case 'prompt_improvement_complete':
              console.log(`[WebSocket] Prompt improvement analysis complete:`, data.analysis_id);
              if (onPromptImprovementCompleteRef.current && data.analysis_id) {
                onPromptImprovementCompleteRef.current(data.analysis_id, data.proposals_count || 0);
              }
              break;

            case 'prompt_improvement_failed':
              console.error(`[WebSocket] Prompt improvement analysis failed:`, data.error);
              if (onPromptImprovementFailedRef.current && data.analysis_id) {
                onPromptImprovementFailedRef.current(data.analysis_id, data.error || 'Unknown error');
              }
              break;
          }
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.onerror = (event) => {
        console.warn('[WebSocket] Connection failed - will retry');
        // Don't set error state for connection failures - it's expected if API isn't running
        setConnected(false);
      };

      ws.onclose = (event) => {
        console.log(`[WebSocket] Disconnected (code: ${event.code}, reason: ${event.reason})`);
        setConnected(false);

        // Attempt to reconnect after 3 seconds
        if (!event.wasClean) {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('[WebSocket] Attempting to reconnect...');
            connect();
          }, 3000);
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[WebSocket] Failed to connect:', err);
      setError('Failed to establish WebSocket connection');
      setConnected(false);
    }
  }, [projectId]);

  useEffect(() => {
    connect();

    // Cleanup on unmount
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    connect();
  }, [connect]);

  return {
    progress,
    connected,
    error,
    reconnect,
    // NEW Phase 2.2: Real-time session feedback
    toolCount,
    assistantMessages,
    apiKeyWarning,
  };
}

/**
 * Get WebSocket URL for a project
 */
export function getProjectWebSocketUrl(projectId: string): string {
  return `${WS_BASE}/api/ws/${projectId}`;
}
