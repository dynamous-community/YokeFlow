'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import type { Screenshot } from '@/lib/types';
import { Download, X, Image as ImageIcon, ChevronDown, ChevronRight } from 'lucide-react';

interface ScreenshotsGalleryProps {
  projectId: string;
}

export function ScreenshotsGallery({ projectId }: ScreenshotsGalleryProps) {
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState<Screenshot | null>(null);
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadScreenshots();
  }, [projectId]);

  async function loadScreenshots() {
    try {
      setLoading(true);
      const data = await api.listScreenshots(projectId);

      // Convert relative URLs to absolute URLs
      const screenshotsWithFullUrls = data.map(s => ({
        ...s,
        url: api.getScreenshotUrl(projectId, s.filename)
      }));

      setScreenshots(screenshotsWithFullUrls);

      // Start with all groups collapsed
      setExpandedGroups(new Set());
    } catch (error) {
      console.error('Failed to load screenshots:', error);
    } finally {
      setLoading(false);
    }
  }

  function toggleGroup(group: string) {
    const newExpanded = new Set(expandedGroups);
    if (newExpanded.has(group)) {
      newExpanded.delete(group);
    } else {
      newExpanded.add(group);
    }
    setExpandedGroups(newExpanded);
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // Parse task description from filename
  // Format: task_10_default_user_seed.png → "Default User Seed"
  function parseTaskDescription(filename: string): string | null {
    // Match: task_[number]_[description].png
    const match = filename.match(/^task_\d+_(.+)\.png$/);

    if (!match) {
      return null;
    }

    // Extract description and convert underscores to spaces, capitalize words
    const description = match[1]
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');

    return description;
  }

  function downloadScreenshot(screenshot: Screenshot) {
    const link = document.createElement('a');
    link.href = screenshot.url;
    link.download = screenshot.filename;
    link.click();
  }

  // Group screenshots by task ID
  const groupedScreenshots = screenshots.reduce((acc, screenshot) => {
    const key = screenshot.task_id?.toString() || 'other';
    if (!acc[key]) acc[key] = [];
    acc[key].push(screenshot);
    return acc;
  }, {} as Record<string, Screenshot[]>);

  // Sort groups: numbered tasks in descending order (newest first), then 'other'
  const sortedGroups = Object.keys(groupedScreenshots).sort((a, b) => {
    if (a === 'other') return 1;
    if (b === 'other') return -1;
    return parseInt(b) - parseInt(a); // Reversed for newest first
  });

  // Sort screenshots within each group by modified_at (newest first)
  Object.keys(groupedScreenshots).forEach(key => {
    groupedScreenshots[key].sort((a, b) =>
      new Date(b.modified_at).getTime() - new Date(a.modified_at).getTime()
    );
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        <span className="ml-3 text-gray-600">Loading screenshots...</span>
      </div>
    );
  }

  if (screenshots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-700 dark:text-gray-500">
        <ImageIcon className="h-16 w-16 mb-4 opacity-50" />
        <p className="text-lg font-medium">No screenshots yet</p>
        <p className="text-sm mt-2">Screenshots will appear here as sessions run</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">
          Screenshots ({screenshots.length})
        </h2>
        <button
          onClick={loadScreenshots}
          className="text-sm text-blue-600 hover:text-blue-700 font-medium"
        >
          Refresh
        </button>
      </div>

      {sortedGroups.map((group) => {
        const groupScreenshots = groupedScreenshots[group];
        const isExpanded = expandedGroups.has(group);

        // Get task description from first screenshot in group
        const taskDescription = group !== 'other' && groupScreenshots[0]
          ? parseTaskDescription(groupScreenshots[0].filename)
          : null;

        const groupTitle = group === 'other'
          ? 'Other Screenshots'
          : `Task #${group}`;

        return (
          <div key={group} className="border rounded-lg overflow-hidden">
            <button
              onClick={() => toggleGroup(group)}
              className="w-full flex items-center p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
            >
              <div className="flex items-center gap-2">
                {isExpanded ? (
                  <ChevronDown className="h-5 w-5 text-gray-500 flex-shrink-0" />
                ) : (
                  <ChevronRight className="h-5 w-5 text-gray-500 flex-shrink-0" />
                )}
                <h3 className="text-base font-medium">{groupTitle}</h3>
                {taskDescription && (
                  <>
                    <span className="text-gray-600 dark:text-gray-400">•</span>
                    <p className="text-sm text-gray-600" title={taskDescription}>
                      {taskDescription}
                    </p>
                  </>
                )}
                <span className="text-sm text-gray-700 dark:text-gray-500">
                  ({groupScreenshots.length})
                </span>
              </div>
            </button>

            {isExpanded && (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
                {groupScreenshots.map((screenshot) => (
                  <div
                    key={screenshot.filename}
                    className="border rounded-lg overflow-hidden hover:shadow-lg transition-shadow bg-white"
                  >
                    <div
                      className="cursor-pointer"
                      onClick={() => setSelectedImage(screenshot)}
                    >
                      <img
                        src={screenshot.url}
                        alt={screenshot.filename}
                        className="w-full h-48 object-contain bg-gray-100"
                        loading="lazy"
                      />
                    </div>
                    <div className="p-3 space-y-2">
                      <p className="text-sm font-medium truncate" title={screenshot.filename}>
                        {screenshot.filename}
                      </p>
                      <div className="flex items-center justify-between text-xs text-gray-700 dark:text-gray-500">
                        <span>{formatFileSize(screenshot.size)}</span>
                        <span>
                          {new Date(screenshot.modified_at).toLocaleDateString()} {new Date(screenshot.modified_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <button
                        onClick={() => downloadScreenshot(screenshot)}
                        className="w-full flex items-center justify-center gap-2 px-3 py-1.5 text-sm bg-blue-50 text-blue-700 rounded hover:bg-blue-100 transition-colors"
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* Lightbox Modal */}
      {selectedImage && (
        <div
          className="fixed inset-0 bg-black bg-opacity-90 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedImage(null)}
        >
          <button
            onClick={() => setSelectedImage(null)}
            className="absolute top-4 right-4 text-white hover:text-gray-300 transition-colors"
            aria-label="Close"
          >
            <X className="h-8 w-8" />
          </button>

          <div className="max-w-6xl max-h-[90vh] flex flex-col items-center gap-4">
            <img
              src={selectedImage.url}
              alt={selectedImage.filename}
              className="max-w-full max-h-[80vh] object-contain"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="bg-white rounded-lg p-4 flex items-center gap-4">
              <div className="flex-1">
                <p className="font-medium text-sm">{selectedImage.filename}</p>
                <p className="text-xs text-gray-500 mt-1">
                  {formatFileSize(selectedImage.size)} • {new Date(selectedImage.modified_at).toLocaleString()}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  downloadScreenshot(selectedImage);
                }}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                <Download className="h-4 w-4" />
                Download
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
