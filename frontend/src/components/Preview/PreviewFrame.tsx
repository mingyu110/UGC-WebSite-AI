// =============================================================================
// UGC AI Demo - Preview Frame Component
// =============================================================================

'use client';

import { forwardRef, useMemo } from 'react';

interface PreviewFrameProps {
  viewportSize: 'desktop' | 'tablet' | 'mobile';
  zoom: number;
  isLoading: boolean;
  hasContent: boolean;
}

const VIEWPORT_SIZES = {
  desktop: { width: 1280, label: '桌面 (1280px)' },
  tablet: { width: 768, label: '平板 (768px)' },
  mobile: { width: 375, label: '手机 (375px)' },
};

export const PreviewFrame = forwardRef<HTMLIFrameElement, PreviewFrameProps>(
  function PreviewFrame({ viewportSize, zoom, isLoading, hasContent }, ref) {
    const viewport = VIEWPORT_SIZES[viewportSize];
    const scale = zoom / 100;

    // Calculate scaled dimensions
    const scaledDimensions = useMemo(() => {
      const scaledWidth = viewportSize === 'desktop'
        ? '100%'
        : `${viewport.width * scale}px`;

      return {
        containerWidth: scaledWidth,
        iframeWidth: viewportSize === 'desktop' ? '100%' : `${viewport.width}px`,
        iframeTransform: `scale(${scale})`,
        iframeTransformOrigin: 'top left',
      };
    }, [viewportSize, viewport.width, scale]);

    return (
      <div className="flex-1 overflow-auto bg-gray-100 dark:bg-gray-950 p-4">
        <div
          className="mx-auto transition-all duration-300"
          style={{
            width: scaledDimensions.containerWidth,
            maxWidth: viewportSize === 'desktop' ? '100%' : `${viewport.width * scale}px`,
          }}
        >
          {/* Browser Chrome */}
          <div className="bg-gray-200 dark:bg-gray-800 rounded-t-lg px-4 py-2 flex items-center gap-2">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <div className="w-3 h-3 rounded-full bg-yellow-500" />
              <div className="w-3 h-3 rounded-full bg-green-500" />
            </div>
            <div className="flex-1 mx-4">
              <div className="bg-white dark:bg-gray-700 rounded px-3 py-1 text-xs text-gray-400 dark:text-gray-500 truncate">
                localhost:3000/preview
              </div>
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {viewport.label}
            </div>
          </div>

          {/* Iframe Container */}
          <div
            className="bg-white relative overflow-hidden rounded-b-lg shadow-lg"
            style={{
              height: `${600 * scale}px`,
              minHeight: `${400 * scale}px`,
            }}
          >
            {isLoading && (
              <div className="absolute inset-0 bg-white dark:bg-gray-900 flex items-center justify-center z-10">
                <div className="text-center">
                  <LoadingAnimation />
                  <p className="mt-4 text-gray-500 dark:text-gray-400">
                    正在生成网站...
                  </p>
                </div>
              </div>
            )}

            {!hasContent && !isLoading && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-center p-8">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-gray-100 dark:bg-gray-800 flex items-center justify-center">
                    <svg
                      className="w-8 h-8 text-gray-400"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                  <p className="text-gray-500 dark:text-gray-400">
                    在左侧聊天框中描述您的需求
                    <br />
                    AI 将在这里生成网站预览
                  </p>
                </div>
              </div>
            )}

            <div
              style={{
                width: scaledDimensions.iframeWidth,
                height: '600px',
                transform: scaledDimensions.iframeTransform,
                transformOrigin: scaledDimensions.iframeTransformOrigin,
              }}
            >
              <iframe
                ref={ref}
                className="w-full h-full border-0"
                title="Website Preview"
                sandbox="allow-scripts allow-same-origin"
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
);

function LoadingAnimation() {
  return (
    <div className="flex items-center justify-center gap-1">
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="w-3 h-3 rounded-full bg-blue-500"
          style={{
            animation: 'bounce 1.4s infinite ease-in-out both',
            animationDelay: `${i * 0.16}s`,
          }}
        />
      ))}
      <style jsx>{`
        @keyframes bounce {
          0%,
          80%,
          100% {
            transform: scale(0);
          }
          40% {
            transform: scale(1);
          }
        }
      `}</style>
    </div>
  );
}
