/**
 * ProjectDetailsPanel - Bottom panel for project configuration and roadmap
 *
 * Contains three tabs:
 * - Settings: Model configuration, sandbox type, max iterations
 * - Environment: .env file configuration
 * - Epics: Project roadmap with tasks and tests
 */

'use client';

import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import { ProjectSettingsForm } from './ProjectSettings';
import { EnvEditor } from './EnvEditor';
import { EpicAccordion } from './EpicAccordion';
import { TaskDetailModal } from './TaskDetailModal';
import { api } from '@/lib/api';
import type { Epic, TaskWithTestCount, Project } from '@/lib/types';

interface ProjectDetailsPanelProps {
  projectId: string;
  project: Project;
  isOpen: boolean;
  activeTab: 'settings' | 'environment' | 'epics';
  onTabChange: (tab: 'settings' | 'environment' | 'epics') => void;
  onProjectUpdated?: () => void;
}

export function ProjectDetailsPanel({
  projectId,
  project,
  isOpen,
  activeTab,
  onTabChange,
  onProjectUpdated,
}: ProjectDetailsPanelProps) {
  // Epics state
  const [epics, setEpics] = useState<Epic[]>([]);
  const [epicTasks, setEpicTasks] = useState<Record<number, TaskWithTestCount[]>>({});
  const [epicsLoading, setEpicsLoading] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState<number | null>(null);
  const [showTaskModal, setShowTaskModal] = useState(false);

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

  return (
    <>
      <div className="bg-gray-900 border-t border-gray-800 mt-6">
        {/* Tabs */}
        <div className="flex border-b border-gray-800">
          <button
            onClick={() => onTabChange('settings')}
            className={`flex-1 px-6 py-4 font-medium transition-colors ${
              activeTab === 'settings'
                ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
            }`}
          >
            Settings
          </button>
          <button
            onClick={() => onTabChange('environment')}
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
            onClick={() => onTabChange('epics')}
            className={`flex-1 px-6 py-4 font-medium transition-colors ${
              activeTab === 'epics'
                ? 'bg-gray-800 text-blue-400 border-b-2 border-blue-500'
                : 'text-gray-400 hover:text-gray-300 hover:bg-gray-800/50'
            }`}
          >
            Epics
            <span className="ml-2 text-sm text-gray-500">({project.progress.total_epics})</span>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 max-h-96 overflow-y-auto">
          {activeTab === 'settings' && (
            <ProjectSettingsForm
              projectId={projectId}
              onSaved={onProjectUpdated}
            />
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
                    <p className="text-sm text-gray-400">
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
      </div>

      {/* Task Detail Modal */}
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
