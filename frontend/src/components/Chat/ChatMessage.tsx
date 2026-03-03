// =============================================================================
// UGC AI Demo - Chat Message Component
// =============================================================================

'use client';

import { useMemo, useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import { ChatMessage as ChatMessageType } from '@/types';
import { cn, formatDate } from '@/lib/utils';

interface ChatMessageProps {
  message: ChatMessageType;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.metadata?.status === 'streaming';
  const isError = message.metadata?.status === 'error';

  return (
    <div
      className={cn(
        'flex w-full mb-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      {/* Avatar for assistant */}
      {!isUser && (
        <div className="flex-shrink-0 mr-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <AIIcon />
          </div>
        </div>
      )}

      <div
        className={cn(
          'max-w-[80%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100',
          isError && !isUser && 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
        )}
      >
        {/* Message Content */}
        <div className={cn(
          'break-words',
          isUser ? 'text-white' : 'prose prose-sm dark:prose-invert max-w-none'
        )}>
          {isUser ? (
            <p className="whitespace-pre-wrap m-0">{message.content}</p>
          ) : (
            <MarkdownContent
              content={message.content}
              isStreaming={isStreaming}
            />
          )}
        </div>

        {/* Timestamp and Status */}
        <div className="flex items-center justify-between mt-2">
          <div
            className={cn(
              'text-xs opacity-70',
              isUser ? 'text-blue-100' : 'text-gray-500 dark:text-gray-400'
            )}
          >
            {formatDate(message.timestamp)}
          </div>

          {/* Status indicator for assistant messages */}
          {!isUser && (
            <div className="flex items-center gap-1">
              {isStreaming && (
                <span className="flex items-center gap-1 text-xs text-blue-500">
                  <StreamingIndicator />
                  <span>生成中</span>
                </span>
              )}
              {isError && (
                <span className="text-xs text-red-500 flex items-center gap-1">
                  <ErrorIcon />
                  发送失败
                </span>
              )}
              {message.metadata?.status === 'complete' && message.metadata?.generatedCode && (
                <span className="text-xs text-green-600 dark:text-green-400 flex items-center gap-1">
                  <CheckIcon />
                  已生成
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Avatar for user */}
      {isUser && (
        <div className="flex-shrink-0 ml-3">
          <div className="w-8 h-8 rounded-full bg-gray-600 flex items-center justify-center">
            <UserIcon />
          </div>
        </div>
      )}
    </div>
  );
}

// Markdown content renderer with streaming cursor
function MarkdownContent({
  content,
  isStreaming
}: {
  content: string;
  isStreaming?: boolean;
}) {
  const [displayedContent, setDisplayedContent] = useState(content);

  // Smooth content update for streaming
  useEffect(() => {
    setDisplayedContent(content);
  }, [content]);

  // Memoize markdown components for performance
  const components = useMemo(() => ({
    // Custom code block renderer
    code: ({ className, children, ...props }: React.ComponentPropsWithoutRef<'code'> & { className?: string }) => {
      const match = /language-(\w+)/.exec(className || '');
      const isInline = !match;

      if (isInline) {
        return (
          <code
            className="px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-700 text-sm font-mono"
            {...props}
          >
            {children}
          </code>
        );
      }

      return (
        <div className="relative group my-3">
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyButton code={String(children).replace(/\n$/, '')} />
          </div>
          {match && (
            <div className="absolute top-2 left-3 text-xs text-gray-400 font-mono">
              {match[1]}
            </div>
          )}
          <pre className="!mt-0 !mb-0 pt-8 rounded-lg overflow-x-auto bg-gray-900 dark:bg-gray-950">
            <code className={cn(className, 'text-sm')} {...props}>
              {children}
            </code>
          </pre>
        </div>
      );
    },
    // Custom paragraph renderer
    p: ({ children, ...props }: React.ComponentPropsWithoutRef<'p'>) => (
      <p className="mb-2 last:mb-0" {...props}>{children}</p>
    ),
    // Custom list renderers
    ul: ({ children, ...props }: React.ComponentPropsWithoutRef<'ul'>) => (
      <ul className="list-disc list-inside mb-2 space-y-1" {...props}>{children}</ul>
    ),
    ol: ({ children, ...props }: React.ComponentPropsWithoutRef<'ol'>) => (
      <ol className="list-decimal list-inside mb-2 space-y-1" {...props}>{children}</ol>
    ),
    // Custom link renderer
    a: ({ children, href, ...props }: React.ComponentPropsWithoutRef<'a'>) => (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="text-blue-600 dark:text-blue-400 hover:underline"
        {...props}
      >
        {children}
      </a>
    ),
    // Custom blockquote renderer
    blockquote: ({ children, ...props }: React.ComponentPropsWithoutRef<'blockquote'>) => (
      <blockquote
        className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 my-2 italic text-gray-600 dark:text-gray-400"
        {...props}
      >
        {children}
      </blockquote>
    ),
  }), []);

  return (
    <div className="markdown-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeHighlight]}
        components={components}
      >
        {displayedContent}
      </ReactMarkdown>
      {isStreaming && <StreamingCursor />}
    </div>
  );
}

// Copy button for code blocks
function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for browsers without clipboard API
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="px-2 py-1 text-xs text-gray-400 hover:text-white bg-gray-800 rounded transition-colors"
      title="复制代码"
    >
      {copied ? '已复制' : '复制'}
    </button>
  );
}

// Streaming cursor animation
function StreamingCursor() {
  return (
    <span className="inline-block w-2 h-4 ml-0.5 bg-blue-500 animate-pulse rounded-sm" />
  );
}

// Streaming indicator animation
function StreamingIndicator() {
  return (
    <span className="flex gap-0.5">
      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
      <span className="w-1 h-1 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
    </span>
  );
}

// Icons
function AIIcon() {
  return (
    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
    </svg>
  );
}
