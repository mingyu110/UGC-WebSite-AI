// =============================================================================
// UGC AI Demo - Main Page (Simplified: AI Generation + Deploy)
// =============================================================================

'use client';

import { useState, useEffect, useCallback } from 'react';
import { Header, SplitLayout } from '@/components/Layout';
import { ChatPanel } from '@/components/Chat';
import { PreviewPanel } from '@/components/Preview';
import { useChat, usePreview } from '@/hooks';
import { generateId } from '@/lib/utils';

export default function Home() {
  const [sessionId, setSessionId] = useState<string>('');

  // Initialize session ID
  useEffect(() => {
    setSessionId(generateId());
  }, []);

  // Preview hook (simplified - no edit mode)
  const {
    previewState,
    iframeRef,
    updateSite,
    setViewportSize,
    refreshPreview,
  } = usePreview({});

  // Handle site update
  const handleSiteUpdate = useCallback(
    (html: string, css: string, javascript?: string) => {
      updateSite(html, css, javascript);
    },
    [updateSite]
  );

  // Chat hook with site generation callback
  const { messages, isLoading, sendMessage, clearMessages } = useChat({
    sessionId,
    onSiteGenerated: (html, css, javascript) => {
      handleSiteUpdate(html, css, javascript);
    },
  });

  // Handle new session
  const handleNewSession = useCallback(() => {
    setSessionId(generateId());
    clearMessages();
    updateSite('', '');
  }, [clearMessages, updateSite]);

  // Handle suggestion clicks
  useEffect(() => {
    const handleSuggestionClick = (event: CustomEvent<string>) => {
      sendMessage(event.detail);
    };

    window.addEventListener(
      'suggestion-click',
      handleSuggestionClick as EventListener
    );
    return () =>
      window.removeEventListener(
        'suggestion-click',
        handleSuggestionClick as EventListener
      );
  }, [sendMessage]);

  return (
    <div className="h-screen flex flex-col bg-gray-50 dark:bg-gray-950">
      <Header
        onNewSession={handleNewSession}
      />

      <div className="flex-1 overflow-hidden">
        <SplitLayout
          left={
            <ChatPanel
              messages={messages}
              isLoading={isLoading}
              onSendMessage={sendMessage}
            />
          }
          right={
            <PreviewPanel
              previewState={previewState}
              iframeRef={iframeRef}
              onViewportChange={setViewportSize}
              onRefresh={refreshPreview}
            />
          }
        />
      </div>
    </div>
  );
}
