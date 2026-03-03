// =============================================================================
// UGC AI Demo - Generate Stream API Route (SSE)
// =============================================================================

import { NextRequest } from 'next/server';
import { getMockTemplate } from '@/lib/mock-templates';
import { generateId } from '@/lib/utils';

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.MOCK_MODE === 'true';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, prompt, context } = body;

    if (!sessionId || !prompt) {
      return new Response(
        JSON.stringify({ error: 'Missing sessionId or prompt' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const encoder = new TextEncoder();

    if (MOCK_MODE) {
      const stream = createMockGenerateStream(encoder, prompt);
      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
      });
    }

    const stream = new ReadableStream({
      async start(controller) {
        try {
          const response = await fetch(`${AGENT_URL}/api/generate/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sessionId, prompt, context }),
          });

          if (!response.ok) {
            const errorData = `data: ${JSON.stringify({ type: 'error', data: 'Generation failed' })}\n\n`;
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
          console.error('Generate stream error:', error);
          const errorData = `data: ${JSON.stringify({ type: 'error', data: 'Stream error' })}\n\n`;
          controller.enqueue(encoder.encode(errorData));
          controller.close();
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
    console.error('Generate stream API error:', error);
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

function createMockGenerateStream(encoder: TextEncoder, prompt: string): ReadableStream {
  const template = getMockTemplate(prompt);
  const message = `好的，我来为您创建${template.name}。`;
  const chars = message.split('');
  let phase = 0;
  let charIndex = 0;

  return new ReadableStream({
    async pull(controller) {
      if (phase === 0) {
        // Stream message characters
        if (charIndex < chars.length) {
          const chunk = `data: ${JSON.stringify({ type: 'content', data: chars[charIndex] })}\n\n`;
          controller.enqueue(encoder.encode(chunk));
          charIndex++;
          await new Promise(r => setTimeout(r, 30));
        } else {
          phase = 1;
          await new Promise(r => setTimeout(r, 500));
        }
      } else if (phase === 1) {
        // Send status
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'status', data: 'generating' })}\n\n`));
        phase = 2;
        await new Promise(r => setTimeout(r, 800));
      } else if (phase === 2) {
        // Send code
        const site = {
          id: generateId(),
          html: template.html,
          css: template.css,
          javascript: template.javascript,
          version: 1,
          createdAt: new Date().toISOString(),
          lastModified: new Date().toISOString(),
        };
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'code', data: JSON.stringify(site) })}\n\n`));
        phase = 3;
      } else {
        // Done
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'done', data: '' })}\n\n`));
        controller.close();
      }
    },
  });
}
