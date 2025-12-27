'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type {
  PromptAnalysisSummary,
  TriggerAnalysisRequest,
  ImprovementMetrics,
  Project,
  ProjectReviewStats,
  TriggerBulkReviewsRequest,
} from '@/lib/types';
import ConfirmDialog from './ConfirmDialog';
import TriggerReviewsDialog from './TriggerReviewsDialog';

export default function PromptImprovementDashboard() {
  const [analyses, setAnalyses] = useState<PromptAnalysisSummary[]>([]);
  const [metrics, setMetrics] = useState<ImprovementMetrics | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [projectStats, setProjectStats] = useState<ProjectReviewStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [deleteDialog, setDeleteDialog] = useState<{ isOpen: boolean; analysisId: string | null }>({
    isOpen: false,
    analysisId: null,
  });
  const [triggerReviewsDialog, setTriggerReviewsDialog] = useState(false);

  // Form state for triggering new analysis
  const [sandboxType, setSandboxType] = useState<'docker' | 'local'>('docker');
  const [lastNDays, setLastNDays] = useState(7);
  const [minSessions, setMinSessions] = useState(5);

  useEffect(() => {
    loadData();
  }, []);

  useEffect(() => {
    if (selectedProjectId) {
      loadProjectStats(selectedProjectId);
    } else {
      setProjectStats(null);
    }
  }, [selectedProjectId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [analysesData, metricsData, projectsData] = await Promise.all([
        api.listPromptAnalyses({ limit: 20 }),
        api.getPromptImprovementMetrics(),
        api.listProjects(),
      ]);
      setAnalyses(analysesData);
      setMetrics(metricsData);
      setProjects(projectsData);
    } catch (err: any) {
      console.error('Failed to load prompt improvement data:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const loadProjectStats = async (projectId: string) => {
    try {
      const stats = await api.getProjectReviewStats(projectId);
      setProjectStats(stats);
    } catch (err: any) {
      console.error('Failed to load project stats:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load project stats');
    }
  };

  const handleDeleteClick = (analysisId: string) => {
    setDeleteDialog({ isOpen: true, analysisId });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteDialog.analysisId) return;

    try {
      await api.deletePromptAnalysis(deleteDialog.analysisId);
      // Reload data after successful deletion
      await loadData();
    } catch (err: any) {
      console.error('Failed to delete analysis:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to delete analysis');
    }
  };

  const triggerAnalysis = async () => {
    try {
      setTriggering(true);
      setError(null);
      setSuccess(null);

      const request: TriggerAnalysisRequest = {
        sandbox_type: sandboxType,
        last_n_days: lastNDays,
        min_sessions_per_project: minSessions,
        ...(selectedProjectId && { project_ids: [selectedProjectId] }),
      };

      const response = await api.triggerPromptAnalysis(request);

      if (response.message) {
        setError(response.message); // Show "No eligible projects" message
        setTriggering(false);
      } else if (response.analysis_id) {
        // Keep triggering state true to show loading message
        // Auto-redirect to analysis details page
        window.location.href = `/prompt-improvements/${response.analysis_id}`;
      } else {
        // Reload data to show new analysis
        await loadData();
        setTriggering(false);
      }
    } catch (err: any) {
      console.error('Failed to trigger analysis:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to trigger analysis');
      setTriggering(false);
    }
  };

  const handleTriggerBulkReviews = async (request: TriggerBulkReviewsRequest) => {
    if (!selectedProjectId) return;

    try {
      const response = await api.triggerBulkReviews(selectedProjectId, request);
      setSuccess(response.message);
      setTriggerReviewsDialog(false);
      // Refresh project stats after triggering
      await loadProjectStats(selectedProjectId);
    } catch (err: any) {
      console.error('Failed to trigger bulk reviews:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to trigger reviews');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500 dark:text-gray-400">Loading prompt improvement data...</div>
      </div>
    );
  }

  // Show analyzing state when analysis is triggered
  if (triggering) {
    return (
      <div className="text-center py-12">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <div className="space-y-2">
            <p className="text-gray-900 dark:text-gray-300 font-medium">
              Analyzing Prompt Patterns...
            </p>
            <p className="text-sm text-gray-500 dark:text-gray-500">
              The agent is analyzing session patterns and generating proposals. This will take a minute or two.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Prompt Improvement System</h1>
        <p className="text-gray-600">
          Analyze session patterns across projects and generate evidence-based prompt improvements
        </p>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-yellow-800">Notice</h3>
              <div className="mt-2 text-sm text-yellow-700">{error}</div>
            </div>
            <button
              onClick={() => setError(null)}
              className="ml-auto flex-shrink-0 text-yellow-400 hover:text-yellow-500"
            >
              <span className="sr-only">Dismiss</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Success Display */}
      {success && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-green-800">Success</h3>
              <div className="mt-2 text-sm text-green-700">{success}</div>
            </div>
            <button
              onClick={() => setSuccess(null)}
              className="ml-auto flex-shrink-0 text-green-400 hover:text-green-500"
            >
              <span className="sr-only">Dismiss</span>
              <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Metrics Overview - MOVED TO TOP */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Analyses</div>
            <div className="text-2xl font-bold">{metrics.total_analyses}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Total Proposals</div>
            <div className="text-2xl font-bold">{metrics.total_proposals}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Accepted</div>
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">{metrics.accepted_proposals}</div>
          </div>
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">Implemented</div>
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{metrics.implemented_proposals}</div>
          </div>
        </div>
      )}

      {/* Project Analysis */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm mb-8">
        <h2 className="text-xl font-semibold mb-4">Project Analysis</h2>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Select Project
            </label>
            <select
              value={selectedProjectId || ''}
              onChange={(e) => setSelectedProjectId(e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select a project...</option>
              {projects.map(project => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
          </div>

          {/* Project Stats */}
          {selectedProjectId && projectStats && (
            <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
              <h3 className="font-semibold text-sm mb-3 text-gray-900 dark:text-gray-100">Deep Review Coverage</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">Total Sessions</div>
                  <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{projectStats.total_sessions}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">With Reviews</div>
                  <div className="text-lg font-bold text-green-600 dark:text-green-400">{projectStats.sessions_with_reviews}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">Without Reviews</div>
                  <div className="text-lg font-bold text-orange-600 dark:text-orange-400">{projectStats.sessions_without_reviews}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">Coverage</div>
                  <div className="text-lg font-bold text-blue-600 dark:text-blue-400">{projectStats.coverage_percent}%</div>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setTriggerReviewsDialog(true)}
                  disabled={projectStats.total_sessions === 0}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
                >
                  Trigger More Reviews
                </button>
              </div>
            </div>
          )}

          {/* Analyze This Project Button */}
          {selectedProjectId && (
            <div className="flex gap-2">
              <button
                onClick={triggerAnalysis}
                disabled={triggering}
                className="px-6 py-3 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-green-300 disabled:cursor-not-allowed transition-colors font-medium"
              >
                {triggering ? 'Analyzing...' : 'Analyze This Project'}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Recent Analyses */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Recent Analyses</h2>
        {analyses.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            No analyses yet. Trigger your first analysis above.
          </div>
        ) : (
          <div className="space-y-4">
            {analyses.map((analysis) => (
              <div
                key={analysis.id}
                className="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:border-blue-300 dark:hover:border-blue-600 bg-white dark:bg-gray-800 transition-colors"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(analysis.created_at)}
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span
                        className={`inline-block px-2 py-1 text-xs rounded ${
                          analysis.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : analysis.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : analysis.status === 'running'
                            ? 'bg-blue-100 text-blue-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {analysis.status}
                      </span>
                      {analysis.sandbox_type && (
                        <span className="inline-block px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded">
                          {analysis.sandbox_type}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <a
                      href={`/prompt-improvements/${analysis.id}`}
                      className="px-4 py-2 text-sm bg-blue-50 dark:bg-blue-900 text-blue-600 dark:text-blue-300 rounded-md hover:bg-blue-100 dark:hover:bg-blue-800 transition-colors"
                    >
                      View Details →
                    </a>
                    <button
                      onClick={() => handleDeleteClick(analysis.id)}
                      className="px-3 py-2 text-sm bg-red-50 dark:bg-red-900 text-red-600 dark:text-red-300 rounded-md hover:bg-red-100 dark:hover:bg-red-800 transition-colors"
                      title="Delete this analysis"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-4 mt-4 text-sm">
                  <div>
                    <div className="text-gray-500 dark:text-gray-400">Projects</div>
                    <div className="font-semibold">{analysis.num_projects}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 dark:text-gray-400">Sessions</div>
                    <div className="font-semibold">{analysis.sessions_analyzed}</div>
                  </div>
                  <div>
                    <div className="text-gray-500 dark:text-gray-400">Proposals</div>
                    <div className="font-semibold">{analysis.total_proposals || 0}</div>
                  </div>
                </div>
                {analysis.quality_impact_estimate && (
                  <div className="mt-3 pt-3 border-t border-gray-200">
                    <div className="text-sm text-gray-500 dark:text-gray-400">
                      Estimated Quality Impact:
                      <span className="ml-2 font-semibold text-green-600 dark:text-green-400">
                        +{analysis.quality_impact_estimate.toFixed(1)} points
                      </span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteDialog.isOpen}
        onClose={() => setDeleteDialog({ isOpen: false, analysisId: null })}
        onConfirm={handleDeleteConfirm}
        title="Delete Analysis"
        message="Are you sure you want to delete this analysis? This will also delete all associated proposals. This action cannot be undone."
        confirmText="Delete"
        cancelText="Cancel"
        variant="danger"
      />

      {/* Trigger Reviews Dialog */}
      {selectedProjectId && projectStats && (
        <TriggerReviewsDialog
          isOpen={triggerReviewsDialog}
          onClose={() => setTriggerReviewsDialog(false)}
          onTrigger={handleTriggerBulkReviews}
          projectName={projects.find(p => p.id === selectedProjectId)?.name || ''}
          totalSessions={projectStats.total_sessions}
          sessionsWithoutReviews={projectStats.sessions_without_reviews}
          unreviewedSessionNumbers={projectStats.unreviewed_session_numbers}
        />
      )}
    </div>
  );
}
