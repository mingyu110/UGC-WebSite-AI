# UGC AI Demo 系统架构

## 概览

```
┌─────────────────┐
│   Frontend      │  Next.js 应用
│   (Next.js)     │  .env.local: AGENT_URL=ECS ALB
└────────┬────────┘
         │ HTTP API
         ▼
┌─────────────────┐
│  ECS Backend    │  FastAPI (agent/server.py)
│  (server.py)    │  API 中转层 + 会话管理
└────────┬────────┘
         │ AgentCoreClient.invoke()
         ▼
┌─────────────────┐
│ AgentCore       │  Bedrock AgentCore Runtime
│ Runtime         │  (agent/agentcore_handler.py)
│                 │  Agent 逻辑 + 工具调用
└─────────────────┘
```

## 组件详解

### 1. Frontend (Next.js)

- **位置**: `frontend/`（Git 子模块）
- **部署**: CloudFront + S3 或本地开发
- **配置**: `frontend/.env.local`
  ```
  AGENT_URL=http://ugc-backend-alb-*.elb.amazonaws.com
  ```

### 2. ECS Backend (server.py)

- **位置**: `agent/server.py`
- **Dockerfile**: `/Dockerfile`（根目录）
- **运行命令**: `uvicorn agent.server:app`
- **端口**: 8000
- **部署**: ECS Fargate + ALB

**职责**:
- HTTP API 端点 (`/api/chat`, `/api/deploy` 等)
- 会话状态管理 (`SessionState`)
- 调用 AgentCore Runtime API
- 响应转发和格式化

**关键代码**:
```python
# server.py
client = get_client()  # AgentCoreClient
response = client.invoke(prompt, session_id, payload)
session.sync_from_response(response.metadata)  # 获取 code
```

### 3. AgentCore Runtime (agentcore_handler.py)

- **位置**: `agent/agentcore_handler.py`
- **Dockerfile**: `agent/Dockerfile`
- **运行命令**: `uvicorn agentcore_handler:app`
- **端口**: 8080
- **部署**: Bedrock AgentCore Runtime

**职责**:
- Strands Agent 执行
- 工具调用 (Browser, Code Interpreter, 部署工具)
- **代码提取** (`extract_code_from_result`)
- Memory 持久化

**关键代码**:
```python
# agentcore_handler.py
@app.entrypoint
async def invoke(payload, context):
    result_str = await invoke_with_mcp(payload, session)
    return format_response(result_str, session)  # 包含 code
```

## 数据流

### 代码生成流程

```
1. Frontend → POST /api/chat {"message": "创建博客API"}
         ↓
2. ECS (server.py)
   - 创建/获取 SessionState
   - client.invoke(prompt, session_id, payload)
         ↓
3. AgentCore Runtime (agentcore_handler.py)
   - Agent 调用 generate_website_code 工具
   - extract_code_from_result() 提取代码到 session.generated_code
   - format_response() 返回 {"code": {"files": {...}}, ...}
         ↓
4. ECS (server.py)
   - sync_from_response(metadata) 获取 code
   - 返回给前端
         ↓
5. Frontend → 显示预览
```

### 响应格式

AgentCore Runtime 返回:
```json
{
  "response": "已生成博客API...",
  "session_id": "xxx",
  "status": "success",
  "phase": "previewing",
  "code": {
    "html": "...",
    "css": "...",
    "javascript": "...",
    "files": {
      "index.html": "...",
      "styles.css": "...",
      "main.js": "...",
      "server.js": "..."
    }
  }
}
```

## 部署方式

| 组件 | 部署命令 | 说明 |
|------|---------|------|
| AgentCore Runtime | `agentcore deploy` | 部署 Agent 逻辑 |
| ECS Backend | `scripts/deploy-ecs-backend.sh` | 部署 API 中转层 |
| Frontend | `scripts/deploy-frontend-lambda.sh` | 部署前端 |

## 何时需要重新部署

| 修改文件 | 需要部署 |
|---------|---------|
| `agent/agentcore_handler.py` | AgentCore Runtime (`agentcore deploy`) |
| `agent/tools/*.py` | AgentCore Runtime |
| `agent/server.py` | ECS Backend |
| `frontend/*` | Frontend |

## 环境变量

### ECS Backend
```
AWS_REGION=us-east-1
AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:...
```

### AgentCore Runtime
```
AGENTCORE_BROWSER_ID=ugc_browser-xxx
AGENTCORE_CODE_INTERPRETER_ID=ugc_code_interpreter-xxx
MEMORY_ID=ugc_website_generator_mem-xxx
```

## 关键文件

```
ugc-ai-demo/
├── Dockerfile                    # ECS Backend 镜像
├── buildspec.yml                 # ECS CodeBuild 配置
├── agent/
│   ├── server.py                 # ECS Backend 入口
│   ├── agentcore_handler.py      # AgentCore Runtime 入口
│   ├── agentcore_client.py       # AgentCore API 客户端
│   ├── Dockerfile                # AgentCore Runtime 镜像
│   ├── .bedrock_agentcore.yaml   # AgentCore 配置
│   └── tools/
│       ├── code_generator.py     # 代码生成工具
│       ├── deploy_tools.py       # 部署工具
│       └── browser_tool.py       # 浏览器工具
└── frontend/                     # Next.js 前端 (子模块)
```

---
最后更新: 2026-03-01
