/**
 * API Client for the YokeFlow FastAPI backend
 */

import axios, { AxiosInstance } from 'axios';
import type {
  Project,
  Progress,
  Session,
  SessionConfig,
  CreateProjectRequest,
  CreateProjectResponse,
  StartSessionResponse,
  StopSessionRequest,
  StopSessionResponse,
  HealthResponse,
  InfoResponse,
  Epic,
  EpicWithTasks,
  Task,
  TaskWithTests,
  ProjectSettings,
  UpdateSettingsRequest,
  ResetProjectResponse,
  PromptAnalysisSummary,
  PromptAnalysisDetail,
  PromptProposal,
  TriggerAnalysisRequest,
  TriggerAnalysisResponse,
  UpdateProposalRequest,
  ApplyProposalResponse,
  ImprovementMetrics,
  ProjectReviewStats,
  TriggerBulkReviewsRequest,
  TriggerBulkReviewsResponse,
  Screenshot,
  ContainerStatus,
  ContainerActionResponse,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string = API_BASE) {
    this.client = axios.create({
      baseURL,
      timeout: 60000, // Increased to 60s for slow operations
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add request interceptor to include JWT token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Add response interceptor to handle 401 errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          const token = localStorage.getItem('auth_token');

          // Don't redirect if in dev mode (no real token)
          if (token === 'dev-mode') {
            return Promise.reject(error);
          }

          // Clear token and redirect to login
          localStorage.removeItem('auth_token');
          const currentPath = window.location.pathname;
          if (currentPath !== '/login') {
            window.location.href = `/login?returnUrl=${encodeURIComponent(currentPath)}`;
          }
        }
        return Promise.reject(error);
      }
    );
  }

  // Health & Info
  async health(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/api/health');
    return response.data;
  }

  async info(): Promise<InfoResponse> {
    const response = await this.client.get<InfoResponse>('/api/info');
    return response.data;
  }

  // Projects
  async listProjects(): Promise<Project[]> {
    const response = await this.client.get<Project[]>('/api/projects');
    return response.data;
  }

  async getProject(projectId: string): Promise<Project> {
    const response = await this.client.get<Project>(`/api/projects/${projectId}`);
    return response.data;
  }

  async createProject(data: CreateProjectRequest): Promise<CreateProjectResponse> {
    const response = await this.client.post<CreateProjectResponse>('/api/projects', data);
    return response.data;
  }

  async createProjectWithFile(
    name: string,
    specFiles: File | File[],
    force: boolean = false,
    sandboxType: 'docker' | 'local' = 'docker',
    initializerModel?: string,
    codingModel?: string,
  ): Promise<CreateProjectResponse> {
    const formData = new FormData();
    formData.append('name', name);

    // Handle single or multiple files
    const files = Array.isArray(specFiles) ? specFiles : [specFiles];
    files.forEach(file => {
      formData.append('spec_files', file);
    });

    formData.append('force', force.toString());
    formData.append('sandbox_type', sandboxType);
    if (initializerModel) formData.append('initializer_model', initializerModel);
    if (codingModel) formData.append('coding_model', codingModel);

    const response = await this.client.post<CreateProjectResponse>('/api/projects', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  }

  async deleteProject(projectId: string): Promise<void> {
    await this.client.delete(`/api/projects/${projectId}`);
  }

  // Container Management

  async getContainerStatus(projectId: string): Promise<ContainerStatus> {
    const response = await this.client.get<ContainerStatus>(`/api/projects/${projectId}/container/status`);
    return response.data;
  }

  async startContainer(projectId: string): Promise<ContainerActionResponse> {
    const response = await this.client.post<ContainerActionResponse>(`/api/projects/${projectId}/container/start`);
    return response.data;
  }

  async stopContainer(projectId: string): Promise<ContainerActionResponse> {
    const response = await this.client.post<ContainerActionResponse>(`/api/projects/${projectId}/container/stop`);
    return response.data;
  }

  async deleteContainer(projectId: string): Promise<ContainerActionResponse> {
    const response = await this.client.delete<ContainerActionResponse>(`/api/projects/${projectId}/container`);
    return response.data;
  }

  // Progress and Settings

  async getProgress(projectId: string): Promise<Progress> {
    const response = await this.client.get<Progress>(`/api/projects/${projectId}/progress`);
    return response.data;
  }

  async getSettings(projectId: string): Promise<ProjectSettings> {
    const response = await this.client.get<ProjectSettings>(`/api/projects/${projectId}/settings`);
    return response.data;
  }

  async updateSettings(projectId: string, settings: UpdateSettingsRequest): Promise<ProjectSettings> {
    const response = await this.client.put<ProjectSettings>(
      `/api/projects/${projectId}/settings`,
      settings
    );
    return response.data;
  }

  async renameProject(projectId: string, name: string): Promise<Project> {
    const response = await this.client.patch<Project>(
      `/api/projects/${projectId}`,
      { name }
    );
    return response.data;
  }

  async resetProject(projectId: string): Promise<ResetProjectResponse> {
    const response = await this.client.post<ResetProjectResponse>(
      `/api/projects/${projectId}/reset`
    );
    return response.data;
  }

  // Sessions (NEW Phase 1 endpoints)
  async initializeProject(projectId: string, initializerModel?: string): Promise<StartSessionResponse> {
    const response = await this.client.post<StartSessionResponse>(
      `/api/projects/${projectId}/initialize`,
      initializerModel ? { initializer_model: initializerModel } : {}
    );
    return response.data;
  }

  async startCodingSessions(
    projectId: string,
    codingModel?: string,
    maxIterations?: number | null
  ): Promise<StartSessionResponse> {
    const response = await this.client.post<StartSessionResponse>(
      `/api/projects/${projectId}/coding/start`,
      {
        ...(codingModel && { coding_model: codingModel }),
        ...(maxIterations !== undefined && { max_iterations: maxIterations }),
      }
    );
    return response.data;
  }

  async cancelInitialization(projectId: string): Promise<{ status: string; message: string }> {
    const response = await this.client.post<{ status: string; message: string }>(
      `/api/projects/${projectId}/initialize/cancel`,
      {}
    );
    return response.data;
  }

  // Legacy session endpoint (deprecated - use initializeProject or startCodingSessions)
  async startSession(projectId: string, config?: SessionConfig): Promise<StartSessionResponse> {
    const response = await this.client.post<StartSessionResponse>(
      `/api/projects/${projectId}/sessions/start`,
      config || {}
    );
    return response.data;
  }

  async stopSession(projectId: string, sessionId: string): Promise<StopSessionResponse> {
    const response = await this.client.post<StopSessionResponse>(
      `/api/projects/${projectId}/sessions/${sessionId}/stop`,
      {}
    );
    return response.data;
  }

  async stopAfterCurrent(projectId: string): Promise<{ message: string }> {
    const response = await this.client.post<{ message: string }>(
      `/api/projects/${projectId}/stop-after-current`,
      {}
    );
    return response.data;
  }

  async cancelStopAfterCurrent(projectId: string): Promise<{ message: string }> {
    const response = await this.client.delete<{ message: string }>(
      `/api/projects/${projectId}/stop-after-current`
    );
    return response.data;
  }

  async listSessions(projectId: string): Promise<Session[]> {
    const response = await this.client.get<Session[]>(
      `/api/projects/${projectId}/sessions`
    );
    return response.data;
  }

  async cleanupOrphanedSessions(): Promise<{ success: boolean; cleaned_count: number; message: string }> {
    const response = await this.client.post<{ success: boolean; cleaned_count: number; message: string }>(
      '/api/admin/cleanup-orphaned-sessions',
      {}
    );
    return response.data;
  }

  // Epics
  async listEpics(projectId: string): Promise<Epic[]> {
    const response = await this.client.get<Epic[]>(`/api/projects/${projectId}/epics`);
    return response.data;
  }

  async getEpic(projectId: string, epicId: number): Promise<EpicWithTasks> {
    const response = await this.client.get<EpicWithTasks>(
      `/api/projects/${projectId}/epics/${epicId}`
    );
    return response.data;
  }

  // Tasks
  async listTasks(projectId: string, filters?: { epic_id?: number; done?: boolean }): Promise<Task[]> {
    const params = new URLSearchParams();
    if (filters?.epic_id) params.append('epic_id', filters.epic_id.toString());
    if (filters?.done !== undefined) params.append('done', filters.done.toString());

    const response = await this.client.get<Task[]>(
      `/api/projects/${projectId}/tasks?${params.toString()}`
    );
    return response.data;
  }

  async getTask(projectId: string, taskId: number): Promise<TaskWithTests> {
    const response = await this.client.get<TaskWithTests>(
      `/api/projects/${projectId}/tasks/${taskId}`
    );
    return response.data;
  }

  async getSessionLogs(projectId: string): Promise<any[]> {
    const response = await this.client.get<any[]>(
      `/api/projects/${projectId}/logs`
    );
    return response.data;
  }

  async getSessionLogContent(
    projectId: string,
    type: 'human' | 'events',
    filename: string
  ): Promise<string> {
    const response = await this.client.get<{ content: string; filename: string }>(
      `/api/projects/${projectId}/logs/${type}/${filename}`
    );
    return response.data.content;
  }

  async getTestCoverage(projectId: string): Promise<any> {
    const response = await this.client.get<any>(
      `/api/projects/${projectId}/coverage`
    );
    return response.data;
  }

  // ============================================================================
  // Prompt Improvement System
  // ============================================================================

  /**
   * Trigger a new prompt improvement analysis
   */
  async triggerPromptAnalysis(request: TriggerAnalysisRequest = {}): Promise<TriggerAnalysisResponse> {
    const response = await this.client.post<TriggerAnalysisResponse>(
      '/api/prompt-improvements',
      request
    );
    return response.data;
  }

  /**
   * List all prompt improvement analyses
   */
  async listPromptAnalyses(params?: { status?: string; limit?: number }): Promise<PromptAnalysisSummary[]> {
    const queryParams = new URLSearchParams();
    if (params?.status) queryParams.append('status', params.status);
    if (params?.limit) queryParams.append('limit', params.limit.toString());

    const response = await this.client.get<PromptAnalysisSummary[]>(
      `/api/prompt-improvements?${queryParams.toString()}`
    );
    return response.data;
  }

  /**
   * Get detailed analysis with findings
   */
  async getPromptAnalysis(analysisId: string): Promise<PromptAnalysisDetail> {
    const response = await this.client.get<PromptAnalysisDetail>(
      `/api/prompt-improvements/${analysisId}`
    );
    return response.data;
  }

  /**
   * Get proposals for a specific analysis
   */
  async getPromptProposals(analysisId: string): Promise<PromptProposal[]> {
    const response = await this.client.get<PromptProposal[]>(
      `/api/prompt-improvements/${analysisId}/proposals`
    );
    return response.data;
  }

  /**
   * Update proposal status (accept, reject, etc.)
   */
  async updatePromptProposal(
    proposalId: string,
    update: UpdateProposalRequest
  ): Promise<PromptProposal> {
    const response = await this.client.patch<PromptProposal>(
      `/api/prompt-improvements/proposals/${proposalId}`,
      update
    );
    return response.data;
  }

  /**
   * Apply a proposal to the actual prompt file
   */
  async applyPromptProposal(proposalId: string): Promise<ApplyProposalResponse> {
    const response = await this.client.post<ApplyProposalResponse>(
      `/api/prompt-improvements/proposals/${proposalId}/apply`
    );
    return response.data;
  }

  /**
   * Get overall prompt improvement metrics
   */
  async getPromptImprovementMetrics(): Promise<ImprovementMetrics> {
    const response = await this.client.get<ImprovementMetrics>(
      '/api/prompt-improvements/metrics'
    );
    return response.data;
  }

  /**
   * Delete a prompt improvement analysis and all its proposals
   */
  async deletePromptAnalysis(analysisId: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.delete<{ success: boolean; message: string }>(
      `/api/prompt-improvements/${analysisId}`
    );
    return response.data;
  }

  /**
   * Get project review statistics
   */
  async getProjectReviewStats(projectId: string): Promise<ProjectReviewStats> {
    const response = await this.client.get<ProjectReviewStats>(
      `/api/projects/${projectId}/review-stats`
    );
    return response.data;
  }

  /**
   * Trigger bulk deep reviews for a project
   */
  async triggerBulkReviews(
    projectId: string,
    request: TriggerBulkReviewsRequest
  ): Promise<TriggerBulkReviewsResponse> {
    const response = await this.client.post<TriggerBulkReviewsResponse>(
      `/api/projects/${projectId}/trigger-reviews`,
      request
    );
    return response.data;
  }

  /**
   * List all screenshots for a project
   */
  async listScreenshots(projectId: string): Promise<Screenshot[]> {
    const response = await this.client.get<Screenshot[]>(
      `/api/projects/${projectId}/screenshots`
    );
    return response.data;
  }

  /**
   * Get the URL for a specific screenshot
   * Returns the full URL that can be used in an <img> tag
   */
  getScreenshotUrl(projectId: string, filename: string): string {
    return `${API_BASE}/api/projects/${projectId}/screenshots/${filename}`;
  }
}

// Export singleton instance
export const api = new ApiClient();

// Export class for testing
export { ApiClient };
