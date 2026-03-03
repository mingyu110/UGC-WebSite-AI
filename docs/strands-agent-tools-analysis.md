# Strands Agent 工具使用分析文档

## 1. 概述

本文档分析了 Strands Agent 的工具使用模式，以及本项目中的具体实现。

## 2. 参考文档

| 文档 | 链接 | 说明 |
|------|------|------|
| **Strands Tools 概念** | https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools | 工具定义、自动加载、热重载 |
| **动态工具加载** | https://builder.aws.com/content/2zeKrP0DJJLqC0Q9jp842IPxLMm/dynamic-tool-loading-in-strands-sdk-enabling-meta-tooling-for-adaptive-ai-agents | 运行时动态加载工具实现 |

## 3. Strands Agent 工具加载方式

### 3.1 目录自动加载 + 热重载（推荐）

通过设置 `load_tools_from_directory` 参数，Agent 会在初始化时自动从指定目录加载工具，并在工具文件修改后自动重新加载（hot reload）。

```python
from strands import Agent
from strands.models import BedrockModel

# 指定工具目录路径
TOOLS_DIRECTORY = "./tools"

agent = Agent(
    model=BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0"),
    system_prompt="Your system prompt",
    load_tools_from_directory=TOOLS_DIRECTORY,  # 自动加载工具目录
    messages=conversation_history,
)
```

**特点：**
- Agent 初始化时自动扫描目录下所有带 `@tool` 装饰器的函数
- 工具文件修改后自动重新加载，无需重启 Agent
- 适合开发时的动态调试体验

### 3.2 运行时动态加载单个工具

使用 `load_tool` 方法可以在 Agent 运行过程中动态加载 Python 工具：

```python
# 从文件路径加载
agent.load_tool("./new_tools/custom_tool.py")

# 从模块加载
agent.load_tool("my_package.tools.custom_tool")
```

**使用场景：**
- Meta-tooling：Agent 自己创建/加载新工具
- 按需加载：根据任务类型动态加载特定工具
- 插件系统：支持第三方工具扩展

### 3.3 手动传入工具列表（传统方式）

```python
from strands import Agent

agent = Agent(
    model=bedrock_model,
    tools=[tool1, tool2, tool3],  # 手动传入工具列表
)
```

## 4. 工具函数定义规范

### 4.1 使用 @tool 装饰器

```python
from strands.tools import tool

@tool
def my_tool(param1: str, param2: int = 10) -> dict:
    """
    工具描述，Agent 会根据此描述决定何时调用。

    Args:
        param1: 参数1描述
        param2: 参数2描述，默认值10

    Returns:
        包含结果的字典
    """
    return {"result": f"Processed {param1} with {param2}"}
```

**要求：**
- 使用 `@tool` 装饰器标记工具函数
- 有清晰的 docstring 描述功能（Agent 根据此决定何时调用）
- 使用类型注解定义参数和返回值
- 返回可序列化的数据（dict, str, list 等）

## 5. 本项目工具架构

### 5.1 工具目录结构

```
agent/tools/
├── __init__.py           # 工具导出
├── browser_tool.py       # 浏览器工具 (@tool)
├── code_interpreter.py   # 代码解释器 (@tool)
├── code_generator.py     # 代码生成器 (@tool)
├── deploy_tools.py       # 部署工具 (@tool)
├── memory_tools.py       # 内存工具 (@tool)
├── s3_cloudfront.py      # S3+CloudFront 部署实现
└── lambda_adapter.py     # Lambda+WebAdapter 部署实现
```

### 5.2 Agent 创建与工具加载（优化后）

```python
# agentcore_handler.py

# 工具目录路径
TOOLS_DIRECTORY = os.path.join(os.path.dirname(__file__), "tools")

async def invoke_with_mcp(payload, session):
    # 创建 Bedrock 模型
    bedrock_model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        temperature=0.0,
        max_tokens=64000,
    )

    # 创建 Agent，使用 load_tools_from_directory 自动加载工具
    # 参考: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools
    agent = Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        load_tools_from_directory=TOOLS_DIRECTORY,  # 自动加载工具目录
        messages=conversation_messages,
    )

    # 调用 Agent
    result = agent(prompt)
```

### 5.3 工具分类

| 类别 | 文件 | 工具函数 | 功能 |
|------|------|---------|------|
| **浏览器** | browser_tool.py | `browse_url`, `extract_design_elements`, `capture_page_screenshot` | 网页浏览、设计提取 |
| **代码解释器** | code_interpreter.py | `validate_code_syntax`, `run_code_check`, `execute_code` | 代码验证、执行 |
| **代码生成** | code_generator.py | `generate_website_code`, `edit_website_code` | AI 代码生成 |
| **部署** | deploy_tools.py | `deploy_to_s3`, `deploy_to_lambda`, `get_deployment_status`, `list_deployments` | 网站部署 |
| **内存** | memory_tools.py | `save_session`, `get_session`, `save_user_preference` 等 | 会话管理 |

## 6. 部署工具实现示例

### 6.1 deploy_to_s3 工具

```python
from strands.tools import tool

@tool
def deploy_to_s3(
    project_name: str,
    files: List[Dict[str, Any]],
    index_document: str = "index.html",
) -> Dict[str, Any]:
    """
    Deploy static website to S3 + CloudFront CDN.

    This tool deploys HTML/CSS/JS files to AWS S3 with CloudFront CDN
    for global content delivery. Perfect for:
    - Static websites
    - Single Page Applications (React, Vue, etc.)
    - Landing pages
    - Portfolio sites

    Args:
        project_name: Unique project identifier
        files: List of files to deploy
        index_document: Main entry file

    Returns:
        Deployment result with CloudFront URL
    """
    # 验证输入
    if not re.match(r'^[a-zA-Z0-9-]+$', project_name):
        return {"status": "failed", "error": "Invalid project_name"}

    # 延迟加载部署器
    deployer = _get_s3_deployer()

    # 同步包装异步操作
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            deployer.deploy(project_name=project_name, files=files)
        )
        return result
    finally:
        loop.close()
```

## 7. AWS 服务集成

| 工具模块 | AWS 服务 | 操作 |
|---------|---------|------|
| s3_cloudfront.py | S3, CloudFront | 创建桶、上传文件、创建 CDN 分发 |
| lambda_adapter.py | Lambda, IAM | 创建函数、配置 URL、管理角色 |
| browser_tool.py | AgentCore Browser | 浏览器自动化 |
| code_interpreter.py | AgentCore Code Interpreter | 代码执行沙箱 |

## 8. 错误处理模式

### 模式1: 字典状态返回
```python
@tool
def tool_function(...) -> dict:
    try:
        result = do_work()
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "failed", "error": str(e)}
```

### 模式2: 带清理的异常处理
```python
async def deploy(...):
    try:
        # 部署逻辑
        return {"status": "deployed", ...}
    except Exception as e:
        await self._cleanup_bucket(bucket_name)
        raise
```

## 9. 架构总结

### 关键设计模式

1. **目录自动加载**: 使用 `load_tools_from_directory` 自动加载 `./tools` 目录下的工具
2. **热重载支持**: 工具文件修改后自动重新加载
3. **@tool 装饰器**: 所有工具函数使用装饰器标记
4. **延迟加载**: 重资源（如 AWS 客户端）按需初始化
5. **同步/异步桥接**: 在同步工具中执行异步操作

### 数据流

```
Request → invoke() → build_session_from_payload()
    → invoke_with_mcp() → Agent(load_tools_from_directory=TOOLS_DIRECTORY)
    → Route to handler → Agent executes with auto-loaded tools
    → Extract results → Save to memory → format_response()
```

### 对比：优化前 vs 优化后

| 方面 | 优化前 | 优化后 |
|------|--------|--------|
| **加载方式** | 手动 import + 列表传递 | `load_tools_from_directory` 自动加载 |
| **热重载** | 不支持 | 支持 |
| **代码量** | 需要维护 `_get_local_tools()` 等函数 | 简化，只需指定目录 |
| **可维护性** | 添加新工具需修改多处 | 添加 .py 文件即可 |

---

## 参考链接

- Strands Tools 概念: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools
- 动态工具加载: https://builder.aws.com/content/2zeKrP0DJJLqC0Q9jp842IPxLMm/dynamic-tool-loading-in-strands-sdk-enabling-meta-tooling-for-adaptive-ai-agents
- AWS AgentCore 文档: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html

---
*生成日期: 2026-02-28*
