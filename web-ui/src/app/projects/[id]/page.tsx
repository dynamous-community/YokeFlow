'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { ProgressBar } from '@/components/ProgressBar';
import { SessionTimeline } from '@/components/SessionTimeline';
import { CurrentSession } from '@/components/CurrentSession';
import { CompletionBanner } from '@/components/CompletionBanner';
import { QualityDashboard } from '@/components/QualityDashboard';
import { SessionLogsViewer } from '@/components/SessionLogsViewer';
import { ScreenshotsGallery } from '@/components/ScreenshotsGallery';
import { ResetProjectDialog } from '@/components/ResetProjectDialog';
import { ProjectDetailsPanel } from '@/components/ProjectDetailsPanel';
import ConfirmDialog from '@/components/ConfirmDialog';
import { useProjectWebSocket } from '@/lib/websocket';
import { api } from '@/lib/api';
import { truncate } from '@/lib/utils';
import type { Project, Session } from '@/lib/types';
import { Settings, AlertCircle } from 'lucide-react';

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isInitializing, setIsInitializing] = useState(false);
  const [isStartingCoding, setIsStartingCoding] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [activeTab, setActiveTab] = useState<'current' | 'history' | 'quality' | 'logs' | 'screenshots'>('current');
  const [isStopping, setIsStopping] = useState(false);
  const [isStoppingAfterCurrent, setIsStoppingAfterCurrent] = useState(false);
  const [isRefreshingSessions, setIsRefreshingSessions] = useState(false);
  const [projectSettings, setProjectSettings] = useState<any>(null);
  const [isEditingName, setIsEditingName] = useState(false);
  const [editedName, setEditedName] = useState('');
  const [isRenamingProject, setIsRenamingProject] = useState(false);
  const [showResetDialog, setShowResetDialog] = useState(false);
  const [showCancelInitDialog, setShowCancelInitDialog] = useState(false);
  const [showDeleteProjectDialog, setShowDeleteProjectDialog] = useState(false);

  // Panel State: 'session' or 'project' (shows Session Details by default)
  const [activePanel, setActivePanel] = useState<'session' | 'project'>('session');
  const [detailsModalTab, setDetailsModalTab] = useState<'settings' | 'environment' | 'epics'>('settings');

  // WebSocket for real-time updates
  const {
    progress: wsProgress,
    connected: wsConnected,
    toolCount,
    assistantMessages,
    apiKeyWarning
  } = useProjectWebSocket(projectId, {
    onSessionStarted: (session) => {
      // Reload sessions when a new session starts (auto-continue)
      console.log('[ProjectDetail] New session started:', session);
      loadSessions();
      // Clear the "starting" states now that session has actually started
      setIsInitializing(false);
      setIsStartingCoding(false);
    },
    onSessionComplete: () => {
      // Reload project and sessions when a session completes
      loadProject();
      loadSessions();
    },
    onTaskUpdated: (taskId, done) => {
      // Reload project to get updated progress when a task is marked complete
      console.log(`[ProjectDetail] Task ${taskId} updated: done=${done}`);
      loadProject();
    },
    onTestUpdated: (testId, passes) => {
      // Reload project to get updated progress when a test result changes
      console.log(`[ProjectDetail] Test ${testId} updated: passes=${passes}`);
      loadProject();
    },
  });

  useEffect(() => {
    loadProject();
    loadSessions();
    loadSettings();
  }, [projectId]);

  // Update progress from WebSocket
  useEffect(() => {
    if (wsProgress) {
      setProject(prev => prev ? { ...prev, progress: wsProgress } : null);
    }
  }, [wsProgress]);

  async function loadProject(retryCount = 0) {
    try {
      const data = await api.getProject(projectId);
      setProject(data);
      setError(null);
      setLoading(false);
    } catch (err: any) {
      console.error(`Failed to load project (attempt ${retryCount + 1}):`, err);

      // Retry up to 3 times with exponential backoff for new projects
      if (retryCount < 3 && (err.code === 'ECONNABORTED' || err.response?.status === 404)) {
        const delay = Math.min(1000 * Math.pow(2, retryCount), 5000); // 1s, 2s, 4s max
        console.log(`Retrying in ${delay}ms...`);
        setTimeout(() => loadProject(retryCount + 1), delay);
        return; // Don't set error or stop loading yet
      }

      // Max retries reached or non-retryable error
      setError('Failed to load project');
      setLoading(false);
    }
  }

  async function loadSessions() {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/projects/${projectId}/sessions`);
      if (response.ok) {
        const data = await response.json();
        setSessions(data);

        // Reset stopping states if no running session
        const hasRunning = data.some((s: any) => s.status === 'running');
        if (!hasRunning) {
          setIsStopping(false);
          setIsStoppingAfterCurrent(false);
        }
      }
    } catch (err) {
      console.error('Failed to load sessions:', err);
      // Silent fail - sessions are optional
    }
  }

  async function loadSettings() {
    try {
      const settings = await api.getSettings(projectId);
      setProjectSettings(settings);
    } catch (err) {
      console.error('Failed to load settings:', err);
      // Silent fail - settings are optional
    }
  }

  async function handleInitializeProject() {
    setIsInitializing(true);
    setError(null);
    try {
      await api.initializeProject(projectId, projectSettings?.initializer_model);
      // Don't reload immediately - wait for WebSocket session_started event
      // The onSessionStarted callback (from useProjectWebSocket) will handle loading sessions
      // Keep isInitializing=true until session actually starts
      console.log('[InitializeProject] Request sent, waiting for session to start...');
      // Switch to Current Session tab to show the starting session
      setActiveTab('current');
    } catch (err: any) {
      console.error('Failed to initialize project:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      toast.error(`Failed to initialize project: ${errorMsg}`, {
        description: 'Check console for details'
      });
      setIsInitializing(false);
    }
    // Note: Don't set isInitializing=false here - let the WebSocket event or session load do it
  }

  async function handleStartCodingSessions() {
    setIsStartingCoding(true);
    setError(null);
    try {
      await api.startCodingSessions(
        projectId,
        projectSettings?.coding_model,
        projectSettings?.max_iterations
      );
      // Don't reload immediately - wait for WebSocket session_started event
      // The onSessionStarted callback will handle loading sessions
      // Keep isStartingCoding=true until session actually starts
      console.log('[StartCodingSessions] Request sent, waiting for session to start...');
      // Switch to Current Session tab to show the starting session
      setActiveTab('current');
    } catch (err: any) {
      console.error('Failed to start coding sessions:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      toast.error(`Failed to start coding sessions: ${errorMsg}`, {
        description: 'Check console for details'
      });
      setIsStartingCoding(false);
    }
    // Note: Don't set isStartingCoding=false here - let the WebSocket event do it
  }

  async function handleCancelInitialization() {
    setShowCancelInitDialog(true);
  }

  async function confirmCancelInitialization() {
    setIsCancelling(true);
    setError(null);
    try {
      await api.cancelInitialization(projectId);
      // Reload project and sessions
      await Promise.all([loadProject(), loadSessions()]);
      toast.success('Initialization cancelled successfully', {
        description: 'You can now restart initialization if needed'
      });
    } catch (err: any) {
      console.error('Failed to cancel initialization:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      toast.error(`Failed to cancel initialization: ${errorMsg}`, {
        description: 'Check console for details'
      });
    } finally {
      setIsCancelling(false);
    }
  }

  async function handleStopSession() {
    const runningSession = sessions.find(s => s.status === 'running');
    if (!runningSession) return;

    setIsStopping(true);
    try {
      await api.stopSession(projectId, runningSession.session_id);
      await loadSessions();
    } catch (err: any) {
      console.error('Failed to stop session:', err);
      setError(`Failed to stop session: ${err.response?.data?.detail || err.message}`);
      setIsStopping(false);
    }
  }

  async function handleRefreshSessions() {
    setIsRefreshingSessions(true);
    try {
      // Call the cleanup endpoint to mark orphaned sessions as interrupted
      await api.cleanupOrphanedSessions();
      // Reload sessions to show updated status
      await loadSessions();
      toast.success('Session status refreshed', {
        description: 'Orphaned sessions have been marked as interrupted'
      });
    } catch (err: any) {
      console.error('Failed to refresh sessions:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      toast.error(`Failed to refresh sessions: ${errorMsg}`);
    } finally {
      setIsRefreshingSessions(false);
    }
  }

  async function handleStopAfterCurrent() {
    setIsStoppingAfterCurrent(true);
    try {
      await api.stopAfterCurrent(projectId);
      // Don't reload sessions - just keep the flag set until session ends
    } catch (err: any) {
      console.error('Failed to set stop-after-current:', err);
      setError(`Failed to set stop-after-current: ${err.response?.data?.detail || err.message}`);
      setIsStoppingAfterCurrent(false);
    }
  }

  async function handleDeleteProject() {
    setShowDeleteProjectDialog(true);
  }

  async function confirmDeleteProject() {
    try {
      await api.deleteProject(projectId);
      toast.success(`Project "${project?.name || projectId}" deleted successfully`);
      router.push('/');
    } catch (err: any) {
      console.error('Failed to delete project:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      toast.error(`Failed to delete project: ${errorMsg}`);
    }
  }

  function handleStartRename() {
    setEditedName(project?.name || '');
    setIsEditingName(true);
  }

  function handleCancelRename() {
    setIsEditingName(false);
    setEditedName('');
  }

  async function handleSaveRename() {
    if (!editedName.trim()) {
      toast.error('Project name cannot be empty');
      return;
    }

    if (editedName === project?.name) {
      setIsEditingName(false);
      return;
    }

    setIsRenamingProject(true);
    try {
      const updatedProject = await api.renameProject(projectId, editedName.trim());
      setProject(updatedProject);
      setIsEditingName(false);
      setEditedName('');
      toast.success('Project renamed successfully');
    } catch (err: any) {
      console.error('Failed to rename project:', err);
      const errorMsg = err.response?.data?.detail || err.message;
      toast.error(`Failed to rename project: ${errorMsg}`);
    } finally {
      setIsRenamingProject(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600 dark:text-gray-400">Loading project...</p>
        </div>
      </div>
    );
  }

  // Only show error if we're not loading and there's actually an error
  if (!loading && (error || !project)) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">Project Not Found</h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4">{error || 'Project does not exist'}</p>
          <Link
            href="/"
            className="inline-block px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  // If still loading and no project yet, show loading state
  if (!project) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <p className="text-gray-600 dark:text-gray-400">Loading project...</p>
        </div>
      </div>
    );
  }

  const { progress, next_task, is_initialized } = project;
  const isComplete = progress.completed_tasks === progress.total_tasks && progress.total_tasks > 0;
  const hasRunningSession = sessions.some(s => s.status === 'running' || s.status === 'pending');
  const hasCodingSessions = sessions.some(s => s.session_number > 0);

  // Check if there's a running initialization session
  const runningInitSession = sessions.find(s =>
    (s.status === 'running' || s.status === 'pending') &&
    (s.type === 'initializer' || s.session_type === 'initializer')
  );

  // Check if there's a running coding session
  const runningCodingSession = sessions.find(s =>
    (s.status === 'running' || s.status === 'pending') &&
    (s.type === 'coding' || s.session_type === 'coding')
  );

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          {/* Breadcrumb with editable project name */}
          <div className="flex items-center gap-2 mb-3">
            <Link href="/" className="text-gray-500 hover:text-gray-300 text-sm">
              Projects
            </Link>
            <span className="text-gray-600">/</span>
            {isEditingName ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={editedName}
                  onChange={(e) => setEditedName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveRename();
                    if (e.key === 'Escape') handleCancelRename();
                  }}
                  className="px-2 py-1 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-gray-900 dark:text-gray-100 text-xl font-semibold focus:outline-none focus:border-blue-500"
                  autoFocus
                  disabled={isRenamingProject}
                />
                <button
                  onClick={handleSaveRename}
                  disabled={isRenamingProject}
                  className="px-2 py-1 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white rounded text-sm"
                >
                  {isRenamingProject ? 'Saving...' : 'Save'}
                </button>
                <button
                  onClick={handleCancelRename}
                  disabled={isRenamingProject}
                  className="px-2 py-1 bg-gray-600 hover:bg-gray-700 disabled:bg-gray-800 text-white rounded text-sm"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2 group">
                <span className="text-gray-900 dark:text-gray-100 text-xl font-semibold">{project.name}</span>
                <button
                  onClick={handleStartRename}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-gray-700 rounded"
                  title="Rename project (note: directory name in generations/ folder will not change)"
                >
                  <svg className="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                </button>
              </div>
            )}
          </div>
          {/* Status badges */}
          <div className="flex items-center gap-2">
            {wsConnected && (
              <span className="flex items-center gap-1 text-sm text-green-400">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                Live
              </span>
            )}
            {projectSettings?.sandbox_type && (
              <span className="px-2 py-1 rounded bg-gray-700/50 text-gray-300 border border-gray-600/50 text-xs font-mono">
                {projectSettings.sandbox_type === 'docker' ? '🐳 Docker' : '💻 Local'}
              </span>
            )}
            {isComplete && (
              <span className="px-3 py-1 rounded-full bg-green-500/20 text-green-400 border border-green-500/30 text-sm">
                Complete
              </span>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              if (activePanel === 'session') {
                // Switching to Project Details
                setDetailsModalTab('settings');
                setActivePanel('project');
              } else {
                // Switching to Session Details
                setActivePanel('session');
              }
            }}
            className={`px-4 py-2 rounded-lg transition-colors font-medium flex items-center gap-2 ${
              activePanel === 'project'
                ? 'bg-blue-600 hover:bg-blue-700 text-white'
                : 'bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-900 dark:text-gray-100'
            }`}
            title={activePanel === 'session' ? 'View Settings, Environment, and Project Roadmap' : 'View Session Details'}
          >
            <Settings className="w-4 h-4" />
            {activePanel === 'session' ? 'Project Details' : 'Session Details'}
            {activePanel === 'session' && project.needs_env_config && (
              <span className="ml-1 w-2 h-2 bg-amber-400 rounded-full animate-pulse"></span>
            )}
          </button>
          {/* Conditional buttons based on initialization state */}
          {!is_initialized && !runningInitSession && (
            <button
              onClick={() => {
                setActivePanel('session');
                handleInitializeProject();
              }}
              disabled={isInitializing}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
              title="Run initialization session (Session 1) to create project roadmap"
            >
              {isInitializing ? 'Initializing...' : 'Initialize Project'}
            </button>
          )}

          {runningInitSession && (
            <button
              onClick={handleCancelInitialization}
              disabled={isCancelling}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
              title="Cancel running initialization and remove all created tasks"
            >
              {isCancelling ? 'Cancelling...' : 'Cancel Initialization'}
            </button>
          )}

          {is_initialized && !runningCodingSession && !isComplete && (
            <button
              onClick={() => {
                setActivePanel('session');
                handleStartCodingSessions();
              }}
              disabled={isStartingCoding}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
              title="Start coding sessions (auto-continue until all tasks complete)"
            >
              {isStartingCoding ? 'Starting...' : 'Start Coding Sessions'}
            </button>
          )}

          {runningCodingSession && (
            <button
              disabled
              className="px-4 py-2 bg-blue-800 cursor-not-allowed text-white rounded-lg transition-colors font-medium"
              title="Coding sessions are running"
            >
              Coding Sessions Running
            </button>
          )}

          {/* Reset Project button - only show if at least one coding session has run */}
          {is_initialized && hasCodingSessions && (
            <button
              onClick={() => setShowResetDialog(true)}
              disabled={hasRunningSession}
              className="px-4 py-2 bg-amber-600/10 hover:bg-amber-600/20 disabled:bg-gray-800 disabled:cursor-not-allowed text-amber-400 disabled:text-gray-600 border border-amber-600/30 disabled:border-gray-700 rounded-lg transition-colors"
              title={hasRunningSession ? "Cannot reset while session is running" : "Reset project to post-initialization state (useful for trying different models or prompts)"}
            >
              Reset
            </button>
          )}

          <button
            onClick={handleDeleteProject}
            className="px-4 py-2 bg-red-600/10 hover:bg-red-600/20 text-red-400 border border-red-600/30 rounded-lg transition-colors"
          >
            Delete
          </button>
        </div>
      </div>

      {/* API Key Warning */}
      {apiKeyWarning && (
        <div className="mb-6 bg-orange-500/10 border border-orange-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-orange-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-orange-300 mb-1">
                ⚠️ Using API Key (Credit-Based Billing)
              </h3>
              <p className="text-sm text-orange-200/80 mb-2">
                {apiKeyWarning}
              </p>
              <div className="text-xs text-orange-200/60 space-y-1">
                <p><strong>Common causes:</strong></p>
                <ul className="list-disc list-inside ml-2 space-y-0.5">
                  <li>ANTHROPIC_API_KEY leaked from generated project .env file</li>
                  <li>ANTHROPIC_API_KEY set in agent's root .env file</li>
                  <li>ANTHROPIC_API_KEY set in system environment</li>
                </ul>
                <p className="mt-2"><strong>To fix:</strong></p>
                <ul className="list-disc list-inside ml-2 space-y-0.5">
                  <li>Check <code className="bg-gray-800 px-1 rounded">generations/{project.name}/.env</code> and remove ANTHROPIC_API_KEY</li>
                  <li>Restart API server to use CLAUDE_CODE_OAUTH_TOKEN instead</li>
                </ul>
                <p className="mt-2 text-orange-300">
                  💡 <strong>Cost difference:</strong> Membership plan (via OAuth) is significantly cheaper than credit-based API usage.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Environment Configuration Alert */}
      {project.needs_env_config && (
        <div className="mb-6 bg-amber-500/10 border border-amber-500/30 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-400 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-amber-300 mb-1">
                Environment Configuration Required
              </h3>
              <p className="text-sm text-amber-200/80 mb-3">
                The initialization session created environment variables that need to be configured before starting coding sessions.
                Please review and update the values (such as API keys) in the .env file.
              </p>
              <button
                onClick={() => {
                  setDetailsModalTab('environment');
                  setActivePanel('project');
                }}
                className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg transition-colors font-medium text-sm flex items-center gap-2"
              >
                <Settings className="w-4 h-4" />
                Configure Environment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Completion Banner */}
      {project.completed_at && (
        <CompletionBanner
          completedAt={project.completed_at}
          totalEpics={progress.total_epics}
          totalTasks={progress.total_tasks}
          totalTests={progress.total_tests}
        />
      )}

      {/* Progress Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gray-100 dark:bg-gray-900 border border-gray-300 dark:border-gray-800 rounded-lg p-4">
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
            {progress.completed_epics}/{progress.total_epics}
          </div>
          <div className="text-xs text-gray-700 dark:text-gray-500 mb-3">Epics Completed</div>
          <ProgressBar
            value={(progress.completed_epics / progress.total_epics) * 100 || 0}
            className="h-2"
            color="blue"
            showPercentage={false}
          />
        </div>

        <div className="bg-gray-100 dark:bg-gray-900 border border-gray-300 dark:border-gray-800 rounded-lg p-4">
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
            {progress.completed_tasks}/{progress.total_tasks}
          </div>
          <div className="text-xs text-gray-700 dark:text-gray-500 mb-3">Tasks Completed</div>
          <ProgressBar
            value={progress.task_completion_pct}
            className="h-2"
            color={progress.task_completion_pct === 100 ? 'green' : 'blue'}
            showPercentage={false}
          />
        </div>

        <div className="bg-gray-100 dark:bg-gray-900 border border-gray-300 dark:border-gray-800 rounded-lg p-4">
          <div className="text-3xl font-bold text-gray-900 dark:text-gray-100 mb-1">
            {progress.passing_tests}/{progress.total_tests}
          </div>
          <div className="text-xs text-gray-700 dark:text-gray-500 mb-3">Tests Passing</div>
          <ProgressBar
            value={progress.test_pass_pct}
            className="h-2"
            color={progress.test_pass_pct === 100 ? 'green' : progress.test_pass_pct > 0 ? 'yellow' : 'red'}
            showPercentage={false}
          />
        </div>
      </div>

      {/* Session Details Panel (shown by default) */}
      {activePanel === 'session' && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
          {/* Tab Headers */}
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setActiveTab('current')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'current'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Current Session
            </button>
            <button
              onClick={() => setActiveTab('history')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'history'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              History
              <span className="ml-2 text-sm text-gray-700 dark:text-gray-500">({sessions.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('quality')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'quality'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Quality
              <span className="ml-2 text-sm">📊</span>
            </button>
            <button
              onClick={() => setActiveTab('logs')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'logs'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Logs
              <span className="ml-2 text-sm">📄</span>
            </button>
            <button
              onClick={() => setActiveTab('screenshots')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'screenshots'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Screenshots
              <span className="ml-2 text-sm">📸</span>
            </button>
          </div>

          {/* Tab Content */}
          <div className="p-6">
            {activeTab === 'current' && (
              <CurrentSession
                session={sessions[0] || null}
                nextTask={next_task}
                onStopSession={handleStopSession}
                onStopAfterCurrent={handleStopAfterCurrent}
                onRefreshSessions={handleRefreshSessions}
                isStopping={isStopping}
                isStoppingAfterCurrent={isStoppingAfterCurrent}
                isRefreshingSessions={isRefreshingSessions}
                maxIterations={projectSettings?.max_iterations}
                toolCount={toolCount}
                assistantMessages={assistantMessages}
                isInitialized={is_initialized}
                isInitializing={isInitializing}
                isStartingCoding={isStartingCoding}
              />
            )}

            {activeTab === 'history' && (
              <SessionTimeline
                sessions={sessions}
                projectId={projectId}
                onSessionStopped={loadSessions}
              />
            )}

            {activeTab === 'quality' && (
              <QualityDashboard projectId={projectId} />
            )}

            {activeTab === 'logs' && (
              <SessionLogsViewer projectId={projectId} />
            )}

            {activeTab === 'screenshots' && (
              <ScreenshotsGallery projectId={projectId} />
            )}
          </div>
        </div>
      )}

      {/* Project Details Panel */}
      {activePanel === 'project' && (
        <ProjectDetailsPanel
          projectId={projectId}
          project={project}
          isOpen={true}
          activeTab={detailsModalTab}
          onTabChange={setDetailsModalTab}
          onProjectUpdated={() => {
            loadProject();
            loadSettings();
          }}
        />
      )}

      {/* Reset Project Dialog */}
      {showResetDialog && (
        <ResetProjectDialog
          projectId={projectId}
          projectName={project.name}
          onClose={() => setShowResetDialog(false)}
          onSuccess={() => {
            // Reload project and sessions after successful reset
            loadProject();
            loadSessions();
          }}
        />
      )}

      {/* Cancel Initialization Confirm Dialog */}
      <ConfirmDialog
        isOpen={showCancelInitDialog}
        onClose={() => setShowCancelInitDialog(false)}
        onConfirm={confirmCancelInitialization}
        title="Cancel Initialization?"
        message="This will remove all created epics, tasks, and tests. You can restart initialization afterwards."
        confirmText="Cancel Initialization"
        variant="warning"
      />

      {/* Delete Project Confirm Dialog */}
      <ConfirmDialog
        isOpen={showDeleteProjectDialog}
        onClose={() => setShowDeleteProjectDialog(false)}
        onConfirm={confirmDeleteProject}
        title="Delete Project?"
        message={`Are you sure you want to delete project "${project?.name || projectId}"?\n\nThis will permanently delete all data, logs, and generated code.\n\nThis action CANNOT be undone.`}
        confirmText="Delete Project"
        cancelText="Cancel"
        variant="danger"
      />
    </div>
  );
}
