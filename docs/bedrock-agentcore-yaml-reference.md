# Amazon Bedrock AgentCore 配置文件参考指南

## 概述

`.bedrock_agentcore.yaml` 是 Amazon Bedrock AgentCore Starter Toolkit 的核心配置文件，用于定义 Agent 的部署配置、AWS 资源设置和运行时参数。该文件由 `agentcore create` 或 `agentcore configure` 命令自动生成，并在 `agentcore deploy`/`agentcore launch` 时读取。

**官方文档参考**：
- [AgentCore Starter Toolkit](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-toolkit.html)
- [UpdateAgentRuntime API](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateAgentRuntime.html)

---

## 配置文件结构

```yaml
default_agent: <agent_name>           # 默认 Agent 名称
agents:
  <agent_name>:                       # Agent 配置块
    name: <agent_name>                # Agent 名称（必需）
    language: python                  # 编程语言：python | typescript
    node_version: '20'                # Node.js 版本（TypeScript 项目）
    entrypoint: <path>                # 入口文件绝对路径
    deployment_type: container        # 部署类型：container | direct_code_deploy
    runtime_type: null                # 运行时类型
    platform: linux/arm64             # 容器平台（AgentCore 要求 ARM64）
    container_runtime: none           # 容器运行时
    source_path: <path>               # 源代码目录路径

    aws:                              # AWS 配置
      execution_role: <role_arn>      # IAM 执行角色 ARN
      execution_role_auto_create: false
      account: '<account_id>'         # AWS 账户 ID
      region: us-east-1               # AWS 区域
      ecr_repository: <ecr_uri>       # ECR 镜像仓库 URI
      ecr_auto_create: false
      s3_path: null                   # S3 代码路径（直接代码部署）
      s3_auto_create: false

      network_configuration:          # 网络配置
        network_mode: PUBLIC          # PUBLIC | VPC
        network_mode_config: null     # VPC 配置（安全组、子网）

      protocol_configuration:         # 协议配置
        server_protocol: HTTP         # HTTP | MCP | A2A

      observability:                  # 可观测性配置
        enabled: true

      lifecycle_configuration:        # 生命周期配置
        idle_runtime_session_timeout: null  # 空闲超时（秒，默认 900）
        max_lifetime: null            # 最大生命周期（秒，默认 28800）

      environment_variables:          # 环境变量（重要）
        KEY: value

    bedrock_agentcore:                # AgentCore 资源信息
      agent_id: <runtime_id>
      agent_arn: <runtime_arn>
      agent_session_id: null

    codebuild:                        # CodeBuild 配置
      project_name: <project_name>
      execution_role: <role_arn>
      source_bucket: <bucket_name>

    memory:                           # AgentCore Memory 配置
      mode: STM_ONLY                  # STM_ONLY | LTM | STM_AND_LTM
      memory_id: <memory_id>
      memory_arn: <memory_arn>
      memory_name: <memory_name>
      event_expiry_days: 30

    identity:                         # 身份配置
      credential_providers: []        # OAuth 凭证提供者
      workload: null

    aws_jwt:                          # JWT 认证配置
      enabled: false
      audiences: []
      signing_algorithm: ES384
      issuer_url: null
      duration_seconds: 300

    authorizer_configuration: null    # 授权配置
    request_header_configuration: null # 请求头配置
    oauth_configuration: null         # OAuth 配置
```

---

## 关键配置详解

### 1. 基本信息

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Agent 唯一名称，用于资源命名 |
| `language` | string | 是 | 编程语言：`python` 或 `typescript` |
| `entrypoint` | string | 是 | Agent 入口文件的绝对路径 |
| `deployment_type` | string | 是 | `container`（容器部署）或 `direct_code_deploy`（直接代码部署） |
| `platform` | string | 是 | 必须为 `linux/arm64`（AgentCore 使用 AWS Graviton） |

### 2. AWS 配置 (`aws`)

#### 2.1 IAM 角色

```yaml
aws:
  execution_role: arn:aws:iam::123456789012:role/MyAgentRole
  execution_role_auto_create: false  # 是否自动创建角色
```

**角色权限要求**：
- `bedrock:InvokeModel` - 调用 Bedrock 模型
- `logs:CreateLogGroup/Stream` - CloudWatch 日志
- `ecr:GetAuthorizationToken` - ECR 访问
- 其他工具所需权限（S3、DynamoDB 等）

#### 2.2 网络配置

```yaml
network_configuration:
  network_mode: PUBLIC              # PUBLIC：公网访问 | VPC：VPC 内部
  network_mode_config:              # 仅 VPC 模式需要
    securityGroups:
      - sg-12345678
    subnets:
      - subnet-12345678
```

#### 2.3 协议配置

```yaml
protocol_configuration:
  server_protocol: HTTP   # HTTP：标准 HTTP | MCP：Model Context Protocol | A2A：Agent-to-Agent
```

#### 2.4 生命周期配置

```yaml
lifecycle_configuration:
  idle_runtime_session_timeout: 900   # 空闲超时，60-28800 秒，默认 900
  max_lifetime: 28800                  # 最大生命周期，60-28800 秒，默认 28800
```

**使用场景建议**：
- 交互式聊天：idle=900, max=28800
- 批处理任务：idle=3600, max=86400
- 开发测试：idle=300, max=3600

### 3. 环境变量 (`environment_variables`)

**这是本次修复的关键配置**。环境变量用于向 Agent 运行时传递配置信息。

```yaml
aws:
  environment_variables:
    AGENTCORE_BROWSER_ID: ugc_browser-pXEF8HjbYA
    AGENTCORE_CODE_INTERPRETER_ID: ugc_code_interpreter-xWbd7jhzHc
    MY_API_KEY: your-api-key
    LOG_LEVEL: INFO
```

**API 限制**（来自 [UpdateAgentRuntime API](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateAgentRuntime.html)）：
- 最多 50 个环境变量
- Key 长度：1-100 字符
- Value 长度：0-5000 字符

**常用环境变量**：

| 变量名 | 用途 |
|--------|------|
| `AGENTCORE_BROWSER_ID` | AgentCore Browser 工具 ID |
| `AGENTCORE_CODE_INTERPRETER_ID` | AgentCore Code Interpreter 工具 ID |
| `BEDROCK_AGENTCORE_MEMORY_ID` | AgentCore Memory ID（自动设置） |
| `AWS_REGION` | AWS 区域 |
| `LOG_LEVEL` | 日志级别 |

**重要提示**：每次执行 `agentcore deploy` 时，CLI 会读取此配置文件并更新 Runtime。如果配置文件中没有 `environment_variables`，之前通过 AWS CLI 设置的环境变量会被覆盖清空。

### 4. Memory 配置

```yaml
memory:
  mode: STM_ONLY                    # 记忆模式
  memory_id: my_agent_mem-xxxxx
  memory_arn: arn:aws:bedrock-agentcore:...
  memory_name: my_agent_mem
  event_expiry_days: 30             # 事件过期天数
```

**记忆模式**：
- `STM_ONLY` - 仅短期记忆（会话内）
- `LTM` - 仅长期记忆（跨会话）
- `STM_AND_LTM` - 短期 + 长期记忆

### 5. Identity 配置

```yaml
identity:
  credential_providers:
    - name: my-oauth-provider
      arn: arn:aws:bedrock-agentcore:...:oauth2credentialprovider/...
      type: custom-oauth2
      callback_url: ''
  workload: null
```

用于配置 OAuth 凭证提供者，支持 Agent 安全访问外部 API。

### 6. CodeBuild 配置

```yaml
codebuild:
  project_name: bedrock-agentcore-my_agent-builder
  execution_role: arn:aws:iam::...:role/...CodeBuild...
  source_bucket: bedrock-agentcore-codebuild-sources-...
```

**说明**：
- 容器部署模式下，使用 AWS CodeBuild 构建 ARM64 镜像
- 无需本地安装 Docker
- 构建日志可在 CloudWatch 查看

---

## CLI 命令与配置文件

| 命令 | 配置文件操作 |
|------|--------------|
| `agentcore create` | 创建新项目并生成配置文件 |
| `agentcore configure` | 更新现有配置文件 |
| `agentcore deploy` | 读取配置文件并部署到 Runtime |
| `agentcore launch` | 同 deploy，完整部署流程 |
| `agentcore dev` | 本地开发服务器，不使用 AWS 资源 |
| `agentcore destroy` | 删除 AWS 资源 |

### 配置命令示例

```bash
# 配置入口文件
agentcore configure -e my_agent.py

# 配置自定义 IAM 角色
agentcore configure -e my_agent.py --execution-role arn:aws:iam::123456789012:role/MyRole

# 配置请求头白名单
agentcore configure --request-header-allowlist "X-Amzn-Bedrock-AgentCore-Runtime-Custom-H1"
```

---

## 使用 AWS CLI 更新 Runtime

当需要更新环境变量但不想重新部署镜像时，可以使用 AWS CLI：

```bash
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id <runtime_id> \
  --role-arn "<role_arn>" \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --agent-runtime-artifact '{"containerConfiguration": {"containerUri": "<ecr_uri>"}}' \
  --environment-variables '{
    "AGENTCORE_BROWSER_ID": "ugc_browser-xxxxx",
    "AGENTCORE_CODE_INTERPRETER_ID": "ugc_code_interpreter-xxxxx"
  }' \
  --region us-east-1
```

**注意**：`update-agent-runtime` 需要所有必需参数（artifact, role-arn, network-configuration），即使只是更新环境变量。

---

## 最佳实践

### 1. 环境变量管理

```yaml
# 在配置文件中明确声明所有环境变量
aws:
  environment_variables:
    # AgentCore 内置工具
    AGENTCORE_BROWSER_ID: ugc_browser-xxxxx
    AGENTCORE_CODE_INTERPRETER_ID: ugc_code_interpreter-xxxxx
    # 应用配置
    LOG_LEVEL: INFO
    AWS_REGION: us-east-1
```

### 2. 版本控制

- `.bedrock_agentcore.yaml` 应该纳入版本控制
- 敏感信息（API Keys）不要直接写入配置文件，使用 AWS Secrets Manager

### 3. 多环境部署

```bash
# 开发环境
agentcore deploy --local

# 生产环境（使用 CodeBuild）
agentcore deploy
```

### 4. 故障排查

```bash
# 查看 Runtime 状态
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id <runtime_id> \
  --region us-east-1

# 查看日志
aws logs tail /aws/bedrock-agentcore/runtimes/<runtime_id>-DEFAULT --follow
```

---

## 常见问题：AgentCore 内置工具环境变量被覆盖

### 问题描述

AgentCore 提供了内置工具（Browser、Code Interpreter），需要通过环境变量传递工具 ID 给 Agent 代码：

```python
# Agent 代码中读取工具 ID
BROWSER_ID = os.environ.get("AGENTCORE_BROWSER_ID", "")
CODE_INTERPRETER_ID = os.environ.get("AGENTCORE_CODE_INTERPRETER_ID", "")
```

**问题**：每次执行 `agentcore deploy` 命令时，CLI 会使用 `UpdateAgentRuntime` API 更新 Runtime 配置。如果 `.bedrock_agentcore.yaml` 配置文件中没有 `environment_variables` 部分，**之前通过 AWS CLI 设置的环境变量会被清空**。

### 问题现象

```
错误: AGENTCORE_BROWSER_ID environment variable is not set
```

浏览器工具、代码解释器等功能突然失效，尽管之前正常工作。

### 根本原因

`agentcore deploy` 命令的行为：

1. 读取 `.bedrock_agentcore.yaml` 配置文件
2. 调用 `UpdateAgentRuntime` API 更新 Runtime
3. API 会用配置文件中的 `environment_variables` **完全替换** Runtime 中的环境变量
4. 如果配置文件没有该字段，则清空所有环境变量

```
部署前 Runtime 环境变量:
  AGENTCORE_BROWSER_ID=ugc_browser-xxxxx
  AGENTCORE_CODE_INTERPRETER_ID=ugc_code_interpreter-xxxxx
  BEDROCK_AGENTCORE_MEMORY_ID=xxx

执行 agentcore deploy (配置文件无 environment_variables)

部署后 Runtime 环境变量:
  BEDROCK_AGENTCORE_MEMORY_ID=xxx  (仅保留 Memory 相关，由 CLI 自动添加)
  ❌ AGENTCORE_BROWSER_ID 丢失
  ❌ AGENTCORE_CODE_INTERPRETER_ID 丢失
```

### 解决方案

#### 方案一：在配置文件中声明环境变量（推荐）

在 `.bedrock_agentcore.yaml` 的 `aws` 部分添加 `environment_variables`：

```yaml
agents:
  my_agent:
    # ... 其他配置 ...
    aws:
      # ... 其他 AWS 配置 ...
      lifecycle_configuration:
        idle_runtime_session_timeout: null
        max_lifetime: null
      environment_variables:                              # 添加此部分
        AGENTCORE_BROWSER_ID: ugc_browser-pXEF8HjbYA
        AGENTCORE_CODE_INTERPRETER_ID: ugc_code_interpreter-xWbd7jhzHc
```

这样每次部署时，环境变量会自动包含在更新请求中。

#### 方案二：部署后使用 AWS CLI 恢复

如果环境变量已经丢失，可以使用 AWS CLI 恢复：

```bash
# 1. 获取当前 Runtime 配置
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id <runtime_id> \
  --region us-east-1

# 2. 更新环境变量（需要提供所有必需参数）
aws bedrock-agentcore-control update-agent-runtime \
  --agent-runtime-id <runtime_id> \
  --role-arn "<从步骤1获取>" \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --agent-runtime-artifact '{"containerConfiguration": {"containerUri": "<从步骤1获取>"}}' \
  --environment-variables '{
    "BEDROCK_AGENTCORE_MEMORY_ID": "<从步骤1获取>",
    "BEDROCK_AGENTCORE_MEMORY_NAME": "<从步骤1获取>",
    "AGENTCORE_BROWSER_ID": "ugc_browser-xxxxx",
    "AGENTCORE_CODE_INTERPRETER_ID": "ugc_code_interpreter-xxxxx"
  }' \
  --region us-east-1
```

### 预防措施

1. **始终在配置文件中声明环境变量** - 不要依赖 AWS CLI 单独设置
2. **将配置文件纳入版本控制** - 确保团队成员使用相同配置
3. **部署后验证** - 使用 `get-agent-runtime` 确认环境变量正确

```bash
# 验证环境变量
aws bedrock-agentcore-control get-agent-runtime \
  --agent-runtime-id <runtime_id> \
  --region us-east-1 \
  --query 'environmentVariables'
```

### 查找内置工具 ID

如果不知道工具 ID，可以查看项目中的配置文件：

```bash
# 查找项目中记录的工具 ID
grep -r "AGENTCORE_BROWSER_ID\|AGENTCORE_CODE_INTERPRETER_ID" \
  --include="*.sh" --include="*.md" --include="*.py" .
```

或者检查 AgentCore 创建工具时的输出记录。

---

## 参考资料

- [Amazon Bedrock AgentCore 文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AgentCore Starter Toolkit GitHub](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [UpdateAgentRuntime API 参考](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_UpdateAgentRuntime.html)
- [Boto3 BedrockAgentCoreControl](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore-control.html)

---

