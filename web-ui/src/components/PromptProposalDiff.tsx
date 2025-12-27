'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type { PromptProposal, ProposalStatus } from '@/lib/types';

interface Props {
  proposal: PromptProposal;
  onProposalUpdated: (proposal: PromptProposal) => void;
}

export default function PromptProposalDiff({ proposal, onProposalUpdated }: Props) {
  const [expanded, setExpanded] = useState(true);
  const [updating, setUpdating] = useState(false);
  const [viewMode, setViewMode] = useState<'diff' | 'full'>('diff');
  const [promptsCollapsed, setPromptsCollapsed] = useState(false);

  const updateStatus = async (newStatus: ProposalStatus) => {
    try {
      setUpdating(true);
      const updated = await api.updatePromptProposal(proposal.id, { status: newStatus });
      onProposalUpdated(updated);
    } catch (err: any) {
      console.error('Failed to update proposal:', err);
      alert(`Failed to update proposal: ${err.response?.data?.detail || err.message}`);
    } finally {
      setUpdating(false);
    }
  };

  const downloadProposedPrompt = () => {
    try {
      const blob = new Blob([proposal.proposed_text], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // Ensure .md extension is properly handled
      const baseName = proposal.prompt_file.replace(/\.md$/, '');
      const filename = `${baseName}_improved.md`;

      console.log('Downloading:', filename, 'Size:', proposal.proposed_text.length);

      a.download = filename;
      a.setAttribute('download', filename); // Ensure download attribute is set

      document.body.appendChild(a);
      a.click();

      // Clean up after a delay to ensure download starts
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 100);
    } catch (err) {
      console.error('Download failed:', err);
      alert('Failed to download file');
    }
  };

  const getStatusBadge = (status: ProposalStatus) => {
    const colors: Record<ProposalStatus, string> = {
      proposed: 'bg-blue-100 text-blue-800',
      accepted: 'bg-green-100 text-green-800',
      rejected: 'bg-red-100 text-red-800',
      implemented: 'bg-purple-100 text-purple-800',
    };
    return (
      <span className={`inline-block px-2 py-1 text-xs rounded ${colors[status]}`}>
        {status}
      </span>
    );
  };

  const getConfidenceBadge = (level: number) => {
    const color =
      level >= 8 ? 'bg-green-100 text-green-800' :
      level >= 6 ? 'bg-yellow-100 text-yellow-800' :
      'bg-orange-100 text-orange-800';

    return (
      <span className={`inline-block px-2 py-1 text-xs rounded ${color}`}>
        Confidence: {level}/10
      </span>
    );
  };

  return (
    <div className="border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 overflow-hidden">
      {/* Header */}
      <div className="bg-gray-50 dark:bg-gray-800 p-4 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-2">
              {getStatusBadge(proposal.status)}
              {getConfidenceBadge(proposal.confidence_level)}
              <span className="text-xs text-gray-700 dark:text-gray-500">{proposal.change_type}</span>
            </div>
            <div className="text-sm font-medium text-gray-900 dark:text-gray-100 mb-1">
              {proposal.prompt_file}
              {proposal.section_name && (
                <span className="text-gray-600 dark:text-gray-400"> › {proposal.section_name}</span>
              )}
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400">{proposal.rationale}</div>
          </div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="ml-4 text-blue-600 hover:text-blue-700 text-sm font-medium"
          >
            {expanded ? 'Hide Details ▲' : 'Show Details ▼'}
          </button>
        </div>
      </div>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4">
          {/* Evidence */}
          {proposal.evidence && Object.keys(proposal.evidence).length > 0 && (
            <div className="mb-4 p-3 bg-blue-50 rounded-lg">
              <h4 className="font-semibold text-sm text-gray-900 mb-2">Evidence</h4>
              <div className="text-sm text-gray-700 space-y-1">
                {proposal.evidence.pattern_frequency !== undefined && (
                  <div>
                    Frequency: {(proposal.evidence.pattern_frequency * 100).toFixed(1)}%
                  </div>
                )}
                {proposal.evidence.session_ids && proposal.evidence.session_ids.length > 0 && (
                  <div>
                    Sessions affected: {proposal.evidence.session_ids.length}
                  </div>
                )}
                {proposal.evidence.quality_scores && proposal.evidence.quality_scores.length > 0 && (
                  <div>
                    Avg quality score: {(
                      proposal.evidence.quality_scores.reduce((a, b) => a + b, 0) /
                      proposal.evidence.quality_scores.length
                    ).toFixed(1)}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Prompt View - Collapsible with Tabs */}
          <div className="mb-4 border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            {/* Header with collapse button and download */}
            <div
              className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-600"
              onClick={() => setPromptsCollapsed(!promptsCollapsed)}
            >
              <h4 className="font-semibold text-sm text-gray-900 dark:text-gray-100">
                Prompt Files ({proposal.original_text.length.toLocaleString()} → {proposal.proposed_text.length.toLocaleString()} chars)
              </h4>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    downloadProposedPrompt();
                  }}
                  className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                  title="Download improved prompt file"
                >
                  ⬇ Download Improved
                </button>
                <span className="text-gray-600 dark:text-gray-400">
                  {promptsCollapsed ? '▼' : '▲'}
                </span>
              </div>
            </div>

            {/* Content */}
            {!promptsCollapsed && (
              <div className="p-4">
                {/* Tab Buttons */}
                <div className="flex gap-2 mb-4 border-b border-gray-200 dark:border-gray-600">
                  <button
                    onClick={() => setViewMode('diff')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      viewMode === 'diff'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-800 dark:text-gray-400'
                    }`}
                  >
                    Side-by-Side
                  </button>
                  <button
                    onClick={() => setViewMode('full')}
                    className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                      viewMode === 'full'
                        ? 'border-blue-600 text-blue-600'
                        : 'border-transparent text-gray-600 hover:text-gray-800 dark:text-gray-400'
                    }`}
                  >
                    Full Prompts
                  </button>
                </div>

                {/* Diff View (Side-by-Side) */}
                {viewMode === 'diff' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Original */}
                    <div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">
                        Original ({proposal.original_text.length.toLocaleString()} chars)
                      </div>
                      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded p-3 max-h-96 overflow-auto">
                        <pre className="text-xs whitespace-pre-wrap font-mono text-red-900 dark:text-red-100">
                          {proposal.original_text}
                        </pre>
                      </div>
                    </div>

                    {/* Proposed */}
                    <div>
                      <div className="text-xs text-gray-500 dark:text-gray-400 mb-1 font-medium">
                        Proposed ({proposal.proposed_text.length.toLocaleString()} chars)
                      </div>
                      <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded p-3 max-h-96 overflow-auto">
                        <pre className="text-xs whitespace-pre-wrap font-mono text-green-900 dark:text-green-100">
                          {proposal.proposed_text}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}

                {/* Full View (Stacked) */}
                {viewMode === 'full' && (
                  <div className="space-y-4">
                    {/* Original */}
                    <div>
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        Original Prompt ({proposal.original_text.length.toLocaleString()} chars)
                      </div>
                      <div className="bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-4 max-h-96 overflow-auto">
                        <pre className="text-xs whitespace-pre-wrap font-mono text-gray-900 dark:text-gray-100">
                          {proposal.original_text}
                        </pre>
                      </div>
                    </div>

                    {/* Proposed */}
                    <div>
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center justify-between">
                        <span>Improved Prompt ({proposal.proposed_text.length.toLocaleString()} chars)</span>
                        <button
                          onClick={downloadProposedPrompt}
                          className="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-xs"
                        >
                          ⬇ Download
                        </button>
                      </div>
                      <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded p-4 max-h-96 overflow-auto">
                        <pre className="text-xs whitespace-pre-wrap font-mono text-gray-900 dark:text-gray-100">
                          {proposal.proposed_text}
                        </pre>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={() => updateStatus('proposed')}
                disabled={updating || proposal.status === 'proposed'}
                className={`px-4 py-2 rounded-md transition-colors text-sm ${
                  proposal.status === 'proposed'
                    ? 'bg-blue-100 text-blue-800 cursor-not-allowed'
                    : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                }`}
              >
                {proposal.status === 'proposed' ? '• Proposed' : 'Proposed'}
              </button>
              <button
                onClick={() => updateStatus('accepted')}
                disabled={updating || proposal.status === 'accepted'}
                className={`px-4 py-2 rounded-md transition-colors text-sm ${
                  proposal.status === 'accepted'
                    ? 'bg-green-100 text-green-800 cursor-not-allowed'
                    : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                }`}
              >
                {proposal.status === 'accepted' ? '• Accepted' : 'Accept'}
              </button>
              <button
                onClick={() => updateStatus('rejected')}
                disabled={updating || proposal.status === 'rejected'}
                className={`px-4 py-2 rounded-md transition-colors text-sm ${
                  proposal.status === 'rejected'
                    ? 'bg-red-100 text-red-800 cursor-not-allowed'
                    : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                }`}
              >
                {proposal.status === 'rejected' ? '• Rejected' : 'Reject'}
              </button>
              <button
                onClick={() => updateStatus('implemented')}
                disabled={updating || proposal.status === 'implemented'}
                className={`px-4 py-2 rounded-md transition-colors text-sm ${
                  proposal.status === 'implemented'
                    ? 'bg-purple-100 text-purple-800 cursor-not-allowed'
                    : 'bg-gray-200 text-gray-800 hover:bg-gray-300'
                }`}
              >
                {proposal.status === 'implemented' ? '• Implemented' : 'Implemented'}
              </button>
            </div>
            <div className="text-sm text-gray-600 dark:text-gray-400 italic">
              ℹ️ Note: Changes must be manually applied to prompt files. Click a status button to mark the proposal accordingly.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
