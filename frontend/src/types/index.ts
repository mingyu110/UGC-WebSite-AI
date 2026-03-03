// =============================================================================
// UGC AI Demo - Type Definitions (Simplified)
// =============================================================================

// -----------------------------------------------------------------------------
// Chat Types
// -----------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  metadata?: {
    generatedCode?: string;
    status?: 'pending' | 'streaming' | 'complete' | 'error';
  };
}

export interface ChatSession {
  id: string;
  messages: ChatMessage[];
  createdAt: Date;
  updatedAt: Date;
  generatedSite?: GeneratedSite;
}

// -----------------------------------------------------------------------------
// Site Generation Types
// -----------------------------------------------------------------------------

export interface GeneratedSite {
  id: string;
  html: string;
  css: string;
  javascript?: string;
  version: number;
  createdAt: Date;
  lastModified: Date;
}

export interface GenerationRequest {
  sessionId: string;
  prompt: string;
  context?: {
    currentSite?: GeneratedSite;
  };
}

export interface GenerationResponse {
  success: boolean;
  site?: GeneratedSite;
  error?: string;
  streamId?: string;
}

// -----------------------------------------------------------------------------
// Preview Types
// -----------------------------------------------------------------------------

export interface PreviewState {
  isLoading: boolean;
  currentSite: GeneratedSite | null;
  viewportSize: 'desktop' | 'tablet' | 'mobile';
  zoom: number;
}

// -----------------------------------------------------------------------------
// API Types
// -----------------------------------------------------------------------------

export interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface StreamChunk {
  type: 'content' | 'code' | 'status' | 'error' | 'done';
  data: string;
  metadata?: Record<string, unknown>;
}

// -----------------------------------------------------------------------------
// WebSocket Types
// -----------------------------------------------------------------------------

export interface WSMessage {
  type: 'subscribe' | 'unsubscribe' | 'message' | 'ping' | 'pong';
  channel?: string;
  payload?: unknown;
}

export interface WSResponse {
  type: 'subscribed' | 'unsubscribed' | 'message' | 'error' | 'pong';
  channel?: string;
  payload?: unknown;
  error?: string;
}
