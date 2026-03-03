# AWS Bedrock AgentCore 内置工具指南

## 概述

Amazon Bedrock AgentCore 提供两个内置工具，帮助 AI Agent 与外部环境交互：

| 工具 | 功能 | 适用场景 |
|------|------|---------|
| **Browser Tool** | 云端浏览器自动化 | 浏览网页、提取内容、截图 |
| **Code Interpreter** | 安全代码执行沙箱 | 代码验证、数据分析、计算 |

---

## 1. Browser Tool

### 1.1 功能介绍

Browser Tool 提供云端托管的 Chromium 浏览器，支持：
- 网页导航和内容提取
- JavaScript 执行
- 截图捕获
- 会话录制和回放
- 实时查看浏览器操作

### 1.2 创建 Browser Tool

**方式一：AWS CLI**

```bash
# 1. 创建 S3 bucket（存储录像）
aws s3api create-bucket \
  --bucket ugc-ai-demo-browser-recordings-${ACCOUNT_ID} \
  --region us-east-1

# 2. 创建 IAM Role
aws iam create-role \
  --role-name ugc-ai-demo-agentcore-tools-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# 3. 附加权限策略
aws iam put-role-policy \
  --role-name ugc-ai-demo-agentcore-tools-role \
  --policy-name AgentCoreToolsPolicy \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": ["s3:PutObject", "s3:GetObject", "s3:ListBucket"],
        "Resource": ["arn:aws:s3:::ugc-ai-demo-browser-recordings-*"]
      },
      {
        "Effect": "Allow",
        "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
        "Resource": "*"
      }
    ]
  }'

# 4. 创建 Browser Tool（名称只能用字母数字和下划线）
aws bedrock-agentcore-control create-browser \
  --region us-east-1 \
  --name "ugc_browser" \
  --description "Browser for web browsing and design extraction" \
  --network-configuration '{"networkMode": "PUBLIC"}' \
  --recording '{"enabled": true, "s3Location": {"bucket": "ugc-ai-demo-browser-recordings-ACCOUNT_ID", "prefix": "recordings"}}' \
  --execution-role-arn "arn:aws:iam::ACCOUNT_ID:role/ugc-ai-demo-agentcore-tools-role"
```

**方式二：AWS Console**

1. 打开 [AgentCore Console](https://console.aws.amazon.com/bedrock-agentcore/home#)
2. 左侧导航 → **Built-in tools** → **Create browser tool**
3. 填写名称、选择网络模式、配置录像存储

### 1.3 本项目使用场景

在 UGC AI Demo 中，Browser Tool 用于：
- 浏览用户提供的参考网站
- 提取设计元素（颜色、字体、布局）
- 截取网页截图作为设计参考

### 1.4 核心代码

**配置（`agent/tools/browser_tool.py`）**

```python
import os
from strands_tools.browser import AgentCoreBrowser

# 从环境变量读取 Browser ID
BROWSER_ID = os.environ.get("AGENTCORE_BROWSER_ID", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

def get_browser():
    """获取 AgentCore Browser 实例"""
    if not BROWSER_ID:
        raise ValueError("AGENTCORE_BROWSER_ID not set")

    return AgentCoreBrowser(
        region=REGION,
        identifier=BROWSER_ID,  # Browser Tool ID
    )
```

**工具函数（`@tool` 装饰器）**

```python
from strands.tools import tool

@tool
def browse_url(url: str, extract_content: bool = True) -> dict:
    """浏览网页并提取内容"""
    browser, _ = get_browser()

    # 初始化会话
    browser.browser(browser_input={
        "action": {"type": "init_session", "session_name": "browse-session"}
    })

    # 导航到 URL
    browser.browser(browser_input={
        "action": {"type": "navigate", "url": url, "session_name": "browse-session"}
    })

    # 提取内容
    if extract_content:
        result = browser.browser(browser_input={
            "action": {"type": "get_html", "selector": "body", "session_name": "browse-session"}
        })
        return {"success": True, "content": result.get("html", "")}

    return {"success": True, "url": url}

@tool
def extract_design_elements(url: str) -> dict:
    """提取网页设计元素"""
    browser, _ = get_browser()

    # 初始化并导航
    browser.browser(browser_input={"action": {"type": "init_session", "session_name": "design-session"}})
    browser.browser(browser_input={"action": {"type": "navigate", "url": url, "session_name": "design-session"}})

    # 执行 JavaScript 提取颜色和字体
    result = browser.browser(browser_input={
        "action": {
            "type": "evaluate",
            "script": """
            (() => {
                const colors = new Set();
                const fonts = new Set();
                document.querySelectorAll('*').forEach(el => {
                    const style = getComputedStyle(el);
                    colors.add(style.color);
                    colors.add(style.backgroundColor);
                    fonts.add(style.fontFamily.split(',')[0].trim());
                });
                return {colors: [...colors].slice(0,10), fonts: [...fonts].slice(0,5)};
            })()
            """,
            "session_name": "design-session"
        }
    })

    return {"success": True, "design_elements": result}
```

---

## 2. Code Interpreter

### 2.1 功能介绍

Code Interpreter 提供安全的代码执行环境：
- 支持 Python、JavaScript、TypeScript
- 隔离的沙箱环境
- 文件读写操作
- 数据分析和可视化

### 2.2 安全模式

| 模式 | 网络访问 | 适用场景 |
|------|---------|---------|
| **SANDBOX** | 无 | 代码验证、本地计算（推荐） |
| **PUBLIC** | 有 | 需要 pip install 或访问外部 API |
| **VPC** | 仅内网 | 访问私有资源 |

### 2.3 创建 Code Interpreter

```bash
# 创建 Code Interpreter（SANDBOX 模式更安全）
aws bedrock-agentcore-control create-code-interpreter \
  --region us-east-1 \
  --name "ugc_code_interpreter" \
  --description "Code Interpreter for code validation" \
  --network-configuration '{"networkMode": "SANDBOX"}' \
  --execution-role-arn "arn:aws:iam::ACCOUNT_ID:role/ugc-ai-demo-agentcore-tools-role"
```

### 2.4 本项目使用场景

在 UGC AI Demo 中，Code Interpreter 用于：
- 验证生成的 HTML/CSS/JavaScript 语法
- 检查代码错误
- 执行简单的数据处理脚本

### 2.5 核心代码

**配置（`agent/tools/code_interpreter.py`）**

```python
import os
from strands_tools.code_interpreter import AgentCoreCodeInterpreter

CODE_INTERPRETER_ID = os.environ.get("AGENTCORE_CODE_INTERPRETER_ID", "")
REGION = os.environ.get("AWS_REGION", "us-east-1")

def get_code_interpreter():
    """获取 Code Interpreter 实例"""
    if CODE_INTERPRETER_ID:
        return AgentCoreCodeInterpreter(
            region=REGION,
            identifier=CODE_INTERPRETER_ID,
        )
    else:
        # 使用默认托管资源
        return AgentCoreCodeInterpreter(region=REGION)
```

**工具函数**

```python
from strands.tools import tool

@tool
def validate_code_syntax(code: str, language: str = "javascript") -> dict:
    """验证代码语法"""
    interpreter, _ = get_code_interpreter()

    if language == "javascript":
        validation_code = f'''
const code = `{code.replace("`", "\\`")}`;
try {{
    new Function(code);
    console.log(JSON.stringify({{valid: true, errors: []}}));
}} catch (e) {{
    console.log(JSON.stringify({{valid: false, errors: [e.message]}}));
}}
'''
    elif language == "python":
        validation_code = f'''
import ast, json
try:
    ast.parse("""{code}""")
    print(json.dumps({{"valid": True, "errors": []}}))
except SyntaxError as e:
    print(json.dumps({{"valid": False, "errors": [str(e)]}}))
'''

    result = interpreter.code_interpreter(code_input={
        "code": validation_code,
        "language": language
    })

    return result

@tool
def run_code_check(files: dict) -> dict:
    """检查多个文件的语法"""
    results = {}
    for filename, content in files.items():
        lang = "javascript" if filename.endswith(".js") else "python"
        results[filename] = validate_code_syntax(content, lang)
    return {"success": all(r.get("valid") for r in results.values()), "results": results}
```

---

## 3. 在 Agent 中集成

### 3.1 环境变量配置

```bash
export AGENTCORE_BROWSER_ID=ugc_browser-pXEF8HjbYA
export AGENTCORE_CODE_INTERPRETER_ID=ugc_code_interpreter-xWbd7jhzHc
export AWS_REGION=us-east-1
```

### 3.2 Agent 加载原生工具

```python
# agentcore_handler.py

def _get_agentcore_tools():
    """加载 AgentCore 原生工具"""
    tools = []

    # Browser Tool
    try:
        from tools.browser_tool import get_native_browser_tool
        browser_tool = get_native_browser_tool()
        if browser_tool:
            tools.append(browser_tool)
    except Exception as e:
        print(f"Browser tool not available: {e}")

    # Code Interpreter
    try:
        from tools.code_interpreter import get_native_code_interpreter_tool
        code_tool = get_native_code_interpreter_tool()
        if code_tool:
            tools.append(code_tool)
    except Exception as e:
        print(f"Code Interpreter not available: {e}")

    return tools

# 创建 Agent
agent = Agent(
    model=bedrock_model,
    system_prompt=SYSTEM_PROMPT,
    tools=_get_agentcore_tools(),  # 原生工具
    load_tools_from_directory=TOOLS_DIRECTORY,  # @tool 装饰的函数
)
```

---

## 4. 本项目资源配置

| 资源 | ID / 名称 |
|------|-----------|
| **Browser Tool** | `ugc_browser-pXEF8HjbYA` |
| **Code Interpreter** | `ugc_code_interpreter-xWbd7jhzHc` |
| **S3 Bucket** | `ugc-ai-demo-browser-recordings-947472889616` |
| **IAM Role** | `ugc-ai-demo-agentcore-tools-role` |

---

## 参考文档

- [Browser Tool 官方文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html)
- [Code Interpreter 官方文档](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)
- [创建 Browser](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-create.html)
- [创建 Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-create.html)

---

**最后更新**：2026-02-28
