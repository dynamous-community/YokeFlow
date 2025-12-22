'use client';

import { useState, useEffect } from 'react';
import { Check, X, AlertCircle, FileText } from 'lucide-react';

interface EnvVariable {
  key: string;
  value: string;
  comment?: string;
  required?: boolean;
}

interface EnvEditorProps {
  projectId: string;
  onSave?: () => void;
  onCancel?: () => void;
}

export function EnvEditor({ projectId, onSave, onCancel }: EnvEditorProps) {
  const [envVars, setEnvVars] = useState<EnvVariable[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasEnvExample, setHasEnvExample] = useState(false);

  useEffect(() => {
    loadEnvFiles();
  }, [projectId]);

  async function loadEnvFiles() {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/projects/${projectId}/env`);

      if (response.ok) {
        const data = await response.json();
        setHasEnvExample(data.has_env_example);
        setEnvVars(data.variables || []);
      } else if (response.status === 404) {
        setHasEnvExample(false);
        setEnvVars([]);
      }
      setError(null);
    } catch (err) {
      console.error('Failed to load environment variables:', err);
      setError('Failed to load environment configuration');
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/projects/${projectId}/env`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ variables: envVars }),
      });

      if (!response.ok) {
        throw new Error('Failed to save environment variables');
      }

      setError(null);
      onSave?.();
    } catch (err) {
      console.error('Failed to save environment variables:', err);
      setError('Failed to save environment configuration');
    } finally {
      setSaving(false);
    }
  }

  function handleChange(index: number, value: string) {
    const updated = [...envVars];
    updated[index].value = value;
    setEnvVars(updated);
  }

  const requiredVars = envVars.filter(v => v.required);
  const allRequiredFilled = requiredVars.every(v => v.value && v.value.trim() !== '');

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  // Allow editing even if .env.example doesn't exist
  // User might need to add/edit variables manually

  if (envVars.length === 0) {
    return (
      <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-6">
        <div className="flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-yellow-900 dark:text-yellow-100 mb-1">
              {hasEnvExample ? 'No Variables in .env.example' : 'No .env.example File Found'}
            </h3>
            <p className="text-sm text-yellow-700 dark:text-yellow-300 mb-3">
              {hasEnvExample
                ? 'The .env.example file exists but contains no variables. You can manually edit the .env file if needed.'
                : 'This project does not have a .env.example file. If you need to configure environment variables (like API keys), you can manually edit the .env file.'}
            </p>
            <p className="text-xs text-yellow-600 dark:text-yellow-400">
              Path: <code className="bg-yellow-100 dark:bg-yellow-900 px-1 rounded">generations/{projectId}/.env</code>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 dark:text-red-400 mt-0.5" />
            <div className="flex-1">
              <h4 className="font-semibold text-red-900 dark:text-red-100 mb-1">Error</h4>
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg">
        <div className="border-b border-gray-200 dark:border-gray-800 px-6 py-4">
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">
            Environment Variables
          </h3>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
            Configure the required environment variables for this project. Variables marked with * are required.
          </p>
        </div>

        <div className="p-6 space-y-4">
          {envVars.map((envVar, index) => (
            <div key={envVar.key} className="space-y-2">
              <label className="block">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-medium text-gray-900 dark:text-gray-100">
                    {envVar.key}
                    {envVar.required && <span className="text-red-500">*</span>}
                  </span>
                </div>
                {envVar.comment && (
                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                    {envVar.comment}
                  </p>
                )}
                <input
                  type="text"
                  value={envVar.value}
                  onChange={(e) => handleChange(index, e.target.value)}
                  placeholder={envVar.required ? 'Required' : 'Optional'}
                  className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-700 rounded-lg text-gray-900 dark:text-gray-100 placeholder-gray-500 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </label>
            </div>
          ))}
        </div>
      </div>

      {requiredVars.length > 0 && !allRequiredFilled && (
        <div className="bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
            <p className="text-sm text-yellow-700 dark:text-yellow-300">
              Please fill in all required environment variables before starting coding sessions.
            </p>
          </div>
        </div>
      )}

      <div className="flex items-center justify-end gap-3">
        {onCancel && (
          <button
            onClick={onCancel}
            className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors"
          >
            Cancel
          </button>
        )}
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium flex items-center gap-2"
        >
          {saving ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              Saving...
            </>
          ) : (
            <>
              <Check className="w-4 h-4" />
              Save Configuration
            </>
          )}
        </button>
      </div>
    </div>
  );
}
