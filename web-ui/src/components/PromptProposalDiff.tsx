'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type { PromptProposal, ProposalStatus } from '@/lib/types';

interface Props {
  proposal: PromptProposal;
  onProposalUpdated: (proposal: PromptProposal) => void;
}

export default function PromptProposalDiff({ proposal, onProposalUpdated }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [applying, setApplying] = useState(false);

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

  const applyProposal = async () => {
    if (!confirm('Are you sure you want to apply this proposal? This will modify the prompt file.')) {
      return;
    }

    try {
      setApplying(true);
      const response = await api.applyPromptProposal(proposal.id);
      if (response.success) {
        alert(`Proposal applied successfully!\n\nFile: ${response.file_path}\nBackup: ${response.backup_path}`);
        // Reload to get updated status
        const updated = await api.updatePromptProposal(proposal.id, { status: 'implemented' });
        onProposalUpdated(updated);
      } else {
        alert(`Failed to apply proposal: ${response.message}`);
      }
    } catch (err: any) {
      console.error('Failed to apply proposal:', err);
      alert(`Failed to apply proposal: ${err.response?.data?.detail || err.message}`);
    } finally {
      setApplying(false);
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
              <span className="text-xs text-gray-500">{proposal.change_type}</span>
            </div>
            <div className="text-sm font-medium text-gray-900 mb-1">
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

          {/* Diff View */}
          <div className="mb-4">
            <h4 className="font-semibold text-sm text-gray-900 mb-2">Proposed Change</h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Original */}
              <div>
                <div className="text-xs text-gray-500 mb-1 font-medium">Original</div>
                <div className="bg-red-50 border border-red-200 rounded p-3">
                  <pre className="text-xs whitespace-pre-wrap font-mono text-red-900">
                    {proposal.original_text}
                  </pre>
                </div>
              </div>

              {/* Proposed */}
              <div>
                <div className="text-xs text-gray-500 mb-1 font-medium">Proposed</div>
                <div className="bg-green-50 border border-green-200 rounded p-3">
                  <pre className="text-xs whitespace-pre-wrap font-mono text-green-900">
                    {proposal.proposed_text}
                  </pre>
                </div>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2 pt-4 border-t border-gray-200">
            {proposal.status === 'proposed' && (
              <>
                <button
                  onClick={() => updateStatus('accepted')}
                  disabled={updating}
                  className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:bg-gray-400 transition-colors text-sm"
                >
                  {updating ? 'Updating...' : 'Accept'}
                </button>
                <button
                  onClick={() => updateStatus('rejected')}
                  disabled={updating}
                  className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-400 transition-colors text-sm"
                >
                  {updating ? 'Updating...' : 'Reject'}
                </button>
              </>
            )}
            {proposal.status === 'accepted' && (
              <button
                onClick={applyProposal}
                disabled={applying}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-colors text-sm"
              >
                {applying ? 'Applying...' : 'Apply to Prompt File'}
              </button>
            )}
            {proposal.status === 'implemented' && (
              <div className="text-sm text-green-600 font-medium">
                ✓ Implemented {proposal.applied_at && `on ${new Date(proposal.applied_at).toLocaleDateString()}`}
              </div>
            )}
            {proposal.status === 'rejected' && (
              <button
                onClick={() => updateStatus('proposed')}
                disabled={updating}
                className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:bg-gray-400 transition-colors text-sm"
              >
                {updating ? 'Updating...' : 'Reconsider'}
              </button>
            )}
          </div>

          {/* Impact Tracking */}
          {(proposal.quality_before !== null || proposal.quality_after !== null) && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <h4 className="font-semibold text-sm text-gray-900 mb-2">Impact Tracking</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <div className="text-gray-500">Before</div>
                  <div>
                    {proposal.sessions_before_change || 0} sessions
                    {proposal.quality_before && ` • Quality: ${proposal.quality_before.toFixed(1)}/10`}
                  </div>
                </div>
                <div>
                  <div className="text-gray-500">After</div>
                  <div>
                    {proposal.sessions_after_change || 0} sessions
                    {proposal.quality_after && (
                      <span>
                        {' '}• Quality: {proposal.quality_after.toFixed(1)}/10
                        {proposal.quality_before && proposal.quality_after > proposal.quality_before && (
                          <span className="text-green-600 ml-1">
                            (+{(proposal.quality_after - proposal.quality_before).toFixed(1)})
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
