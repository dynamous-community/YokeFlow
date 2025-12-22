'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type { PromptVersion } from '@/lib/types';

interface Props {
  promptFile: string;
}

export default function PromptVersionHistory({ promptFile }: Props) {
  const [versions, setVersions] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activating, setActivating] = useState<string | null>(null);

  useEffect(() => {
    loadVersions();
  }, [promptFile]);

  const loadVersions = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.listPromptVersions(promptFile);
      setVersions(data);
    } catch (err: any) {
      console.error('Failed to load versions:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to load versions');
    } finally {
      setLoading(false);
    }
  };

  const activateVersion = async (versionId: string) => {
    if (!confirm('Are you sure you want to activate this version? It will become the active prompt.')) {
      return;
    }

    try {
      setActivating(versionId);
      await api.activatePromptVersion(versionId);
      await loadVersions(); // Reload to show updated is_active status
    } catch (err: any) {
      console.error('Failed to activate version:', err);
      alert(`Failed to activate version: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActivating(null);
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-500">Loading version history...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
        <h3 className="text-red-800 font-semibold">Error</h3>
        <p className="text-red-700 mt-2">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-xl font-semibold">Version History: {promptFile}</h2>
        <div className="text-sm text-gray-500">{versions.length} versions</div>
      </div>

      {versions.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          No versions found for this prompt file.
        </div>
      ) : (
        <div className="space-y-3">
          {versions.map((version) => (
            <div
              key={version.id}
              className={`border rounded-lg p-4 ${
                version.is_active
                  ? 'border-blue-400 bg-blue-50'
                  : 'border-gray-200 bg-white'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="font-semibold">{version.version_name}</h3>
                    {version.is_active && (
                      <span className="inline-block px-2 py-1 text-xs bg-blue-600 text-white rounded">
                        ACTIVE
                      </span>
                    )}
                    {version.is_default && (
                      <span className="inline-block px-2 py-1 text-xs bg-gray-600 text-white rounded">
                        DEFAULT
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-gray-500">
                    Created: {formatDate(version.created_at)}
                    {version.created_by && ` by ${version.created_by}`}
                  </div>
                  {version.changes_summary && (
                    <div className="text-sm text-gray-700 mt-2">
                      {version.changes_summary}
                    </div>
                  )}
                </div>
                {!version.is_active && (
                  <button
                    onClick={() => activateVersion(version.id)}
                    disabled={activating === version.id}
                    className="ml-4 px-3 py-1 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 transition-colors"
                  >
                    {activating === version.id ? 'Activating...' : 'Activate'}
                  </button>
                )}
              </div>

              {/* Performance Stats */}
              <div className="grid grid-cols-3 gap-4 mt-3 pt-3 border-t border-gray-200">
                <div>
                  <div className="text-xs text-gray-500">Projects Using</div>
                  <div className="font-semibold">{version.projects_using}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Total Sessions</div>
                  <div className="font-semibold">{version.total_sessions}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Avg Quality</div>
                  <div className="font-semibold">
                    {version.avg_quality_rating
                      ? `${version.avg_quality_rating.toFixed(1)}/10`
                      : 'N/A'}
                  </div>
                </div>
              </div>

              {version.git_commit_hash && (
                <div className="mt-2 text-xs text-gray-500">
                  Git: <code className="bg-gray-100 px-1 rounded">{version.git_commit_hash.substring(0, 8)}</code>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
