/**
 * QualityDashboard - Display project-wide quality metrics and trends
 *
 * Features:
 * - Overall quality summary
 * - Quality trend chart over sessions
 * - Browser verification compliance
 * - Recent quality issues
 * - Deep review recommendations
 */

'use client';

import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { api } from '@/lib/api';
import { SessionQualityBadge, QualityLegend } from './SessionQualityBadge';
import { TestCoverageReport } from './TestCoverageReport';
import { TrendingUp, CheckCircle, Eye, Download, AlertTriangle } from 'lucide-react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface QualityDashboardProps {
  projectId: string;
}

interface QualitySummary {
  total_sessions: number;
  checked_sessions: number;
  avg_quality_rating: number | null;
  sessions_without_browser_verification: number;
  avg_error_rate_percent: number | null;
  avg_playwright_calls_per_session: number | null;
}

interface SessionQuality {
  id: string;  // Quality check ID (unique)
  session_id: string;
  session_number: number;
  check_type: 'quick' | 'deep' | 'final';
  overall_rating: number;
  playwright_count: number;
  playwright_screenshot_count: number;
  error_count: number;
  error_rate: number;
  critical_issues: any[];
  warnings: any[];
  prompt_improvements: any[];
  review_text: string | null;
  created_at: string;
}

interface DeepReview {
  id: string;  // Review ID
  session_id: string;
  session_number: number;
  review_version: string;
  created_at: string;
  overall_rating: number;
  review_text: string;
  review_summary: {
    rating: number;
    one_line: string;
    summary: string;
  };
  prompt_improvements: string[];
  model: string;
}

export function QualityDashboard({ projectId }: QualityDashboardProps) {
  const [summary, setSummary] = useState<QualitySummary | null>(null);
  const [sessions, setSessions] = useState<SessionQuality[]>([]);
  const [deepReviews, setDeepReviews] = useState<DeepReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedSession, setExpandedSession] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'test-coverage' | 'session-quality' | 'deep-reviews'>('test-coverage');

  useEffect(() => {
    loadQualityData();
  }, [projectId]);

  function downloadReview(sessionNumber: number, reviewText: string) {
    const blob = new Blob([reviewText], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deep-review-session-${sessionNumber}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async function loadQualityData() {
    try {
      setLoading(true);
      setError(null);

      // Load all quality data in parallel
      const [summaryRes, sessionsData, deepReviewsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/projects/${projectId}/quality`),
        api.listSessions(projectId),
        axios.get(`${API_BASE}/api/projects/${projectId}/deep-reviews`)
      ]);

      setSummary(summaryRes.data);
      setDeepReviews(deepReviewsRes.data.reviews || []);

      // Fetch quality data for each session
      const sessionsWithQuality = await Promise.all(
        sessionsData.map(async (session: any) => {
          try {
            const qualityRes = await axios.get(
              `${API_BASE}/api/projects/${projectId}/sessions/${session.id}/quality`
            );
            return {
              ...qualityRes.data,
              session_number: session.session_number,
              // Don't override session_id if it already exists in qualityRes.data
              session_id: qualityRes.data.session_id || session.id
            };
          } catch (err: any) {
            // Session might not have quality check yet - suppress 404 errors
            if (err.response?.status !== 404) {
              console.error(`Failed to load quality for session ${session.id}:`, err);
            }
            return null;
          }
        })
      );

      // Filter out nulls and sort by session number
      const validSessions = sessionsWithQuality
        .filter((s) => s !== null)
        .sort((a, b) => a!.session_number - b!.session_number) as SessionQuality[];

      // Deduplicate by quality check ID to prevent React key warnings
      const uniqueSessions = validSessions.reduce((acc, session) => {
        if (!acc.find(s => s.id === session.id)) {
          acc.push(session);
        } else {
          console.warn(`Duplicate quality check ID found: ${session.id} (session ${session.session_number})`);
        }
        return acc;
      }, [] as SessionQuality[]);

      setSessions(uniqueSessions);
    } catch (err: any) {
      console.error('Failed to load quality data:', err);
      setError(err.message || 'Failed to load quality data');
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3"></div>
          <p className="text-gray-400 text-sm">Loading quality data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-600/50 rounded-lg p-4">
        <div className="flex items-center gap-2 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          <span className="font-medium">Failed to load quality data</span>
        </div>
        <p className="text-sm text-gray-400 mt-1">{error}</p>
      </div>
    );
  }

  // Calculate quality trend (for session quality tab)
  const recentSessions = sessions.slice(-10); // Last 10 sessions
  const avgQuality = summary?.avg_quality_rating || 0;
  const browserVerificationCompliance =
    summary && summary.total_sessions > 0
      ? ((summary.total_sessions - summary.sessions_without_browser_verification) /
          summary.total_sessions) *
        100
      : 0;

  // Quality tab workflow:
  // - Test Coverage tab: Populated after Session 0 (initialization) completes
  // - Session Quality tab: Populated after Session 1+ (coding sessions) complete
  //
  // This means projects will always show Test Coverage first, then Session Quality
  // appears once coding begins.
  const hasSessionQualityData = summary && sessions.length > 0;

  return (
    <div className="space-y-6">
      {/* Sub-tabs */}
      <div className="flex gap-2 border-b border-gray-700">
        <button
          onClick={() => setActiveTab('test-coverage')}
          className={`px-4 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'test-coverage'
              ? 'text-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Test Coverage
          {activeTab === 'test-coverage' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400"></div>
          )}
        </button>
        <button
          onClick={() => setActiveTab('session-quality')}
          className={`px-4 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'session-quality'
              ? 'text-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Session Quality
          {activeTab === 'session-quality' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400"></div>
          )}
        </button>
        <button
          onClick={() => setActiveTab('deep-reviews')}
          className={`px-4 py-2 text-sm font-medium transition-colors relative ${
            activeTab === 'deep-reviews'
              ? 'text-blue-400'
              : 'text-gray-400 hover:text-gray-300'
          }`}
        >
          Deep Reviews
          {deepReviews.length > 0 && (
            <span className="ml-1.5 px-1.5 py-0.5 text-xs bg-blue-500/20 text-blue-300 rounded">
              {deepReviews.length}
            </span>
          )}
          {activeTab === 'deep-reviews' && (
            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-400"></div>
          )}
        </button>
      </div>

      {/* Test Coverage Tab */}
      {activeTab === 'test-coverage' && (
        <div className="animate-fadeIn">
          <TestCoverageReport projectId={projectId} />
        </div>
      )}

      {/* Session Quality Tab */}
      {activeTab === 'session-quality' && (
        <div className="animate-fadeIn space-y-6">
          {!hasSessionQualityData ? (
            <div className="text-center py-12">
              <div className="text-gray-500 text-4xl mb-3">📊</div>
              <p className="text-gray-600 dark:text-gray-400">No session quality data available yet</p>
              <p className="text-sm text-gray-500 mt-2">
                Quality checks run after Session 1+ (coding sessions) complete
              </p>
              <p className="text-xs text-gray-600 mt-3">
                💡 Tip: Check the <span className="text-blue-400">Test Coverage</span> tab to see initialization results
              </p>
            </div>
          ) : (
            <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Average Quality */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Avg Quality</span>
            <TrendingUp className="w-4 h-4 text-blue-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-100">
              {avgQuality.toFixed(1)}
            </span>
            <span className="text-sm text-gray-700 dark:text-gray-500">/  10</span>
          </div>
          <div className="mt-2">
            <SessionQualityBadge
              rating={Math.round(avgQuality)}
              size="sm"
              showLabel={false}
            />
          </div>
        </div>

        {/* Sessions Checked */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Sessions Checked</span>
            <CheckCircle className="w-4 h-4 text-green-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-100">
              {summary.checked_sessions}
            </span>
            <span className="text-sm text-gray-700 dark:text-gray-500">
              / {summary.total_sessions}
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {summary.total_sessions > 0
              ? `${Math.round((summary.checked_sessions / summary.total_sessions) * 100)}% coverage`
              : 'No sessions yet'}
          </div>
        </div>

        {/* Browser Verification */}
        <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-600 dark:text-gray-400">Browser Checks</span>
            <Eye className="w-4 h-4 text-purple-400" />
          </div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-100">
              {browserVerificationCompliance.toFixed(0)}%
            </span>
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {summary.sessions_without_browser_verification > 0
              ? `${summary.sessions_without_browser_verification} sessions without`
              : 'All sessions verified'}
          </div>
        </div>
      </div>

      {/* Quality Trend Chart */}
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold text-gray-100 mb-4">Quality Trend</h3>
        <div className="space-y-2">
          {recentSessions.map((session) => (
            <div
              key={session.id}
              className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-gray-700/50 transition-colors"
            >
              <div className="flex-shrink-0 w-24 text-sm text-gray-600 dark:text-gray-400">
                Session {session.session_number}
              </div>
              <div className="flex-1">
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all ${
                      session.overall_rating >= 9
                        ? 'bg-green-500'
                        : session.overall_rating >= 7
                          ? 'bg-blue-500'
                          : session.overall_rating >= 5
                            ? 'bg-yellow-500'
                            : 'bg-red-500'
                    }`}
                    style={{ width: `${session.overall_rating * 10}%` }}
                  ></div>
                </div>
              </div>
              <div className="flex-shrink-0">
                <SessionQualityBadge
                  rating={session.overall_rating}
                  checkType={session.check_type}
                  size="sm"
                  showLabel={false}
                />
              </div>
              <div className="flex-shrink-0 w-32 text-xs text-gray-500 text-right">
                {session.playwright_count > 0
                  ? `${session.playwright_count} Browser Checks`
                  : 'No Browser Checks'}
              </div>
            </div>
          ))}
        </div>
        {sessions.length > 10 && (
          <div className="mt-4 text-sm text-gray-500 text-center">
            Showing last 10 sessions
          </div>
        )}
      </div>

      {/* Quality Legend */}
      <div className="flex justify-center">
        <QualityLegend />
      </div>

            </>
          )}
        </div>
      )}

      {/* Deep Reviews Tab */}
      {activeTab === 'deep-reviews' && (
        <div className="animate-fadeIn space-y-6">
          {deepReviews.length === 0 ? (
            <div className="text-center py-12">
              <div className="text-gray-500 text-4xl mb-3">🔍</div>
              <p className="text-gray-600 dark:text-gray-400">No deep reviews available yet</p>
              <p className="text-sm text-gray-500 mt-2">
                Deep reviews are AI-powered comprehensive analyses of coding sessions
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {deepReviews.map((review) => {
                const isExpanded = expandedSession === review.id;
                return (
                  <div key={review.id} className="border border-gray-700 rounded-lg bg-gray-800">
                    <div className="flex items-center justify-between p-4">
                      <button
                        onClick={() => setExpandedSession(isExpanded ? null : review.id)}
                        className="flex-1 flex items-center justify-between hover:bg-gray-700/30 transition-colors text-left pr-3 -ml-4 -my-4 pl-4 py-4 rounded-l-lg"
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-sm font-medium text-gray-300">
                            Session {review.session_number}
                          </span>
                          <SessionQualityBadge
                            rating={review.overall_rating}
                            checkType="deep"
                            size="sm"
                          />
                          {review.review_summary?.one_line && (
                            <span className="text-xs text-gray-400 max-w-md truncate">
                              {review.review_summary.one_line}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-xs text-gray-700 dark:text-gray-500">
                            {isExpanded ? 'Collapse' : 'Expand'}
                          </span>
                          <svg
                            className={`w-5 h-5 text-gray-400 transition-transform ${
                              isExpanded ? 'transform rotate-180' : ''
                            }`}
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M19 9l-7 7-7-7"
                            />
                          </svg>
                        </div>
                      </button>
                      <button
                        onClick={() => downloadReview(review.session_number, review.review_text)}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs text-blue-400 hover:text-blue-300 hover:bg-blue-500/10 rounded transition-colors"
                        title="Download review as markdown"
                      >
                        <Download className="w-4 h-4" />
                        <span>Download</span>
                      </button>
                    </div>
                    {isExpanded && (
                      <div className="border-t border-gray-700 p-4 bg-gray-900/30">
                        {/* Review Summary */}
                        {review.review_summary && (
                          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded">
                            <p className="text-sm text-gray-300">{review.review_summary.summary}</p>
                          </div>
                        )}

                        {/* Prompt Improvements Badge */}
                        {review.prompt_improvements && review.prompt_improvements.length > 0 && (
                          <div className="mb-4 flex items-center gap-2">
                            <span className="text-xs font-medium text-yellow-400">
                              ⚡ {review.prompt_improvements.length} Prompt Improvement{review.prompt_improvements.length > 1 ? 's' : ''}
                            </span>
                          </div>
                        )}

                        {/* Full Review Text */}
                        <div className="prose prose-invert prose-sm max-w-none">
                          <div
                            className="text-sm text-gray-300 whitespace-pre-wrap"
                            style={{
                              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                              lineHeight: '1.6'
                            }}
                          >
                            {review.review_text}
                          </div>
                        </div>

                        {/* Metadata Footer */}
                        <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-between text-xs text-gray-700 dark:text-gray-500">
                          <span>Model: {review.model}</span>
                          <span>Version: {review.review_version}</span>
                          <span>{new Date(review.created_at).toLocaleString()}</span>
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
    </div>
  );
}
