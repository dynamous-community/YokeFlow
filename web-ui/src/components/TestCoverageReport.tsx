/**
 * TestCoverageReport - Display test coverage analysis from initialization
 *
 * Shows test-to-task ratio analysis performed after Session 0 (initialization).
 * Helps identify epics with poor test coverage before coding begins.
 *
 * Features:
 * - Overall coverage statistics
 * - Per-epic breakdown
 * - Tasks without tests highlighted
 * - Coverage warnings
 */

'use client';

import React, { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import {
  TestCoverageResponse,
  TestCoverageData,
  PoorCoverageEpic,
  TestCoverageEpic,
} from '@/lib/types';
import { AlertTriangle, CheckCircle, BarChart3, ChevronDown, ChevronRight } from 'lucide-react';

interface TestCoverageReportProps {
  projectId: string;
}

export function TestCoverageReport({ projectId }: TestCoverageReportProps) {
  const [coverage, setCoverage] = useState<TestCoverageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedEpic, setExpandedEpic] = useState<number | null>(null);

  useEffect(() => {
    loadCoverageData();
  }, [projectId]);

  async function loadCoverageData() {
    try {
      setLoading(true);
      setError(null);
      const data = await api.getTestCoverage(projectId);
      setCoverage(data);
    } catch (err: any) {
      console.error('Failed to load test coverage:', err);
      // Don't show error if coverage data doesn't exist yet (project not initialized)
      if (err.response?.status !== 404) {
        setError(err.message || 'Failed to load test coverage data');
      }
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3"></div>
          <p className="text-gray-400 text-sm">Loading test coverage...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-600/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          <span className="font-medium">Failed to load test coverage</span>
        </div>
        <p className="text-sm text-gray-400 mt-1">{error}</p>
      </div>
    );
  }

  if (!coverage) {
    return (
      <div className="text-center py-12">
        <div className="text-gray-500 text-4xl mb-3">📊</div>
        <p className="text-gray-600 dark:text-gray-400">No test coverage data available</p>
        <p className="text-sm text-gray-500 mt-2">
          Test coverage analysis runs after initialization (Session 0) completes
        </p>
      </div>
    );
  }

  const { data } = coverage;
  const { overall, poor_coverage_epics, warnings } = data;

  // Determine coverage quality color
  const getCoverageColor = (percentage: number) => {
    if (percentage >= 90) return 'text-green-400';
    if (percentage >= 70) return 'text-blue-400';
    if (percentage >= 50) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getCoverageBgColor = (percentage: number) => {
    if (percentage >= 90) return 'bg-green-500';
    if (percentage >= 70) return 'bg-blue-500';
    if (percentage >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-100 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          Test Coverage Analysis
        </h3>
        {coverage.analyzed_at && (
          <span className="text-xs text-gray-700 dark:text-gray-500">
            Analyzed: {new Date(coverage.analyzed_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Warnings */}
      {warnings.length > 0 && (
        <div className="bg-yellow-900/20 border border-yellow-600/50 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-medium text-yellow-400 mb-2">Coverage Warnings</h4>
              <ul className="space-y-1">
                {warnings.map((warning, idx) => (
                  <li key={idx} className="text-sm text-gray-300">
                    {warning}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Overall Statistics */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h4 className="font-medium text-gray-100 mb-4">Overall Statistics</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-100">{overall.total_tasks}</div>
            <div className="text-xs text-gray-400 mt-1">Total Tasks</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-100">{overall.total_tests}</div>
            <div className="text-xs text-gray-400 mt-1">Total Tests</div>
          </div>
          <div className="text-center">
            <div className={`text-2xl font-bold ${getCoverageColor(overall.coverage_percentage)}`}>
              {overall.coverage_percentage.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-400 mt-1">Coverage</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-100">
              {overall.avg_tests_per_task.toFixed(2)}
            </div>
            <div className="text-xs text-gray-400 mt-1">Avg Tests/Task</div>
          </div>
        </div>

        {/* Coverage Progress Bar */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
            <span>{overall.tasks_with_tests} tasks with tests</span>
            <span>{overall.tasks_without_tests} without tests</span>
          </div>
          <div className="h-3 bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all ${getCoverageBgColor(overall.coverage_percentage)}`}
              style={{ width: `${overall.coverage_percentage}%` }}
            ></div>
          </div>
        </div>
      </div>

      {/* Poor Coverage Epics */}
      {poor_coverage_epics.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-yellow-600/50">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <h4 className="font-medium text-gray-100">
              Epics with Poor Coverage ({poor_coverage_epics.length})
            </h4>
          </div>
          <p className="text-sm text-gray-400 mb-4">
            These epics have more than 50% of tasks without tests
          </p>
          <div className="space-y-3">
            {poor_coverage_epics.map((epic) => (
              <div
                key={epic.epic_id}
                className="bg-gray-900/50 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-medium text-gray-300">
                        Epic {epic.epic_id}: {epic.epic_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
                      <span>
                        {epic.tasks_without_tests} / {epic.total_tasks} tasks without tests
                      </span>
                      <span className={getCoverageColor(epic.coverage_percentage)}>
                        {epic.coverage_percentage.toFixed(1)}% coverage
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() =>
                      setExpandedEpic(expandedEpic === epic.epic_id ? null : epic.epic_id)
                    }
                    className="text-gray-400 hover:text-gray-300 transition-colors"
                  >
                    {expandedEpic === epic.epic_id ? (
                      <ChevronDown className="w-5 h-5" />
                    ) : (
                      <ChevronRight className="w-5 h-5" />
                    )}
                  </button>
                </div>

                {/* Expanded: Show tasks without tests */}
                {expandedEpic === epic.epic_id && (
                  <div className="mt-3 pt-3 border-t border-gray-700">
                    <p className="text-xs text-gray-400 mb-2">Tasks without tests:</p>
                    <ul className="space-y-1">
                      {epic.tasks.slice(0, 10).map((task) => (
                        <li key={task.id} className="text-xs text-gray-500 pl-4">
                          • Task {task.id}: {task.description.slice(0, 80)}
                          {task.description.length > 80 ? '...' : ''}
                        </li>
                      ))}
                      {epic.tasks.length > 10 && (
                        <li className="text-xs text-gray-500 pl-4 italic">
                          ... and {epic.tasks.length - 10} more
                        </li>
                      )}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* All Epics Coverage (if no poor coverage) */}
      {poor_coverage_epics.length === 0 && (
        <div className="bg-gray-800 rounded-lg p-6 border border-green-600/50">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <h4 className="font-medium text-gray-100">Excellent Test Coverage!</h4>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            All epics have adequate test coverage (≥50% of tasks have tests)
          </p>
        </div>
      )}

      {/* Legend */}
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
        <h4 className="text-sm font-medium text-gray-300 mb-3">Coverage Quality</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-green-500 rounded"></div>
            <span className="text-gray-600 dark:text-gray-400">90%+ Excellent</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-blue-500 rounded"></div>
            <span className="text-gray-600 dark:text-gray-400">70-89% Good</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-yellow-500 rounded"></div>
            <span className="text-gray-600 dark:text-gray-400">50-69% Fair</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 bg-red-500 rounded"></div>
            <span className="text-gray-600 dark:text-gray-400">&lt;50% Poor</span>
          </div>
        </div>
      </div>
    </div>
  );
}
