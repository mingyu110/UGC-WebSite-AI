// =============================================================================
// UGC AI Demo - Preview Toolbar Component (Simplified)
// =============================================================================

'use client';

interface PreviewToolbarProps {
  viewportSize: 'desktop' | 'tablet' | 'mobile';
  zoom?: number;
  hasContent: boolean;
  onViewportChange: (size: 'desktop' | 'tablet' | 'mobile') => void;
  onZoomChange?: (zoom: number) => void;
  onRefresh: () => void;
}

const ZOOM_PRESETS = [25, 50, 75, 100, 125, 150, 200];

export function PreviewToolbar({
  viewportSize,
  zoom = 100,
  hasContent,
  onViewportChange,
  onZoomChange,
  onRefresh,
}: PreviewToolbarProps) {
  const handleZoomIn = () => {
    if (!onZoomChange) return;
    const currentIndex = ZOOM_PRESETS.findIndex((z) => z >= zoom);
    if (currentIndex < ZOOM_PRESETS.length - 1) {
      onZoomChange(ZOOM_PRESETS[currentIndex + 1]);
    }
  };

  const handleZoomOut = () => {
    if (!onZoomChange) return;
    const currentIndex = ZOOM_PRESETS.findIndex((z) => z >= zoom);
    if (currentIndex > 0) {
      onZoomChange(ZOOM_PRESETS[currentIndex - 1]);
    } else if (currentIndex === 0 && zoom > ZOOM_PRESETS[0]) {
      onZoomChange(ZOOM_PRESETS[0]);
    }
  };

  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800">
      {/* Viewport Controls */}
      <div className="flex items-center gap-1">
        <ViewportButton
          icon={<DesktopIcon />}
          active={viewportSize === 'desktop'}
          onClick={() => onViewportChange('desktop')}
          label="桌面"
        />
        <ViewportButton
          icon={<TabletIcon />}
          active={viewportSize === 'tablet'}
          onClick={() => onViewportChange('tablet')}
          label="平板"
        />
        <ViewportButton
          icon={<MobileIcon />}
          active={viewportSize === 'mobile'}
          onClick={() => onViewportChange('mobile')}
          label="手机"
        />

        {/* Separator */}
        <div className="w-px h-6 bg-gray-300 dark:bg-gray-600 mx-2" />

        {/* Zoom Controls */}
        <div className="flex items-center gap-1">
          <button
            onClick={handleZoomOut}
            disabled={zoom <= ZOOM_PRESETS[0]}
            className="p-1.5 rounded text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="缩小"
          >
            <ZoomOutIcon />
          </button>
          <select
            value={zoom}
            onChange={(e) => onZoomChange?.(Number(e.target.value))}
            className="w-20 px-2 py-1 text-xs font-medium text-gray-700 dark:text-gray-300 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
          >
            {ZOOM_PRESETS.map((z) => (
              <option key={z} value={z}>
                {z}%
              </option>
            ))}
          </select>
          <button
            onClick={handleZoomIn}
            disabled={zoom >= ZOOM_PRESETS[ZOOM_PRESETS.length - 1]}
            className="p-1.5 rounded text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            title="放大"
          >
            <ZoomInIcon />
          </button>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <button
          onClick={onRefresh}
          disabled={!hasContent}
          className="p-2 rounded-lg text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          title="刷新预览"
        >
          <RefreshIcon />
        </button>
      </div>
    </div>
  );
}

interface ViewportButtonProps {
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
  label: string;
}

function ViewportButton({ icon, active, onClick, label }: ViewportButtonProps) {
  return (
    <button
      onClick={onClick}
      className={`p-2 rounded-lg transition-colors ${
        active
          ? 'bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-400'
          : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:bg-gray-700'
      }`}
      title={label}
    >
      {icon}
    </button>
  );
}

// Icons
function DesktopIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}

function TabletIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 18h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z"
      />
    </svg>
  );
}

function MobileIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"
      />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
      />
    </svg>
  );
}

function ZoomInIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7"
      />
    </svg>
  );
}

function ZoomOutIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7"
      />
    </svg>
  );
}
