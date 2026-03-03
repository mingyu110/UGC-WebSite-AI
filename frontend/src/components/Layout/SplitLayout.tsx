// =============================================================================
// UGC AI Demo - Split Layout Component
// =============================================================================

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

interface SplitLayoutProps {
  left: React.ReactNode;
  right: React.ReactNode;
  defaultLeftWidth?: number;
  minLeftWidth?: number;
  maxLeftWidth?: number;
}

export function SplitLayout({
  left,
  right,
  defaultLeftWidth = 400,
  minLeftWidth = 300,
  maxLeftWidth = 600,
}: SplitLayoutProps) {
  const [leftWidth, setLeftWidth] = useState(defaultLeftWidth);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;

      setLeftWidth(Math.min(Math.max(newWidth, minLeftWidth), maxLeftWidth));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, minLeftWidth, maxLeftWidth]);

  return (
    <div
      ref={containerRef}
      className="flex h-full w-full overflow-hidden"
    >
      {/* Left Panel */}
      <div
        className="h-full flex-shrink-0 overflow-hidden"
        style={{ width: leftWidth }}
      >
        {left}
      </div>

      {/* Resizer */}
      <div
        className={cn(
          'w-1 h-full cursor-col-resize flex-shrink-0 group relative',
          'bg-gray-200 dark:bg-gray-700',
          'hover:bg-blue-500 dark:hover:bg-blue-500',
          isDragging && 'bg-blue-500'
        )}
        onMouseDown={handleMouseDown}
      >
        <div
          className={cn(
            'absolute inset-y-0 -left-1 -right-1',
            'group-hover:bg-blue-500/10'
          )}
        />
      </div>

      {/* Right Panel */}
      <div className="flex-1 h-full overflow-hidden">
        {right}
      </div>

      {/* Drag Overlay */}
      {isDragging && (
        <div className="fixed inset-0 cursor-col-resize z-50" />
      )}
    </div>
  );
}
