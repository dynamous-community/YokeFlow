'use client';

import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import ConfirmDialog from '@/components/ConfirmDialog';
import type { Project, ContainerStatus } from '@/lib/types';

interface ProjectWithContainer {
  project: Project;
  container: ContainerStatus | null;
  loading: boolean;
  error: string | null;
}

export default function ContainersPage() {
  const [projectContainers, setProjectContainers] = useState<ProjectWithContainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<{ projectId: string; projectName: string } | null>(null);

  const loadContainers = async () => {
    try {
      setLoading(true);

      // Get all projects
      const projects = await api.listProjects();

      // Get container status for each Docker project
      const containersData = await Promise.all(
        projects.map(async (project) => {
          if (project.sandbox_type !== 'docker') {
            return {
              project,
              container: null,
              loading: false,
              error: null,
            };
          }

          try {
            const status = await api.getContainerStatus(project.id);
            return {
              project,
              container: status,
              loading: false,
              error: null,
            };
          } catch (err) {
            return {
              project,
              container: null,
              loading: false,
              error: err instanceof Error ? err.message : 'Failed to load container',
            };
          }
        })
      );

      setProjectContainers(containersData);
    } catch (err) {
      console.error('Failed to load containers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadContainers();
  }, []);

  const handleAction = async (
    projectId: string,
    projectName: string,
    action: 'start' | 'stop' | 'delete'
  ) => {
    try {
      // For delete, show confirmation dialog
      if (action === 'delete') {
        setDeleteConfirm({ projectId, projectName });
        return;
      }

      setActionLoading(`${projectId}-${action}`);

      if (action === 'start') {
        const result = await api.startContainer(projectId);
        if (result.started) {
          toast.success(`Container started successfully`);
        } else {
          toast.info(`Container was already running`);
        }
      } else if (action === 'stop') {
        const result = await api.stopContainer(projectId);
        if (result.stopped) {
          toast.success(`Container stopped successfully`);
        } else {
          toast.info(`Container was not running`);
        }
      }

      // Reload containers after action
      await loadContainers();
    } catch (err) {
      console.error(`Failed to ${action} container:`, err);
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      toast.error(`Failed to ${action} container: ${errorMsg}`);
    } finally {
      setActionLoading(null);
    }
  };

  const confirmDelete = async () => {
    if (!deleteConfirm) return;

    try {
      setActionLoading(`${deleteConfirm.projectId}-delete`);
      const result = await api.deleteContainer(deleteConfirm.projectId);

      if (result.deleted) {
        toast.success(`Container deleted successfully`);
      } else {
        toast.info(`Container doesn't exist`);
      }

      // Reload containers after deletion
      await loadContainers();
    } catch (err) {
      console.error('Failed to delete container:', err);
      const errorMsg = err instanceof Error ? err.message : 'Unknown error';
      toast.error(`Failed to delete container: ${errorMsg}`);
    } finally {
      setActionLoading(null);
      setDeleteConfirm(null);
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status) {
      case 'running':
        return 'text-green-400';
      case 'exited':
        return 'text-gray-400';
      case 'paused':
        return 'text-yellow-400';
      default:
        return 'text-gray-500';
    }
  };

  const getStatusBadge = (status?: string) => {
    const color = getStatusColor(status);
    return (
      <span className={`text-xs font-medium px-2 py-1 rounded ${color}`}>
        {status || 'unknown'}
      </span>
    );
  };

  const dockerProjects = projectContainers.filter(pc => pc.project.sandbox_type === 'docker');
  const runningCount = dockerProjects.filter(pc => pc.container?.status === 'running').length;
  const stoppedCount = dockerProjects.filter(pc => pc.container?.status === 'exited').length;
  const totalCount = dockerProjects.length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 text-gray-100 p-8">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-3xl font-bold mb-8">Docker Containers</h1>
          <div className="text-gray-600 dark:text-gray-400">Loading containers...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">Docker Containers</h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage Docker containers for your YokeFlow projects
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Containers</div>
            <div className="text-2xl font-bold">{totalCount}</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Running</div>
            <div className="text-2xl font-bold text-green-400">{runningCount}</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Stopped</div>
            <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">{stoppedCount}</div>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Actions</div>
            <button
              onClick={loadContainers}
              className="text-sm bg-blue-600 hover:bg-blue-700 px-3 py-1 rounded"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* No Docker projects */}
        {dockerProjects.length === 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
            <div className="text-gray-400 mb-2">No Docker projects found</div>
            <div className="text-sm text-gray-500 mb-4">
              {projectContainers.length > 0
                ? `You have ${projectContainers.length} project(s), but none are using Docker sandbox.`
                : 'No projects found in the database.'}
            </div>
            <div className="text-sm text-gray-700 dark:text-gray-500">
              Create a project with Docker sandbox to see containers here.
            </div>
            {projectContainers.length > 0 && (
              <div className="mt-4 text-xs text-gray-600">
                <div className="font-mono">
                  Existing projects: {projectContainers.map(pc => `${pc.project.name} (${pc.project.sandbox_type || 'unknown'})`).join(', ')}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Containers Table */}
        {dockerProjects.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 bg-gray-800/50">
                  <th className="text-left p-4 font-medium">Project</th>
                  <th className="text-left p-4 font-medium">Container Name</th>
                  <th className="text-left p-4 font-medium">Status</th>
                  <th className="text-left p-4 font-medium">Container ID</th>
                  <th className="text-left p-4 font-medium">Ports</th>
                  <th className="text-right p-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {dockerProjects.map(({ project, container, error }) => (
                  <tr key={project.id} className="border-b border-gray-800 hover:bg-gray-800/30">
                    <td className="p-4">
                      <div className="font-medium">{project.name}</div>
                      <div className="text-xs text-gray-700 dark:text-gray-500">
                        {project.completed_at ? '✓ Complete' : 'In Progress'}
                      </div>
                    </td>
                    <td className="p-4">
                      <div className="font-mono text-sm text-gray-600 dark:text-gray-400">
                        {container?.container_name || `yokeflow-${project.name}`}
                      </div>
                    </td>
                    <td className="p-4">
                      {error ? (
                        <span className="text-xs text-red-400">Error</span>
                      ) : container?.container_exists ? (
                        getStatusBadge(container.status)
                      ) : (
                        <span className="text-xs text-gray-700 dark:text-gray-500">No container</span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="font-mono text-xs text-gray-700 dark:text-gray-500">
                        {container?.container_id || '-'}
                      </div>
                    </td>
                    <td className="p-4">
                      {container?.ports && Object.keys(container.ports).length > 0 ? (
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                          {Object.entries(container.ports).map(([port, bindings]) => (
                            <div key={port}>{port}</div>
                          ))}
                        </div>
                      ) : (
                        <span className="text-xs text-gray-700 dark:text-gray-500">-</span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex justify-end gap-2">
                        {container?.container_exists ? (
                          <>
                            {container.status === 'running' ? (
                              <button
                                onClick={() => handleAction(project.id, project.name, 'stop')}
                                disabled={actionLoading === `${project.id}-stop`}
                                className="text-xs bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-800 px-3 py-1 rounded"
                              >
                                {actionLoading === `${project.id}-stop` ? 'Stopping...' : 'Stop'}
                              </button>
                            ) : (
                              <button
                                onClick={() => handleAction(project.id, project.name, 'start')}
                                disabled={actionLoading === `${project.id}-start`}
                                className="text-xs bg-green-600 hover:bg-green-700 disabled:bg-green-800 px-3 py-1 rounded"
                              >
                                {actionLoading === `${project.id}-start` ? 'Starting...' : 'Start'}
                              </button>
                            )}
                            <button
                              onClick={() => handleAction(project.id, project.name, 'delete')}
                              disabled={actionLoading === `${project.id}-delete`}
                              className="text-xs bg-red-600 hover:bg-red-700 disabled:bg-red-800 px-3 py-1 rounded"
                            >
                              {actionLoading === `${project.id}-delete` ? 'Deleting...' : 'Delete'}
                            </button>
                          </>
                        ) : (
                          <span className="text-xs text-gray-700 dark:text-gray-500">No actions available</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Info Box */}
        <div className="mt-8 bg-blue-900/20 border border-blue-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-blue-400 mb-2">About Container Management</h3>
          <ul className="text-sm text-gray-400 space-y-1">
            <li>• Containers are automatically stopped when projects complete to free up ports</li>
            <li>• Stopped containers preserve the environment and can be restarted</li>
            <li>• Deleting a container will free up disk space (container will be recreated when needed)</li>
            <li>• Container names follow the pattern: <span className="font-mono">yokeflow-[project-name]</span></li>
            <li>• Use Docker Desktop for advanced container management features</li>
          </ul>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={deleteConfirm !== null}
        onClose={() => setDeleteConfirm(null)}
        onConfirm={confirmDelete}
        title="Delete Container"
        message={
          deleteConfirm
            ? `Are you sure you want to delete the container for "${deleteConfirm.projectName}"? The container can be recreated when you start a new session.`
            : ''
        }
        confirmText="Delete Container"
        variant="danger"
      />
    </div>
  );
}
