// =============================================================================
// UGC AI Demo - API Client (Simplified)
// =============================================================================

import {
  ChatMessage,
  GenerationRequest,
  GenerationResponse,
  StreamChunk,
} from '@/types';
import { parseSSEStream } from './utils';

const API_BASE = '/api';

/**
 * Send a chat message and get AI response
 */
export async function sendChatMessage(
  sessionId: string,
  message: string
): Promise<Response> {
  return fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, message }),
  });
}

/**
 * Stream chat response with SSE
 */
export async function* streamChatResponse(
  sessionId: string,
  message: string,
  code?: Record<string, string>,
): AsyncGenerator<StreamChunk> {
  const body: Record<string, unknown> = { sessionId, message };
  if (code && Object.keys(code).length > 0) {
    body.code = code;
  }

  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  for await (const data of parseSSEStream(reader)) {
    try {
      yield JSON.parse(data) as StreamChunk;
    } catch {
      yield { type: 'content', data };
    }
  }
}

/**
 * Generate website from prompt
 */
export async function generateSite(
  request: GenerationRequest
): Promise<GenerationResponse> {
  const response = await fetch(`${API_BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    return { success: false, error: error.message };
  }

  return response.json();
}

/**
 * Stream website generation with SSE
 */
export async function* streamSiteGeneration(
  request: GenerationRequest
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/generate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  for await (const data of parseSSEStream(reader)) {
    try {
      yield JSON.parse(data) as StreamChunk;
    } catch {
      yield { type: 'content', data };
    }
  }
}

/**
 * Get chat history
 */
export async function getChatHistory(sessionId: string): Promise<ChatMessage[]> {
  const response = await fetch(`${API_BASE}/chat/history/${sessionId}`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}
