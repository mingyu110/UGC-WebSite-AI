// =============================================================================
// UGC AI Demo - Preview Panel Component (Simplified)
// =============================================================================

'use client';

import { PreviewToolbar } from './PreviewToolbar';
import { PreviewFrame } from './PreviewFrame';
import { PreviewState } from '@/types';

interface PreviewPanelProps {
  previewState: PreviewState;
  iframeRef: React.RefObject<HTMLIFrameElement | null>;
  onViewportChange: (size: 'desktop' | 'tablet' | 'mobile') => void;
  onZoomChange?: (zoom: number) => void;
  onRefresh: () => void;
}

export function PreviewPanel({
  previewState,
  iframeRef,
  onViewportChange,
  onZoomChange,
  onRefresh,
}: PreviewPanelProps) {
  const hasContent = !!previewState.currentSite;

  return (
    <div className="flex flex-col h-full bg-white dark:bg-gray-900">
      <PreviewToolbar
        viewportSize={previewState.viewportSize}
        zoom={previewState.zoom}
        hasContent={hasContent}
        onViewportChange={onViewportChange}
        onZoomChange={onZoomChange}
        onRefresh={onRefresh}
      />

      <PreviewFrame
        ref={iframeRef}
        viewportSize={previewState.viewportSize}
        zoom={previewState.zoom}
        isLoading={previewState.isLoading}
        hasContent={hasContent}
      />
    </div>
  );
}
