"""
AgentCore Runtime 入口

基于 AgentCore Runtime 运行的网站生成 Agent，集成内置部署工具。
使用内置部署工具（deploy_to_s3, deploy_to_lambda）直接调用 AWS SDK。

工具加载方式：
- 使用 Strands Agent 的 load_tools_from_directory 自动加载 ./tools 目录下的工具
- 支持热重载：工具文件修改后自动重新加载

参考文档：
- Strands Tools 概念: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools
- 动态工具加载: https://builder.aws.com/content/2zeKrP0DJJLqC0Q9jp842IPxLMm/dynamic-tool-loading-in-strands-sdk-enabling-meta-tooling-for-adaptive-ai-agents

集成模块：
- prompts: 不同阶段的系统提示词
- memory: AgentCore Memory API，会话持久化
- tools: 浏览器、代码解释器、代码生成器、内置部署工具

演示功能：
- Amazon Bedrock AgentCore Runtime
- S3 + CloudFront 静态网站部署
- Lambda + Web Adapter 动态应用部署
"""

import json
import logging
import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from botocore.config import Config

# 使用延迟加载导入集成模块，避免初始化超时
# AgentCore Runtime 初始化限制为 120 秒
# 启动时只导入必要模块
from prompts.planning import PLANNING_SYSTEM_PROMPT

# 延迟加载的模块（首次使用时导入）
_memory_service_module = None
_agentcore_tools_module = None


def _get_memory_module():
    """延迟加载 Memory 模块。"""
    global _memory_service_module
    if _memory_service_module is None:
        from memory.memory_service import AgentCoreMemoryService, create_memory_service
        _memory_service_module = {"AgentCoreMemoryService": AgentCoreMemoryService, "create_memory_service": create_memory_service}
    return _memory_service_module


def _get_agentcore_tools():
    """
    延迟加载 AgentCore 内置工具（Browser, Code Interpreter）。

    这些工具需要在 AgentCore Runtime 环境中才能使用。
    返回可用的原生工具列表，用于传递给 Agent。

    参考文档:
    - Browser: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html
    - Code Interpreter: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html
    """
    global _agentcore_tools_module
    if _agentcore_tools_module is not None:
        return _agentcore_tools_module

    tools = []
    _agentcore_tools_module = []  # Initialize to empty list to prevent repeated attempts

    # Try to load Browser tool
    try:
        from tools.browser_tool import get_native_browser_tool
        browser_tool = get_native_browser_tool()
        if browser_tool:
            tools.append(browser_tool)
            print("[DEBUG] Native Browser tool loaded successfully")
    except Exception as e:
        print(f"[DEBUG] Browser tool not available: {e}")

    # Try to load Code Interpreter tool
    try:
        from tools.code_interpreter import get_native_code_interpreter_tool
        code_tool = get_native_code_interpreter_tool()
        if code_tool:
            tools.append(code_tool)
            print("[DEBUG] Native Code Interpreter tool loaded successfully")
    except Exception as e:
        print(f"[DEBUG] Code Interpreter tool not available: {e}")

    _agentcore_tools_module = tools
    print(f"[DEBUG] Loaded {len(tools)} native AgentCore tools")
    return tools


# 工具目录路径（用于 Strands Agent 自动加载）
TOOLS_DIRECTORY = os.path.join(os.path.dirname(__file__), "tools")

logger = logging.getLogger(__name__)

# 环境变量配置
REGION = os.environ.get("AWS_REGION", "us-east-1")

# Memory ID from AgentCore configuration (for supplementary persistence)
MEMORY_ID = os.environ.get("AGENTCORE_MEMORY_ID", "")

# 系统提示词：基础规划提示词 + 部署决策指南
# 基础提示词来自 prompts/planning.py，此处追加部署相关规则
SYSTEM_PROMPT = PLANNING_SYSTEM_PROMPT + """

##CRITICAL: Deployment Decision Guide##
<deployment_decision>
**MANDATORY RULE: Check file list FIRST! If server.js/app.py exists → MUST use deploy_to_lambda!**

**DYNAMIC DEPLOYMENT (deploy_to_lambda) - USE WHEN:**
- server.js exists → MUST use Lambda + Web Adapter
- app.py/main.py exists → MUST use Lambda + Web Adapter
- Node.js/Express servers
- Python/Flask/FastAPI backends
- Any app with backend API routes
- Apps that need data persistence (博客, 电商, 用户系统)

**STATIC DEPLOYMENT (deploy_to_s3) - ONLY WHEN:**
- NO server.js, app.py, or main.py in files
- Pure HTML/CSS/JS client-side only
- Landing pages, portfolio sites
- Documentation sites

**CRITICAL: S3 CANNOT run server-side code! If you see server.js in the files, you MUST use Lambda!**
</deployment_decision>

##Database Selection Guide##
<database_decision>
When deploying dynamic apps that need data persistence, choose the appropriate database type:

**CRITICAL: Be CONSISTENT! If you propose Aurora in your design plan, you MUST use Aurora when deploying!**

**Aurora PostgreSQL (database_type="aurora")** - USE FOR THESE KEYWORDS:
- 博客, blog, 文章, 帖子, 评论 → MUST use Aurora
- 电商, 订单, 购物车 → MUST use Aurora
- 用户系统, 角色权限, 会员 → MUST use Aurora
- Complex queries with JOINs
- Data with relationships (users->posts->comments)
- Need transactions (ACID compliance)

**DynamoDB (database_type="dynamodb")** - For simple apps:
- Simple CRUD operations (Create, Read, Update, Delete)
- Key-value or document storage
- No complex relationships between data
- Examples: Todo apps, notes, user preferences, session data, counters
- Use when: User mentions "保存", "存储", "数据", but doesn't need relations

**Redis (database_type="elasticache")** - For caching/real-time:
- Real-time leaderboards/rankings
- Session caching
- Message queues
- Rate limiting
- Use when: User mentions "实时", "排行榜", "缓存", "消息队列"

**Decision Priority (STRICT ORDER):**
1. If user explicitly mentions database type → use that type
2. If keywords match Aurora (博客/blog/订单/用户系统) → MUST use Aurora
3. If app needs real-time/caching → Redis
4. Default for simple data persistence → DynamoDB

**IMPORTANT: Once you choose a database in your design proposal, you MUST use the SAME database type when deploying. Do NOT change from Aurora to DynamoDB during deployment!**

**How to use:** Call deploy_to_lambda with database_type parameter:
- deploy_to_lambda(project_name="my-app", files=[...], database_type="aurora")  # For blogs, e-commerce, user systems
- deploy_to_lambda(project_name="my-app", files=[...], database_type="dynamodb")  # For simple apps
- deploy_to_lambda(project_name="my-app", files=[...], database_type="elasticache")  # For caching

Connection details are pre-configured - just specify the database_type!
</database_decision>

##Code Generation Format##
**CRITICAL: After calling generate_website_code tool, you MUST output the returned code in code blocks!**

The tool returns: {"files": {"index.html": "...", "styles.css": "...", "main.js": "..."}, ...}

You MUST extract each file and output like this:

```html:index.html
[Complete HTML code from tool result]
```

```css:styles.css
[Complete CSS code from tool result]
```

```javascript:main.js
[Complete JavaScript code from tool result]
```

For dynamic apps, also include:
```javascript:server.js
[Complete server code from tool result]
```

**Without code blocks, the preview will NOT work!**

##Additional Guardrails##
<prohibited_behaviors>
- When deploying dynamic apps, ALWAYS use deploy_to_lambda, NOT deploy_to_s3
- Do NOT describe what you will do - just execute directly
</prohibited_behaviors>

##Deployment Tool Behavior##
<deployment_notes>
**IMPORTANT**: Deployment tools use async task management.

When user requests deployment:
1. Call the deployment tool (deploy_to_s3 or deploy_to_lambda)
2. The tool returns IMMEDIATELY with a task_id
3. Tell the user: "Deployment task initiated (Task ID: xxx). The deployment is running in the background and will take 40-60 seconds. Results will be automatically saved to your conversation history."
4. Do NOT wait or poll for results - the deployment runs asynchronously
5. When user returns later, check conversation history for deployment results

Example response after calling deploy_to_s3:
"I've initiated the deployment (Task ID: abc12345). The deployment is running in the background and typically takes 40-60 seconds to complete. Once finished, the result will appear in your conversation history. You can continue with other tasks or check back shortly for the deployment URL."
</deployment_notes>
"""


class BusinessPhase(str, Enum):
    """业务工作流阶段。"""
    RECEIVING = "RECEIVING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    PREVIEWING = "PREVIEWING"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"


@dataclass
class SessionState:
    """临时会话状态 — 每次请求从 payload 重建。

    AgentCore handler 是无状态的。所有上下文通过 ECS 后端的 payload 传入。
    此数据类仅作为当前请求上下文的容器，不会跨请求持久化。
    """
    session_id: str
    phase: BusinessPhase = BusinessPhase.RECEIVING
    generated_code: Dict[str, str] = field(default_factory=dict)
    deployment_url: Optional[str] = None
    deployment_type: Optional[str] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    memory_service: Optional[Any] = None  # AgentCoreMemoryService, lazy loaded


def build_session_from_payload(payload: Dict[str, Any]) -> SessionState:
    """
    Build a SessionState entirely from the incoming payload.

    This is the core of the stateless design — no _sessions dict, no
    cross-request memory. The ECS Backend is the single source of truth
    and passes everything we need in every request.
    """
    session_id = payload.get("session_id", "default")
    actor_id = payload.get("actor_id")

    session = SessionState(session_id=session_id)

    # Restore phase
    if payload.get("phase"):
        try:
            session.phase = BusinessPhase(payload["phase"])
        except ValueError:
            pass

    # Restore generated code
    if payload.get("code"):
        code = payload["code"]
        if isinstance(code, dict):
            if "files" in code:
                session.generated_code.update(code["files"])
            else:
                session.generated_code.update(code)

    # Restore deployment info
    if payload.get("deployment_url"):
        session.deployment_url = payload["deployment_url"]
    if payload.get("deployment_type"):
        session.deployment_type = payload["deployment_type"]

    # Restore conversation history (passed by ECS Backend)
    if payload.get("conversation_history"):
        session.conversation_history = payload["conversation_history"]

    # Optionally initialize memory service for supplementary persistence
    if MEMORY_ID:
        try:
            mem_module = _get_memory_module()
            session.memory_service = mem_module["create_memory_service"](
                memory_id=MEMORY_ID,
                actor_id=actor_id or session_id,
                session_id=session_id,
                region=REGION,
            )
        except Exception as e:
            print(f"[WARNING] Failed to create memory service: {e}")

    print(f"[DEBUG] Session rebuilt from payload: phase={session.phase.value}, "
          f"code_files={list(session.generated_code.keys())}, "
          f"history_turns={len(session.conversation_history)}")

    return session


def save_to_memory(session: SessionState, role: str, content: str) -> None:
    """Persist conversation turn to AgentCore Memory for cross-session durability."""
    if session.memory_service:
        try:
            session.memory_service.add_conversation_turn(role, content)
        except Exception as e:
            print(f"[WARNING] Failed to save to memory: {e}")


def extract_code_from_result(result: str, session: SessionState) -> None:
    """
    Extract code blocks from agent result.

    Supports multiple formats:
    1. Tool result with "files" key (from generate_website_code tool)
    2. ```language:filename.ext - explicit filename
    3. ```language // filename.ext - filename in comment
    4. ```language - auto-detect based on content
    """
    try:
        # Strategy 1: Try to parse as direct JSON first
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict) and 'files' in parsed:
                files = parsed['files']
                if isinstance(files, dict):
                    session.generated_code.update(files)
                    print(f"[DEBUG] Extracted {len(files)} files from direct JSON")
                    return
        except (json.JSONDecodeError, TypeError):
            pass

        # Strategy 2: Try to find embedded JSON with files structure
        # Look for JSON object containing "files" key
        # Use bracket counting for proper nested structure handling
        if '"files"' in result or "'files'" in result:
            # Find potential JSON start positions
            for start_marker in ['{', "{'files'", '{"files"']:
                start_idx = 0
                while True:
                    start_idx = result.find(start_marker[0], start_idx)
                    if start_idx == -1:
                        break

                    # Try to find matching closing brace
                    depth = 0
                    end_idx = start_idx
                    in_string = False
                    escape_next = False
                    string_char = None

                    for i, char in enumerate(result[start_idx:], start_idx):
                        if escape_next:
                            escape_next = False
                            continue
                        if char == '\\':
                            escape_next = True
                            continue
                        if char in '"\'':
                            if not in_string:
                                in_string = True
                                string_char = char
                            elif char == string_char:
                                in_string = False
                            continue
                        if in_string:
                            continue
                        if char == '{':
                            depth += 1
                        elif char == '}':
                            depth -= 1
                            if depth == 0:
                                end_idx = i + 1
                                break

                    if depth == 0 and end_idx > start_idx:
                        json_candidate = result[start_idx:end_idx]
                        # Try JSON parse
                        try:
                            parsed = json.loads(json_candidate)
                            if isinstance(parsed, dict) and 'files' in parsed:
                                session.generated_code.update(parsed['files'])
                                print(f"[DEBUG] Extracted files from embedded JSON")
                                return
                        except json.JSONDecodeError:
                            # Try Python literal eval for dict with single quotes
                            try:
                                import ast
                                parsed = ast.literal_eval(json_candidate)
                                if isinstance(parsed, dict) and 'files' in parsed:
                                    session.generated_code.update(parsed['files'])
                                    print(f"[DEBUG] Extracted files from Python dict literal")
                                    return
                            except (ValueError, SyntaxError):
                                pass

                    start_idx += 1

        # Pattern 1: ```language:filename or ```language filename
        named_blocks = re.findall(
            r'```(\w+)(?::|[\s]+)([^\s\n]+\.\w+)\s*\n([\s\S]*?)```',
            result
        )
        for lang, filename, content in named_blocks:
            session.generated_code[filename] = content.strip()
            print(f"[DEBUG] Extracted {filename} (named)")

        # Pattern 2: ```language with // filename.ext comment on first line
        comment_named = re.findall(
            r'```(\w+)\s*\n\s*(?://|#|/\*)\s*(\S+\.\w+)[^\n]*\n([\s\S]*?)```',
            result
        )
        for lang, filename, content in comment_named:
            if filename not in session.generated_code:
                session.generated_code[filename] = content.strip()
                print(f"[DEBUG] Extracted {filename} (comment)")

        # Pattern 3: Auto-detect standard files
        # HTML
        if "index.html" not in session.generated_code:
            html_match = re.search(r'```html\s*\n([\s\S]*?)```', result)
            if html_match:
                session.generated_code["index.html"] = html_match.group(1).strip()
                print(f"[DEBUG] Extracted index.html (auto-detect)")

        # CSS
        if "styles.css" not in session.generated_code:
            css_match = re.search(r'```css\s*\n([\s\S]*?)```', result)
            if css_match:
                session.generated_code["styles.css"] = css_match.group(1).strip()
                print(f"[DEBUG] Extracted styles.css (auto-detect)")

        # JavaScript - detect if server-side or client-side
        js_matches = re.findall(r'```(?:javascript|js)\s*\n([\s\S]*?)```', result)
        for code in js_matches:
            code = code.strip()
            # Skip if already extracted as named file
            if code in [v for v in session.generated_code.values()]:
                continue

            # Detect server-side code (Node.js, Express, etc.)
            server_indicators = ['express()', 'app.listen', 'http.createserver',
                               'require(\'express', 'require("express', 'fastify',
                               'app.get(', 'app.post(', 'router.']
            if any(ind in code.lower() for ind in server_indicators):
                if "server.js" not in session.generated_code:
                    session.generated_code["server.js"] = code
                    print(f"[DEBUG] Extracted server.js (auto-detect)")
            else:
                if "main.js" not in session.generated_code:
                    session.generated_code["main.js"] = code
                    print(f"[DEBUG] Extracted main.js (auto-detect)")

        # Python backend detection
        py_matches = re.findall(r'```python\s*\n([\s\S]*?)```', result)
        for code in py_matches:
            code = code.strip()
            if code in [v for v in session.generated_code.values()]:
                continue
            # Detect Flask/FastAPI
            if any(ind in code.lower() for ind in ['flask', 'fastapi', '@app.route', '@app.get']):
                if "app.py" not in session.generated_code:
                    session.generated_code["app.py"] = code
                    print(f"[DEBUG] Extracted app.py (auto-detect)")

        # package.json
        if "package.json" not in session.generated_code:
            json_matches = re.findall(r'```json\s*\n([\s\S]*?)```', result)
            for content in json_matches:
                if '"dependencies"' in content or '"name"' in content:
                    session.generated_code["package.json"] = content.strip()
                    print(f"[DEBUG] Extracted package.json (auto-detect)")
                    break

        # requirements.txt
        if "requirements.txt" not in session.generated_code:
            req_match = re.search(r'```(?:txt|text|requirements)?\s*\n((?:[\w-]+==[^\n]+\n?)+)```', result)
            if req_match:
                session.generated_code["requirements.txt"] = req_match.group(1).strip()
                print(f"[DEBUG] Extracted requirements.txt (auto-detect)")

        print(f"[DEBUG] Total extracted files: {list(session.generated_code.keys())}")

    except Exception as e:
        logger.warning(f"Failed to extract code: {e}")


def extract_deployment_info(result: str, session: SessionState) -> None:
    """Extract deployment URL from agent result."""
    try:
        # Look for CloudFront URLs
        cloudfront_match = re.search(r'https://[a-z0-9]+\.cloudfront\.net[^\s"\']*', result)
        if cloudfront_match:
            session.deployment_url = cloudfront_match.group(0)
            session.deployment_type = "static"
            session.phase = BusinessPhase.DEPLOYED
            return

        # Look for Lambda Function URLs
        lambda_match = re.search(r'https://[a-z0-9]+\.lambda-url\.[a-z0-9-]+\.on\.aws[^\s"\']*', result)
        if lambda_match:
            session.deployment_url = lambda_match.group(0)
            session.deployment_type = "dynamic"
            session.phase = BusinessPhase.DEPLOYED
            return
    except Exception as e:
        logger.warning(f"Failed to extract deployment info: {e}")


def format_response(
    response_text: str,
    session: SessionState,
    status: str = "success"
) -> Dict[str, Any]:
    """Format response for frontend compatibility."""
    result: Dict[str, Any] = {
        "response": response_text,
        "session_id": session.session_id,
        "status": status,
        "phase": session.phase.value,
    }

    if session.generated_code:
        result["code"] = {
            "html": session.generated_code.get("index.html", ""),
            "css": session.generated_code.get("styles.css", ""),
            "javascript": session.generated_code.get("main.js", ""),
            "files": session.generated_code,
        }

    if session.deployment_url:
        result["deployment_url"] = session.deployment_url
        result["deployment_type"] = session.deployment_type

    return result


def prepare_files_for_deployment(session: SessionState) -> List[Dict[str, Any]]:
    """Prepare files in MCP tool format."""
    files = []
    for path, content in session.generated_code.items():
        files.append({
            "path": path,
            "content": content,
            "encoding": "utf-8"
        })
    return files


# Initialize the AgentCore App
app = BedrockAgentCoreApp()


def get_conversation_messages(session: SessionState) -> List[Dict[str, Any]]:
    """
    Build conversation messages for the Strands Agent.

    Uses a two-layer strategy:
    1. PRIMARY: conversation_history from payload (reliable, immediate)
    2. SUPPLEMENTARY: AgentCore Memory Service (persistent, cross-session)
       - Fills in gaps if payload history is empty (first request after restart)
       - Provides long-term context via semantic search

    This ensures context is never lost even when routed to a new MicroVM,
    while still leveraging AgentCore Memory for persistence and search.
    """
    messages = []

    # Layer 1 (PRIMARY): Conversation history from payload
    if session.conversation_history:
        for turn in session.conversation_history:
            role = turn.get("role", "").lower()
            content = turn.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({
                    "role": role,
                    "content": [{"text": content}]
                })
        print(f"[DEBUG] Built {len(messages)} messages from payload history")

    # Layer 2 (SUPPLEMENTARY): AgentCore Memory Service
    # Only used as fallback when payload has no history, OR to enrich
    # context with long-term memories (e.g. user preferences)
    if session.memory_service:
        if not messages:
            # Fallback: payload had no history, recover from Memory
            try:
                history = session.memory_service.get_conversation_history(limit=20)
                print(f"[DEBUG] Fallback: recovered {len(history)} turns from AgentCore Memory")
                for turn in history:
                    role = turn.get("role", "").lower()
                    content = turn.get("content", "")
                    if role in ["user", "assistant"] and content:
                        messages.append({
                            "role": role,
                            "content": [{"text": content}]
                        })
            except Exception as e:
                print(f"[WARNING] Failed to recover history from Memory: {e}")

        # Enrich with user preferences from long-term memory
        try:
            preferences = session.memory_service.get_user_preferences()
            if preferences:
                pref_str = ", ".join(f"{k}: {v}" for k, v in preferences.items())
                messages.insert(0, {
                    "role": "user",
                    "content": [{"text": f"[用户偏好] {pref_str}"}]
                })
                messages.insert(1, {
                    "role": "assistant",
                    "content": [{"text": "好的，我已了解您的偏好设置。"}]
                })
                print(f"[DEBUG] Enriched context with {len(preferences)} user preferences")
        except Exception as e:
            print(f"[DEBUG] No user preferences available: {e}")

    # Inject actual code content as context (not just file names)
    if session.generated_code and session.phase != BusinessPhase.RECEIVING:
        code_context = "当前已生成的代码文件:\n"
        for filename, content in session.generated_code.items():
            # Truncate very large files to keep within token limits
            truncated = content[:3000] if len(content) > 3000 else content
            code_context += f"\n--- {filename} ---\n{truncated}\n"
        if session.deployment_url:
            code_context += f"\n部署地址: {session.deployment_url}"

        messages.append({
            "role": "user",
            "content": [{"text": f"[上下文信息] {code_context}"}]
        })
        messages.append({
            "role": "assistant",
            "content": [{"text": "好的，我已了解当前的代码状态和所有文件内容。"}]
        })

    return messages


async def invoke_with_mcp(
    payload: Dict[str, Any],
    session: SessionState,
) -> str:
    """
    调用 agent 执行任务。

    使用内置部署工具（deploy_to_s3, deploy_to_lambda）直接调用 AWS SDK，
    绕过 MCP Gateway 避免网络超时问题。

    从 Memory service 恢复对话历史以保持跨请求的上下文。
    """
    prompt = payload.get("prompt", "")
    action = payload.get("action", "chat")
    reference_urls = payload.get("reference_urls", [])
    framework = payload.get("framework", "html")

    print(f"[DEBUG] invoke_with_mcp called with action={action}")

    # 获取对话历史以保持上下文
    conversation_messages = get_conversation_messages(session)
    print(f"[DEBUG] Loaded {len(conversation_messages)} messages for context")

    try:
        # 创建 Bedrock 模型，配置 max_tokens 用于网站生成
        # Claude Sonnet 4 支持最多 64,000 输出 tokens（使用 beta header 可达 128K）
        # 参考: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages-request-response.html
        bedrock_model = BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            temperature=0.0,
            max_tokens=64000,
            boto_client_config=Config(
                connect_timeout=300,
                read_timeout=600,
                retries={"max_attempts": 10, "mode": "adaptive"}
            )
        )

        # 创建 agent，结合以下两种工具加载方式:
        # 1. load_tools_from_directory: 自动加载 ./tools 目录下的 @tool 装饰函数
        # 2. tools: 原生 AgentCore 工具（Browser, Code Interpreter）
        #
        # 参考文档:
        # - Strands Tools: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools
        # - Browser Tool: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html
        # - Code Interpreter: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html

        # 加载原生 AgentCore 工具
        native_tools = _get_agentcore_tools()
        print(f"[DEBUG] Creating Agent with {len(native_tools)} native tools + directory loading from: {TOOLS_DIRECTORY}")

        agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=native_tools if native_tools else None,  # 原生 AgentCore 工具
            load_tools_from_directory=TOOLS_DIRECTORY,  # 自动加载工具目录
            messages=conversation_messages if conversation_messages else None,
        )
        print(f"[DEBUG] Agent created with native tools + auto-loaded tools from directory")

        # 处理不同的 action
        result = None
        if action == "edit":
            result = await handle_edit(agent, payload, session)
        elif action == "deploy":
            result = await handle_deploy(agent, payload, session)
        else:  # chat or generate
            result = await handle_generate(agent, prompt, reference_urls, framework, session)

        # 确保 agent 完全执行完成
        print(f"[DEBUG] Agent execution completed, result length: {len(result) if result else 0}")

        return result or ""

    except Exception as e:
        print(f"[ERROR] Agent execution failed: {e}")
        raise


@app.entrypoint
async def invoke(payload: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AgentCore Runtime entry point for the Website Generator Agent.

    STATELESS DESIGN with two-layer memory:
    - Layer 1 (PRIMARY): Full context via payload from ECS Backend
    - Layer 2 (PERSISTENT): AgentCore Memory for cross-session persistence,
      user preferences, and fallback recovery

    Supports actions: chat, generate, edit, deploy
    """
    session_id = payload.get("session_id") or getattr(context, "session_id", "default")
    action = payload.get("action", "chat")
    prompt = payload.get("prompt", "")

    logger.info(f"Processing {action} request for session: {session_id}")

    # Rebuild session entirely from payload — no _sessions dict
    payload["session_id"] = session_id  # ensure it's set
    session = build_session_from_payload(payload)

    # Persist user message to AgentCore Memory (for cross-session durability)
    if prompt:
        save_to_memory(session, "USER", prompt)

    try:
        result_str = await invoke_with_mcp(payload, session)

        # Persist assistant response to AgentCore Memory
        # Smart truncation: keep beginning (plan/explanation) + end (summary/result)
        if len(result_str) > 4000:
            memory_content = result_str[:2000] + "\n...[truncated]...\n" + result_str[-2000:]
        else:
            memory_content = result_str
        save_to_memory(session, "ASSISTANT", memory_content)

        return format_response(result_str, session)

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return format_response(f"Error: {str(e)}", session, "error")


async def handle_edit(agent: Agent, payload: Dict[str, Any], session: SessionState) -> str:
    """Handle edit action."""
    prompt = payload.get("prompt", "")
    current_code = payload.get("current_code", {})

    # Use current_code from payload or session
    html = current_code.get("html") or session.generated_code.get("index.html", "")
    css = current_code.get("css") or session.generated_code.get("styles.css", "")
    js = current_code.get("javascript") or session.generated_code.get("main.js", "")

    edit_prompt = f"""Edit the following website code based on this request: {prompt}

Current HTML:
```html
{html}
```

Current CSS:
```css
{css}
```

Current JavaScript:
```javascript
{js}
```

Please output the complete modified code in the same format."""

    result = agent(edit_prompt)
    result_str = str(result) if result else ""

    extract_code_from_result(result_str, session)
    return result_str


def detect_deployment_type(code: Dict[str, str]) -> str:
    """
    Auto-detect whether code should be deployed as static or dynamic.

    Dynamic indicators:
    - server.js, app.py, main.py files
    - Express, Flask, FastAPI imports
    - API route patterns
    - Server-side rendering patterns
    """
    dynamic_indicators = [
        # File names
        "server.js", "app.py", "main.py", "index.js",
        # Patterns in code
        "express", "fastapi", "flask", "http.createServer",
        "app.listen", "app.run", "getServerSideProps",
        "api/", "/api", "router.get", "router.post",
        "req, res", "request, response",
    ]

    code_content = " ".join(str(v).lower() for v in code.values())
    file_names = " ".join(code.keys()).lower()

    # Check file names
    if any(name in file_names for name in ["server.js", "app.py", "main.py"]):
        return "dynamic"

    # Check code content
    for indicator in dynamic_indicators:
        if indicator.lower() in code_content:
            return "dynamic"

    return "static"


async def handle_deploy(agent: Agent, payload: Dict[str, Any], session: SessionState) -> str:
    """Handle deploy action using MCP tools."""
    deployment_id = payload.get("deployment_id", session.session_id[:8])
    code = payload.get("code") or session.generated_code

    if not code:
        return "Error: No code to deploy. Please generate code first."

    # Update session code if provided in payload
    if payload.get("code"):
        session.generated_code = code

    # Auto-detect deployment type if not specified
    deployment_type = payload.get("deployment_type")
    if not deployment_type:
        deployment_type = detect_deployment_type(code)
        print(f"[DEBUG] Auto-detected deployment type: {deployment_type}")

    session.phase = BusinessPhase.DEPLOYING

    # Prepare files for deployment
    files = prepare_files_for_deployment(session)

    # Build deployment prompt
    if deployment_type == "static":
        deploy_prompt = f"""Deploy this static website using the deploy_to_s3 tool.

Project name: ugc-{deployment_id}
Files to deploy:
{json.dumps(files, indent=2)}

Use index.html as the index document. Enable SPA mode."""

    else:  # dynamic
        deploy_prompt = f"""**CRITICAL: This is a DYNAMIC application with server.js. You MUST use deploy_to_lambda!**

**DO NOT use deploy_to_s3! This app has backend server code that requires Lambda + Web Adapter.**

Deploy using the deploy_to_lambda tool:

Project name: ugc-dynamic-{deployment_id}
Files to deploy:
{json.dumps(files, indent=2)}

**MANDATORY INSTRUCTIONS:**
1. MUST use deploy_to_lambda tool (NOT deploy_to_s3!)
2. This app has server.js - it CANNOT run on S3 static hosting
3. Auto-detect runtime (nodejs20.x) and port (3000) from files
4. Choose appropriate database_type based on app requirements

NEVER deploy server.js apps to S3. Lambda + Web Adapter is required for Express/Node.js servers."""

    # 同步调用 agent，Strands 会自动等待工具执行完成
    print(f"[DEBUG] Calling agent with deployment prompt...")
    result = agent(deploy_prompt)
    result_str = str(result) if result else ""
    print(f"[DEBUG] Agent returned result, length: {len(result_str)}")

    extract_deployment_info(result_str, session)
    return result_str


async def handle_generate(
    agent: Agent,
    prompt: str,
    reference_urls: List[str],
    framework: str,
    session: SessionState
) -> str:
    """Handle chat/generate action."""
    full_prompt = prompt

    if reference_urls:
        urls_str = "\n".join(f"- {url}" for url in reference_urls)
        full_prompt += f"\n\nReference websites for design inspiration:\n{urls_str}"

    if framework != "html":
        full_prompt += f"\n\nUse {framework} framework."

    result = agent(full_prompt)
    result_str = str(result) if result else ""

    # Extract code from agent execution
    # Strategy 1: First pass - extract from tool results (highest priority)
    tool_result_files = {}
    try:
        if hasattr(agent, 'messages') and agent.messages:
            for msg in agent.messages:
                if not hasattr(msg, 'content'):
                    continue

                content = msg.content
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # Check for tool result in various formats
                            # Format 1: Strands tool result with 'content' as JSON string
                            if 'content' in item and isinstance(item['content'], str):
                                content_str = item['content']
                                # Try to parse as JSON
                                try:
                                    parsed = json.loads(content_str)
                                    if isinstance(parsed, dict) and 'files' in parsed:
                                        tool_result_files.update(parsed['files'])
                                        print(f"[DEBUG] Found files in JSON tool result: {list(parsed['files'].keys())}")
                                except (json.JSONDecodeError, TypeError):
                                    # Try Python literal eval (for single-quoted dicts)
                                    try:
                                        import ast
                                        parsed = ast.literal_eval(content_str)
                                        if isinstance(parsed, dict) and 'files' in parsed:
                                            tool_result_files.update(parsed['files'])
                                            print(f"[DEBUG] Found files in Python dict tool result: {list(parsed['files'].keys())}")
                                    except (ValueError, SyntaxError):
                                        pass

                            # Format 2: Direct dict with files
                            if 'files' in item and isinstance(item['files'], dict):
                                tool_result_files.update(item['files'])
                                print(f"[DEBUG] Found files in direct dict: {list(item['files'].keys())}")

                            # Format 3: toolResult with result containing files
                            if item.get('type') == 'tool_result' or 'toolResult' in str(item):
                                result_data = item.get('result') or item.get('toolResult') or item.get('content')
                                if isinstance(result_data, dict) and 'files' in result_data:
                                    tool_result_files.update(result_data['files'])
                                    print(f"[DEBUG] Found files in toolResult: {list(result_data['files'].keys())}")
                                elif isinstance(result_data, str):
                                    try:
                                        parsed = json.loads(result_data)
                                        if isinstance(parsed, dict) and 'files' in parsed:
                                            tool_result_files.update(parsed['files'])
                                            print(f"[DEBUG] Found files in toolResult JSON: {list(parsed['files'].keys())}")
                                    except:
                                        pass

    except Exception as e:
        print(f"[DEBUG] Error extracting from tool results: {e}")

    # If we found files from tool results, use them (they include preview files)
    if tool_result_files:
        session.generated_code.update(tool_result_files)
        print(f"[DEBUG] Using tool result files: {list(tool_result_files.keys())}")

    # Strategy 2: Extract from text content (for files not in tool results)
    try:
        if hasattr(agent, 'messages') and agent.messages:
            for msg in agent.messages:
                if not hasattr(msg, 'content'):
                    continue
                content = msg.content
                if isinstance(content, str):
                    extract_code_from_result(content, session)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, str):
                            extract_code_from_result(item, session)
                        elif isinstance(item, dict) and 'text' in item:
                            extract_code_from_result(str(item['text']), session)
    except Exception as e:
        print(f"[DEBUG] Error extracting from text content: {e}")

    # Strategy 3: Fallback to result string if no code extracted
    if not session.generated_code:
        extract_code_from_result(result_str, session)

    if session.generated_code:
        session.phase = BusinessPhase.PREVIEWING
        print(f"[DEBUG] Final extracted files: {list(session.generated_code.keys())}")

    return result_str


if __name__ == "__main__":
    app.run(port=8080)
