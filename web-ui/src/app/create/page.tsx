'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';

type Mode = 'upload' | 'generate';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function CreateProjectPage() {
  const router = useRouter();

  // Shared state
  const [mode, setMode] = useState<Mode>('upload');
  const [projectName, setProjectName] = useState('');
  const [sandboxType, setSandboxType] = useState<'docker' | 'local'>('docker');
  const [initializerModel, setInitializerModel] = useState('claude-opus-4-5-20251101');
  const [codingModel, setCodingModel] = useState('claude-sonnet-4-5-20250929');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [nameValidationError, setNameValidationError] = useState<string | null>(null);

  // Upload mode state
  const [specFiles, setSpecFiles] = useState<File[]>([]);

  // Generate mode state
  const [description, setDescription] = useState('');
  const [techPreferences, setTechPreferences] = useState('');
  const [contextFiles, setContextFiles] = useState<File[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationProgress, setGenerationProgress] = useState<string[]>([]);
  const [generatedSpec, setGeneratedSpec] = useState('');
  const [validationResult, setValidationResult] = useState<{
    valid: boolean;
    errors: string[];
    warnings: string[];
    sections: Array<{ name: string; use_when?: string; depends_on?: string }>;
  } | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [contextStrategy, setContextStrategy] = useState<any>(null); // Strategy from spec generation

  const progressRef = useRef<HTMLDivElement>(null);

  // ============================================================================
  // Upload Mode Handlers
  // ============================================================================

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    if (files.length > 0) {
      setSpecFiles(files);

      // Auto-fill project name from first file if empty
      if (!projectName) {
        const name = files[0].name
          .replace(/\.(txt|md)$/, '')
          .toLowerCase()
          .replace(/[^a-z0-9_-]+/g, '-')
          .replace(/^-+|-+$/g, '');
        setProjectName(name);
      }
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);

    if (files.length > 0) {
      const allowedExtensions = ['.txt', '.md', '.py', '.ts', '.js', '.tsx', '.jsx', '.json', '.yaml', '.yml', '.sql', '.sh', '.css', '.html'];
      const validFiles = files.filter(f =>
        allowedExtensions.some(ext => f.name.endsWith(ext))
      );

      if (validFiles.length > 0) {
        if (mode === 'upload') {
          setSpecFiles(prevFiles => {
            const newFiles = validFiles.filter(newFile =>
              !prevFiles.some(existingFile => existingFile.name === newFile.name)
            );
            return [...prevFiles, ...newFiles];
          });

          if (!projectName) {
            const primaryFile = validFiles.find(f => f.name.endsWith('.md') || f.name.endsWith('.txt')) || validFiles[0];
            const name = primaryFile.name
              .replace(/\.(txt|md|py|ts|js|tsx|jsx|json|yaml|yml|sql|sh|css|html)$/, '')
              .toLowerCase()
              .replace(/[^a-z0-9_-]+/g, '-')
              .replace(/^-+|-+$/g, '');
            setProjectName(name);
          }
        } else {
          // Generate mode - add to context files
          setContextFiles(prevFiles => {
            const newFiles = validFiles.filter(newFile =>
              !prevFiles.some(existingFile => existingFile.name === newFile.name)
            );
            return [...prevFiles, ...newFiles];
          });
        }
      }
    }
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault();
  }

  function removeSpecFile(index: number) {
    setSpecFiles(specFiles.filter((_, i) => i !== index));
  }

  function removeContextFile(index: number) {
    setContextFiles(contextFiles.filter((_, i) => i !== index));
  }

  // ============================================================================
  // Generate Mode Handlers
  // ============================================================================

  async function handleGenerateSpec() {
    if (!description.trim()) {
      setError('Please provide a project description');
      return;
    }

    setError(null);
    setIsGenerating(true);
    setGenerationProgress([]);
    setGeneratedSpec('');

    try {
      const formData = new FormData();
      formData.append('description', description);
      if (projectName) formData.append('project_name', projectName);
      if (techPreferences) formData.append('technology_preferences', techPreferences);
      contextFiles.forEach(file => formData.append('context_files', file));

      const token = localStorage.getItem('auth_token');
      const response = await fetch(`${API_BASE}/api/generate-spec`, {
        method: 'POST',
        body: formData,
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.type === 'spec_progress') {
                setGenerationProgress(prev => [...prev, data.content]);
                // Auto-scroll progress
                if (progressRef.current) {
                  progressRef.current.scrollTop = progressRef.current.scrollHeight;
                }
              } else if (data.type === 'spec_complete') {
                setGeneratedSpec(data.markdown || data.xml); // Handle both new markdown and legacy xml
                setValidationResult(null); // Reset validation when new spec generated
                if (data.project_name && !projectName) {
                  setProjectName(data.project_name);
                }
                // Capture context strategy
                if (data.context_strategy) {
                  setContextStrategy(data.context_strategy);
                  console.log('Context strategy:', data.context_strategy);
                }
              } else if (data.type === 'spec_error') {
                setError(data.error);
              }
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    } catch (err: any) {
      console.error('Failed to generate spec:', err);
      setError(err.message || 'Failed to generate specification');
    } finally {
      setIsGenerating(false);
    }
  }

  // ============================================================================
  // Validation Handler
  // ============================================================================

  async function handleValidateSpec() {
    if (!generatedSpec) return;

    setIsValidating(true);
    setError(null);

    try {
      const result = await api.validateSpec(generatedSpec);
      setValidationResult(result);

      if (!result.valid) {
        setError(`Specification has ${result.errors.length} error(s) that must be fixed`);
      }
    } catch (err: any) {
      console.error('Failed to validate spec:', err);
      setError(err.message || 'Failed to validate specification');
    } finally {
      setIsValidating(false);
    }
  }

  // ============================================================================
  // Submit Handler
  // ============================================================================

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);

    if (!projectName.trim()) {
      setError('Project name is required');
      return;
    }

    if (!/^[a-z0-9_-]+$/.test(projectName)) {
      setError('Project name must contain only lowercase letters, numbers, hyphens, and underscores');
      return;
    }

    // Check we have a spec
    if (mode === 'upload' && specFiles.length === 0) {
      setError('At least one specification file is required');
      return;
    }

    if (mode === 'generate' && !generatedSpec) {
      setError('Please generate a specification first');
      return;
    }

    // Validate generated spec before submission
    if (mode === 'generate' && generatedSpec) {
      setIsValidating(true);
      try {
        const result = await api.validateSpec(generatedSpec);
        setValidationResult(result);

        if (!result.valid) {
          setError(`Please fix ${result.errors.length} validation error(s) before creating the project`);
          setIsValidating(false);
          return;
        }
      } catch (err: any) {
        console.error('Validation failed:', err);
        // Allow creation to continue if validation endpoint fails
      } finally {
        setIsValidating(false);
      }
    }

    setIsCreating(true);

    try {
      let filesToUpload: File | File[];

      if (mode === 'generate') {
        // Convert generated spec string to File
        const specBlob = new Blob([generatedSpec], { type: 'text/plain' });
        const specFile = new File([specBlob], 'app_spec.txt', { type: 'text/plain' });
        filesToUpload = specFile;
      } else {
        filesToUpload = specFiles.length === 1 ? specFiles[0] : specFiles;
      }

      const result = await api.createProjectWithFile(
        projectName,
        filesToUpload,
        false,
        sandboxType,
        initializerModel,
        codingModel,
        contextFiles, // Pass optional context files
        contextStrategy // Pass context strategy from spec generation
      );

      router.push(`/projects/${result.id}`);
    } catch (err: any) {
      console.error('Failed to create project:', err);
      const errorMessage = err.response?.data?.detail || err.message;
      if (err.response?.status === 409) {
        setError(errorMessage || 'A project with this name already exists');
      } else {
        setError(errorMessage || 'Failed to create project. Check console for details.');
      }
      setIsCreating(false);
    }
  }

  // ============================================================================
  // Render
  // ============================================================================

  const isDisabled = isCreating || isGenerating;

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
          {mode === 'upload'
            ? 'Upload a specification file and configure your project settings'
            : 'Describe your project and let AI generate the specification'}
        </p>
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-2 mb-6">
        <button
          type="button"
          onClick={() => setMode('upload')}
          disabled={isDisabled}
          className={`flex-1 py-3 px-4 rounded-lg font-medium transition-colors ${mode === 'upload'
            ? 'bg-blue-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
            } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          Upload Spec File
        </button>
        <button
          type="button"
          onClick={() => setMode('generate')}
          disabled={isDisabled}
          className={`flex-1 py-3 px-4 rounded-lg font-medium transition-colors ${mode === 'generate'
            ? 'bg-purple-600 text-white'
            : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-300'
            } ${isDisabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          Generate with AI
        </button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Project Name */}
        <div>
          <label htmlFor="projectName" className="block text-sm font-medium text-gray-300 mb-2">
            Project Name {mode === 'upload' ? '*' : '(optional)'}
          </label>
          <input
            type="text"
            id="projectName"
            value={projectName}
            onChange={(e) => {
              const value = e.target.value;
              setProjectName(value);
              if (value && !/^[a-z0-9_-]+$/.test(value)) {
                setNameValidationError('Use only lowercase letters, numbers, hyphens, and underscores');
              } else {
                setNameValidationError(null);
              }
            }}
            placeholder="my-awesome-project"
            className={`w-full px-4 py-3 bg-gray-900 border rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:border-transparent ${nameValidationError ? 'border-red-500 focus:ring-red-500' : 'border-gray-800 focus:ring-blue-500'
              }`}
            disabled={isDisabled}
          />
          {nameValidationError ? (
            <p className="mt-1 text-sm text-red-400">{nameValidationError}</p>
          ) : (
            <p className="mt-1 text-sm text-gray-500">
              {mode === 'generate' ? 'Leave empty to auto-generate from description' : 'Use lowercase letters, numbers, and hyphens'}
            </p>
          )}
        </div>

        {/* Upload Mode: Spec File Upload */}
        {mode === 'upload' && (
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
                    <div className="text-sm text-gray-500">
                      {(specFiles.reduce((sum, f) => sum + f.size, 0) / 1024).toFixed(1)} KB total
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSpecFiles([])}
                    className="text-sm text-blue-400 hover:text-blue-300"
                    disabled={isDisabled}
                  >
                    Remove all files
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="text-4xl text-gray-600">📁</div>
                  <div>
                    <label htmlFor="fileInput" className="text-blue-400 hover:text-blue-300 cursor-pointer">
                      Click to upload
                    </label>
                    <span className="text-gray-500"> or drag and drop</span>
                  </div>
                  <div className="text-sm text-gray-500">
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
                disabled={isDisabled}
              />
            </div>

            {/* Selected Files List */}
            {specFiles.length > 0 && (
              <div className="mt-3 space-y-2">
                <div className="text-sm font-medium text-gray-400">Selected files:</div>
                {specFiles.map((file, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-900 rounded-lg border border-gray-800">
                    <div className="flex items-center gap-3">
                      <span className="text-2xl">📄</span>
                      <div>
                        <div className="text-sm text-gray-300">{file.name}</div>
                        <div className="text-xs text-gray-500">{(file.size / 1024).toFixed(1)} KB</div>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeSpecFile(index)}
                      className="text-red-400 hover:text-red-300 text-sm px-3 py-1"
                      disabled={isDisabled}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Generate Mode: Description and Context */}
        {mode === 'generate' && (
          <>
            {/* Description */}
            <div>
              <label htmlFor="description" className="block text-sm font-medium text-gray-300 mb-2">
                Describe Your Project *
              </label>
              <textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Build a task management application that allows teams to create projects, assign tasks to members, track progress with kanban boards, and set deadlines with notifications..."
                rows={6}
                className="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-none"
                disabled={isDisabled}
              />
              <p className="mt-1 text-sm text-gray-500">
                Be specific about features, user types, and any technical requirements
              </p>
            </div>

            {/* Technology Preferences */}
            <div>
              <label htmlFor="techPrefs" className="block text-sm font-medium text-gray-300 mb-2">
                Technology Preferences (optional)
              </label>
              <input
                type="text"
                id="techPrefs"
                value={techPreferences}
                onChange={(e) => setTechPreferences(e.target.value)}
                placeholder="React, Node.js, PostgreSQL, Tailwind CSS..."
                className="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                disabled={isDisabled}
              />
              <p className="mt-1 text-sm text-gray-500">
                Leave empty for AI to recommend technologies based on your requirements
              </p>
            </div>

            {/* Context Files */}
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Context Files (optional)
              </label>
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                className="border-2 border-dashed border-gray-700 rounded-lg p-6 text-center hover:border-gray-600 transition-colors cursor-pointer"
              >
                {contextFiles.length > 0 ? (
                  <div className="text-sm text-gray-400">
                    {contextFiles.length} file{contextFiles.length > 1 ? 's' : ''} added for context
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div className="text-sm text-gray-500">
                      Drop code examples, schemas, or existing specs to provide context
                    </div>
                    <div className="text-xs text-gray-600">
                      Supported: .txt, .md, .py, .ts, .js, .tsx, .jsx, .json, .yaml, .yml, .sql, .sh, .css, .html
                    </div>
                  </div>
                )}
              </div>
              {contextFiles.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {contextFiles.map((file, index) => (
                    <span key={index} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-800 rounded text-sm text-gray-300">
                      {file.name}
                      <button
                        type="button"
                        onClick={() => removeContextFile(index)}
                        className="text-gray-500 hover:text-red-400"
                        disabled={isDisabled}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Generate Button */}
            {!generatedSpec && (
              <button
                type="button"
                onClick={handleGenerateSpec}
                disabled={isGenerating || !description.trim()}
                className="w-full py-3 px-4 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-800 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
              >
                {isGenerating ? 'Generating Specification...' : 'Generate Specification'}
              </button>
            )}

            {/* Generation Progress */}
            {/* Progress Display */}
            {(isGenerating || generationProgress.length > 0) && !generatedSpec && (
              <div className="p-4 bg-gray-900 border border-gray-800 rounded-lg">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-sm font-medium text-gray-300">Generation Progress</div>
                  <div className="text-xs text-gray-500">Usually takes 1-2 minutes</div>
                </div>

                {/* Current Status - Claude Code style */}
                {isGenerating && generationProgress.length > 0 && (
                  <div className="mb-3 p-3 bg-purple-900/20 border border-purple-800/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <div className="relative">
                        <span className="inline-block w-2 h-2 bg-purple-500 rounded-full animate-pulse"></span>
                        <span className="absolute top-0 left-0 w-2 h-2 bg-purple-500 rounded-full animate-ping opacity-75"></span>
                      </div>
                      <span className="text-purple-300 font-medium">
                        {generationProgress[generationProgress.length - 1]}
                      </span>
                    </div>
                  </div>
                )}

                {/* Progress History */}
                <div
                  ref={progressRef}
                  className="max-h-24 overflow-y-auto text-sm text-gray-500 space-y-1"
                >
                  {generationProgress.slice(0, -1).map((msg, i) => (
                    <div key={i} className="flex items-start gap-2 opacity-60">
                      <span className="text-gray-600">✓</span>
                      <span>{msg}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Generated Spec Editor */}
            {generatedSpec && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-300">
                    Generated Specification (editable)
                  </label>
                  <button
                    type="button"
                    onClick={() => {
                      setGeneratedSpec('');
                      setGenerationProgress([]);
                    }}
                    className="text-sm text-gray-400 hover:text-gray-300"
                    disabled={isDisabled}
                  >
                    Regenerate
                  </button>
                </div>
                <textarea
                  value={generatedSpec}
                  onChange={(e) => {
                    setGeneratedSpec(e.target.value);
                    setValidationResult(null); // Reset validation when content changes
                  }}
                  rows={15}
                  className="w-full px-4 py-3 bg-gray-900 border border-gray-800 rounded-lg text-gray-100 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent resize-y"
                  disabled={isDisabled}
                />
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-sm text-gray-500">
                    Review and edit the specification before creating the project
                  </p>
                  <button
                    type="button"
                    onClick={handleValidateSpec}
                    disabled={isValidating || isDisabled}
                    className="px-3 py-1 bg-purple-700 hover:bg-purple-600 disabled:bg-purple-900 disabled:cursor-not-allowed text-white text-sm rounded transition-colors"
                  >
                    {isValidating ? 'Validating...' : 'Validate'}
                  </button>
                </div>

                {/* Validation Results */}
                {validationResult && (
                  <div className={`mt-3 p-3 rounded-lg border ${validationResult.valid
                    ? 'bg-green-950/30 border-green-900/50'
                    : 'bg-red-950/30 border-red-900/50'
                    }`}>
                    {validationResult.valid ? (
                      <div className="text-green-400 text-sm">
                        ✅ Specification is valid ({validationResult.sections.length} sections found)
                      </div>
                    ) : (
                      <div>
                        <div className="text-red-400 text-sm font-medium mb-2">
                          ❌ {validationResult.errors.length} validation error(s):
                        </div>
                        <ul className="text-red-300 text-sm space-y-1">
                          {validationResult.errors.map((error, i) => (
                            <li key={i}>• {error}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {validationResult.warnings.length > 0 && (
                      <div className="mt-2">
                        <div className="text-yellow-400 text-sm font-medium mb-1">
                          ⚠️ {validationResult.warnings.length} warning(s):
                        </div>
                        <ul className="text-yellow-300 text-sm space-y-1">
                          {validationResult.warnings.slice(0, 5).map((warning, i) => (
                            <li key={i}>• {warning}</li>
                          ))}
                          {validationResult.warnings.length > 5 && (
                            <li className="text-gray-400">...and {validationResult.warnings.length - 5} more</li>
                          )}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}

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
            disabled={isDisabled}
          >
            <option value="docker">Docker (isolated container, recommended)</option>
            <option value="local">Local (direct filesystem access, faster)</option>
          </select>
          <p className="mt-1 text-sm text-gray-500">
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
              <div>
                <label htmlFor="initModel" className="block text-sm font-medium text-gray-300 mb-2">
                  Initializer Model
                </label>
                <select
                  id="initModel"
                  value={initializerModel}
                  onChange={(e) => setInitializerModel(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isDisabled}
                >
                  <option value="claude-opus-4-5-20251101">Claude Opus (better planning)</option>
                  <option value="claude-sonnet-4-5-20250929">Claude Sonnet (faster)</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">Model used for creating the project roadmap</p>
              </div>

              <div>
                <label htmlFor="codeModel" className="block text-sm font-medium text-gray-300 mb-2">
                  Coding Model
                </label>
                <select
                  id="codeModel"
                  value={codingModel}
                  onChange={(e) => setCodingModel(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-950 border border-gray-800 rounded-lg text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={isDisabled}
                >
                  <option value="claude-sonnet-4-5-20250929">Claude Sonnet (recommended)</option>
                  <option value="claude-opus-4-5-20251101">Claude Opus (more capable)</option>
                </select>
                <p className="mt-1 text-xs text-gray-500">Model used for implementation sessions</p>
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
            disabled={
              isDisabled ||
              !projectName ||
              !!nameValidationError ||
              (mode === 'upload' && specFiles.length === 0) ||
              (mode === 'generate' && !generatedSpec)
            }
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
