# Bedrock AgentCore CLI 部署 MCP Server 完整指南

## 目录

1. [概述](#概述)
2. [前置要求](#前置要求)
3. [安装 AgentCore CLI](#安装-agentcore-cli)
4. [MCP Server 项目结构](#mcp-server-项目结构)
5. [配置文件详解](#配置文件详解)
6. [部署流程](#部署流程)
7. [Gateway 配置](#gateway-配置)
8. [OAuth 认证配置](#oauth-认证配置)
9. [常见问题排查](#常见问题排查)
10. [最佳实践](#最佳实践)

---

## 概述

Amazon Bedrock AgentCore 提供了两种部署 MCP Server 的方式：

1. **AgentCore Runtime** - 无服务器运行时环境
   - 同步请求超时：15 分钟
   - 异步会话超时：可配置（默认 8 小时）
   - 适合长时间运行的任务

2. **AgentCore Gateway** - API Gateway 模式
   - 调用超时：5 分钟
   - 适合快速响应的工具
   - 支持多个 MCP Server 聚合

本指南重点介绍如何使用 **AgentCore CLI** 部署 MCP Server 到这两种环境。

---

## 前置要求

### 1. AWS 账户和权限

需要以下 IAM 权限：
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock-agentcore:*",
        "ecr:*",
        "iam:CreateRole",
        "iam:AttachRolePolicy",
        "iam:PassRole",
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. 本地环境

- **Python 3.9+**
- **Docker** - 用于构建容器镜像
- **AWS CLI** - 配置好凭证
- **pip** - Python 包管理器

### 3. 验证环境

```bash
# 检查 Python 版本
python --version  # 应该 >= 3.9

# 检查 Docker
docker --version

# 检查 AWS CLI 配置
aws sts get-caller-identity

# 检查 AWS 区域
aws configure get region  # 推荐 us-east-1
```

---

## 安装 AgentCore CLI

### 方法 1：使用 pip 安装（推荐）

```bash
# 安装 AgentCore Starter Toolkit（包含 CLI）
pip install bedrock-agentcore-starter-toolkit

# 验证安装
agentcore --version
```

### CLI 命令概览

```bash
# 查看所有命令
agentcore --help

# 主要命令：
# - create      创建新的 Agent 项目
# - deploy      部署 Agent/MCP Server 到 AgentCore Runtime（推荐）
# - dev         本地开发服务器
# - invoke      调用已部署的 Agent
# - status      查看 Runtime 状态
# - destroy     销毁 Runtime 资源
```

**重要说明：**
- CLI 命令是 `agentcore`，不是 `bedrock-agentcore`
- 主要用于部署 **Agent**，MCP Server 是 Agent 的一种特殊形式
- 两种部署类型：
  - `direct_code_deploy`: Python 代码直接部署，无需 Docker（推荐 MCP Server）
  - `container`: 使用 CodeBuild 构建 ARM64 容器镜像（推荐复杂 Agent）

---

## MCP Server 项目结构

### 标准项目结构

```
my-mcp-server/
├── .bedrock_agentcore.yaml    # AgentCore 配置文件（通过 configure 生成）
├── requirements.txt            # Python 依赖（必需）
├── mcp_server.py               # MCP Server 入口文件（必需）
└── __init__.py                 # Python 包标识（必需）
```

**最小化项目结构（必需文件）：**
1. `mcp_server.py` - MCP Server 代码
2. `requirements.txt` - 依赖列表
3. `__init__.py` - 空文件即可
4. `.bedrock_agentcore.yaml` - 通过 `agentcore configure` 生成

### 初始化新项目

```bash
# 创建项目目录
mkdir my-mcp-server
cd my-mcp-server

# 创建必需文件
touch __init__.py
touch requirements.txt
touch mcp_server.py

# 配置部署（生成 .bedrock_agentcore.yaml）
agentcore configure -e mcp_server.py --protocol MCP

# 这会启动交互式配置向导，生成：
# - .bedrock_agentcore.yaml
```

**注意：**
- 不需要手动创建 Dockerfile（CLI 会自动生成）
- 使用 `agentcore configure` 而不是 `init`
- 必须指定 `--protocol MCP` 来标识这是 MCP Server

---

## 配置文件详解

### .bedrock_agentcore.yaml

这是 AgentCore CLI 的核心配置文件：

```yaml
# MCP Server 基本信息
name: my-mcp-server              # Runtime 名称（必需）
description: "My MCP Server"     # 描述（可选）

# 运行时配置
runtime:
  type: mcp                      # 固定为 mcp
  port: 8000                     # 容器内端口（必需，固定 8000）
  host: 0.0.0.0                  # 监听地址（必需，固定 0.0.0.0）
  transport: streamable-http     # 传输协议（必需）
  
# 容器配置
container:
  # 方式 1：使用 CLI 自动构建（推荐）
  build:
    context: .                   # 构建上下文目录
    dockerfile: Dockerfile       # Dockerfile 路径（可选）
  
  # 方式 2：使用已有镜像
  # image: 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-mcp-server:latest
  
  # 资源配置
  memory: 2048                   # 内存 MB（可选，默认 2048）
  cpu: 1024                      # CPU 单位（可选，默认 1024）
  
  # 环境变量
  environment:
    AWS_REGION: us-east-1
    LOG_LEVEL: INFO
    CUSTOM_VAR: value

# 超时配置
timeout:
  idle: 900                      # 空闲超时（秒，默认 900 = 15 分钟）
  max_session: 28800             # 最大会话时长（秒，默认 28800 = 8 小时）

# IAM 角色（可选）
# 如果不指定，CLI 会自动创建
execution_role_arn: arn:aws:iam::123456789012:role/MyMCPServerRole

# 标签（可选）
tags:
  Environment: production
  Team: ai-team
  Project: mcp-deployment
```

### 配置说明

#### 1. 必需字段

- `name` - Runtime 名称，全局唯一
- `runtime.type` - 必须是 `mcp`
- `runtime.port` - 必须是 `8000`
- `runtime.host` - 必须是 `0.0.0.0`
- `runtime.transport` - 必须是 `streamable-http`

#### 2. 容器配置

**选项 A：自动构建（推荐）**
```yaml
container:
  build:
    context: .
    dockerfile: Dockerfile  # 可选，默认 ./Dockerfile
```

**选项 B：使用已有镜像**
```yaml
container:
  image: <ECR_IMAGE_URI>
```

#### 3. 资源限制

```yaml
container:
  memory: 2048    # 512 - 30720 MB
  cpu: 1024       # 256 - 4096 (1 vCPU = 1024)
```

#### 4. 超时配置

```yaml
timeout:
  idle: 900           # 空闲超时（15 分钟）
  max_session: 28800  # 最大会话（8 小时）
```

对于长时间运行的任务，增加这些值：
```yaml
timeout:
  idle: 3600          # 1 小时
  max_session: 86400  # 24 小时
```

---

## 部署流程

### 步骤 1：准备 MCP Server 代码

**server.py 示例：**

```python
"""
MCP Server for AgentCore Runtime
必须监听 0.0.0.0:8000 并使用 streamable-http 传输
"""
from mcp.server.fastmcp import FastMCP
import os

# 创建 MCP Server
# 关键配置：host="0.0.0.0", stateless_http=True
mcp = FastMCP(
    name="my-mcp-server",
    host="0.0.0.0",
    stateless_http=True
)

@mcp.tool()
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b

if __name__ == "__main__":
    # 使用 streamable-http 传输
    mcp.run(transport="streamable-http")
```

**requirements.txt：**

```txt
mcp>=1.0.0
fastmcp>=0.1.0
boto3>=1.34.0
```

### 步骤 2：创建 requirements.txt

```txt
mcp>=1.0.0
```

**注意：** 只需要 `mcp` 包，CLI 会自动处理其他依赖。

### 步骤 3：配置部署

**方法 1：使用 CLI 创建项目（推荐新项目）**

```bash
# 创建新的 Agent 项目
agentcore create

# 交互式向导会询问：
# 1. Agent name
# 2. Language (Python/TypeScript)
# 3. Protocol (HTTP/MCP)
# 4. 等等...
```

**方法 2：手动配置（已有项目）**

在项目目录下创建 `.bedrock_agentcore.yaml`，然后运行：

```bash
# 进入项目目录
cd my-mcp-server

# 直接部署（会读取现有配置）
agentcore deploy
```

配置文件示例见上文"配置文件详解"章节。

### 步骤 4：部署到 AgentCore Runtime

```bash
# 部署 MCP Server（推荐方式）
agentcore deploy

# 这个命令会根据配置自动选择部署模式：
# - direct_code_deploy: Python 代码直接部署（无需 Docker）
# - container: 使用 CodeBuild 构建 ARM64 容器镜像

# 部署选项：
# agentcore deploy                → 云端部署（推荐）
# agentcore deploy --local        → 本地开发模式
# agentcore deploy --local-build  → 本地构建 + 云端部署

# 部署成功后会返回 Runtime ARN：
# arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/my-mcp-server-abc123
```

### 步骤 5：验证部署

```bash
# 调用已部署的 MCP Server
agentcore invoke --runtime-arn <RUNTIME_ARN>

# 或者设置环境变量
export AGENT_ARN="<RUNTIME_ARN>"
agentcore invoke
```

### 步骤 5：测试 MCP Server

**方法 1：使用 MCP Client（Python）**

```python
# test_mcp_remote.py
import asyncio
import os
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async def main():
    # 从环境变量获取
    agent_arn = os.getenv('AGENT_ARN')
    bearer_token = os.getenv('BEARER_TOKEN')  # OAuth token
    
    # 编码 ARN 用于 URL
    encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
    
    # 构建 MCP URL
    mcp_url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    
    # 设置认证头
    headers = {
        "authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json"
    }
    
    # 连接并测试
    async with streamablehttp_client(
        mcp_url, 
        headers, 
        timeout=120, 
        terminate_on_close=False
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            
            # 列出工具
            tools = await session.list_tools()
            print(f"Available tools: {tools}")
            
            # 调用工具
            result = await session.call_tool("hello", {"name": "World"})
            print(f"Result: {result}")

# 运行
asyncio.run(main())
```

**方法 2：使用 Strands MCPClient**

```python
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient
import os

# Runtime URL
agent_arn = os.getenv('AGENT_ARN')
bearer_token = os.getenv('BEARER_TOKEN')

encoded_arn = agent_arn.replace(':', '%3A').replace('/', '%2F')
runtime_url = f"https://bedrock-agentcore.us-east-1.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

# 创建客户端
headers = {"authorization": f"Bearer {bearer_token}"}
mcp_client = MCPClient(
    lambda: streamablehttp_client(runtime_url, headers=headers)
)

# 测试工具
with mcp_client:
    tools = mcp_client.list_tools_sync()
    print(f"Available tools: {[t.tool_name for t in tools]}")
    
    # 调用工具
    result = mcp_client.call_tool_sync("hello", {"name": "World"})
    print(f"Result: {result}")
```

---

## Gateway 配置

### 什么是 AgentCore Gateway？

Gateway 允许你将多个 MCP Server 聚合到一个端点，提供：
- 统一的访问入口
- OAuth 认证
- 请求路由
- 负载均衡

### 创建 Gateway

**使用 AgentCore Starter Toolkit CLI：**

```bash
# 创建基本 Gateway
bedrock-agentcore-starter-toolkit gateway create-mcp-gateway \
  --name my-mcp-gateway \
  --region us-east-1

# 启用语义搜索
bedrock-agentcore-starter-toolkit gateway create-mcp-gateway \
  --name my-mcp-gateway \
  --region us-east-1 \
  --enable_semantic_search

# 使用自定义 IAM 角色
bedrock-agentcore-starter-toolkit gateway create-mcp-gateway \
  --name my-mcp-gateway \
  --region us-east-1 \
  --role-arn arn:aws:iam::123456789012:role/MyGatewayRole
```

**注意：** Gateway CLI 命令使用 `bedrock-agentcore-starter-toolkit gateway`，不是 `agentcore`。

### 添加 Runtime 到 Gateway

```bash
# 添加 MCP Server Target
bedrock-agentcore-starter-toolkit gateway create-mcp-gateway-target \
  --gateway-arn <GATEWAY_ARN> \
  --gateway-url <GATEWAY_URL> \
  --role-arn <EXECUTION_ROLE_ARN> \
  --name my-mcp-server \
  --target-type mcp_server \
  --target-payload '{"runtimeArn": "<RUNTIME_ARN>"}'
```

### Gateway URL 格式

```
https://<gateway-id>.gateway.bedrock-agentcore.<region>.amazonaws.com/mcp
```

### 使用 Gateway

```python
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp.mcp_client import MCPClient

# Gateway URL
gateway_url = "https://my-gateway-abc123.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"

# 如果 Gateway 启用了 OAuth，需要添加 token
headers = {"Authorization": f"Bearer {oauth_token}"}

mcp_client = MCPClient(
    lambda: streamablehttp_client(gateway_url, headers=headers)
)

with mcp_client:
    # Gateway 会自动路由到正确的 Runtime
    tools = mcp_client.list_tools_sync()
    print(tools)
```

---

## OAuth 认证配置

### 为什么需要 OAuth？

- 保护 MCP Server 不被未授权访问
- 支持 M2M（Machine-to-Machine）认证
- 集成企业身份系统

### 使用 Cognito 配置 OAuth

#### 1. 创建 Cognito User Pool

```bash
aws cognito-idp create-user-pool \
  --pool-name mcp-gateway-pool \
  --policies "PasswordPolicy={MinimumLength=8}" \
  --region us-east-1
```

#### 2. 创建 Resource Server

```bash
aws cognito-idp create-resource-server \
  --user-pool-id <USER_POOL_ID> \
  --identifier mcp-gateway \
  --name "MCP Gateway" \
  --scopes ScopeName=invoke,ScopeDescription="Invoke MCP tools" \
  --region us-east-1
```

#### 3. 创建 App Client（M2M）

```bash
aws cognito-idp create-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-name mcp-m2m-client \
  --generate-secret \
  --allowed-o-auth-flows client_credentials \
  --allowed-o-auth-scopes mcp-gateway/invoke \
  --region us-east-1
```

#### 4. 配置 Gateway 使用 Cognito

```bash
aws bedrock-agentcore update-gateway \
  --gateway-id <GATEWAY_ID> \
  --auth-config '{
    "type": "COGNITO",
    "cognitoConfig": {
      "userPoolId": "<USER_POOL_ID>",
      "clientId": "<CLIENT_ID>",
      "scopes": ["mcp-gateway/invoke"]
    }
  }' \
  --region us-east-1
```

#### 5. 获取 OAuth Token

```python
import requests

def get_oauth_token(domain, client_id, client_secret, scope):
    """从 Cognito 获取 M2M OAuth token"""
    token_url = f"https://{domain}.auth.us-east-1.amazoncognito.com/oauth2/token"
    
    response = requests.post(
        token_url,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope,
        }
    )
    
    return response.json()["access_token"]

# 使用
token = get_oauth_token(
    domain="my-domain",
    client_id="abc123",
    client_secret="secret",
    scope="mcp-gateway/invoke"
)
```

---

## 常见问题排查

### 1. 部署失败：权限不足

**错误：**
```
Error: User is not authorized to perform: bedrock-agentcore:CreateRuntime
```

**解决：**
```bash
# 检查 IAM 权限
aws iam get-user

# 添加必要权限（联系管理员）
```

### 2. 容器启动失败

**错误：**
```
Container failed to start: Port 8000 not responding
```

**检查清单：**
- ✅ mcp_server.py 中 `host="0.0.0.0"`
- ✅ mcp_server.py 中 `mcp.run(transport="streamable-http")`
- ✅ requirements.txt 包含 `mcp`
- ✅ 项目包含 `__init__.py` 文件

**查看日志：**
```bash
# 使用 AWS CLI 查看日志
aws logs tail /aws/bedrock-agentcore/runtime/<runtime-name> --follow

# 或使用 CloudWatch 控制台
```

### 3. 工具调用超时

**错误：**
```
RuntimeError: Connection to the MCP server was closed
```

**解决方案：**

**选项 A：增加超时配置**
```yaml
# .bedrock_agentcore.yaml
timeout:
  idle: 3600        # 增加到 1 小时
  max_session: 86400  # 增加到 24 小时
```

**选项 B：使用异步任务管理**（推荐）
- 工具立即返回任务 ID
- 后台执行长时间任务
- 客户端轮询状态

### 4. Gateway 认证失败

**错误：**
```
401 Unauthorized: Invalid token
```

**检查：**
```bash
# 验证 token
curl -H "Authorization: Bearer $TOKEN" \
  https://<gateway-url>/mcp

# 检查 token 过期时间
echo $TOKEN | base64 -d | jq .exp
```

### 5. 内存不足

**错误：**
```
Container killed: Out of memory
```

**解决：**
```yaml
# .bedrock_agentcore.yaml
container:
  memory: 4096  # 增加到 4GB
  cpu: 2048     # 增加到 2 vCPU
```

---

## 最佳实践

### 1. 项目组织

```
my-mcp-project/
├── .bedrock_agentcore.yaml
├── .dockerignore
├── .gitignore
├── Dockerfile
├── requirements.txt
├── README.md
├── server.py                 # MCP Server 入口
├── config/                   # 配置文件
│   ├── __init__.py
│   └── settings.py
├── tools/                    # MCP 工具实现
│   ├── __init__.py
│   ├── tool1.py
│   └── tool2.py
├── utils/                    # 工具函数
│   ├── __init__.py
│   └── helpers.py
└── tests/                    # 测试
    ├── __init__.py
    └── test_tools.py
```

### 2. 环境变量管理

```yaml
# .bedrock_agentcore.yaml
container:
  environment:
    # 从 AWS Secrets Manager 读取
    DB_PASSWORD: "{{resolve:secretsmanager:my-secret:SecretString:password}}"
    
    # 从 Systems Manager Parameter Store 读取
    API_KEY: "{{resolve:ssm:/my-app/api-key}}"
    
    # 直接设置
    LOG_LEVEL: INFO
    AWS_REGION: us-east-1
```

### 3. 日志记录

```python
import logging
import json

# 使用结构化日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@mcp.tool()
def my_tool(param: str) -> str:
    logger.info(json.dumps({
        "event": "tool_invoked",
        "tool": "my_tool",
        "param": param
    }))
    
    try:
        result = do_work(param)
        logger.info(json.dumps({
            "event": "tool_completed",
            "tool": "my_tool",
            "result": result
        }))
        return result
    except Exception as e:
        logger.error(json.dumps({
            "event": "tool_failed",
            "tool": "my_tool",
            "error": str(e)
        }))
        raise
```

### 4. 错误处理

```python
from typing import Dict, Any

@mcp.tool()
def safe_tool(param: str) -> Dict[str, Any]:
    """工具应该返回结构化的结果，包含错误信息"""
    try:
        result = do_work(param)
        return {
            "status": "success",
            "data": result
        }
    except ValueError as e:
        return {
            "status": "error",
            "error_type": "validation_error",
            "message": str(e)
        }
    except Exception as e:
        logger.exception("Unexpected error")
        return {
            "status": "error",
            "error_type": "internal_error",
            "message": "An unexpected error occurred"
        }
```

### 5. 性能优化

```python
# 使用连接池
import boto3
from functools import lru_cache

@lru_cache(maxsize=1)
def get_s3_client():
    """复用 boto3 客户端"""
    return boto3.client('s3')

@mcp.tool()
def upload_file(content: str, key: str) -> str:
    s3 = get_s3_client()  # 复用连接
    s3.put_object(Bucket='my-bucket', Key=key, Body=content)
    return f"Uploaded to s3://my-bucket/{key}"
```

### 6. 版本管理

```yaml
# .bedrock_agentcore.yaml
name: my-mcp-server-v2  # 使用版本后缀

tags:
  Version: "2.0.0"
  GitCommit: "abc123"
  DeployedBy: "ci-cd"
  DeployedAt: "2024-02-27"
```

### 7. CI/CD 集成

```yaml
# .github/workflows/deploy.yml
name: Deploy MCP Server

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Install AgentCore CLI
        run: pip install bedrock-agentcore-starter-toolkit

      - name: Deploy MCP Server
        run: agentcore deploy
```

### 8. 监控和告警

```python
# 使用 CloudWatch Metrics
import boto3

cloudwatch = boto3.client('cloudwatch')

@mcp.tool()
def monitored_tool(param: str) -> str:
    import time
    start = time.time()
    
    try:
        result = do_work(param)
        
        # 记录成功指标
        cloudwatch.put_metric_data(
            Namespace='MCPServer',
            MetricData=[{
                'MetricName': 'ToolSuccess',
                'Value': 1,
                'Unit': 'Count'
            }, {
                'MetricName': 'ToolDuration',
                'Value': time.time() - start,
                'Unit': 'Seconds'
            }]
        )
        
        return result
    except Exception as e:
        # 记录失败指标
        cloudwatch.put_metric_data(
            Namespace='MCPServer',
            MetricData=[{
                'MetricName': 'ToolFailure',
                'Value': 1,
                'Unit': 'Count'
            }]
        )
        raise
```

---

## 参考资料

### 官方文档

- [Amazon Bedrock AgentCore 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AgentCore CLI GitHub](https://github.com/aws/bedrock-agentcore-sdk-python)
- [MCP 协议规范](https://modelcontextprotocol.io/docs)
- [FastMCP 文档](https://github.com/jlowin/fastmcp)

### 示例项目

- [AWS 官方示例](https://github.com/aws-samples/sample-mcp-for-long-runing-tasks-with-amazon-bedrock-agentcore)
- [Strands Agents 文档](https://strandsagents.com/latest/)

### 相关博客

- [在 Amazon Bedrock AgentCore 上构建长时间运行的 MCP 服务器](https://aws.amazon.com/blogs/machine-learning/build-long-running-mcp-servers-on-amazon-bedrock-agentcore-with-strands-agents-integration/)

---

## 总结

使用 Bedrock AgentCore CLI 部署 MCP Server 的关键步骤：

1. ✅ 安装 CLI：`pip install bedrock-agentcore-starter-toolkit`
2. ✅ 创建项目文件：`server.py`, `requirements.txt`, `__init__.py`
3. ✅ 初始化配置：`agentcore create` 或手动创建 `.bedrock_agentcore.yaml`
4. ✅ 部署：`agentcore deploy`
5. ✅ 测试：使用 MCPClient 调用工具

**关键配置要点：**
- 端口必须是 `8000`
- 主机必须是 `0.0.0.0`
- 传输必须是 `streamable-http`
- 使用 `stateless_http=True`
- 必须包含 `__init__.py` 文件

**CLI 命令区别：**
- `agentcore` - 用于 Agent/MCP Server 部署
- `bedrock-agentcore-starter-toolkit gateway` - 用于 Gateway 管理

**生产环境建议：**
- 使用 Gateway 聚合多个 MCP Server
- 配置 OAuth 认证保护端点（使用 Cognito）
- 实施结构化日志和监控
- 使用 CI/CD 自动化部署
- 对长时间任务使用异步模式

**重要提示：**
- AgentCore Runtime 的 URL 格式是：
  ```
  https://bedrock-agentcore.<region>.amazonaws.com/runtimes/<encoded-arn>/invocations?qualifier=DEFAULT
  ```
- 不是 `https://<runtime-id>.runtime.bedrock-agentcore.<region>.amazonaws.com/mcp`
- 必须对 ARN 进行 URL 编码（`:` → `%3A`, `/` → `%2F`）

---

---

## 附录：UGC AI Demo Agent 部署

### 快速部署命令

```bash
# 1. 激活虚拟环境
cd /Users/jackljx/Documents/Agnes/ugc-ai-demo/agent
source ../.venv/bin/activate

# 2. 设置环境变量（AgentCore 内置工具）
export AWS_REGION=us-east-1
export AGENTCORE_BROWSER_ID=ugc_browser-pXEF8HjbYA
export AGENTCORE_CODE_INTERPRETER_ID=ugc_code_interpreter-xWbd7jhzHc

# 3. 部署
agentcore deploy
```

### 部署输出信息

```
Agent Name: ugc_website_generator
Agent ARN: arn:aws:bedrock-agentcore:us-east-1:947472889616:runtime/ugc_website_generator-r4ApYLEVE1
ECR URI: 947472889616.dkr.ecr.us-east-1.amazonaws.com/bedrock-agentcore-ugc_website_generator:latest
Memory ID: ugc_website_generator_mem-Zd80vx6DdN
```

### AgentCore 内置工具配置

| 工具 | ID | 模式 | 用途 |
|------|-----|------|------|
| **Browser** | `ugc_browser-pXEF8HjbYA` | PUBLIC | 浏览参考网站、提取设计元素 |
| **Code Interpreter** | `ugc_code_interpreter-xWbd7jhzHc` | SANDBOX | 代码语法验证、安全执行 |

### 验证部署

```bash
# 查看状态
agentcore status

# 测试调用
agentcore invoke '{"prompt": "Hello"}'

# 查看日志
aws logs tail /aws/bedrock-agentcore/runtimes/ugc_website_generator-r4ApYLEVE1-DEFAULT \
  --log-stream-name-prefix "$(date +%Y/%m/%d)/[runtime-logs]" --follow
```

### 部署注意事项

1. **必须在虚拟环境中运行** - `agentcore` CLI 安装在 `.venv` 中
2. **使用 CodeBuild 构建** - 默认使用云端 ARM64 构建，无需本地 Docker
3. **环境变量传递** - Browser/Code Interpreter ID 通过代码中的 `os.environ.get()` 读取
4. **部署时间** - 通常约 1-2 分钟完成

---

**最后更新**：2026-02-28
**版本**：1.2.0
