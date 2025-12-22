'use client';

import { useState, useEffect } from 'react';
import { X, Settings as SettingsIcon, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import type { ProjectSettings, UpdateSettingsRequest } from '@/lib/types';

interface ProjectSettingsFormProps {
  projectId: string;
  onSaved?: () => void;
}

interface ProjectSettingsModalProps {
  projectId: string;
  onClose: () => void;
  onSaved?: () => void;
}

export function ProjectSettingsModal({ projectId, onClose, onSaved }: ProjectSettingsModalProps) {
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [codingModel, setCodingModel] = useState('claude-sonnet-4-5-20250929');
  const [maxIterations, setMaxIterations] = useState<string>('0'); // 0 = unlimited

  useEffect(() => {
    loadSettings();
  }, [projectId]);

  async function loadSettings() {
    try {
      const data = await api.getSettings(projectId);
      setSettings(data);
      setCodingModel(data.coding_model);
      // Convert null to 0 (unlimited), keep actual values
      setMaxIterations(data.max_iterations?.toString() || '0');
      setError(null);
    } catch (err: any) {
      console.error('Failed to load settings:', err);
      setError(err.response?.data?.detail || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);

    try {
      const iterations = parseInt(maxIterations, 10);

      // Validate: must be 0 or 2+
      if (isNaN(iterations) || iterations < 0) {
        setError('Max sessions must be 0 or a positive number.');
        setSaving(false);
        return;
      }

      const updates: UpdateSettingsRequest = {
        coding_model: codingModel,
        // Convert 0 to null (unlimited), otherwise use the number
        max_iterations: iterations === 0 ? null : iterations,
      };

      await api.updateSettings(projectId, updates);
      onSaved?.();
      onClose();
    } catch (err: any) {
      console.error('Failed to save settings:', err);
      setError(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-900 border border-gray-700 rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 bg-gray-900 border-b border-gray-700 p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <SettingsIcon className="w-6 h-6 text-blue-400" />
            <h2 className="text-2xl font-bold text-gray-100">Project Settings</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 transition-colors"
            disabled={saving}
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
            </div>
          )}

          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
              <p className="text-sm text-red-400">{error}</p>
            </div>
          )}

          {!loading && settings && (
            <>
              {/* Max Sessions */}
              <div>
                <label className="block text-gray-100 font-medium mb-2">Max Sessions</label>
                <input
                  type="number"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  placeholder="0 = Unlimited"
                  min="0"
                />
                <p className="text-sm text-gray-400 mt-1">
                  Maximum number of sessions to run automatically. 0 = unlimited (auto-continue), 1 = run once and stop, 2+ = run N sessions then stop.
                </p>
              </div>

              {/* Coding Model */}
              <div>
                <label className="block text-gray-100 font-medium mb-2">Coding Model</label>
                <input
                  type="text"
                  value={codingModel}
                  onChange={(e) => setCodingModel(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
                  placeholder="claude-sonnet-4-5-20250929"
                />
                <p className="text-sm text-gray-400 mt-1">
                  Model used for coding sessions (Session 2+). Sonnet is recommended for speed and cost.
                </p>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-900 border-t border-gray-700 p-6 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 text-gray-100 rounded-lg transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading || saving}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium flex items-center gap-2"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * ProjectSettingsForm - Inline form for project settings (no modal wrapper)
 * Use this when embedding the form directly in a panel/page
 */
export function ProjectSettingsForm({ projectId, onSaved }: ProjectSettingsFormProps) {
  const [settings, setSettings] = useState<ProjectSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [codingModel, setCodingModel] = useState('claude-sonnet-4-5-20250929');
  const [maxIterations, setMaxIterations] = useState<string>('0'); // 0 = unlimited

  useEffect(() => {
    loadSettings();
  }, [projectId]);

  async function loadSettings() {
    try {
      const data = await api.getSettings(projectId);
      setSettings(data);
      setCodingModel(data.coding_model);
      // Convert null to 0 (unlimited), keep actual values
      setMaxIterations(data.max_iterations?.toString() || '0');
      setError(null);
    } catch (err: any) {
      console.error('Failed to load settings:', err);
      setError(err.response?.data?.detail || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);

    try {
      const iterations = parseInt(maxIterations, 10);

      // Validate: must be 0 or positive
      if (isNaN(iterations) || iterations < 0) {
        setError('Max sessions must be 0 or a positive number.');
        setSaving(false);
        return;
      }

      const updates: UpdateSettingsRequest = {
        coding_model: codingModel,
        // Convert 0 to null (unlimited), otherwise use the number
        max_iterations: iterations === 0 ? null : iterations,
      };

      await api.updateSettings(projectId, updates);
      toast.success('Settings saved successfully');
      onSaved?.();
    } catch (err: any) {
      console.error('Failed to save settings:', err);
      const errorMsg = err.response?.data?.detail || 'Failed to save settings';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {settings && (
        <>
          {/* Max Sessions */}
          <div>
            <label className="block text-gray-100 font-medium mb-2">Max Sessions</label>
            <input
              type="number"
              value={maxIterations}
              onChange={(e) => setMaxIterations(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="0 = Unlimited"
              min="0"
            />
            <p className="text-sm text-gray-400 mt-1">
              Maximum number of sessions to run automatically. 0 = unlimited (auto-continue), 1 = run once and stop, 2+ = run N sessions then stop.
            </p>
          </div>

          {/* Coding Model */}
          <div>
            <label className="block text-gray-100 font-medium mb-2">Coding Model</label>
            <input
              type="text"
              value={codingModel}
              onChange={(e) => setCodingModel(e.target.value)}
              className="w-full px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-gray-100 focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm"
              placeholder="claude-sonnet-4-5-20250929"
            />
            <p className="text-sm text-gray-400 mt-1">
              Model used for coding sessions (Session 2+). Sonnet is recommended for speed and cost.
            </p>
          </div>

          {/* Save Button */}
          <div className="flex items-center justify-end pt-4 border-t border-gray-800">
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium flex items-center gap-2"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
