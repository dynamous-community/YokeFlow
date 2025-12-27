/**
 * ResetProjectDialog Component
 * Modal dialog for resetting a project to post-initialization state
 */

'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import type { ResetProjectResponse } from '@/lib/types';
import { AlertCircle, RefreshCw, Check, X } from 'lucide-react';

interface ResetProjectDialogProps {
  projectId: string;
  projectName: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function ResetProjectDialog({
  projectId,
  projectName,
  onClose,
  onSuccess,
}: ResetProjectDialogProps) {
  const [confirmText, setConfirmText] = useState('');
  const [isResetting, setIsResetting] = useState(false);
  const [resetResult, setResetResult] = useState<ResetProjectResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isConfirmed = confirmText.toLowerCase() === 'reset';

  async function handleReset() {
    if (!isConfirmed) return;

    setIsResetting(true);
    setError(null);

    try {
      const result = await api.resetProject(projectId);
      setResetResult(result);

      if (result.success) {
        // Wait a moment to show success, then notify parent and close
        setTimeout(() => {
          onSuccess();
          onClose();
        }, 2000);
      } else {
        setError(result.error || 'Reset failed');
      }
    } catch (err: any) {
      console.error('Failed to reset project:', err);
      const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
      setError(`Failed to reset project: ${errorMsg}`);
    } finally {
      setIsResetting(false);
    }
  }

  // Show success screen
  if (resetResult?.success) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-gray-800 border border-green-500/30 rounded-lg max-w-2xl w-full p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
              <Check className="w-6 h-6 text-green-400" />
            </div>
            <h2 className="text-xl font-bold text-green-400">Reset Complete!</h2>
          </div>

          <div className="bg-gray-900 rounded-lg p-4 mb-4">
            <div className="text-sm text-gray-300 space-y-2">
              <p>
                <span className="text-green-400 font-medium">✓</span> Database reset to post-initialization state
              </p>
              <p>
                <span className="text-green-400 font-medium">✓</span> Git repository reset to initialization commit
              </p>
              <p>
                <span className="text-green-400 font-medium">✓</span> Coding session logs archived
              </p>
              {resetResult.archive_path && (
                <p className="text-xs text-gray-400 mt-2">
                  Archive location: <code className="bg-gray-800 px-1 py-0.5 rounded">{resetResult.archive_path}</code>
                </p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-900 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Completed Tasks</div>
              <div className="flex items-baseline gap-2">
                <span className="text-red-400 line-through">{resetResult.state_before.completed_tasks}</span>
                <span className="text-gray-600">→</span>
                <span className="text-green-400 font-semibold">{resetResult.state_after.completed_tasks}</span>
              </div>
            </div>
            <div className="bg-gray-900 rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Coding Sessions</div>
              <div className="flex items-baseline gap-2">
                <span className="text-red-400 line-through">{resetResult.state_before.coding_sessions}</span>
                <span className="text-gray-600">→</span>
                <span className="text-green-400 font-semibold">{resetResult.state_after.coding_sessions}</span>
              </div>
            </div>
          </div>

          <p className="text-sm text-gray-400 text-center">
            Closing in a moment...
          </p>
        </div>
      </div>
    );
  }

  // Show error screen
  if (error) {
    return (
      <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
        <div className="bg-gray-800 border border-red-500/30 rounded-lg max-w-2xl w-full p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
              <X className="w-6 h-6 text-red-400" />
            </div>
            <h2 className="text-xl font-bold text-red-400">Reset Failed</h2>
          </div>

          <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-4">
            <p className="text-sm text-red-200">{error}</p>
          </div>

          {resetResult?.steps && (
            <div className="bg-gray-900 rounded-lg p-4 mb-4">
              <div className="text-xs text-gray-400 mb-2">Reset steps:</div>
              <div className="space-y-1 text-sm">
                {Object.entries(resetResult.steps).map(([step, result]) => (
                  <div key={step} className="flex items-center gap-2">
                    {result.success ? (
                      <Check className="w-4 h-4 text-green-400" />
                    ) : (
                      <X className="w-4 h-4 text-red-400" />
                    )}
                    <span className="text-gray-300 capitalize">{step}</span>
                    {'error' in result && result.error && (
                      <span className="text-xs text-red-400">: {result.error}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Show confirmation dialog
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 border border-red-500/30 rounded-lg max-w-2xl w-full p-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center">
            <AlertCircle className="w-6 h-6 text-red-400" />
          </div>
          <h2 className="text-xl font-bold text-red-400">Reset Project to Post-Initialization State</h2>
        </div>

        {/* Warning */}
        <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-200 mb-3">
            <strong>Warning:</strong> This will reset the project "{projectName}" back to the state immediately after initialization.
            This is useful for testing prompt improvements or debugging without re-running initialization (10-20 minutes).
          </p>
        </div>

        {/* What will be reset */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">What will be reset:</h3>
          <div className="bg-gray-900 rounded-lg p-4 space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <div>
                <span className="text-gray-300">Database:</span>
                <span className="text-gray-600 dark:text-gray-400"> All task/test completion status</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <div>
                <span className="text-gray-300">Git:</span>
                <span className="text-gray-600 dark:text-gray-400"> Reset to commit after initialization</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <div>
                <span className="text-gray-300">Logs:</span>
                <span className="text-gray-600 dark:text-gray-400"> Coding session logs archived to </span>
                <code className="text-xs bg-gray-800 px-1 py-0.5 rounded">logs/old_attempts/TIMESTAMP/</code>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-red-400 mt-0.5">✗</span>
              <div>
                <span className="text-gray-300">Progress:</span>
                <span className="text-gray-600 dark:text-gray-400"> Progress notes backed up and reset</span>
              </div>
            </div>
          </div>
        </div>

        {/* What will be preserved */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold text-gray-300 mb-3">What will be preserved:</h3>
          <div className="bg-gray-900 rounded-lg p-4 space-y-2 text-sm">
            <div className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <div>
                <span className="text-gray-300">Complete project roadmap</span>
                <span className="text-gray-600 dark:text-gray-400"> (all epics, tasks, tests)</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <div>
                <span className="text-gray-300">Initialization session</span>
                <span className="text-gray-600 dark:text-gray-400"> (Session 0 commit and logs)</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <div>
                <span className="text-gray-300">Project structure</span>
                <span className="text-gray-600 dark:text-gray-400"> (init.sh and generated folders)</span>
              </div>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-green-400 mt-0.5">✓</span>
              <div>
                <span className="text-gray-300">Configuration files</span>
                <span className="text-gray-600 dark:text-gray-400"> (.env.example, etc.)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Confirmation input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Type <code className="bg-gray-900 px-2 py-0.5 rounded text-red-400">reset</code> to confirm:
          </label>
          <input
            type="text"
            value={confirmText}
            onChange={(e) => setConfirmText(e.target.value)}
            placeholder="Type 'reset' to confirm"
            className="w-full px-3 py-2 bg-gray-900 border border-gray-700 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:border-red-500"
            disabled={isResetting}
            autoFocus
          />
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isResetting}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleReset}
            disabled={!isConfirmed || isResetting}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium flex items-center gap-2"
          >
            {isResetting ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Resetting...
              </>
            ) : (
              <>
                <RefreshCw className="w-4 h-4" />
                Reset Project
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
