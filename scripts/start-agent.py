#!/usr/bin/env python3
"""
UGC AI Demo - Agent HTTP Server

Starts the WebsiteGeneratorAgent as an HTTP service with SSE streaming support.
"""

import asyncio
import json
import os
import sys
import uuid
from typing import AsyncGenerator

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    print("Missing dependencies. Install with: pip install fastapi uvicorn")
    sys.exit(1)

from agent import WebsiteGeneratorAgent

app = FastAPI(title="UGC AI Demo Agent API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
sessions: dict[str, WebsiteGeneratorAgent] = {}


def get_or_create_agent(session_id: str) -> WebsiteGeneratorAgent:
    if session_id not in sessions:
        sessions[session_id] = WebsiteGeneratorAgent(session_id=session_id)
    return sessions[session_id]


class ChatRequest(BaseModel):
    sessionId: str
    message: str


class GenerateRequest(BaseModel):
    sessionId: str
    prompt: str
    context: dict | None = None


class EditRequest(BaseModel):
    sessionId: str
    elementId: str
    selector: str
    editType: str
    previousValue: str | None = None
    newValue: str | None = None
    naturalLanguageRequest: str | None = None


async def sse_stream(data_generator: AsyncGenerator) -> AsyncGenerator[str, None]:
    """Convert data generator to SSE format."""
    async for chunk in data_generator:
        yield f"data: {json.dumps(chunk)}\n\n"


@app.post("/api/chat")
async def chat(request: ChatRequest):
    agent = get_or_create_agent(request.sessionId)
    result = await agent.continue_conversation(request.message)
    return {"message": result.get("raw_output", str(result)), "sessionId": request.sessionId}


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    async def generate():
        agent = get_or_create_agent(request.sessionId)
        yield {"type": "status", "data": "processing"}
        result = await agent.continue_conversation(request.message)
        output = result.get("raw_output", str(result))
        for char in output:
            yield {"type": "content", "data": char}
            await asyncio.sleep(0.02)
        yield {"type": "done", "data": ""}

    return StreamingResponse(
        sse_stream(generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/generate")
async def generate(request: GenerateRequest):
    agent = get_or_create_agent(request.sessionId)
    result = await agent.generate_website(request.prompt)
    return {"success": True, "site": result.get("code"), "message": "Generated"}


@app.post("/api/generate/stream")
async def generate_stream(request: GenerateRequest):
    async def generate():
        agent = get_or_create_agent(request.sessionId)
        yield {"type": "status", "data": "generating"}
        result = await agent.generate_website(request.prompt)
        if result.get("code"):
            yield {"type": "code", "data": json.dumps(result["code"])}
        yield {"type": "done", "data": ""}

    return StreamingResponse(
        sse_stream(generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/edit")
async def edit(request: EditRequest):
    agent = get_or_create_agent(request.sessionId)
    edit_prompt = f"Edit element {request.selector}: {request.naturalLanguageRequest or request.newValue}"
    result = await agent.continue_conversation(edit_prompt)
    return {"success": True, "updatedSite": result.get("code")}


@app.post("/api/edit/stream")
async def edit_stream(request: EditRequest):
    async def generate():
        agent = get_or_create_agent(request.sessionId)
        yield {"type": "status", "data": "editing"}
        edit_prompt = f"Edit element {request.selector}: {request.naturalLanguageRequest or request.newValue}"
        result = await agent.continue_conversation(edit_prompt)
        if result.get("code"):
            yield {"type": "code", "data": json.dumps(result["code"])}
        yield {"type": "done", "data": ""}

    return StreamingResponse(
        sse_stream(generate()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "sessions": len(sessions)}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting Agent API server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
