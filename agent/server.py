"""
UGC AI Website Generator HTTP API

FastAPI server providing REST endpoints for website generation.
Uses Strands Agent with AgentCore Runtime for AI-powered website creation.
"""

import asyncio
import json
import logging
import uuid
from enum import Enum
from typing import Optional, AsyncGenerator, Dict, Any, List
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

from agent.server_config import get_config
from agent.agentcore_client import AgentCoreClient, get_agentcore_client


class BusinessPhase(str, Enum):
    """Business workflow phases for website generation."""
    RECEIVING = "RECEIVING"
    PLANNING = "PLANNING"
    WAITING_CONFIRM = "WAITING_CONFIRM"
    EXECUTING = "EXECUTING"
    PREVIEWING = "PREVIEWING"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"


@dataclass
class SessionState:
    """Session state for tracking agent conversations.

    This is the SINGLE SOURCE OF TRUTH for all session state.
    AgentCore handler is stateless — all context is passed via payload
    and returned in the response, then merged back here.
    """
    session_id: str
    business_phase: BusinessPhase = BusinessPhase.RECEIVING
    generated_code: Dict[str, str] = field(default_factory=dict)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    # Conversation history sent to AgentCore for LLM context
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    deployment_url: Optional[str] = None
    deployment_type: Optional[str] = None

    def add_turn(self, role: str, content: str) -> None:
        """Add a conversation turn and keep history bounded."""
        self.conversation_history.append({"role": role, "content": content})
        # Keep last 20 turns to avoid payload bloat
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def build_payload_context(self) -> Dict[str, Any]:
        """Build the full context payload to send to AgentCore.

        This is the key method — it packages ALL state so the handler
        can be completely stateless.
        """
        ctx: Dict[str, Any] = {
            "phase": self.business_phase.value,
            "conversation_history": self.conversation_history,
        }
        if self.generated_code:
            ctx["code"] = self.generated_code
        if self.deployment_url:
            ctx["deployment_url"] = self.deployment_url
        if self.deployment_type:
            ctx["deployment_type"] = self.deployment_type
        return ctx

    def sync_from_response(self, metadata: Optional[Dict[str, Any]]) -> None:
        """Merge state returned by AgentCore back into this session."""
        if not metadata:
            return
        # Sync code
        code = metadata.get("code")
        if code:
            files = code.get("files") if isinstance(code, dict) and "files" in code else code
            if isinstance(files, dict):
                self.generated_code.update(files)
        # Sync deployment info
        if metadata.get("deployment_url"):
            self.deployment_url = metadata["deployment_url"]
            self.deployment_type = metadata.get("deployment_type", self.deployment_type)
        # Sync phase if handler advanced it (e.g. after deploy)
        if metadata.get("phase"):
            try:
                self.business_phase = BusinessPhase(metadata["phase"])
            except ValueError:
                pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "business_phase": self.business_phase.value,
            "has_code": bool(self.generated_code),
            "code_files": list(self.generated_code.keys()),
            "deployment_url": self.deployment_url,
        }

logger = logging.getLogger(__name__)

app = FastAPI(
    title="UGC AI Website Generator API",
    description="AI-powered website generation with deployment to AWS",
    version="1.0.0",
)
config = get_config()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session storage
_sessions: Dict[str, SessionState] = {}


# AgentCore Runtime client (lazy initialized)
_agentcore_client: AgentCoreClient = None


def get_client() -> AgentCoreClient:
    """Get the AgentCore Runtime client."""
    global _agentcore_client
    if _agentcore_client is None:
        _agentcore_client = get_agentcore_client()
    return _agentcore_client


def _extract_code_from_text(text: str, session: SessionState) -> None:
    """
    Extract code blocks from raw LLM text response into session.generated_code.

    This is the server-side fallback when AgentCore returns plain text
    instead of structured JSON (e.g. during streaming or format mismatch).
    """
    import re

    # Pattern 1: ```language:filename or ```language filename
    named_blocks = re.findall(
        r'```(\w+)(?::|[\s]+)([^\s\n]+\.\w+)\s*\n([\s\S]*?)```',
        text
    )
    for lang, filename, content in named_blocks:
        session.generated_code[filename] = content.strip()

    # Pattern 2: ```language with // filename.ext comment on first line
    comment_named = re.findall(
        r'```(\w+)\s*\n\s*(?://|#|/\*)\s*(\S+\.\w+)[^\n]*\n([\s\S]*?)```',
        text
    )
    for lang, filename, content in comment_named:
        if filename not in session.generated_code:
            session.generated_code[filename] = content.strip()

    # Pattern 3: Auto-detect by language tag
    if "index.html" not in session.generated_code:
        html_match = re.search(r'```html\s*\n([\s\S]*?)```', text)
        if html_match:
            session.generated_code["index.html"] = html_match.group(1).strip()

    if "styles.css" not in session.generated_code:
        css_match = re.search(r'```css\s*\n([\s\S]*?)```', text)
        if css_match:
            session.generated_code["styles.css"] = css_match.group(1).strip()

    if "main.js" not in session.generated_code:
        js_matches = re.findall(r'```(?:javascript|js)\s*\n([\s\S]*?)```', text)
        for code in js_matches:
            code = code.strip()
            if code in session.generated_code.values():
                continue
            server_indicators = ['express()', 'app.listen', 'http.createserver',
                                 'require(\'express', 'require("express']
            if any(ind in code.lower() for ind in server_indicators):
                session.generated_code.setdefault("server.js", code)
            else:
                session.generated_code.setdefault("main.js", code)

    # Pattern 4: Detect single-file full HTML (contains <style> and/or <script> inline)
    # Some LLMs output a single complete HTML file instead of separate files
    if "index.html" not in session.generated_code:
        # Look for a large HTML block that contains <!DOCTYPE or <html
        full_html_match = re.search(
            r'```(?:html)?\s*\n([\s\S]*?(?:<!DOCTYPE|<html)[\s\S]*?</html>\s*)```',
            text, re.IGNORECASE
        )
        if full_html_match:
            session.generated_code["index.html"] = full_html_match.group(1).strip()

    if session.generated_code:
        logger.info(f"Extracted code files from text: {list(session.generated_code.keys())}")


def _filter_code_blocks(text: str) -> str:
    """
    Filter out large HTML/CSS/JS code blocks from AI response text.
    Only call AFTER code has been extracted into session.generated_code.
    """
    import re

    def replace_large_code_block(match):
        lang = match.group(1) or ''
        code = match.group(2)
        if lang.lower() in ['html', 'css', 'javascript', 'js', 'jsx', 'tsx', ''] and len(code) > 200:
            return ''
        return match.group(0)

    text = re.sub(r'```(\w*)\n([\s\S]*?)```', replace_large_code_block, text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def get_or_create_session(session_id: str) -> SessionState:
    """Get existing session or create new one."""
    if session_id not in _sessions:
        _sessions[session_id] = SessionState(session_id=session_id)
    return _sessions[session_id]


# Request/Response Models (support both camelCase and snake_case)
from pydantic import Field, ConfigDict


class ChatRequest(BaseModel):
    """Chat request model."""
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    message: str
    code: Optional[Dict[str, str]] = None  # Frontend can send back generated code for state recovery


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    response: str
    phase: str
    tool_calls: Optional[list] = None


class GenerateRequest(BaseModel):
    """Website generation request model."""
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    description: str = Field(default="", alias="prompt")  # Frontend sends 'prompt'
    reference_urls: Optional[list[str]] = Field(default=None, alias="referenceUrls")
    framework: str = "html"
    design_elements: Optional[dict] = Field(default=None, alias="designElements")
    auto_deploy: bool = Field(default=False, alias="autoDeploy")
    context: Optional[dict] = None


class GenerateResponse(BaseModel):
    """Website generation response model."""
    session_id: str
    deployment_id: Optional[str] = None
    url: Optional[str] = None
    framework: str
    files: list[str]
    status: str
    phase: str
    code: Optional[dict] = None
    response: Optional[str] = None  # Agent's text response (plan description)
    reference_designs: Optional[list] = None  # Extracted design elements


class DeployRequest(BaseModel):
    """Deploy request model."""
    model_config = ConfigDict(populate_by_name=True)

    session_id: str = Field(alias="sessionId")
    deployment_type: str = Field(default="static", alias="deploymentType")
    code: Optional[dict] = None


class DeployResponse(BaseModel):
    """Deploy response model."""
    deployment_id: str
    deployment_type: str
    url: str
    status: str


class DeploymentStatusRequest(BaseModel):
    """Deployment status request model."""
    model_config = ConfigDict(populate_by_name=True)

    deployment_id: str = Field(alias="deploymentId")
    deployment_type: str = Field(default="static", alias="deploymentType")


class DeploymentStatusResponse(BaseModel):
    """Deployment status response model."""
    deployment_id: str
    status: str
    url: Optional[str] = None
    files: Optional[list[str]] = None


# Health check
@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ugc-ai-website-generator",
        "active_sessions": len(_sessions),
        "config": {
            "s3_bucket": config.STATIC_S3_BUCKET,
            "cloudfront_domain": config.STATIC_CLOUDFRONT_DOMAIN,
            "lambda_function": config.DYNAMIC_LAMBDA_FUNCTION,
        }
    }


# Chat endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the website generator agent.

    Supports natural language conversation for website planning and generation.
    """
    session = get_or_create_session(request.session_id)

    try:
        # Restore code state from frontend if backend lost it (e.g. after restart)
        if request.code and not session.generated_code:
            session.generated_code = request.code
            session.business_phase = BusinessPhase.PREVIEWING
            logger.info(f"Restored session state from frontend: {list(request.code.keys())}")

        # Check phase transitions based on user input
        msg_lower = request.message.lower()
        confirm_keywords = ["确认", "开始生成", "生成代码", "proceed", "confirm", "go ahead"]
        if session.business_phase == BusinessPhase.RECEIVING:
            if any(kw in msg_lower for kw in confirm_keywords):
                logger.info("User confirmed plan, transitioning to EXECUTING phase")
                session.business_phase = BusinessPhase.EXECUTING

        # Record user turn BEFORE calling AgentCore
        session.add_turn("user", request.message)

        # Call AgentCore Runtime with FULL session context
        client = get_client()
        response = client.invoke(
            prompt=request.message,
            session_id=request.session_id,
            payload_extra=session.build_payload_context(),
        )
        result_str = response.content

        # Sync all state returned by AgentCore
        session.sync_from_response(response.metadata)

        # Fallback: if no code from metadata, try extracting from text
        if not session.generated_code:
            _extract_code_from_text(result_str, session)

        # Filter code blocks from display text AFTER extraction
        display_text = _filter_code_blocks(result_str)

        # Record assistant turn
        session.add_turn("assistant", display_text[:4000])

        # Update phase if code was generated
        if session.generated_code and session.business_phase == BusinessPhase.EXECUTING:
            session.business_phase = BusinessPhase.PREVIEWING

        return ChatResponse(
            session_id=request.session_id,
            response=display_text,
            phase=session.business_phase.value,
            tool_calls=None,
        )
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def generate_sse_events(generator: AsyncGenerator) -> AsyncGenerator[str, None]:
    """Convert async generator to SSE format."""
    async for event in generator:
        yield f"data: {json.dumps(event)}\n\n"


# Stream chat endpoint
@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream chat responses from the agent.

    Returns Server-Sent Events (SSE) for real-time streaming.
    """
    async def generate():
        session = get_or_create_session(request.session_id)

        # Restore code state from frontend if backend lost it (e.g. after restart)
        if request.code and not session.generated_code:
            session.generated_code = request.code
            session.business_phase = BusinessPhase.PREVIEWING
            logger.info(f"Restored session state from frontend: {list(request.code.keys())}")

        # Check phase transitions based on user input
        msg_lower = request.message.lower()

        # RECEIVING -> EXECUTING: User confirms the plan
        confirm_keywords = ["确认", "开始生成", "生成代码", "proceed", "confirm", "go ahead", "开始", "好的", "可以"]
        if session.business_phase == BusinessPhase.RECEIVING:
            if any(kw in msg_lower for kw in confirm_keywords):
                logger.info("User confirmed plan, transitioning to EXECUTING phase")
                session.business_phase = BusinessPhase.EXECUTING

        # PREVIEWING -> DEPLOYING: User confirms deployment
        deploy_keywords = ["部署", "deploy", "发布", "上线", "publish"]
        if session.business_phase == BusinessPhase.PREVIEWING:
            if any(kw in msg_lower for kw in deploy_keywords):
                logger.info("User requested deployment, transitioning to DEPLOYING phase")
                session.business_phase = BusinessPhase.DEPLOYING
                session.business_phase = BusinessPhase.DEPLOYING

        # Record user turn BEFORE calling AgentCore
        session.add_turn("user", request.message)

        yield {"type": "start", "session_id": request.session_id}
        yield {"type": "phase", "phase": session.business_phase.value}

        try:
            # Send progress message based on current phase
            if session.business_phase == BusinessPhase.EXECUTING:
                yield {"type": "content", "data": "正在生成网站代码...\n\n"}
                await asyncio.sleep(0.1)
            elif session.business_phase == BusinessPhase.DEPLOYING:
                yield {"type": "content", "data": "正在部署网站到云端...\n\n"}
                await asyncio.sleep(0.1)

            # Call AgentCore Runtime with FULL session context
            client = get_client()
            result_str = ""

            # Use asyncio queue to receive chunks while sending keep-alive
            chunk_queue: asyncio.Queue = asyncio.Queue()
            invocation_done = asyncio.Event()

            async def collect_chunks():
                """Background task to collect AgentCore chunks."""
                nonlocal result_str
                try:
                    async for chunk in client.invoke_stream_async(
                        prompt=request.message,
                        session_id=request.session_id,
                        payload_extra=session.build_payload_context(),
                    ):
                        result_str += chunk
                        if chunk.strip():
                            await chunk_queue.put(chunk)
                except Exception as e:
                    await chunk_queue.put({"error": str(e)})
                finally:
                    invocation_done.set()

            # Start background task for AgentCore invocation
            asyncio.create_task(collect_chunks())

            # Stream chunks with keep-alive pings
            keep_alive_interval = 20  # Send keep-alive every 20 seconds
            last_activity = asyncio.get_event_loop().time()

            while not invocation_done.is_set() or not chunk_queue.empty():
                try:
                    # Wait for chunk with timeout for keep-alive
                    chunk = await asyncio.wait_for(chunk_queue.get(), timeout=keep_alive_interval)
                    if isinstance(chunk, dict) and "error" in chunk:
                        raise Exception(chunk["error"])
                    yield {"type": "content", "data": chunk}
                    last_activity = asyncio.get_event_loop().time()
                    await asyncio.sleep(0.01)
                except asyncio.TimeoutError:
                    # Send keep-alive ping to prevent connection timeout
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_activity > keep_alive_interval - 1:
                        yield {"type": "ping", "data": ""}
                        last_activity = current_time

            if result_str:
                # Try to parse response and extract code / state updates
                try:
                    parsed = json.loads(result_str)
                    # Sync state from structured response
                    session.sync_from_response(parsed)
                    result_str = parsed.get("response", result_str)
                    # If structured response didn't contain code, try extracting from text
                    if not session.generated_code:
                        _extract_code_from_text(result_str, session)
                except json.JSONDecodeError:
                    # AgentCore returned plain text — extract code from it
                    _extract_code_from_text(result_str, session)

                # Filter code blocks from display text AFTER extraction
                result_str = _filter_code_blocks(result_str)

                # Record assistant turn
                session.add_turn("assistant", result_str[:4000])

            # Update phase if code was generated
            if session.generated_code and session.business_phase == BusinessPhase.EXECUTING:
                session.business_phase = BusinessPhase.PREVIEWING

            # Send completion message
            if session.business_phase == BusinessPhase.PREVIEWING and session.generated_code:
                yield {"type": "content", "data": "\n\n网站代码生成完成！请在右侧预览面板查看效果。\n"}
                yield {"type": "content", "data": f"生成的文件: {', '.join(session.generated_code.keys())}\n"}
            elif session.business_phase == BusinessPhase.DEPLOYED:
                yield {"type": "content", "data": "\n\n网站部署成功！\n"}

            yield {"type": "status", "data": session.business_phase.value}

            if session.generated_code:
                code_for_frontend = {
                    "html": session.generated_code.get("index.html", ""),
                    "css": session.generated_code.get("styles.css", session.generated_code.get("styles/main.css", "")),
                    "javascript": session.generated_code.get("main.js", session.generated_code.get("scripts/main.js", "")),
                    "files": session.generated_code,
                }
                yield {"type": "code", "data": json.dumps(code_for_frontend)}

            yield {"type": "done", "data": ""}

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield {"type": "error", "error": str(e)}

    return StreamingResponse(
        generate_sse_events(generate()),
        media_type="text/event-stream",
    )


# Generate endpoint
@app.post("/api/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Generate a website from description.

    Creates website code and optionally deploys to AWS.
    """
    session = get_or_create_session(request.session_id)

    try:
        # Build prompt
        prompt = f"请根据以下需求创建网站:\n\n{request.description}"
        if request.reference_urls:
            urls_str = "\n".join(f"- {url}" for url in request.reference_urls)
            prompt += f"\n\n请参考以下网站的设计风格:\n{urls_str}"
        if request.design_elements:
            prompt += f"\n\n用户风格偏好: {request.design_elements}"

        # Record user turn
        session.add_turn("user", prompt)

        # Call AgentCore Runtime with FULL session context
        client = get_client()
        payload_ctx = session.build_payload_context()
        payload_ctx["action"] = "generate"
        payload_ctx["framework"] = request.framework
        response = client.invoke(
            prompt=prompt,
            session_id=request.session_id,
            payload_extra=payload_ctx,
        )
        result_str = response.content

        # Sync state from AgentCore response
        session.sync_from_response(response.metadata)

        # Fallback: if no code from metadata, try extracting from text
        if not session.generated_code:
            _extract_code_from_text(result_str, session)

        # Filter code blocks from display text AFTER extraction
        display_text = _filter_code_blocks(result_str)

        # Record assistant turn
        session.add_turn("assistant", display_text[:4000])

        # Update phase
        if session.generated_code:
            session.business_phase = BusinessPhase.PREVIEWING

        files = list(session.generated_code.keys())

        response_data = {
            "session_id": request.session_id,
            "framework": request.framework,
            "files": files,
            "status": "generated" if session.generated_code else "processing",
            "phase": session.business_phase.value,
            "code": session.generated_code if session.generated_code else None,
            "response": display_text,
            "reference_designs": [],
        }

        return GenerateResponse(**response_data)

    except Exception as e:
        logger.error(f"Generate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Stream generate endpoint
@app.post("/api/generate/stream")
async def generate_stream(request: GenerateRequest):
    """
    Stream website generation progress.
    """
    async def stream_generate():
        session = get_or_create_session(request.session_id)

        yield {"type": "start", "session_id": request.session_id}

        try:
            yield {"type": "phase", "phase": "planning"}

            # Build prompt
            prompt = f"请根据以下需求创建网站:\n\n{request.description}"
            if request.reference_urls:
                urls_str = "\n".join(f"- {url}" for url in request.reference_urls)
                prompt += f"\n\n请参考以下网站的设计风格:\n{urls_str}"

            # Record user turn
            session.add_turn("user", prompt)

            # Call AgentCore Runtime with FULL session context
            client = get_client()
            payload_ctx = session.build_payload_context()
            payload_ctx["action"] = "generate"
            response = client.invoke(
                prompt=prompt,
                session_id=request.session_id,
                payload_extra=payload_ctx,
            )
            result_str = response.content

            # Sync state from AgentCore response
            session.sync_from_response(response.metadata)

            # Fallback: if no code from metadata, try extracting from text
            if not session.generated_code:
                _extract_code_from_text(result_str, session)

            # Filter code blocks from display text AFTER extraction
            display_text = _filter_code_blocks(result_str)

            # Record assistant turn
            session.add_turn("assistant", display_text[:4000])

            if session.generated_code:
                session.business_phase = BusinessPhase.PREVIEWING

            yield {"type": "phase", "phase": session.business_phase.value}

            if session.generated_code:
                code_for_frontend = {
                    "html": session.generated_code.get("index.html", ""),
                    "css": session.generated_code.get("styles.css", ""),
                    "javascript": session.generated_code.get("main.js", ""),
                    "files": session.generated_code,
                }
                yield {"type": "code", "code": code_for_frontend, "files": list(session.generated_code.keys())}

            yield {"type": "end", "status": "completed"}

        except Exception as e:
            logger.error(f"Generate stream error: {e}")
            yield {"type": "error", "error": str(e)}

    return StreamingResponse(
        generate_sse_events(stream_generate()),
        media_type="text/event-stream",
    )


# Deploy endpoint
@app.post("/api/deploy", response_model=DeployResponse)
async def deploy(request: DeployRequest):
    """
    Deploy generated code to AWS.
    """
    session = get_or_create_session(request.session_id)

    try:
        code = request.code or session.generated_code

        if not code:
            raise HTTPException(status_code=400, detail="No code to deploy")

        # If code came from request, merge into session
        if request.code:
            if isinstance(request.code, dict):
                session.generated_code.update(request.code)

        deployment_id = str(uuid.uuid4())[:8]

        # Call AgentCore Runtime for deployment with FULL context
        client = get_client()
        payload_ctx = session.build_payload_context()
        payload_ctx["action"] = "deploy"
        payload_ctx["deployment_type"] = request.deployment_type
        payload_ctx["deployment_id"] = deployment_id
        # Ensure code is always in payload for deploy
        payload_ctx["code"] = session.generated_code

        response = client.invoke(
            prompt=f"Deploy the website as {request.deployment_type}",
            session_id=request.session_id,
            payload_extra=payload_ctx,
        )

        # Sync state from AgentCore response
        session.sync_from_response(response.metadata)

        # Get URL from response or construct default
        url = session.deployment_url or ""
        if not url:
            if request.deployment_type == "static":
                url = f"https://{config.STATIC_CLOUDFRONT_DOMAIN}/deployments/{deployment_id}/index.html"
            else:
                url = config.DYNAMIC_FUNCTION_URL

        session.business_phase = BusinessPhase.DEPLOYED
        session.deployment_url = url

        return DeployResponse(
            deployment_id=deployment_id,
            deployment_type=request.deployment_type,
            url=url,
            status="deployed",
        )

    except Exception as e:
        logger.error(f"Deploy error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Deployment status endpoint
@app.post("/api/deployment/status", response_model=DeploymentStatusResponse)
async def deployment_status(request: DeploymentStatusRequest):
    """
    Get deployment status.
    """
    try:
        # For now, return a simple status - actual status comes from AgentCore
        # In production, this would query the deployment infrastructure
        return DeploymentStatusResponse(
            deployment_id=request.deployment_id,
            status="deployed",
            url=f"https://{config.STATIC_CLOUDFRONT_DOMAIN}/deployments/{request.deployment_id}/index.html"
            if request.deployment_type == "static"
            else config.DYNAMIC_FUNCTION_URL,
            files=None,
        )

    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Delete deployment endpoint
@app.delete("/api/deployment/{deployment_id}")
async def delete_deployment(deployment_id: str, deployment_type: str = "static"):
    """
    Delete a deployment.
    """
    try:
        # Deployment deletion is handled by AgentCore Runtime
        # For now, return success - actual deletion would be implemented in AgentCore
        return {
            "deployment_id": deployment_id,
            "status": "deleted",
        }

    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Get session status
@app.get("/api/session/{session_id}/status")
async def get_session_status(session_id: str):
    """
    Get status of a session.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]
    return session.get_status()


# List sessions
@app.get("/api/sessions")
async def list_sessions():
    """
    List all active sessions.
    """
    return {
        "sessions": [
            {
                "session_id": sid,
                "phase": session.business_phase.value,
                "has_code": bool(session.generated_code),
            }
            for sid, session in _sessions.items()
        ]
    }


# Confirm plan endpoint
@app.post("/api/session/{session_id}/confirm")
async def confirm_plan(session_id: str):
    """
    Confirm the current plan and proceed to execution.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _sessions[session_id]

    if session.business_phase not in [BusinessPhase.WAITING_CONFIRM, BusinessPhase.RECEIVING, BusinessPhase.PLANNING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot confirm in phase: {session.business_phase.value}"
        )

    session.business_phase = BusinessPhase.EXECUTING

    return {
        "session_id": session_id,
        "phase": session.business_phase.value,
        "status": "confirmed",
    }


# Lambda handler using Mangum
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except ImportError:
    handler = None


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
    )
