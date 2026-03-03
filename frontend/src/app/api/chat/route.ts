// =============================================================================
// UGC AI Demo - Chat API Route
// =============================================================================

import { NextRequest, NextResponse } from 'next/server';

const AGENT_URL = process.env.AGENT_URL || 'http://localhost:8000';
const MOCK_MODE = process.env.MOCK_MODE === 'true';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { sessionId, message } = body;

    if (!sessionId || !message) {
      return NextResponse.json(
        { error: 'Missing sessionId or message' },
        { status: 400 }
      );
    }

    if (MOCK_MODE) {
      return NextResponse.json({
        message: getMockChatResponse(message),
        sessionId,
      });
    }

    const response = await fetch(`${AGENT_URL}/api/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId, message }),
    });

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.message || 'Agent request failed' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}

function getMockChatResponse(message: string): string {
  const lower = message.toLowerCase();
  if (lower.includes('帮助') || lower.includes('help')) {
    return '我是AI建站助手。您可以描述想要的网站，我会为您生成。';
  }
  return '我可以帮您创建网站。请描述您想要的网站类型。';
}
