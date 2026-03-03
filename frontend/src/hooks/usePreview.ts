// =============================================================================
// UGC AI Demo - Preview Hook (Simplified)
// =============================================================================

'use client';

import { useState, useCallback, useRef } from 'react';
import { GeneratedSite, PreviewState } from '@/types';
import { generateId, buildHtmlDocument } from '@/lib/utils';

interface UsePreviewOptions {
  // Reserved for future use
}

interface UsePreviewReturn {
  previewState: PreviewState;
  iframeRef: React.RefObject<HTMLIFrameElement | null>;
  updateSite: (html: string, css: string, javascript?: string) => void;
  setViewportSize: (size: 'desktop' | 'tablet' | 'mobile') => void;
  setZoom: (zoom: number) => void;
  refreshPreview: () => void;
  setLoading: (loading: boolean) => void;
}

export function usePreview(_options: UsePreviewOptions = {}): UsePreviewReturn {
  const [previewState, setPreviewState] = useState<PreviewState>({
    isLoading: false,
    currentSite: null,
    viewportSize: 'desktop',
    zoom: 100,
  });

  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  // Update site content
  const updateSite = useCallback((html: string, css: string, javascript?: string) => {
    setPreviewState((prev) => {
      const newSite: GeneratedSite = {
        id: generateId(),
        html,
        css,
        javascript,
        version: (prev.currentSite?.version || 0) + 1,
        createdAt: prev.currentSite?.createdAt || new Date(),
        lastModified: new Date(),
      };

      // Update iframe content
      if (iframeRef.current) {
        const doc = iframeRef.current.contentDocument;
        if (doc) {
          doc.open();
          doc.write(buildHtmlDocument(html, css, javascript));
          doc.close();
        }
      }

      return {
        ...prev,
        currentSite: newSite,
        isLoading: false,
      };
    });
  }, []);

  // Set viewport size
  const setViewportSize = useCallback((size: 'desktop' | 'tablet' | 'mobile') => {
    setPreviewState((prev) => ({
      ...prev,
      viewportSize: size,
    }));
  }, []);

  // Set zoom level
  const setZoom = useCallback((zoom: number) => {
    const clampedZoom = Math.min(Math.max(zoom, 25), 200);
    setPreviewState((prev) => ({
      ...prev,
      zoom: clampedZoom,
    }));
  }, []);

  // Refresh preview
  const refreshPreview = useCallback(() => {
    if (previewState.currentSite) {
      updateSite(
        previewState.currentSite.html,
        previewState.currentSite.css,
        previewState.currentSite.javascript
      );
    }
  }, [previewState.currentSite, updateSite]);

  // Set loading state
  const setLoading = useCallback((loading: boolean) => {
    setPreviewState((prev) => ({
      ...prev,
      isLoading: loading,
    }));
  }, []);

  return {
    previewState,
    iframeRef,
    updateSite,
    setViewportSize,
    setZoom,
    refreshPreview,
    setLoading,
  };
}
