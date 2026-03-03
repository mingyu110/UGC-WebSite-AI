// =============================================================================
// UGC AI Demo - Chat Stream API Route (SSE)
// =============================================================================

import { NextRequest } from 'next/server';

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.MOCK_MODE === 'true';

// Configure route for long-running requests (up to 10 minutes)
// maxDuration works with Vercel, for local dev keep-alive handles timeout
export const maxDuration = 600; // 10 minutes in seconds

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, message, code } = body;

    if (!sessionId || !message) {
      return new Response(
        JSON.stringify({ error: 'Missing sessionId or message' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const encoder = new TextEncoder();

    if (MOCK_MODE) {
      const stream = createMockChatStream(encoder, message);
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
      });
    }

    // Build payload, include code for state recovery if present
    const payload: Record<string, unknown> = { sessionId, message };
    if (code) {
      payload.code = code;
    }

    const stream = new ReadableStream({
      async start(controller) {
        // Keep-alive interval to prevent connection timeout during long operations
        let keepAliveInterval: NodeJS.Timeout | null = null;

        try {
          // Start keep-alive ping immediately and every 15 seconds
          // This keeps the connection alive while waiting for backend response
          keepAliveInterval = setInterval(() => {
            try {
              controller.enqueue(encoder.encode(`: keep-alive ${Date.now()}\n\n`));
            } catch {
              // Controller might be closed
            }
          }, 15000);

          // Send initial keep-alive immediately
          controller.enqueue(encoder.encode(`: keep-alive start\n\n`));

          const response = await fetch(`${AGENT_URL}/api/chat/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
          });

          if (!response.ok) {
            const errorData = `data: ${JSON.stringify({ type: 'error', data: 'Agent request failed' })}\n\n`;
            controller.enqueue(encoder.encode(errorData));
            controller.close();
            return;
          }

          const reader = response.body?.getReader();
          if (!reader) {
            const errorData = `data: ${JSON.stringify({ type: 'error', data: 'No response body' })}\n\n`;
            controller.enqueue(encoder.encode(errorData));
            controller.close();
            return;
          }

          const decoder = new TextDecoder();
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            controller.enqueue(encoder.encode(decoder.decode(value, { stream: true })));
          }
          controller.close();
        } catch (error) {
          console.error('Stream error:', error);
          const errorData = `data: ${JSON.stringify({ type: 'error', data: 'Stream error' })}\n\n`;
          controller.enqueue(encoder.encode(errorData));
          controller.close();
        } finally {
          if (keepAliveInterval) {
            clearInterval(keepAliveInterval);
          }
        }
      },
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Chat stream API error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

function createMockChatStream(encoder: TextEncoder, message: string): ReadableStream {
  const lower = message.toLowerCase();
  let response = '我可以帮您创建网站。请描述您想要的网站类型。';
  if (lower.includes('帮助') || lower.includes('help')) {
    response = '我是AI建站助手。您可以描述想要的网站，我会为您生成。';
  }

  const chars = response.split('');
  let index = 0;

  return new ReadableStream({
    async pull(controller) {
      if (index < chars.length) {
        const chunk = `data: ${JSON.stringify({ type: 'content', data: chars[index] })}\n\n`;
        controller.enqueue(encoder.encode(chunk));
        index++;
        await new Promise(r => setTimeout(r, 30));
      } else {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', data: '' })}\n\n`));
        controller.close();
      }
    },
  });
}
