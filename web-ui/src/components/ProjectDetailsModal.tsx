/**
 * ProjectDetailsModal - Unified modal for project configuration and roadmap
 *
 * Contains three tabs:
 * - Settings: Model configuration, sandbox type, max iterations
 * - Environment: .env file configuration
 * - Epics: Project roadmap with tasks and tests
 */

'use client';

import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { toast } from 'sonner';
import { ProjectSettingsModal } from './ProjectSettings';
import { EnvEditor } from './EnvEditor';
import { EpicAccordion } from './EpicAccordion';
import { TaskDetailModal } from './TaskDetailModal';
import { api } from '@/lib/api';
import type { Epic, TaskWithTestCount, Project } from '@/lib/types';

interface ProjectDetailsModalProps {
  projectId: string;
  project: Project;
  isOpen: boolean;
  onClose: () => void;
  onProjectUpdated?: () => void;
  initialTab?: 'settings' | 'environment' | 'epics';
}

export function ProjectDetailsModal({
  projectId,
  project,
  isOpen,
  onClose,
  onProjectUpdated,
  initialTab = 'settings',
}: ProjectDetailsModalProps) {
  const [activeTab, setActiveTab] = useState<'settings' | 'environment' | 'epics'>(initialTab);
  const [showSettingsModal, setShowSettingsModal] = useState(false);

  // Epics state
  const [epics, setEpics] = useState<Epic[]>([]);
  const [epicTasks, setEpicTasks] = useState<Record<number, TaskWithTestCount[]>>({});
  const [epicsLoading, setEpicsLoading] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

  // Reset active tab when modal opens
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

  // Load epics when switching to Epics tab
  useEffect(() => {
    if (isOpen && activeTab === 'epics' && epics.length === 0) {
      loadEpics();
    }
  }, [isOpen, activeTab]);

  async function loadEpics() {
    try {
      setEpicsLoading(true);
      const epicsData = await api.listEpics(projectId);
      setEpics(epicsData);

      // Load tasks for each epic
      const tasksPromises = epicsData.map(async (epic) => {
        const epicDetail = await api.getEpic(projectId, epic.id);
        return { epicId: epic.id, tasks: epicDetail.tasks };
      });

      const tasksResults = await Promise.all(tasksPromises);
      const tasksMap: Record<number, TaskWithTestCount[]> = {};
      tasksResults.forEach(({ epicId, tasks }) => {
        tasksMap[epicId] = tasks;
      });
      setEpicTasks(tasksMap);
    } catch (err) {
      console.error('Failed to load epics:', err);
      toast.error('Failed to load epics');
    } finally {
      setEpicsLoading(false);
    }
  }

  if (!isOpen) return null;

  // Backdrop click handler
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <>
      <div
        className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
        onClick={handleBackdropClick}
      >
        <div className="bg-gray-900 border border-gray-800 rounded-lg max-w-6xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-gray-800">
            <div>
              <h2 className="text-2xl font-semibold text-gray-100">Project Details</h2>
              <p className="text-sm text-gray-400 mt-1">{project.name}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-300 transition-colors"
            >
              <X className="w-6 h-6" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-gray-800">
            <button
              onClick={() => setActiveTab('settings')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'settings'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Settings
            </button>
            <button
              onClick={() => setActiveTab('environment')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'environment'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Environment
              {project.needs_env_config && (
                <span className="ml-2 w-2 h-2 bg-amber-400 rounded-full inline-block animate-pulse"></span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('epics')}
              className={`flex-1 px-6 py-4 font-medium transition-colors ${
                activeTab === 'epics'
                  ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                  : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
              }`}
            >
              Epics
              <span className="ml-2 text-sm text-gray-700 dark:text-gray-500">({project.progress.total_epics})</span>
            </button>
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {activeTab === 'settings' && (
              <div>
                <button
                  onClick={() => setShowSettingsModal(true)}
                  className="w-full px-4 py-3 bg-gray-800 hover:bg-gray-700 text-gray-100 rounded-lg transition-colors text-left"
                >
                  <div className="font-medium mb-1">Configure Project Settings</div>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Model selection, sandbox type, iteration limits
                  </div>
                </button>
              </div>
            )}

            {activeTab === 'environment' && (
              <div>
                <EnvEditor
                  projectId={projectId}
                  onSave={() => {
                    onProjectUpdated?.();
                    toast.success('Environment configuration saved');
                  }}
                  onCancel={() => {}}
                />
              </div>
            )}

            {activeTab === 'epics' && (
              <div>
                {epicsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-3"></div>
                      <p className="text-gray-400 text-sm">Loading epics...</p>
                    </div>
                  </div>
                ) : epics.length === 0 ? (
                  <div className="text-center py-12">
                    <p className="text-gray-500 mb-2">No epics yet</p>
                    <p className="text-sm text-gray-600">Run initialization to create your project roadmap</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div className="mb-4">
                      <h3 className="text-lg font-semibold text-gray-100 mb-2">Project Roadmap</h3>
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {project.progress.completed_epics}/{project.progress.total_epics} epics complete •
                        {' '}{project.progress.completed_tasks}/{project.progress.total_tasks} tasks complete •
                        {' '}{project.progress.passing_tests}/{project.progress.total_tests} tests passing
                      </p>
                    </div>
                    {epics.map((epic) => (
                      <EpicAccordion
                        key={epic.id}
                        epic={epic}
                        tasks={epicTasks[epic.id] || []}
                        onTaskClick={(taskId) => {
                          setSelectedTaskId(taskId);
                          setShowTaskModal(true);
                        }}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 p-6 border-t border-gray-800">
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-100 rounded-lg transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      {/* Nested Modals */}
      {showSettingsModal && (
        <ProjectSettingsModal
          projectId={projectId}
          onClose={() => setShowSettingsModal(false)}
          onSaved={() => {
            setShowSettingsModal(false);
            onProjectUpdated?.();
          }}
        />
      )}

      {showTaskModal && selectedTaskId && (
        <TaskDetailModal
          projectId={projectId}
          taskId={selectedTaskId}
          isOpen={showTaskModal}
          onClose={() => {
            setShowTaskModal(false);
            setSelectedTaskId(null);
          }}
        />
      )}
    </>
  );
}
