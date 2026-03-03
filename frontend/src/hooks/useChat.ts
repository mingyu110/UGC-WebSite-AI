// =============================================================================
// UGC AI Demo - Chat Hook
// =============================================================================

'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatMessage, StreamChunk } from '@/types';
import { generateId } from '@/lib/utils';
import { streamChatResponse } from '@/lib/api';

// Throttle helper to batch state updates
function useThrottledValue<T>(value: T, delay: number): T {
  const [throttledValue, setThrottledValue] = useState(value);
  const lastUpdate = useRef(Date.now());

  useEffect(() => {
    const now = Date.now();
    if (now - lastUpdate.current >= delay) {
      setThrottledValue(value);
      lastUpdate.current = now;
    } else {
      const timer = setTimeout(() => {
        setThrottledValue(value);
        lastUpdate.current = Date.now();
      }, delay - (now - lastUpdate.current));
      return () => clearTimeout(timer);
    }
  }, [value, delay]);

  return throttledValue;
}

interface UseChatOptions {
  sessionId: string;
  onSiteGenerated?: (html: string, css: string, javascript?: string) => void;
}

interface UseChatReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
}

export function useChat({ sessionId, onSiteGenerated }: UseChatOptions): UseChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  // Track latest generated code to send back to backend for state recovery
  const generatedCodeRef = useRef<Record<string, string> | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      setError(null);
      setIsLoading(true);

      // Add user message
      const userMessage: ChatMessage = {
        id: generateId(),
        role: 'user',
        content,
        timestamp: new Date(),
      };

      // Add placeholder for assistant message
      const assistantMessage: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        metadata: { status: 'streaming' },
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);

      try {
        let fullContent = '';
        let generatedCode = '';
        let lastUpdateTime = Date.now();
        const UPDATE_INTERVAL = 100; // Throttle updates to 100ms

        for await (const chunk of streamChatResponse(sessionId, content, generatedCodeRef.current ?? undefined)) {
          switch (chunk.type) {
            case 'content':
              fullContent += chunk.data;
              // Throttle state updates to avoid React maximum update depth error
              const now = Date.now();
              if (now - lastUpdateTime >= UPDATE_INTERVAL) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessage.id
                      ? { ...msg, content: fullContent }
                      : msg
                  )
                );
                lastUpdateTime = now;
              }
              break;

            case 'code':
              generatedCode = chunk.data;
              // Parse and notify about generated code
              if (onSiteGenerated && generatedCode) {
                try {
                  const parsed = JSON.parse(generatedCode);
                  const html = parsed.html || '';
                  const css = parsed.css || '';
                  const js = parsed.javascript || '';
                  // Save files for state recovery on subsequent requests
                  if (parsed.files) {
                    generatedCodeRef.current = parsed.files;
                  }
                  onSiteGenerated(html, css, js);
                } catch {
                  // Code might be streamed incrementally
                }
              }
              break;

            case 'status':
              // Update status in metadata
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessage.id
                    ? {
                        ...msg,
                        metadata: { ...msg.metadata, status: chunk.data as 'pending' | 'streaming' | 'complete' | 'error' },
                      }
                    : msg
                )
              );
              break;

            case 'error':
              setError(chunk.data);
              break;

            case 'done':
              // Final update with complete content
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === assistantMessage.id
                    ? {
                        ...msg,
                        content: fullContent,  // Ensure final content is set
                        metadata: {
                          ...msg.metadata,
                          status: 'complete',
                          generatedCode: generatedCode || undefined,
                        },
                      }
                    : msg
                )
              );
              break;
          }
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : '发送消息失败';
        setError(errorMessage);
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === assistantMessage.id
              ? {
                  ...msg,
                  content: '抱歉，处理您的请求时出现错误。请重试。',
                  metadata: { ...msg.metadata, status: 'error' },
                }
              : msg
          )
        );
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading, onSiteGenerated]
  );

  const clearMessages = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  };
}
