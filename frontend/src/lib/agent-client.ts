// =============================================================================
// UGC AI Demo - Agent Client (Simplified)
// =============================================================================

import { GeneratedSite, StreamChunk } from '@/types';
import { generateId, parseSSEStream } from './utils';
import { getMockTemplate } from './mock-templates';

// Configuration
const AGENT_URL = process.env.NEXT_PUBLIC_AGENT_URL || 'http://localhost:8000';
const USE_MOCK = process.env.NEXT_PUBLIC_USE_MOCK === 'true';
const MAX_RETRIES = 3;
const RETRY_DELAY = 1000;

export interface AgentResponse {
  success: boolean;
  message?: string;
  site?: GeneratedSite;
  error?: string;
  cancelled?: boolean;
}

export interface AgentClientOptions {
  useMock?: boolean;
  agentUrl?: string;
  maxRetries?: number;
  retryDelay?: number;
}

export interface RequestOptions {
  signal?: AbortSignal;
  onStream?: (chunk: StreamChunk) => void;
  onRetry?: (attempt: number, error: Error) => void;
}

/**
 * Agent Client - handles communication with the Python Agent backend
 * Features: Mock mode, retry logic, request cancellation, streaming
 */
export class AgentClient {
  private useMock: boolean;
  private agentUrl: string;
  private maxRetries: number;
  private retryDelay: number;

  constructor(options: AgentClientOptions = {}) {
    this.useMock = options.useMock ?? USE_MOCK;
    this.agentUrl = options.agentUrl ?? AGENT_URL;
    this.maxRetries = options.maxRetries ?? MAX_RETRIES;
    this.retryDelay = options.retryDelay ?? RETRY_DELAY;
  }

  /**
   * Generate a website from natural language prompt
   */
  async generateSite(
    sessionId: string,
    prompt: string,
    options: RequestOptions = {}
  ): Promise<AgentResponse> {
    if (this.useMock) {
      return this.mockGenerateSite(prompt, options);
    }

    return this.executeWithRetry(
      () => this.doGenerateSite(sessionId, prompt, options),
      options
    );
  }

  /**
   * Send a chat message and get AI response
   */
  async chat(
    sessionId: string,
    message: string,
    options: RequestOptions = {}
  ): Promise<AgentResponse> {
    if (this.useMock) {
      return this.mockChat(message, options);
    }

    return this.executeWithRetry(
      () => this.doChat(sessionId, message, options),
      options
    );
  }

  /**
   * Check if the agent backend is available
   */
  async healthCheck(): Promise<boolean> {
    if (this.useMock) return true;

    try {
      const response = await fetch(`${this.agentUrl}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  // ---------------------------------------------------------------------------
  // Core Request Methods
  // ---------------------------------------------------------------------------

  private async doGenerateSite(
    sessionId: string,
    prompt: string,
    options: RequestOptions
  ): Promise<AgentResponse> {
    const response = await fetch(`${this.agentUrl}/api/generate/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, prompt }),
      signal: options.signal,
    });

    if (!response.ok) {
      throw new AgentError(`HTTP ${response.status}`, response.status);
    }

    return this.handleStreamResponse(response, options);
  }

  private async doChat(
    sessionId: string,
    message: string,
    options: RequestOptions
  ): Promise<AgentResponse> {
    const response = await fetch(`${this.agentUrl}/api/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, message }),
      signal: options.signal,
    });

    if (!response.ok) {
      throw new AgentError(`HTTP ${response.status}`, response.status);
    }

    return this.handleStreamResponse(response, options);
  }

  // ---------------------------------------------------------------------------
  // Retry Logic
  // ---------------------------------------------------------------------------

  private async executeWithRetry(
    operation: () => Promise<AgentResponse>,
    options: RequestOptions
  ): Promise<AgentResponse> {
    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        // Check if request was cancelled
        if (options.signal?.aborted) {
          return { success: false, cancelled: true };
        }

        return await operation();
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        // Don't retry if request was cancelled
        if (error instanceof DOMException && error.name === 'AbortError') {
          return { success: false, cancelled: true };
        }

        // Don't retry on client errors (4xx)
        if (error instanceof AgentError && error.statusCode >= 400 && error.statusCode < 500) {
          return { success: false, error: lastError.message };
        }

        // Notify about retry
        if (attempt < this.maxRetries) {
          options.onRetry?.(attempt, lastError);
          await this.delay(this.retryDelay * attempt);
        }
      }
    }

    return {
      success: false,
      error: lastError?.message || 'Request failed after retries',
    };
  }

  // ---------------------------------------------------------------------------
  // Stream Handling
  // ---------------------------------------------------------------------------

  private async handleStreamResponse(
    response: Response,
    options: RequestOptions,
    baseVersion: number = 0
  ): Promise<AgentResponse> {
    const reader = response.body?.getReader();
    if (!reader) {
      return { success: false, error: 'No response body' };
    }

    let site: GeneratedSite | undefined;
    let message = '';

    try {
      for await (const data of parseSSEStream(reader)) {
        // Check for cancellation
        if (options.signal?.aborted) {
          reader.cancel();
          return { success: false, cancelled: true };
        }

        try {
          const chunk = JSON.parse(data) as StreamChunk;
          options.onStream?.(chunk);

          switch (chunk.type) {
            case 'code':
              if (chunk.data) {
                const parsed = JSON.parse(chunk.data);
                site = {
                  id: generateId(),
                  html: parsed.html || '',
                  css: parsed.css || '',
                  javascript: parsed.javascript,
                  version: baseVersion + 1,
                  createdAt: new Date(),
                  lastModified: new Date(),
                };
              }
              break;

            case 'content':
              message += chunk.data;
              break;

            case 'error':
              return { success: false, error: chunk.data };
          }
        } catch {
          // Non-JSON chunk, treat as content
          message += data;
          options.onStream?.({ type: 'content', data });
        }
      }
    } finally {
      reader.releaseLock();
    }

    return { success: true, message, site };
  }

  // ---------------------------------------------------------------------------
  // Mock Methods
  // ---------------------------------------------------------------------------

  private async mockGenerateSite(
    prompt: string,
    options: RequestOptions
  ): Promise<AgentResponse> {
    const template = getMockTemplate(prompt);
    const responseText = `好的，我来为您创建${template.name}。`;

    // Simulate streaming with cancellation support
    for (const char of responseText) {
      if (options.signal?.aborted) {
        return { success: false, cancelled: true };
      }
      await this.delay(30);
      options.onStream?.({ type: 'content', data: char });
    }

    await this.delay(500);
    options.onStream?.({ type: 'status', data: 'generating' });

    if (options.signal?.aborted) {
      return { success: false, cancelled: true };
    }

    await this.delay(1000);

    const site: GeneratedSite = {
      id: generateId(),
      html: template.html,
      css: template.css,
      javascript: template.javascript,
      version: 1,
      createdAt: new Date(),
      lastModified: new Date(),
    };

    options.onStream?.({
      type: 'code',
      data: JSON.stringify({ html: site.html, css: site.css }),
    });

    await this.delay(200);
    options.onStream?.({ type: 'done', data: '' });

    return { success: true, message: responseText, site };
  }

  private async mockChat(
    message: string,
    options: RequestOptions
  ): Promise<AgentResponse> {
    const responses: Record<string, string> = {
      default: '我可以帮您创建网站。请描述您想要的网站类型，例如"创建一个咖啡店的落地页"。',
      help: '我是AI建站助手。您可以告诉我想要什么样的网站，我会为您生成。',
    };

    const responseText = message.includes('帮助') || message.includes('help')
      ? responses.help
      : responses.default;

    for (const char of responseText) {
      if (options.signal?.aborted) {
        return { success: false, cancelled: true };
      }
      await this.delay(25);
      options.onStream?.({ type: 'content', data: char });
    }

    options.onStream?.({ type: 'done', data: '' });

    return { success: true, message: responseText };
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

/**
 * Custom error class for Agent errors
 */
export class AgentError extends Error {
  constructor(
    message: string,
    public statusCode: number = 0
  ) {
    super(message);
    this.name = 'AgentError';
  }
}

// Export singleton instance
export const agentClient = new AgentClient();
