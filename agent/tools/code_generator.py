"""
Code Generator Tool

Generates website code based on descriptions and design elements.
Uses ModelRouter for intelligent model selection and cost optimization:
- Nova 2 Lite for copywriting and template tasks (~90% cost savings)
- Claude Sonnet for code generation (highest quality)
"""

import json
import os
import re
from typing import Optional

from strands.tools import tool

from model_router import ModelRouter, TaskType, create_model_router

# Global model router instance
_model_router: Optional[ModelRouter] = None


def _is_blog_api(api_name: str, endpoints: list) -> bool:
    """Check if this is a blog-type API."""
    name_lower = api_name.lower()
    blog_keywords = ["blog", "博客", "文章", "article", "post"]
    if any(kw in name_lower for kw in blog_keywords):
        return True
    # Check endpoints for blog patterns
    for ep in endpoints:
        path = ep.get("path", "").lower()
        if any(p in path for p in ["/posts", "/articles", "/blog"]):
            return True
    return False


def _generate_blog_frontend(api_name: str, endpoints: list, primary_color: str = "#3b82f6") -> dict:
    """Generate a blog-style frontend for blog APIs."""
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_name}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-brand">{api_name}</div>
        <button class="btn-new" onclick="showModal()">+ 写文章</button>
    </nav>
    <main class="container">
        <div class="posts-grid" id="posts"></div>
        <div class="empty-state" id="empty">
            <p>暂无文章</p>
            <button class="btn-primary" onclick="showModal()">创建第一篇文章</button>
        </div>
    </main>
    <div class="modal" id="modal">
        <div class="modal-content">
            <h2 id="modal-title">写文章</h2>
            <input type="hidden" id="edit-id">
            <input type="text" id="title" placeholder="文章标题" required>
            <input type="text" id="author" placeholder="作者" required>
            <textarea id="content" placeholder="文章内容..." required></textarea>
            <div class="modal-actions">
                <button class="btn-secondary" onclick="hideModal()">取消</button>
                <button class="btn-primary" onclick="savePost()">发布</button>
            </div>
        </div>
    </div>
    <script src="main.js"></script>
</body>
</html>'''

    css = f'''* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; color: #333; }}
.navbar {{ background: {primary_color}; color: white; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }}
.nav-brand {{ font-size: 1.4rem; font-weight: 600; }}
.btn-new {{ background: white; color: {primary_color}; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500; }}
.container {{ max-width: 900px; margin: 24px auto; padding: 0 16px; }}
.posts-grid {{ display: flex; flex-direction: column; gap: 16px; }}
.post-card {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
.post-card h3 {{ color: #333; margin-bottom: 8px; cursor: pointer; }}
.post-card h3:hover {{ color: {primary_color}; }}
.post-meta {{ color: #888; font-size: 0.85rem; margin-bottom: 12px; }}
.post-excerpt {{ color: #555; line-height: 1.6; }}
.post-actions {{ margin-top: 12px; display: flex; gap: 8px; }}
.btn-edit, .btn-delete {{ padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.85rem; }}
.btn-edit {{ background: #e3f2fd; color: #1976d2; }}
.btn-delete {{ background: #ffebee; color: #d32f2f; }}
.empty-state {{ text-align: center; padding: 60px 20px; color: #888; }}
.empty-state p {{ margin-bottom: 16px; }}
.btn-primary {{ background: {primary_color}; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }}
.btn-secondary {{ background: #e0e0e0; color: #333; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; }}
.modal {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); justify-content: center; align-items: center; }}
.modal.active {{ display: flex; }}
.modal-content {{ background: white; padding: 24px; border-radius: 12px; width: 90%; max-width: 500px; }}
.modal-content h2 {{ margin-bottom: 16px; color: {primary_color}; }}
.modal-content input, .modal-content textarea {{ width: 100%; padding: 12px; margin-bottom: 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 1rem; }}
.modal-content textarea {{ height: 150px; resize: vertical; }}
.modal-actions {{ display: flex; gap: 8px; justify-content: flex-end; }}'''

    js = '''const API = window.location.origin;
const isPreview = window.location.protocol === "file:" || !window.location.hostname;
let posts = [];

const mockPosts = [
  { id: 1, title: "欢迎使用博客系统", author: "管理员", content: "这是一个示例文章，展示博客系统的基本功能。您可以创建、编辑和删除文章。", created_at: "2024-01-15" },
  { id: 2, title: "如何写好一篇博客", author: "作者", content: "写博客需要明确主题，组织好内容结构，使用清晰的语言表达观点。", created_at: "2024-01-14" }
];

async function loadPosts() {
  if (isPreview) { posts = mockPosts; renderPosts(); return; }
  try {
    const res = await fetch(API + "/api/posts");
    const data = await res.json();
    posts = data.posts || data || [];
    renderPosts();
  } catch (e) { posts = mockPosts; renderPosts(); }
}

function renderPosts() {
  const grid = document.getElementById("posts");
  const empty = document.getElementById("empty");
  if (!posts.length) { grid.innerHTML = ""; empty.style.display = "block"; return; }
  empty.style.display = "none";
  grid.innerHTML = posts.map(p => `
    <div class="post-card">
      <h3 onclick="viewPost(${p.id})">${p.title}</h3>
      <div class="post-meta">${p.author} · ${p.created_at?.split("T")[0] || "刚刚"}</div>
      <div class="post-excerpt">${(p.content || "").substring(0, 100)}...</div>
      <div class="post-actions">
        <button class="btn-edit" onclick="editPost(${p.id})">编辑</button>
        <button class="btn-delete" onclick="deletePost(${p.id})">删除</button>
      </div>
    </div>
  `).join("");
}

function showModal(post = null) {
  document.getElementById("modal").classList.add("active");
  document.getElementById("modal-title").textContent = post ? "编辑文章" : "写文章";
  document.getElementById("edit-id").value = post?.id || "";
  document.getElementById("title").value = post?.title || "";
  document.getElementById("author").value = post?.author || "";
  document.getElementById("content").value = post?.content || "";
}

function hideModal() { document.getElementById("modal").classList.remove("active"); }

function editPost(id) { const p = posts.find(x => x.id === id); if (p) showModal(p); }

function viewPost(id) { const p = posts.find(x => x.id === id); if (p) alert("标题: " + p.title + "\\n\\n" + p.content); }

async function savePost() {
  const id = document.getElementById("edit-id").value;
  const data = { title: document.getElementById("title").value, author: document.getElementById("author").value, content: document.getElementById("content").value };
  if (!data.title || !data.author || !data.content) { alert("请填写所有字段"); return; }
  if (isPreview) {
    if (id) { const i = posts.findIndex(x => x.id == id); if (i >= 0) posts[i] = {...posts[i], ...data}; }
    else { posts.unshift({ id: Date.now(), ...data, created_at: new Date().toISOString() }); }
    hideModal(); renderPosts(); return;
  }
  try {
    const url = id ? API + "/api/posts/" + id : API + "/api/posts";
    await fetch(url, { method: id ? "PUT" : "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(data) });
    hideModal(); loadPosts();
  } catch (e) { alert("保存失败: " + e.message); }
}

async function deletePost(id) {
  if (!confirm("确定删除这篇文章吗？")) return;
  if (isPreview) { posts = posts.filter(x => x.id !== id); renderPosts(); return; }
  try { await fetch(API + "/api/posts/" + id, { method: "DELETE" }); loadPosts(); }
  catch (e) { alert("删除失败: " + e.message); }
}

document.addEventListener("DOMContentLoaded", loadPosts);'''

    return {"index.html": html, "styles.css": css, "main.js": js}


def _generate_api_preview_page(api_name: str, endpoints: list, primary_color: str = "#3b82f6") -> dict:
    """
    Generate an interactive API preview page for backend projects.

    Args:
        api_name: Name of the API
        endpoints: List of endpoint dicts with method, path, description
        primary_color: Primary theme color

    Returns:
        dict with index.html, styles.css, main.js for preview
    """
    # Build endpoints HTML
    endpoints_html = ""
    for ep in endpoints:
        method = ep.get("method", "GET")
        path = ep.get("path", "/")
        desc = ep.get("description", "")
        method_class = method.lower()
        endpoints_html += f'''
            <div class="endpoint" data-method="{method}" data-path="{path}">
                <span class="method {method_class}">{method}</span>
                <span class="path">{path}</span>
                <span class="desc">{desc}</span>
            </div>'''

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{api_name} - API 文档</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>📡 {api_name}</h1>
            <span class="status" id="status">● 预览模式</span>
        </header>

        <main>
            <section class="endpoints-panel">
                <h2>API 端点</h2>
                <div class="endpoints-list">{endpoints_html}
                </div>
            </section>

            <section class="test-panel">
                <h2>测试面板</h2>
                <div class="request-form">
                    <div class="form-row">
                        <select id="method">
                            <option value="GET">GET</option>
                            <option value="POST">POST</option>
                            <option value="PUT">PUT</option>
                            <option value="DELETE">DELETE</option>
                        </select>
                        <input type="text" id="url" placeholder="/api/endpoint">
                    </div>
                    <div class="form-row">
                        <textarea id="body" placeholder='{{"key": "value"}}'></textarea>
                    </div>
                    <button id="send-btn">发送请求</button>
                </div>

                <div class="response-panel">
                    <h3>响应</h3>
                    <pre id="response">{{"message": "点击端点或发送请求查看响应"}}</pre>
                </div>
            </section>
        </main>

        <footer>
            <p>部署后，此页面将连接真实 API 端点</p>
        </footer>
    </div>
    <script src="main.js"></script>
</body>
</html>'''

    css_content = f'''* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #f5f5f5;
    color: #333;
    line-height: 1.6;
}}

.container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}}

header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    background: {primary_color};
    color: white;
    border-radius: 8px;
    margin-bottom: 20px;
}}

header h1 {{
    font-size: 1.5rem;
}}

.status {{
    padding: 6px 12px;
    background: rgba(255,255,255,0.2);
    border-radius: 20px;
    font-size: 0.85rem;
}}

.status.online {{
    background: #22c55e;
}}

main {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}}

@media (max-width: 768px) {{
    main {{
        grid-template-columns: 1fr;
    }}
}}

section {{
    background: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}}

section h2 {{
    margin-bottom: 15px;
    color: {primary_color};
    font-size: 1.1rem;
}}

.endpoints-list {{
    display: flex;
    flex-direction: column;
    gap: 8px;
}}

.endpoint {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: #f8f9fa;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}}

.endpoint:hover {{
    background: #e9ecef;
    transform: translateX(4px);
}}

.endpoint.active {{
    background: {primary_color}15;
    border-left: 3px solid {primary_color};
}}

.method {{
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
    color: white;
    min-width: 60px;
    text-align: center;
}}

.method.get {{ background: #22c55e; }}
.method.post {{ background: #3b82f6; }}
.method.put {{ background: #f59e0b; }}
.method.delete {{ background: #ef4444; }}

.path {{
    font-family: monospace;
    font-weight: 500;
}}

.desc {{
    color: #666;
    font-size: 0.85rem;
    margin-left: auto;
}}

.request-form {{
    display: flex;
    flex-direction: column;
    gap: 10px;
}}

.form-row {{
    display: flex;
    gap: 10px;
}}

.form-row select {{
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-size: 0.9rem;
    background: white;
}}

.form-row input {{
    flex: 1;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-family: monospace;
}}

.form-row textarea {{
    width: 100%;
    height: 80px;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: 6px;
    font-family: monospace;
    resize: vertical;
}}

#send-btn {{
    padding: 12px 20px;
    background: {primary_color};
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
}}

#send-btn:hover {{
    background: {primary_color}dd;
}}

.response-panel {{
    margin-top: 20px;
}}

.response-panel h3 {{
    margin-bottom: 10px;
    font-size: 0.95rem;
    color: #666;
}}

#response {{
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 15px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 0.85rem;
    max-height: 300px;
    overflow-y: auto;
}}

footer {{
    margin-top: 20px;
    text-align: center;
    color: #666;
    font-size: 0.85rem;
}}'''

    js_content = '''// API Preview Page JavaScript
const API_BASE = window.location.origin;

// Mock responses for preview mode
const mockResponses = {
    'GET /api/articles': {
        success: true,
        data: [
            { id: 1, title: '示例文章1', author: '作者A', created_at: '2024-01-01' },
            { id: 2, title: '示例文章2', author: '作者B', created_at: '2024-01-02' }
        ],
        pagination: { page: 1, limit: 10, total: 2 }
    },
    'GET /api/articles/:id': {
        success: true,
        data: { id: 1, title: '示例文章', content: '这是文章内容...', author: '作者' }
    },
    'POST /api/articles': {
        success: true,
        message: '文章创建成功',
        data: { id: 3, title: '新文章', author: '作者' }
    },
    'PUT /api/articles/:id': {
        success: true,
        message: '文章更新成功'
    },
    'DELETE /api/articles/:id': {
        success: true,
        message: '文章删除成功'
    },
    'GET /health': {
        success: true,
        message: 'API服务运行正常',
        timestamp: new Date().toISOString()
    }
};

// Check if running in preview mode (local file or localhost without backend)
function isPreviewMode() {
    return window.location.protocol === 'file:' ||
           !window.location.hostname ||
           window.location.hostname === 'localhost';
}

// Get mock response
function getMockResponse(method, path) {
    const key = `${method} ${path}`;
    // Try exact match first
    if (mockResponses[key]) return mockResponses[key];
    // Try pattern match (replace :id with actual pattern)
    for (const [pattern, response] of Object.entries(mockResponses)) {
        const regex = new RegExp('^' + pattern.replace(/:id/g, '\\\\d+') + '$');
        if (regex.test(key)) return response;
    }
    return { success: true, message: '请求成功（模拟响应）' };
}

// Update response display
function showResponse(data, isError = false) {
    const responseEl = document.getElementById('response');
    responseEl.textContent = JSON.stringify(data, null, 2);
    responseEl.style.color = isError ? '#ef4444' : '#d4d4d4';
}

// Send request
async function sendRequest() {
    const method = document.getElementById('method').value;
    const url = document.getElementById('url').value;
    const body = document.getElementById('body').value;

    if (!url) {
        showResponse({ error: '请输入 URL' }, true);
        return;
    }

    // Preview mode - return mock response
    if (isPreviewMode()) {
        const mockData = getMockResponse(method, url);
        showResponse(mockData);
        return;
    }

    // Real mode - send actual request
    try {
        const options = {
            method,
            headers: { 'Content-Type': 'application/json' }
        };
        if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {
            options.body = body;
        }

        const response = await fetch(API_BASE + url, options);
        const data = await response.json();
        showResponse(data, !response.ok);
    } catch (error) {
        showResponse({ error: error.message }, true);
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Update status
    const statusEl = document.getElementById('status');
    if (isPreviewMode()) {
        statusEl.textContent = '● 预览模式';
    } else {
        statusEl.textContent = '● 在线';
        statusEl.classList.add('online');
    }

    // Endpoint click handler
    document.querySelectorAll('.endpoint').forEach(el => {
        el.addEventListener('click', () => {
            // Update active state
            document.querySelectorAll('.endpoint').forEach(e => e.classList.remove('active'));
            el.classList.add('active');

            // Fill form
            document.getElementById('method').value = el.dataset.method;
            document.getElementById('url').value = el.dataset.path;

            // Show mock response
            if (isPreviewMode()) {
                const mockData = getMockResponse(el.dataset.method, el.dataset.path);
                showResponse(mockData);
            }
        });
    });

    // Send button handler
    document.getElementById('send-btn').addEventListener('click', sendRequest);

    // Enter key handler
    document.getElementById('url').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendRequest();
    });
});'''

    return {
        "index.html": html_content,
        "styles.css": css_content,
        "main.js": js_content,
    }


def _is_backend_api_project(files: dict) -> bool:
    """Check if the generated files represent a backend API project."""
    backend_indicators = ["server.js", "app.py", "main.py", "index.js"]
    backend_patterns = ["express", "flask", "fastapi", "app.get(", "app.post(", "@app.route"]

    for filename in files.keys():
        if filename in backend_indicators:
            return True

    for content in files.values():
        content_lower = content.lower() if isinstance(content, str) else ""
        for pattern in backend_patterns:
            if pattern.lower() in content_lower:
                return True

    return False


def _extract_api_endpoints(files: dict) -> list:
    """Extract API endpoints from backend code."""
    endpoints = []
    seen = set()

    for content in files.values():
        if not isinstance(content, str):
            continue

        # Match Express.js patterns: app.get('/path', ...) or router.get('/path', ...)
        express_patterns = re.findall(
            r"(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]",
            content,
            re.IGNORECASE
        )
        for method, path in express_patterns:
            key = f"{method.upper()}:{path}"
            if key not in seen:
                seen.add(key)
                endpoints.append({"method": method.upper(), "path": path, "description": ""})

        # Match Flask/FastAPI patterns: @app.route('/path') or @app.get('/path')
        flask_patterns = re.findall(
            r"@(?:app|router)\.(?:route\s*\(\s*['\"]([^'\"]+)['\"].*?methods\s*=\s*\[([^\]]+)\]|"
            r"(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"])",
            content,
            re.IGNORECASE
        )
        for match in flask_patterns:
            if match[0]:  # @app.route with methods
                path = match[0]
                methods = re.findall(r"['\"](\w+)['\"]", match[1])
                for method in methods:
                    key = f"{method.upper()}:{path}"
                    if key not in seen:
                        seen.add(key)
                        endpoints.append({"method": method.upper(), "path": path, "description": ""})
            elif match[2]:  # @app.get/@app.post etc
                method = match[2]
                path = match[3]
                key = f"{method.upper()}:{path}"
                if key not in seen:
                    seen.add(key)
                    endpoints.append({"method": method.upper(), "path": path, "description": ""})

    # Sort endpoints by path
    endpoints.sort(key=lambda x: (x["path"], x["method"]))

    # If no endpoints found, add default
    if not endpoints:
        endpoints = [
            {"method": "GET", "path": "/", "description": "根路径"},
            {"method": "GET", "path": "/health", "description": "健康检查"},
        ]

    return endpoints


def _get_model_router() -> ModelRouter:
    """Get or create the global ModelRouter instance."""
    global _model_router
    if _model_router is None:
        _model_router = create_model_router(
            region=os.environ.get('AWS_REGION', 'us-east-1')
        )
    return _model_router


def _is_backend_api_description(description: str) -> bool:
    """Check if the description is requesting a backend API project (needs server-side code)."""
    desc_lower = description.lower()

    # Keywords that indicate server-side/dynamic functionality
    backend_keywords = [
        "api", "后端", "backend", "服务端", "server",
        "接口", "restful", "rest api", "crud",
        "增删改查"
    ]

    # Keywords that STRONGLY indicate need for backend (even if "网站" is mentioned)
    database_keywords = [
        "数据库", "database", "保存数据", "存储数据", "永久保存",
        "数据要能保存", "mysql", "postgresql", "mongodb", "redis",
        "aurora", "dynamodb"
    ]

    # Keywords that indicate pure frontend (static) website
    static_frontend_keywords = ["静态", "static", "landing page", "着陆页", "展示页"]

    has_backend = any(kw in desc_lower for kw in backend_keywords)
    has_database = any(kw in desc_lower for kw in database_keywords)
    is_static = any(kw in desc_lower for kw in static_frontend_keywords)

    # If needs database or has backend keywords, it's a dynamic project
    # Database requirement takes priority - even "博客网站" with "数据库" is dynamic
    if has_database and not is_static:
        return True

    return has_backend and not is_static


def _generate_code_with_llm(description: str, design_elements: Optional[dict], framework: str) -> Optional[dict]:
    """
    Use LLM to generate actual website code based on description.

    Uses ModelRouter for intelligent model selection:
    - Claude Sonnet for code generation (highest quality)
    """
    router = _get_model_router()

    # Build prompt for code generation
    colors = design_elements.get("colors", {}) if design_elements else {}
    primary_color = colors.get("primary", "#3b82f6") if isinstance(colors, dict) else "#3b82f6"

    # Detect if this is a backend API project
    is_backend = _is_backend_api_description(description)
    print(f"[DEBUG code_generator] is_backend_api_description: {is_backend}")

    if is_backend:
        # Dynamic website prompt - front-end + back-end separation architecture
        prompt = f"""你是一个全栈开发者。生成一个前后端分离的动态网站。

## 需求
{description}

## 架构要求（前后端分离）
这是一个动态网站，必须包含：
1. **前端**：静态 HTML/CSS/JS 文件，通过 fetch 调用后端 API
2. **后端**：Express.js API 服务，连接数据库

## 必须生成的文件（缺一不可）

### index.html（前端入口 - 必须！）
- 完整的用户界面 HTML
- 内联 CSS 样式（<style> 标签内）
- 内联 JavaScript（<script> 标签内）
- 使用 fetch() 调用后端 API
- 主色调: {primary_color}
- 现代简洁的响应式设计

### server.js（后端 API - 必须！）
- Express.js 服务
- 提供 RESTful API（GET/POST/PUT/DELETE）
- 使用 express.static 提供静态文件
- 数据库连接使用环境变量 DATABASE_URL
- 临时使用内存数组存储数据（部署时连接真实数据库）
- 端口使用 process.env.PORT || 3000

### package.json（依赖配置 - 必须！）
- 包含 express, cors, pg 等依赖
- scripts 中包含 start 命令

## 输出格式
严格按照以下 JSON 格式输出，不要有任何其他内容：
```json
{{
  "index.html": "<!DOCTYPE html>...(完整HTML，包含内联CSS和JS)",
  "server.js": "const express = require('express')...(完整代码)",
  "package.json": "{{...}}"
}}
```

重要：
- 只输出 JSON，不要解释
- index.html 必须是完整的 HTML 文件
- 不要使用 React/Vue/Next.js 等框架
- JSON 字符串中的引号要用 \\" 转义"""
    else:
        # Frontend website prompt
        prompt = f"""你是一个专业的前端开发者。根据以下需求生成完整的网站代码。

## 需求描述
{description}

## 设计元素
- 主色调: {primary_color}
- 设计风格: {design_elements.get('layout', '现代简约') if design_elements else '现代简约'}

## 要求
1. 生成完整的 HTML、CSS、JavaScript 代码
2. 代码应该包含实际的内容（品牌名、产品介绍、联系方式等），不要显示需求描述本身
3. 使用响应式设计，适配移动端
4. CSS 使用指定的主色调
5. 代码结构清晰，注释完整

请直接输出 JSON 格式的结果，包含三个文件：
```json
{{
  "index.html": "完整的HTML代码",
  "styles.css": "完整的CSS代码",
  "main.js": "完整的JavaScript代码"
}}
```

只输出 JSON，不要其他内容。"""

    try:
        # Use ModelRouter with CODE_GENERATION task type for highest quality
        print(f"[DEBUG code_generator] Using ModelRouter with TaskType.CODE_GENERATION")
        config = router.get_model_config(TaskType.CODE_GENERATION)
        print(f"[DEBUG code_generator] Selected model: {config.model_id}")

        # Use sync invoke method
        content = router.invoke_sync(
            task_type=TaskType.CODE_GENERATION,
            prompt=prompt,
            max_tokens=8000,
            temperature=0.7,
        )

        print(f"[DEBUG code_generator] LLM response length: {len(content)}")

        # Extract JSON from response - look for ```json code block
        files = None
        json_match = re.search(r'```json\s*\n([\s\S]*?)```', content)
        if json_match:
            try:
                files = json.loads(json_match.group(1))
                print(f"[DEBUG code_generator] Parsed JSON files: {list(files.keys()) if files else 'None'}")
            except json.JSONDecodeError as e:
                print(f"[DEBUG code_generator] JSON parse failed: {e}")

        # Fallback: Extract files from code blocks if JSON parsing failed
        if not files:
            print("[DEBUG code_generator] JSON not found, trying code block extraction")
            files = {}

            # Extract all code blocks with any language tag
            all_blocks = re.findall(r'```(\w+)\s*\n([\s\S]*?)```', content)
            print(f"[DEBUG code_generator] Found {len(all_blocks)} code blocks")

            for lang, code in all_blocks:
                code = code.strip()
                lang_lower = lang.lower()

                # HTML files
                if lang_lower == 'html':
                    if "index.html" not in files:
                        files["index.html"] = code

                # CSS files
                elif lang_lower == 'css':
                    if "styles.css" not in files:
                        files["styles.css"] = code

                # JavaScript/Node.js files
                elif lang_lower in ['javascript', 'js', 'node']:
                    if any(ind in code.lower() for ind in ['express', 'app.listen', 'app.get(', 'app.post(', 'require(']):
                        if "server.js" not in files:
                            files["server.js"] = code
                    elif "main.js" not in files:
                        files["main.js"] = code

                # JSON files (package.json, etc.)
                elif lang_lower == 'json':
                    if '"name"' in code and '"dependencies"' in code:
                        files["package.json"] = code
                    elif '"name"' in code:
                        files["package.json"] = code

                # Python files
                elif lang_lower in ['python', 'py']:
                    if any(ind in code.lower() for ind in ['flask', 'fastapi', '@app.route', '@app.get']):
                        if "app.py" not in files:
                            files["app.py"] = code

                # Markdown files
                elif lang_lower in ['markdown', 'md']:
                    if "README.md" not in files:
                        files["README.md"] = code

            if files:
                print(f"[DEBUG code_generator] Extracted from code blocks: {list(files.keys())}")

        # Process files if we have any
        if files:
            # Log preview status - do NOT force generate preview
            # Preview is optional; deployed website functionality is the priority
            has_preview = "index.html" in files
            print(f"[DEBUG code_generator] Files generated: {list(files.keys())}, has_preview: {has_preview}")

            return {
                "files": files,
                "framework": framework,
                "deployment_type": "static" if framework == "html" else "dynamic",
            }
        else:
            print("[DEBUG code_generator] No files extracted from LLM response")

    except Exception as e:
        print(f"[ERROR] LLM code generation failed: {e}")

    # Fallback to template if LLM fails
    return None


# ==================== Edit Helper Functions ====================


def _normalize_selector_for_css(selector: str) -> str:
    """Normalize a DOM selector for CSS matching."""
    css_selector = selector.replace(" > ", " ").strip()
    return css_selector


def _get_fuzzy_selector(selector: str) -> str:
    """Get a fuzzy/simplified version of a selector for matching."""
    parts = selector.replace(">", " ").split()
    if parts:
        last_part = parts[-1].strip()
        if "#" in last_part:
            return "#" + last_part.split("#")[-1].split(".")[0].split("[")[0]
        elif "." in last_part:
            return "." + last_part.split(".")[-1].split("[")[0]
        else:
            return last_part.split("[")[0]
    return selector


def _apply_structured_style(css: str, selector: str, style_string: str) -> tuple:
    """
    Apply structured CSS properties to a selector.
    Handles input like: "color: #ff0000; font-size: 24px"
    """
    changes = []

    # Parse CSS properties
    properties = {}
    for prop in style_string.split(";"):
        prop = prop.strip()
        if ":" in prop:
            key, value = prop.split(":", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                properties[key] = value

    if not properties:
        return css, changes

    print(f"[DEBUG _apply_structured_style] Parsed properties: {properties}")

    css_selector = _normalize_selector_for_css(selector)
    rule_found = False

    # Try exact match
    selector_pattern = re.escape(css_selector)
    rule_match = re.search(rf'({selector_pattern})\s*\{{([^}}]*)\}}', css)

    if rule_match:
        rule_found = True
        old_rule_content = rule_match.group(2)
        new_rule_content = old_rule_content

        for prop, value in properties.items():
            prop_pattern = rf'{re.escape(prop)}\s*:\s*[^;]+;?'
            if re.search(prop_pattern, new_rule_content):
                new_rule_content = re.sub(prop_pattern, f'{prop}: {value};', new_rule_content)
            else:
                new_rule_content = new_rule_content.rstrip() + f'\n  {prop}: {value};'

        css = css.replace(rule_match.group(0), f'{css_selector} {{{new_rule_content}}}')
        changes.append(f"Updated styles for {css_selector}")

    # Try fuzzy match if not found
    if not rule_found:
        fuzzy_selector = _get_fuzzy_selector(selector)
        if fuzzy_selector != css_selector:
            rule_match = re.search(rf'([^{{}}]*{re.escape(fuzzy_selector)}[^{{}}]*)\s*\{{([^}}]*)\}}', css)
            if rule_match:
                rule_found = True
                matched_selector = rule_match.group(1).strip()
                old_rule_content = rule_match.group(2)
                new_rule_content = old_rule_content

                for prop, value in properties.items():
                    prop_pattern = rf'{re.escape(prop)}\s*:\s*[^;]+;?'
                    if re.search(prop_pattern, new_rule_content):
                        new_rule_content = re.sub(prop_pattern, f'{prop}: {value};', new_rule_content)
                    else:
                        new_rule_content = new_rule_content.rstrip() + f'\n  {prop}: {value};'

                css = css.replace(rule_match.group(0), f'{matched_selector} {{{new_rule_content}}}')
                changes.append(f"Updated styles for {matched_selector}")

    # Create new rule if not found
    if not rule_found:
        props_str = '\n  '.join(f'{k}: {v};' for k, v in properties.items())
        new_rule = f"\n{css_selector} {{\n  {props_str}\n}}\n"
        css += new_rule
        changes.append(f"Added new style rule for {css_selector}")

    return css, changes


def _apply_direct_edit(html: str, previous_value: str, new_value: str) -> tuple:
    """Apply direct text replacement in HTML."""
    changes = []

    if previous_value and new_value:
        if previous_value in html:
            html = html.replace(previous_value, new_value, 1)
            changes.append(f"Replaced text content")
        else:
            # Try with whitespace normalization
            pattern = re.escape(previous_value).replace(r'\ ', r'\s+')
            new_html, count = re.subn(pattern, new_value, html, count=1)
            if count > 0:
                html = new_html
                changes.append(f"Replaced content (normalized match)")

    return html, changes


def _apply_ai_edit(html: str, css: str, javascript: str, selector: str, edit_request: str) -> Optional[dict]:
    """Apply AI-powered natural language edit using LLM."""
    router = _get_model_router()

    prompt = f"""你是一个专业的前端开发者。请根据用户的编辑指令修改网站代码。

## 当前代码

### HTML
```html
{html[:3000]}
```

### CSS
```css
{css[:2000]}
```

## 用户选择的元素
CSS 选择器: {selector}

## 用户的编辑指令
{edit_request}

## 要求
1. 根据用户指令修改相应的代码
2. 只修改必要的部分，保持其他代码不变
3. 确保修改后的代码语法正确

请输出修改后的完整代码，使用 JSON 格式：
```json
{{
  "html": "修改后的完整HTML代码",
  "css": "修改后的完整CSS代码",
  "javascript": "修改后的完整JavaScript代码（如无修改返回原值）",
  "changes": ["描述修改内容"]
}}
```

只输出 JSON，不要其他内容。"""

    try:
        print(f"[DEBUG _apply_ai_edit] Calling LLM for AI edit")

        content = router.invoke_sync(
            task_type=TaskType.CODE_GENERATION,
            prompt=prompt,
            max_tokens=8000,
            temperature=0.3,
        )

        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            # Ensure javascript is preserved if not modified
            if "javascript" not in result or not result["javascript"]:
                result["javascript"] = javascript
            print(f"[DEBUG _apply_ai_edit] LLM edit successful")
            return result

    except Exception as e:
        print(f"[ERROR _apply_ai_edit] LLM edit failed: {e}")

    return None


# ==================== Main Edit Tool ====================


@tool
def edit_website_code(
    html: str,
    css: str,
    javascript: str,
    selector: str,
    edit_request: str,
    edit_type: str = "content",
    previous_value: str = "",
    is_natural_language: bool = False,
) -> dict:
    """
    Edit existing website code based on user request.

    Args:
        html: Current HTML code
        css: Current CSS code
        javascript: Current JavaScript code
        selector: CSS selector of the element to edit
        edit_request: Edit request (structured CSS, new value, or natural language)
        edit_type: Type of edit - content, style, attribute, delete
        previous_value: Previous value for direct replacement (direct edit mode)
        is_natural_language: True if edit_request is natural language (AI edit mode)

    Returns:
        dict containing:
            - files: Dict of filename to updated content
            - changes: List of changes made
    """
    changes = []

    print(f"[DEBUG edit_website_code] edit_type={edit_type}, selector={selector}")
    print(f"[DEBUG edit_website_code] previous_value={previous_value[:50] if previous_value else 'None'}...")
    print(f"[DEBUG edit_website_code] is_natural_language={is_natural_language}")

    # Route to appropriate handler based on edit mode
    if edit_type == "style":
        # Check if edit_request is structured CSS (contains : and ;)
        if ":" in edit_request and (";" in edit_request or edit_request.count(":") == 1):
            # Structured CSS format from style editor
            css, style_changes = _apply_structured_style(css, selector, edit_request)
            changes.extend(style_changes)
        else:
            # Natural language style request
            css, style_changes = _apply_style_edit(css, selector, edit_request)
            changes.extend(style_changes)

    elif edit_type == "delete" or any(word in edit_request.lower() for word in ["删除", "移除", "delete", "remove"]):
        # Delete element
        html, delete_changes = _apply_delete_edit(html, selector)
        changes.extend(delete_changes)

    elif edit_type == "content":
        if previous_value:
            # Direct edit mode - simple text replacement
            html, content_changes = _apply_direct_edit(html, previous_value, edit_request)
            changes.extend(content_changes)
        elif is_natural_language:
            # AI edit mode - call LLM for natural language processing
            result = _apply_ai_edit(html, css, javascript, selector, edit_request)
            if result:
                html = result.get("html", html)
                css = result.get("css", css)
                javascript = result.get("javascript", javascript)
                changes.extend(result.get("changes", []))
            else:
                # Fallback to regex if LLM fails
                html, content_changes = _apply_content_edit(html, selector, edit_request)
                changes.extend(content_changes)
        else:
            # Default content edit with regex
            html, content_changes = _apply_content_edit(html, selector, edit_request)
            changes.extend(content_changes)

    else:
        # Default to content edit
        html, content_changes = _apply_content_edit(html, selector, edit_request)
        changes.extend(content_changes)

    return {
        "files": {
            "index.html": html,
            "styles.css": css,
            "main.js": javascript,
        },
        "changes": changes,
        "success": len(changes) > 0,
    }


def _apply_style_edit(css: str, selector: str, edit_request: str) -> tuple:
    """Apply style changes to CSS."""
    changes = []
    edit_lower = edit_request.lower()

    print(f"[DEBUG _apply_style_edit] selector: {selector}, edit_request: {edit_request}")

    # Extract color from request
    color_match = re.search(r'#[0-9a-fA-F]{3,6}', edit_request)
    color_name_map = {
        "红": "#e53935", "red": "#e53935",
        "蓝": "#1e88e5", "blue": "#1e88e5",
        "绿": "#43a047", "green": "#43a047",
        "黄": "#fdd835", "yellow": "#fdd835",
        "白": "#ffffff", "white": "#ffffff",
        "黑": "#212121", "black": "#212121",
        "紫": "#8e24aa", "purple": "#8e24aa",
        "橙": "#fb8c00", "orange": "#fb8c00",
        "粉": "#ec407a", "pink": "#ec407a",
        "星巴克": "#00704A", "starbucks": "#00704A",
    }

    new_color = None
    if color_match:
        new_color = color_match.group()
    else:
        for name, hex_color in color_name_map.items():
            if name in edit_lower:
                new_color = hex_color
                break

    print(f"[DEBUG _apply_style_edit] new_color: {new_color}")

    # Check if this is a "主色调" (primary color) request - apply globally
    is_primary_color_request = any(word in edit_lower for word in ["主色", "主色调", "primary", "theme"])

    if new_color and is_primary_color_request:
        # Replace all instances of the primary color in CSS
        # Find existing primary-looking colors (typically in header, buttons, h1, etc.)
        old_primary_pattern = r'(header|\.cta-button|\.hero h1|nav|\.primary)[^{]*\{[^}]*(?:background|color):\s*(#[0-9a-fA-F]{3,6})'

        # Find all color values that might be the primary color
        all_colors = re.findall(r'#[0-9a-fA-F]{3,6}', css)
        if all_colors:
            # Get the most common color (likely the primary)
            from collections import Counter
            color_counts = Counter(all_colors)
            # Exclude white/black/gray
            excluded = {'#fff', '#ffffff', '#000', '#000000', '#333', '#1f2937', '#212121', '#64748b'}
            primary_candidates = [(c, count) for c, count in color_counts.most_common() if c.lower() not in excluded]
            if primary_candidates:
                old_primary = primary_candidates[0][0]
                # Replace all instances of the old primary color
                css = css.replace(old_primary, new_color)
                changes.append(f"Changed primary color from {old_primary} to {new_color}")
                print(f"[DEBUG _apply_style_edit] Replaced primary color {old_primary} -> {new_color}")
                return css, changes

    # Normalize selector for CSS matching
    css_selector = selector.replace(" > ", " ").strip()

    # Check if selector already exists in CSS
    if new_color:
        # Determine property based on request
        if any(word in edit_lower for word in ["背景", "background"]):
            prop = "background-color"
        else:
            prop = "color"

        # Check if rule exists
        selector_pattern = re.escape(css_selector)
        rule_match = re.search(rf'{selector_pattern}\s*\{{[^}}]*\}}', css)

        if rule_match:
            # Update existing rule
            old_rule = rule_match.group()
            if f'{prop}:' in old_rule:
                # Replace existing property
                new_rule = re.sub(rf'{prop}:\s*[^;]+;', f'{prop}: {new_color};', old_rule)
            else:
                # Add new property
                new_rule = old_rule.replace('}', f'  {prop}: {new_color};\n}}')
            css = css.replace(old_rule, new_rule)
            changes.append(f"Updated {prop} to {new_color} for {css_selector}")
        else:
            # Add new rule
            new_rule = f"\n{css_selector} {{\n  {prop}: {new_color};\n}}\n"
            css += new_rule
            changes.append(f"Added {prop}: {new_color} for {css_selector}")

    # Handle font size
    size_match = re.search(r'(\d+)(px|rem|em)?', edit_request)
    if any(word in edit_lower for word in ["大", "大小", "size", "font"]) and size_match:
        size = size_match.group(1)
        unit = size_match.group(2) or "px"
        if "大" in edit_lower and not size_match:
            size = "24"
            unit = "px"

        selector_pattern = re.escape(css_selector)
        rule_match = re.search(rf'{selector_pattern}\s*\{{[^}}]*\}}', css)

        if rule_match:
            old_rule = rule_match.group()
            if 'font-size:' in old_rule:
                new_rule = re.sub(r'font-size:\s*[^;]+;', f'font-size: {size}{unit};', old_rule)
            else:
                new_rule = old_rule.replace('}', f'  font-size: {size}{unit};\n}}')
            css = css.replace(old_rule, new_rule)
            changes.append(f"Updated font-size to {size}{unit} for {css_selector}")
        else:
            new_rule = f"\n{css_selector} {{\n  font-size: {size}{unit};\n}}\n"
            css += new_rule
            changes.append(f"Added font-size: {size}{unit} for {css_selector}")

    return css, changes


def _apply_content_edit(html: str, selector: str, edit_request: str) -> tuple:
    """Apply content changes to HTML."""
    changes = []

    # Try to find the new content from the edit request
    # Look for quoted content or content after "改成" / "change to"
    new_content = None

    print(f"[DEBUG _apply_content_edit] selector: {selector}, edit_request: {edit_request}")

    # Pattern: "修改为xxx", "改成xxx", "改为xxx", "换成xxx"
    match = re.search(r'(?:修改|改|换)(?:成|为)["\']?([^"\'，。！？]+)["\']?', edit_request)
    if match:
        new_content = match.group(1).strip()
        print(f"[DEBUG] Matched Chinese pattern, new_content: {new_content}")

    # Pattern: "change to xxx" or "replace with xxx"
    if not new_content:
        match = re.search(r'(?:change\s+to|replace\s+with|set\s+to)["\s]*([^"]+)', edit_request, re.IGNORECASE)
        if match:
            new_content = match.group(1).strip()
            print(f"[DEBUG] Matched English pattern, new_content: {new_content}")

    # Pattern: quoted content (last resort)
    if not new_content:
        match = re.search(r'["\']([^"\']+)["\']', edit_request)
        if match:
            new_content = match.group(1).strip()
            print(f"[DEBUG] Matched quoted pattern, new_content: {new_content}")

    # Pattern: if the edit_request itself looks like content (no keywords)
    if not new_content and not any(kw in edit_request for kw in ['改', '换', 'change', 'replace', 'set']):
        new_content = edit_request.strip()
        print(f"[DEBUG] Using edit_request as content: {new_content}")

    if new_content:
        # Parse selector to find element type - handle complex selectors like "section#home.hero > h1"
        # Get the last part of the selector (the actual element)
        selector_parts = selector.split('>')
        last_selector = selector_parts[-1].strip() if selector_parts else selector

        tag_match = re.match(r'^(\w+)', last_selector)
        tag = tag_match.group(1) if tag_match else 'div'

        print(f"[DEBUG] Parsed tag: {tag} from selector: {last_selector}")

        # Try to find and replace element content
        class_match = re.search(r'\.([^\s.#:\[\]]+)', last_selector)
        id_match = re.search(r'#([^\s.#:\[\]]+)', last_selector)

        replaced = False

        if id_match:
            # Match by ID - handle both direct content and nested content
            element_id = id_match.group(1)
            # Pattern 1: Direct text content
            pattern = rf'(<{tag}[^>]*id=["\']?{element_id}["\']?[^>]*>)([^<]*)(</{tag}>)'
            new_html, count = re.subn(pattern, rf'\1{new_content}\3', html, flags=re.IGNORECASE)
            if count > 0:
                html = new_html
                replaced = True
                changes.append(f"Changed content of #{element_id} to '{new_content}'")
            else:
                # Pattern 2: Content might contain the text we want to replace
                # Find the element and replace its text content
                element_pattern = rf'(<{tag}[^>]*id=["\']?{element_id}["\']?[^>]*>)([\s\S]*?)(</{tag}>)'
                match = re.search(element_pattern, html, re.IGNORECASE)
                if match:
                    old_content = match.group(2)
                    # Replace inner text while preserving structure (simplified)
                    html = html[:match.start()] + match.group(1) + new_content + match.group(3) + html[match.end():]
                    replaced = True
                    changes.append(f"Changed content of #{element_id} to '{new_content}'")

        if not replaced and class_match:
            # Match by class
            class_name = class_match.group(1)
            # Pattern 1: Direct text content
            pattern = rf'(<{tag}[^>]*class=["\'][^"\']*\b{class_name}\b[^"\']*["\'][^>]*>)([^<]*)(</{tag}>)'
            new_html, count = re.subn(pattern, rf'\1{new_content}\3', html, count=1, flags=re.IGNORECASE)
            if count > 0:
                html = new_html
                replaced = True
                changes.append(f"Changed content of .{class_name} to '{new_content}'")
            else:
                # Pattern 2: Handle nested content
                element_pattern = rf'(<{tag}[^>]*class=["\'][^"\']*\b{class_name}\b[^"\']*["\'][^>]*>)([\s\S]*?)(</{tag}>)'
                match = re.search(element_pattern, html, re.IGNORECASE)
                if match:
                    html = html[:match.start()] + match.group(1) + new_content + match.group(3) + html[match.end():]
                    replaced = True
                    changes.append(f"Changed content of .{class_name} to '{new_content}'")

        if not replaced:
            # Match by tag only (first occurrence)
            pattern = rf'(<{tag}[^>]*>)([^<]*)(</{tag}>)'
            new_html, count = re.subn(pattern, rf'\1{new_content}\3', html, count=1, flags=re.IGNORECASE)
            if count > 0:
                html = new_html
                replaced = True
                changes.append(f"Changed content of {tag} to '{new_content}'")

        print(f"[DEBUG] Content edit result: replaced={replaced}, changes={changes}")

    return html, changes


def _apply_delete_edit(html: str, selector: str) -> tuple:
    """Delete an element from HTML."""
    changes = []

    tag_match = re.match(r'^(\w+)', selector)
    tag = tag_match.group(1) if tag_match else 'div'

    class_match = re.search(r'\.([^\s.#:]+)', selector)
    id_match = re.search(r'#([^\s.#:]+)', selector)

    if id_match:
        pattern = rf'<{tag}[^>]*id=["\']?{id_match.group(1)}["\']?[^>]*>.*?</{tag}>'
        html = re.sub(pattern, '', html, flags=re.IGNORECASE | re.DOTALL)
        changes.append(f"Deleted element #{id_match.group(1)}")
    elif class_match:
        pattern = rf'<{tag}[^>]*class=["\'][^"\']*{class_match.group(1)}[^"\']*["\'][^>]*>.*?</{tag}>'
        html = re.sub(pattern, '', html, count=1, flags=re.IGNORECASE | re.DOTALL)
        changes.append(f"Deleted element .{class_match.group(1)}")

    return html, changes


@tool
def generate_website_code(
    description: str,
    design_elements: Optional[dict] = None,
    framework: str = "html",
) -> dict:
    """
    Generate website code based on description using AI.

    This tool uses LLM to generate actual website content based on the
    description, not just a template. The generated code will contain
    real content like brand names, product descriptions, contact info, etc.

    Args:
        description: Natural language description of the website including
                     brand name, products, features, contact info, etc.
        design_elements: Optional design elements (colors, fonts, layout)
        framework: Target framework - html, react, nextjs

    Returns:
        dict containing:
            - files: Dict of filename to content (actual website code)
            - framework: The framework used
            - deployment_type: Recommended deployment type
    """
    # Try LLM-based generation first
    llm_result = _generate_code_with_llm(description, design_elements, framework)
    if llm_result:
        return llm_result

    # Fallback to template-based generation
    print("[WARN] LLM generation failed, falling back to template")
    if framework == "html":
        return _generate_html(description, design_elements)
    elif framework == "react":
        return _generate_react(description, design_elements)
    elif framework == "nextjs":
        return _generate_nextjs(description, design_elements)
    else:
        return _generate_html(description, design_elements)


def _get_colors(design_elements: Optional[dict]) -> dict:
    """Extract color scheme from design elements."""
    defaults = {
        "primary": "#3b82f6",
        "secondary": "#64748b",
        "background": "#ffffff",
        "text": "#1f2937",
    }
    if design_elements and "colors" in design_elements:
        colors = design_elements["colors"]
        # Handle both dict format {"primary": "#xxx"} and list format ["#xxx", "#yyy"]
        if isinstance(colors, dict):
            defaults.update(colors)
        elif isinstance(colors, list) and len(colors) > 0:
            # Map list to color keys
            keys = ["primary", "secondary", "background", "text"]
            for i, color in enumerate(colors[:len(keys)]):
                if isinstance(color, str) and color.startswith("#"):
                    defaults[keys[i]] = color
    return defaults


def _generate_html(description: str, design_elements: Optional[dict]) -> dict:
    """Generate static HTML/CSS/JS website."""
    colors = _get_colors(design_elements)
    title = design_elements.get("title", "My Website") if design_elements else "My Website"

    html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <header>
        <nav>
            <div class="logo">{title}</div>
            <ul class="nav-links">
                <li><a href="#home">Home</a></li>
                <li><a href="#about">About</a></li>
                <li><a href="#contact">Contact</a></li>
            </ul>
        </nav>
    </header>
    <main>
        <section id="home" class="hero">
            <h1>Welcome to {title}</h1>
            <p>{description}</p>
            <button class="cta-button">Get Started</button>
        </section>
        <section id="about" class="about">
            <h2>About Us</h2>
            <p>Learn more about what we do.</p>
        </section>
        <section id="contact" class="contact">
            <h2>Contact</h2>
            <p>Get in touch with us.</p>
        </section>
    </main>
    <footer>
        <p>&copy; 2024 {title}. All rights reserved.</p>
    </footer>
    <script src="main.js"></script>
</body>
</html>'''

    css_content = f'''* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background-color: {colors["background"]};
    color: {colors["text"]};
    line-height: 1.6;
}}

header {{
    background: {colors["primary"]};
    padding: 1rem 2rem;
    position: fixed;
    width: 100%;
    top: 0;
    z-index: 1000;
}}

nav {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    max-width: 1200px;
    margin: 0 auto;
}}

.logo {{
    font-size: 1.5rem;
    font-weight: bold;
    color: white;
}}

.nav-links {{
    display: flex;
    list-style: none;
    gap: 2rem;
}}

.nav-links a {{
    color: white;
    text-decoration: none;
    transition: opacity 0.3s;
}}

.nav-links a:hover {{
    opacity: 0.8;
}}

main {{
    padding-top: 80px;
}}

section {{
    padding: 4rem 2rem;
    max-width: 1200px;
    margin: 0 auto;
}}

.hero {{
    min-height: calc(100vh - 80px);
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
}}

.hero h1 {{
    font-size: 3rem;
    margin-bottom: 1rem;
    color: {colors["primary"]};
}}

.hero p {{
    font-size: 1.25rem;
    margin-bottom: 2rem;
    color: {colors["secondary"]};
    max-width: 600px;
}}

.cta-button {{
    background: {colors["primary"]};
    color: white;
    border: none;
    padding: 1rem 2rem;
    font-size: 1rem;
    border-radius: 8px;
    cursor: pointer;
    transition: transform 0.3s, box-shadow 0.3s;
}}

.cta-button:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.4);
}}

.about, .contact {{
    text-align: center;
}}

.about h2, .contact h2 {{
    font-size: 2rem;
    margin-bottom: 1rem;
    color: {colors["primary"]};
}}

footer {{
    background: {colors["text"]};
    color: white;
    text-align: center;
    padding: 2rem;
}}'''

    js_content = '''document.addEventListener('DOMContentLoaded', function() {
    // Smooth scrolling
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    // CTA button
    const ctaButton = document.querySelector('.cta-button');
    if (ctaButton) {
        ctaButton.addEventListener('click', function() {
            alert('Thank you for your interest!');
        });
    }
});'''

    return {
        "files": {
            "index.html": html_content,
            "styles.css": css_content,
            "main.js": js_content,
        },
        "framework": "html",
        "deployment_type": "static",
    }


def _generate_react(description: str, design_elements: Optional[dict]) -> dict:
    """Generate React SPA."""
    colors = _get_colors(design_elements)
    title = design_elements.get("title", "My App") if design_elements else "My App"

    app_jsx = f'''import React from 'react';
import './App.css';

function App() {{
  return (
    <div className="App">
      <header>
        <nav>
          <div className="logo">{title}</div>
          <ul className="nav-links">
            <li><a href="#home">Home</a></li>
            <li><a href="#about">About</a></li>
          </ul>
        </nav>
      </header>
      <main>
        <section id="home" className="hero">
          <h1>Welcome to {title}</h1>
          <p>{description}</p>
          <button className="cta-button">Get Started</button>
        </section>
      </main>
    </div>
  );
}}

export default App;'''

    app_css = f'''.App {{
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}}

header {{
  background: {colors["primary"]};
  padding: 1rem 2rem;
  position: fixed;
  width: 100%;
  top: 0;
}}

nav {{
  display: flex;
  justify-content: space-between;
  align-items: center;
}}

.logo {{
  font-size: 1.5rem;
  font-weight: bold;
  color: white;
}}

.nav-links {{
  display: flex;
  list-style: none;
  gap: 2rem;
}}

.nav-links a {{
  color: white;
  text-decoration: none;
}}

.hero {{
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding-top: 80px;
}}

.hero h1 {{
  color: {colors["primary"]};
}}

.cta-button {{
  background: {colors["primary"]};
  color: white;
  border: none;
  padding: 1rem 2rem;
  border-radius: 8px;
  cursor: pointer;
}}'''

    index_js = '''import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);'''

    index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body>
    <div id="root"></div>
</body>
</html>'''

    package_json = '''{
  "name": "generated-app",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build"
  }
}'''

    return {
        "files": {
            "src/App.jsx": app_jsx,
            "src/App.css": app_css,
            "src/index.js": index_js,
            "public/index.html": index_html,
            "package.json": package_json,
        },
        "framework": "react",
        "deployment_type": "static",
    }


def _generate_nextjs(description: str, design_elements: Optional[dict]) -> dict:
    """Generate Next.js app with API routes."""
    colors = _get_colors(design_elements)
    title = design_elements.get("title", "My App") if design_elements else "My App"

    page_tsx = f'''export default function Home() {{
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-4xl font-bold">{title}</h1>
      <p className="mt-4">{description}</p>
    </main>
  );
}}'''

    api_route = '''import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ message: 'Hello from API' });
}'''

    layout_tsx = f'''export const metadata = {{
  title: '{title}',
}};

export default function RootLayout({{ children }}: {{ children: React.ReactNode }}) {{
  return (
    <html lang="en">
      <body>{{children}}</body>
    </html>
  );
}}'''

    package_json = '''{
  "name": "nextjs-app",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.0.0",
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }
}'''

    return {
        "files": {
            "app/page.tsx": page_tsx,
            "app/layout.tsx": layout_tsx,
            "app/api/hello/route.ts": api_route,
            "package.json": package_json,
        },
        "framework": "nextjs",
        "deployment_type": "dynamic",
    }
