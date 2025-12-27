/**
 * SessionQualityBadge - Display session quality rating with color coding
 *
 * Color scheme:
 * - 9-10: Green (Excellent)
 * - 7-8:  Blue (Good)
 * - 5-6:  Yellow (Fair)
 * - 1-4:  Red (Poor)
 */

import React from 'react';

interface SessionQualityBadgeProps {
  rating: number | null;
  checkType?: 'quick' | 'deep' | 'final';
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
}

export function SessionQualityBadge({
  rating,
  checkType = 'quick',
  size = 'md',
  showLabel = true
}: SessionQualityBadgeProps) {
  if (rating === null || rating === undefined) {
    return (
      <span className="text-gray-500 text-sm">N/A</span>
    );
  }

  // Determine color based on rating
  const getColorClasses = (rating: number) => {
    if (rating >= 9) {
      return {
        bg: 'bg-green-900/30',
        text: 'text-green-400',
        border: 'border-green-600/50'
      };
    } else if (rating >= 7) {
      return {
        bg: 'bg-blue-900/30',
        text: 'text-blue-400',
        border: 'border-blue-600/50'
      };
    } else if (rating >= 5) {
      return {
        bg: 'bg-yellow-900/30',
        text: 'text-yellow-400',
        border: 'border-yellow-600/50'
      };
    } else {
      return {
        bg: 'bg-red-900/30',
        text: 'text-red-400',
        border: 'border-red-600/50'
      };
    }
  };

  // Determine size classes
  const getSizeClasses = (size: string) => {
    if (size === 'sm') {
      return {
        padding: 'px-2 py-0.5',
        text: 'text-xs',
        font: 'font-medium'
      };
    } else if (size === 'lg') {
      return {
        padding: 'px-4 py-2',
        text: 'text-lg',
        font: 'font-bold'
      };
    } else {
      return {
        padding: 'px-3 py-1',
        text: 'text-sm',
        font: 'font-semibold'
      };
    }
  };

  const colors = getColorClasses(rating);
  const sizes = getSizeClasses(size);

  // Get label based on check type
  const getCheckTypeIcon = (type: string) => {
    switch (type) {
      case 'deep':
        return '🔍'; // Deep review
      case 'final':
        return '🏁'; // Final review
      default:
        return '✓'; // Quick check
    }
  };

  const icon = getCheckTypeIcon(checkType);

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-md border
        ${colors.bg} ${colors.text} ${colors.border}
        ${sizes.padding} ${sizes.text} ${sizes.font}
      `}
      title={`${checkType} check: ${rating}/10`}
    >
      {showLabel && <span className="opacity-70">{icon}</span>}
      <span>{rating}/10</span>
    </span>
  );
}

/**
 * Quality rating legend component
 */
export function QualityLegend() {
  return (
    <div className="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400">
      <div className="flex items-center gap-1">
        <div className="w-3 h-3 rounded-sm bg-green-900/30 border border-green-600/50"></div>
        <span>9-10 (Excellent)</span>
      </div>
      <div className="flex items-center gap-1">
        <div className="w-3 h-3 rounded-sm bg-blue-900/30 border border-blue-600/50"></div>
        <span>7-8 (Good)</span>
      </div>
      <div className="flex items-center gap-1">
        <div className="w-3 h-3 rounded-sm bg-yellow-900/30 border border-yellow-600/50"></div>
        <span>5-6 (Fair)</span>
      </div>
      <div className="flex items-center gap-1">
        <div className="w-3 h-3 rounded-sm bg-red-900/30 border border-red-600/50"></div>
        <span>1-4 (Poor)</span>
      </div>
    </div>
  );
}
