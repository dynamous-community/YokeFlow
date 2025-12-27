'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type {
  PromptAnalysisDetail,
  PromptProposal,
  IdentifiedPattern,
} from '@/lib/types';
import PromptProposalDiff from './PromptProposalDiff';

interface Props {
  analysisId: string;
}

export default function PromptAnalysisDetailComponent({ analysisId }: Props) {
  const [analysis, setAnalysis] = useState<PromptAnalysisDetail | null>(null);
  const [proposals, setProposals] = useState<PromptProposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProposal, setSelectedProposal] = useState<PromptProposal | null>(null);
  const [patternsExpanded, setPatternsExpanded] = useState<string | null>(null);
  const [patternsSectionCollapsed, setPatternsSectionCollapsed] = useState(true);

  useEffect(() => {
    loadAnalysis();
  }, [analysisId]);

  const loadAnalysis = async () => {
    try {
      setLoading(true);
      setError(null);
      const [analysisData, proposalsData] = await Promise.all([
        api.getPromptAnalysis(analysisId),
        api.getPromptProposals(analysisId),
      ]);
      setAnalysis(analysisData);
      setProposals(proposalsData);
    } catch (err: any) {
      console.error('Failed to load analysis:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const handleProposalUpdated = (updatedProposal: PromptProposal) => {
    setProposals(proposals.map(p =>
      p.id === updatedProposal.id ? updatedProposal : p
    ));
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString();
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      completed: 'bg-green-100 text-green-800',
      running: 'bg-blue-100 text-blue-800',
      failed: 'bg-red-100 text-red-800',
      pending: 'bg-gray-100 text-gray-800',
    };
    return (
      <span className={`inline-block px-2 py-1 text-xs rounded ${colors[status] || colors.pending}`}>
        {status}
      </span>
    );
  };

  const getSeverityColor = (severity: string) => {
    const colors: Record<string, string> = {
      critical: 'text-red-600',
      high: 'text-orange-600',
      medium: 'text-yellow-600',
      low: 'text-blue-600',
    };
    return colors[severity] || 'text-gray-600';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500 dark:text-gray-400">Loading analysis details...</div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-semibold">Error</h3>
          <p className="text-red-700 mt-2">{error || 'Analysis not found'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <a
              href="/prompt-improvements"
              className="text-sm text-blue-600 hover:text-blue-700 mb-2 inline-block"
            >
              ← Back to Analyses
            </a>
            <h1 className="text-3xl font-bold">Analysis Details</h1>
          </div>
          <div>{getStatusBadge(analysis.status)}</div>
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          Created: {formatDate(analysis.created_at)}
          {analysis.completed_at && ` • Completed: ${formatDate(analysis.completed_at)}`}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">Projects Analyzed</div>
          <div className="text-2xl font-bold">{analysis.num_projects}</div>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">Sessions Analyzed</div>
          <div className="text-2xl font-bold">{analysis.sessions_analyzed}</div>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">Proposals Generated</div>
          <div className="text-2xl font-bold">{proposals.length}</div>
        </div>
        <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="text-sm text-gray-500 dark:text-gray-400">Quality Impact</div>
          <div className="text-2xl font-bold text-green-600">
            {analysis.quality_impact_estimate
              ? `+${analysis.quality_impact_estimate.toFixed(1)}`
              : 'N/A'}
          </div>
        </div>
      </div>

      {/* Patterns Identified */}
      {analysis.patterns_identified && Object.keys(analysis.patterns_identified).length > 0 && (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm mb-8">
          <button
            onClick={() => setPatternsSectionCollapsed(!patternsSectionCollapsed)}
            className="w-full flex items-center justify-between mb-4 hover:opacity-80 transition-opacity"
          >
            <h2 className="text-xl font-semibold">
              Patterns Identified ({Object.keys(analysis.patterns_identified).length})
            </h2>
            <span className="text-lg text-gray-500 dark:text-gray-400">
              {patternsSectionCollapsed ? '▶' : '▼'}
            </span>
          </button>
          {!patternsSectionCollapsed && (
          <div className="space-y-2">
            {Object.entries(analysis.patterns_identified).map(([key, pattern]) => {
              const isExpanded = patternsExpanded === key;
              const patternData = pattern as any;

              return (
                <div key={key} className="border border-gray-200 dark:border-gray-700 rounded-lg">
                  {/* Pattern Header - Always Visible */}
                  <button
                    onClick={() => setPatternsExpanded(isExpanded ? null : key)}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
                      <div className="text-left">
                        <div className="font-medium text-gray-900 dark:text-gray-100">
                          {key.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                        </div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          {patternData.frequency || 0} occurrences • {patternData.unique_sessions || 0} sessions
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm px-2 py-1 bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200 rounded">
                        Avg Quality: {patternData.avg_quality ? patternData.avg_quality.toFixed(1) : 'N/A'}
                      </span>
                    </div>
                  </button>

                  {/* Pattern Details - Expanded */}
                  {isExpanded && (
                    <div className="px-4 pb-4 border-t border-gray-200 dark:border-gray-700 mt-2 pt-4">
                      <div className="space-y-3">
                        <div>
                          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Recommendations:</span>
                          <div className="mt-2 space-y-2">
                            {(patternData.recommendations || []).map((rec: any, idx: number) => (
                              <div key={idx} className="text-sm text-gray-600 dark:text-gray-400 pl-3 border-l-2 border-gray-300 dark:border-gray-600">
                                {rec.title || rec}
                              </div>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Sessions Affected:</span>
                          <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                            {(patternData.sessions || []).map((s: any) => `Session ${s.session_number}`).join(', ')}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          )}
        </div>
      )}


      {/* Overall Findings */}
      {analysis.overall_findings && (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm mb-8">
          <h2 className="text-xl font-semibold mb-4">Overall Findings</h2>
          <div className="prose max-w-none text-gray-700 dark:text-gray-300">
            {analysis.overall_findings}
          </div>
        </div>
      )}

      {/* Proposals */}
      <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
        <h2 className="text-xl font-semibold mb-4">Prompt Change Proposals</h2>
        {proposals.length === 0 ? (
          <div className="text-center py-8 text-gray-500 dark:text-gray-400">
            No proposals generated for this analysis.
            {analysis.sessions_analyzed > 0 && (
              <p className="mt-2 text-sm">
                This typically means the sessions analyzed are already high quality
                and no systemic issues were detected.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {proposals
              .sort((a, b) => b.confidence_level - a.confidence_level)
              .map((proposal) => (
                <PromptProposalDiff
                  key={proposal.id}
                  proposal={proposal}
                  onProposalUpdated={handleProposalUpdated}
                />
              ))}
          </div>
        )}
      </div>
    </div>
  );
}
