'use client';

import { useState } from 'react';
import type { TriggerBulkReviewsRequest } from '@/lib/types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onTrigger: (request: TriggerBulkReviewsRequest) => Promise<void>;
  projectName: string;
  totalSessions: number;
  sessionsWithoutReviews: number;
  unreviewedSessionNumbers: number[];
}

export default function TriggerReviewsDialog({
  isOpen,
  onClose,
  onTrigger,
  projectName,
  totalSessions,
  sessionsWithoutReviews,
  unreviewedSessionNumbers,
}: Props) {
  const [mode, setMode] = useState<'all' | 'unreviewed' | 'last_n' | 'single'>('unreviewed');
  const [lastN, setLastN] = useState(5);
  const [sessionNumber, setSessionNumber] = useState(unreviewedSessionNumbers[0] || 1);
  const [triggering, setTriggering] = useState(false);

  if (!isOpen) return null;

  const handleTrigger = async () => {
    try {
      setTriggering(true);
      const request: TriggerBulkReviewsRequest = {
        mode,
        ...(mode === 'last_n' && { last_n: lastN }),
        ...(mode === 'single' && { session_number: sessionNumber }),
      };
      await onTrigger(request);
      onClose();
    } catch (err) {
      console.error('Failed to trigger reviews:', err);
    } finally {
      setTriggering(false);
    }
  };

  const getSessionCount = () => {
    if (mode === 'all') return totalSessions;
    if (mode === 'unreviewed') return sessionsWithoutReviews;
    if (mode === 'last_n') return Math.min(lastN, totalSessions);
    if (mode === 'single') return 1;
    return 0;
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
        <h2 className="text-xl font-semibold mb-4">Trigger Deep Reviews</h2>
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
          Project: <span className="font-medium">{projectName}</span>
        </p>

        {/* Mode Selection */}
        <div className="space-y-4 mb-6">
          <div>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="radio"
                value="unreviewed"
                checked={mode === 'unreviewed'}
                onChange={(e) => setMode(e.target.value as any)}
                className="w-4 h-4 text-blue-600"
              />
              <div>
                <div className="font-medium">Unreviewed Sessions Only</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {sessionsWithoutReviews} session{sessionsWithoutReviews !== 1 ? 's' : ''} without reviews
                </div>
              </div>
            </label>
          </div>

          <div>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="radio"
                value="last_n"
                checked={mode === 'last_n'}
                onChange={(e) => setMode(e.target.value as any)}
                className="w-4 h-4 text-blue-600"
              />
              <div className="flex-1">
                <div className="font-medium">Last N Sessions</div>
                {mode === 'last_n' && (
                  <input
                    type="number"
                    value={lastN}
                    onChange={(e) => setLastN(parseInt(e.target.value) || 1)}
                    min="1"
                    max={totalSessions}
                    className="mt-2 w-24 px-3 py-1 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  />
                )}
              </div>
            </label>
          </div>

          <div>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="radio"
                value="single"
                checked={mode === 'single'}
                onChange={(e) => setMode(e.target.value as any)}
                className="w-4 h-4 text-blue-600"
                disabled={unreviewedSessionNumbers.length === 0}
              />
              <div className="flex-1">
                <div className="font-medium">Specific Session</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {unreviewedSessionNumbers.length === 0 ? 'No unreviewed sessions' : 'Select an unreviewed session'}
                </div>
                {mode === 'single' && unreviewedSessionNumbers.length > 0 && (
                  <select
                    value={sessionNumber}
                    onChange={(e) => setSessionNumber(parseInt(e.target.value))}
                    className="mt-2 w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                  >
                    {unreviewedSessionNumbers.map(num => (
                      <option key={num} value={num}>
                        Session {num}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            </label>
          </div>

          <div>
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="radio"
                value="all"
                checked={mode === 'all'}
                onChange={(e) => setMode(e.target.value as any)}
                className="w-4 h-4 text-blue-600"
              />
              <div>
                <div className="font-medium">All Sessions</div>
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  {totalSessions} total session{totalSessions !== 1 ? 's' : ''}
                </div>
                {mode === 'all' && (
                  <div className="text-sm text-orange-600 dark:text-orange-400 mt-1">
                    ⚠️ Warning: This will re-review sessions that already have reviews
                  </div>
                )}
              </div>
            </label>
          </div>
        </div>

        {/* Summary */}
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4 mb-6">
          <p className="text-sm text-blue-900 dark:text-blue-100">
            This will trigger <span className="font-bold">{getSessionCount()}</span> deep review
            {getSessionCount() !== 1 ? 's' : ''}. Reviews run in the background and results will appear
            in the Quality Dashboard when complete.
          </p>
        </div>

        {/* Actions */}
        <div className="flex justify-end space-x-3">
          <button
            onClick={onClose}
            disabled={triggering}
            className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleTrigger}
            disabled={triggering || getSessionCount() === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
          >
            {triggering ? 'Triggering...' : `Trigger ${getSessionCount()} Review${getSessionCount() !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  );
}
