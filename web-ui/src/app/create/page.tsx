'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

export default function CreateProjectPage() {
  const router = useRouter();
  const [projectName, setProjectName] = useState('');
  const [specFiles, setSpecFiles] = useState<File[]>([]);
  const [sandboxType, setSandboxType] = useState<'docker' | 'local'>('docker');
  const [initializerModel, setInitializerModel] = useState('claude-opus-4-5-20251101');
  const [codingModel, setCodingModel] = useState('claude-sonnet-4-5-20250929');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [nameValidationError, setNameValidationError] = useState<string | null>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setSpecFiles(files);

      // Auto-fill project name from first file if empty
      if (!projectName) {
        const name = files[0].name
          .replace(/\.(txt|md)$/, '')
          .toLowerCase()
          .replace(/[^a-z0-9_-]+/g, '-')  // Replace invalid chars with hyphens
          .replace(/^-+|-+$/g, '');        // Remove leading/trailing hyphens
        setProjectName(name);
      }
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);

    if (files.length > 0) {
      // Filter to allowed file types (spec files + code examples)
      const allowedExtensions = ['.txt', '.md', '.py', '.ts', '.js', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.sql', '.sh', '.css', '.html'];
      const validFiles = files.filter(f =>
        allowedExtensions.some(ext => f.name.endsWith(ext))
      );

      if (validFiles.length > 0) {
        // Append to existing files instead of replacing
        setSpecFiles(prevFiles => {
          // Filter out duplicates (same filename)
          const newFiles = validFiles.filter(newFile =>
            !prevFiles.some(existingFile => existingFile.name === newFile.name)
          );
          return [...prevFiles, ...newFiles];
        });

        // Auto-fill project name from first .md or .txt file if empty
        if (!projectName) {
          const primaryFile = validFiles.find(f => f.name.endsWith('.md') || f.name.endsWith('.txt')) || validFiles[0];
          const name = primaryFile.name
            .replace(/\.(txt|md|py|ts|js|tsx|jsx|json|yaml|yml|sql|sh|css|html)$/, '')
            .toLowerCase()
            .replace(/[^a-z0-9_-]+/g, '-')  // Replace invalid chars with hyphens
            .replace(/^-+|-+$/g, '');        // Remove leading/trailing hyphens
          setProjectName(name);
        }
      }
    }
  }

  function removeFile(index: number) {
    setSpecFiles(specFiles.filter((_, i) => i !== index));
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!projectName.trim()) {
      setError('Project name is required');
      return;
    }

    // Validate project name format
    if (!/^[a-z0-9_-]+$/.test(projectName)) {
      setError('Project name must contain only lowercase letters, numbers, hyphens, and underscores (no spaces or special characters)');
      return;
    }

    if (specFiles.length === 0) {
      setError('At least one specification file is required');
      return;
    }

    setIsCreating(true);

    try {
      // Create project with spec file(s) upload
      const result = await api.createProjectWithFile(
        projectName,
        specFiles.length === 1 ? specFiles[0] : specFiles,
        false,
        sandboxType,
        initializerModel,
        codingModel
      );

      // Navigate to the new project immediately (user will click Initialize button)
      router.push(`/projects/${result.id}`);
    } catch (err: any) {
      console.error('Failed to create project:', err);
      // Use the detailed error message from the server if available
      const errorMessage = err.response?.data?.detail || err.message;
      if (err.response?.status === 409) {
        setError(errorMessage || 'A project with this name already exists');
      } else {
        setError(errorMessage || 'Failed to create project. Check console for details.');
      }
      setIsCreating(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-2 text-sm">
          <Link href="/" className="text-gray-500 hover:text-gray-300">
            Projects
          </Link>
          <span className="text-gray-600">/</span>
          <span className="text-gray-100">Create</span>
        </div>
        <h1 className="text-4xl font-bold mb-2">Create New Project</h1>
        <p className="text-gray-600 dark:text-gray-400">
          Upload a specification file and configure your project settings
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Name */}
        <div>
          <label htmlFor="projectName" className="block text-sm font-medium text-gray-300 mb-2">
            Project Name *
          </label>
          <input
            type="text"
            id="projectName"
            value={projectName}
            onChange={(e) => {
              const value = e.target.value;
              setProjectName(value);
              // Validate in real-time
              if (value && !/^[a-z0-9_-]+$/.test(value)) {
                setNameValidationError('Project name must contain only lowercase letters, numbers, hyphens, and underscores (no spaces)');
              } else {
                setNameValidationError(null);
              }
            }}
            placeholder="my-awesome-project"
            className={`w-full px-4 py-3 bg-gray-900 border rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:border-transparent ${
              nameValidationError ? 'border-red-500 focus:ring-red-500' : 'border-gray-800 focus:ring-blue-500'
            }`}
            disabled={isCreating}
          />
          {nameValidationError ? (
            <p className="mt-1 text-sm text-red-400">
              {nameValidationError}
            </p>
          ) : (
            <p className="mt-1 text-sm text-gray-700 dark:text-gray-500">
              Use lowercase letters, numbers, and hyphens
            </p>
          )}
        </div>

        {/* Spec File Upload */}
        <div>
          <label className="block text-sm font-medium text-gray-300 mb-2">
            Specification File(s) *
          </label>
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className="border-2 border-dashed border-gray-700 rounded-lg p-8 text-center hover:border-gray-600 transition-colors cursor-pointer"
          >
            {specFiles.length > 0 ? (
              <div className="space-y-3">
                <div className="text-4xl">📄</div>
                <div>
                  <div className="text-gray-300 font-medium">
                    {specFiles.length} file{specFiles.length > 1 ? 's' : ''} selected
                  </div>
                  <div className="text-sm text-gray-700 dark:text-gray-500">
                    {(specFiles.reduce((sum, f) => sum + f.size, 0) / 1024).toFixed(1)} KB total
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setSpecFiles([])}
                  className="text-sm text-blue-400 hover:text-blue-300"
                  disabled={isCreating}
                >
                  Remove all files
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="text-4xl text-gray-600">📁</div>
                <div>
                  <label
                    htmlFor="fileInput"
                    className="text-blue-400 hover:text-blue-300 cursor-pointer"
                  >
                    Click to upload
                  </label>
                  <span className="text-gray-700 dark:text-gray-500"> or drag and drop</span>
                </div>
                <div className="text-sm text-gray-700 dark:text-gray-500">
                  Specs (.txt, .md) + Code examples (.py, .ts, .js, etc.)
                </div>
              </div>
            )}
            <input
              type="file"
              id="fileInput"
              onChange={handleFileChange}
              accept=".txt,.md,.py,.ts,.js,.tsx,.jsx,.json,.yaml,.yml,.sql,.sh,.css,.html"
              multiple
              className="hidden"
              disabled={isCreating}
            />
          </div>

          {/* Selected Files List */}
          {specFiles.length > 0 && (
            <div className="mt-3 space-y-2">
              <div className="text-sm font-medium text-gray-600 dark:text-gray-400">
                Selected files:
              </div>
              {specFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between p-3 bg-gray-900 rounded-lg border border-gray-800"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl">📄</span>
                    <div>
                      <div className="text-sm text-gray-300">{file.name}</div>
                      <div className="text-xs text-gray-700 dark:text-gray-500">
                        {(file.size / 1024).toFixed(1)} KB
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeFile(index)}
                    className="text-red-400 hover:text-red-300 text-sm px-3 py-1"
                    disabled={isCreating}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Helpful Hint for Multiple Files */}
          {specFiles.length > 1 && (
            <div className="mt-3 p-3 bg-blue-950/30 border border-blue-900/50 rounded-lg">
              <div className="flex gap-2">
                <span className="text-blue-400 flex-shrink-0">💡</span>
                <div className="text-sm text-blue-300">
                  <strong>Tip:</strong> Name your main spec file <code className="bg-blue-900/30 px-1 rounded">main.md</code> or <code className="bg-blue-900/30 px-1 rounded">spec.md</code>. The agent will read it first, then load other files (including code examples) as needed for reference.
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Sandbox Type */}
        <div>
          <label htmlFor="sandboxType" className="block text-sm font-medium text-gray-300 mb-2">
            Sandbox Type *
          </label>
          <select
            id="sandboxType"
            value={sandboxType}
            onChange={(e) => setSandboxType(e.target.value as 'docker' | 'local')}
            className="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            disabled={isCreating}
          >
            <option value="docker">Docker (isolated container, recommended)</option>
            <option value="local">Local (direct filesystem access, faster)</option>
          </select>
          <p className="mt-1 text-sm text-gray-700 dark:text-gray-500">
            Docker provides isolation but may be slower. Local is faster but runs on the host system.
          </p>
        </div>

        {/* Advanced Options */}
        <div>
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="flex items-center gap-2 text-sm text-gray-400 hover:text-gray-300 transition-colors"
          >
            <span>{showAdvanced ? '▼' : '▶'}</span>
            <span>Advanced Options</span>
          </button>

          {showAdvanced && (
            <div className="mt-4 space-y-4 p-4 bg-gray-900 border border-gray-800 rounded-lg">
              {/* Initializer Model */}
              <div>
                <label htmlFor="initModel" className="block text-sm font-medium text-gray-300 mb-2">
                  Initializer Model
                </label>
                <select
                  id="initModel"
                  value={initializerModel}
                  onChange={(e) => setInitializerModel(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isCreating}
                >
                  <option value="claude-opus-4-5-20251101">Claude Opus (better planning)</option>
                  <option value="claude-sonnet-4-5-20250929">Claude Sonnet (faster)</option>
                </select>
                <p className="mt-1 text-xs text-gray-700 dark:text-gray-500">
                  Model used for creating the project roadmap
                </p>
              </div>

              {/* Coding Model */}
              <div>
                <label htmlFor="codeModel" className="block text-sm font-medium text-gray-300 mb-2">
                  Coding Model
                </label>
                <select
                  id="codeModel"
                  value={codingModel}
                  onChange={(e) => setCodingModel(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isCreating}
                >
                  <option value="claude-sonnet-4-5-20250929">Claude Sonnet (recommended)</option>
                  <option value="claude-opus-4-5-20251101">Claude Opus (more capable)</option>
                </select>
                <p className="mt-1 text-xs text-gray-700 dark:text-gray-500">
                  Model used for implementation sessions
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-950/30 border border-red-900/50 rounded-lg">
            <div className="text-red-400 text-sm">{error}</div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between pt-4">
          <Link
            href="/"
            className="px-6 py-3 text-gray-400 hover:text-gray-300 transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={isCreating || !projectName || specFiles.length === 0 || !!nameValidationError}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors font-medium"
          >
            {isCreating ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </form>

      {/* Info Note */}
      <div className="mt-8 bg-blue-950/20 border border-blue-900/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <div className="text-blue-500 text-xl">💡</div>
          <div>
            <div className="font-semibold text-blue-400 mb-1">What happens next?</div>
            <div className="text-sm text-gray-400 space-y-1">
              <p>1. Project directory is created in generations/</p>
              <p>2. Your spec file is saved as app_spec.txt</p>
              <p>3. Initialization session starts automatically</p>
              <p>4. The initializer creates epics, tasks, and tests</p>
              <p>5. Then coding sessions implement your application</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
