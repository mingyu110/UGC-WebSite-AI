// =============================================================================
// UGC AI Demo - Generate API Route
// =============================================================================

import { NextRequest, NextResponse } from 'next/server';
import { getMockTemplate } from '@/lib/mock-templates';
import { generateId } from '@/lib/utils';

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.MOCK_MODE === 'true';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, prompt, context } = body;

    if (!sessionId || !prompt) {
      return NextResponse.json(
        { error: 'Missing sessionId or prompt' },
        { status: 400 }
      );
    }

    if (MOCK_MODE) {
      const template = getMockTemplate(prompt);
      return NextResponse.json({
        success: true,
        site: {
          id: generateId(),
          html: template.html,
          css: template.css,
          javascript: template.javascript,
          version: 1,
          createdAt: new Date(),
          lastModified: new Date(),
        },
      });
    }

    const response = await fetch(`${AGENT_URL}/api/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, prompt, context }),
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { success: false, error: error.message || 'Generation failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json({ success: true, ...data });
  } catch (error) {
    console.error('Generate API error:', error);
    return NextResponse.json(
      { success: false, error: 'Internal server error' },
      { status: 500 }
    );
  }
}
