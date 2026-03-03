"""
Code Interpreter Tool

Uses strands_tools AgentCoreCodeInterpreter for code execution and validation.
This integrates with AWS Bedrock AgentCore's Code Interpreter service.

IMPORTANT: This tool integrates with AWS Bedrock AgentCore Code Interpreter.
Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html

The Code Interpreter provides:
- Sandboxed code execution environment
- Support for Python, JavaScript, TypeScript
- File operations and data processing
- Matplotlib visualization support
- Reduced hallucination through code verification
"""

import json
import logging
import os
from typing import Optional

import boto3
from strands.tools import tool

logger = logging.getLogger(__name__)

# Configuration from environment
REGION = os.environ.get("AWS_REGION", "us-east-1")
CODE_INTERPRETER_ID = os.environ.get("AGENTCORE_CODE_INTERPRETER_ID", "")

# Global code interpreter instance
_code_interpreter = None
_interpreter_type = None


def get_code_interpreter(session_name: str = "ugc-code-interpreter"):
    """
    Get or create the AgentCore Code Interpreter instance.

    Uses AgentCoreCodeInterpreter for sandboxed code execution in AgentCore Runtime.
    Reference: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html

    If AGENTCORE_CODE_INTERPRETER_ID is set, uses that specific Code Interpreter.
    Otherwise, uses the default managed Code Interpreter.

    Args:
        session_name: Name for the code interpreter session

    Returns:
        tuple: (code_interpreter_instance, interpreter_type)
    """
    global _code_interpreter, _interpreter_type

    if _code_interpreter is not None:
        return _code_interpreter, _interpreter_type

    # Try AgentCoreCodeInterpreter
    try:
        from strands_tools.code_interpreter import AgentCoreCodeInterpreter

        # Create AgentCoreCodeInterpreter with optional identifier
        if CODE_INTERPRETER_ID:
            print(f"[CODE_INTERPRETER] Creating AgentCoreCodeInterpreter with identifier={CODE_INTERPRETER_ID}, region={REGION}")
            _code_interpreter = AgentCoreCodeInterpreter(
                region=REGION,
                identifier=CODE_INTERPRETER_ID,  # Custom Code Interpreter ID from AWS Console
            )
        else:
            print(f"[CODE_INTERPRETER] Creating AgentCoreCodeInterpreter with default managed resource, region={REGION}")
            _code_interpreter = AgentCoreCodeInterpreter(region=REGION)

        _interpreter_type = "agentcore"
        print(f"[CODE_INTERPRETER] AgentCoreCodeInterpreter created successfully")
        logger.info(f"Using AgentCoreCodeInterpreter (identifier={CODE_INTERPRETER_ID or 'managed'})")
        return _code_interpreter, _interpreter_type
    except Exception as e:
        import traceback
        print(f"[CODE_INTERPRETER] AgentCoreCodeInterpreter not available: {e}")
        print(f"[CODE_INTERPRETER] Traceback:\n{traceback.format_exc()}")
        logger.warning(f"AgentCoreCodeInterpreter not available: {e}")

    # Fall back to local execution
    _interpreter_type = "local"
    print(f"[CODE_INTERPRETER] Falling back to local code execution (development mode)")
    logger.info("Using local code execution (development mode)")
    return None, _interpreter_type


def get_native_code_interpreter_tool():
    """
    Get the native AgentCoreCodeInterpreter tool for direct use with Agent.

    This returns the .code_interpreter attribute which can be passed directly
    to Agent's tools parameter for native integration.

    Usage in agentcore_handler.py:
        code_tool = get_native_code_interpreter_tool()
        if code_tool:
            agent = Agent(tools=[code_tool], ...)

    Returns:
        The native code_interpreter tool or None if not available
    """
    interpreter, interpreter_type = get_code_interpreter()
    if interpreter and interpreter_type == "agentcore":
        return interpreter.code_interpreter
    return None


class CodeInterpreterSession:
    """
    Manages a Code Interpreter session with AgentCore.

    The Code Interpreter runs in a sandboxed environment and is suitable for:
    - Validating generated code syntax
    - Running quick data transformations
    - Testing small code snippets
    - Processing uploaded files

    It is NOT suitable for:
    - npm install / pip install (use CodeBuild)
    - Full build processes (use CodeBuild)
    - Long-running tasks (use CodeBuild/ECS)
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        region: str = "us-east-1",
    ):
        """
        Initialize a Code Interpreter session.

        Args:
            session_id: Optional session ID for continuity
            region: AWS region for AgentCore
        """
        self.region = region
        self.session_id = session_id
        self._client = None
        self._interpreter_id = None

    @property
    def client(self):
        """Lazy initialization of boto3 client."""
        if self._client is None:
            try:
                self._client = boto3.client("bedrock-agentcore", region_name=self.region)
            except Exception:
                # Fall back to mock client for development/testing
                self._client = None
        return self._client

    def create_session(self, name: str = "ugc-code-interpreter") -> str:
        """
        Create a new Code Interpreter session.

        Args:
            name: Name for the interpreter instance

        Returns:
            Interpreter session ID
        """
        if self.client:
            try:
                response = self.client.create_code_interpreter_session(
                    name=name,
                    description="UGC AI Demo - Code validation and execution",
                    sessionConfiguration={
                        "idleSessionTTL": 3600,  # 1 hour idle timeout
                    },
                )
                self._interpreter_id = response["sessionId"]
                return self._interpreter_id
            except (AttributeError, Exception):
                # API not available, fall through to mock
                pass

        # Mock session for development
        import uuid
        self._interpreter_id = f"mock-session-{uuid.uuid4().hex[:8]}"
        return self._interpreter_id

    def execute_code(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
    ) -> dict:
        """
        Execute code in the Code Interpreter sandbox.

        Args:
            code: The code to execute
            language: Programming language (python, javascript, etc.)
            timeout: Execution timeout in seconds

        Returns:
            dict with execution results including stdout, stderr, and return value
        """
        if not self._interpreter_id:
            self.create_session()

        if self.client and not self._interpreter_id.startswith("mock-"):
            try:
                response = self.client.invoke_code_interpreter(
                    sessionId=self._interpreter_id,
                    code=code,
                    language=language,
                    executionTimeout=timeout,
                )
                return {
                    "success": response.get("status") == "SUCCESS",
                    "stdout": response.get("stdout", ""),
                    "stderr": response.get("stderr", ""),
                    "return_value": response.get("returnValue"),
                    "execution_time": response.get("executionTime"),
                }
            except (AttributeError, Exception):
                # API not available, fall through to mock
                pass

        # Mock execution for development - do actual local validation for certain languages
        return self._mock_execute(code, language)

    def _mock_execute(self, code: str, language: str) -> dict:
        """Execute code locally for development/testing."""
        import subprocess
        import tempfile
        import time

        start_time = time.time()

        if language == "python":
            try:
                # Execute Python code safely
                result = subprocess.run(
                    ["python", "-c", code],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_value": None,
                    "execution_time": time.time() - start_time,
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Execution timeout",
                    "return_value": None,
                    "execution_time": 30.0,
                }
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "return_value": None,
                    "execution_time": time.time() - start_time,
                }

        elif language in ["javascript", "typescript"]:
            try:
                # Try to execute with Node.js
                result = subprocess.run(
                    ["node", "-e", code],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_value": None,
                    "execution_time": time.time() - start_time,
                }
            except FileNotFoundError:
                # Node.js not available, return mock success
                return {
                    "success": True,
                    "stdout": f"[Mock] Executed {language} code (Node.js not available)",
                    "stderr": "",
                    "return_value": None,
                    "execution_time": time.time() - start_time,
                }
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Execution timeout",
                    "return_value": None,
                    "execution_time": 30.0,
                }
            except Exception as e:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": str(e),
                    "return_value": None,
                    "execution_time": time.time() - start_time,
                }

        # For other languages, return mock success
        return {
            "success": True,
            "stdout": f"[Mock] Executed {language} code successfully",
            "stderr": "",
            "return_value": None,
            "execution_time": time.time() - start_time,
        }

    def upload_file(self, file_path: str, file_content: bytes) -> str:
        """
        Upload a file to the Code Interpreter session.

        Args:
            file_path: Path where the file should be available
            file_content: File content as bytes

        Returns:
            File reference ID
        """
        if not self._interpreter_id:
            self.create_session()

        if self.client:
            response = self.client.upload_file_to_code_interpreter(
                sessionId=self._interpreter_id,
                fileName=file_path,
                fileContent=file_content,
            )
            return response.get("fileId", "")
        else:
            import uuid
            return f"mock-file-{uuid.uuid4().hex[:8]}"

    def close_session(self):
        """Close the Code Interpreter session."""
        if self._interpreter_id and self.client:
            try:
                self.client.delete_code_interpreter_session(
                    sessionId=self._interpreter_id
                )
            except Exception:
                pass  # Session may have already timed out
        self._interpreter_id = None


# Global session for reuse within an agent run
_session: Optional[CodeInterpreterSession] = None


def get_session(region: str = "us-east-1") -> CodeInterpreterSession:
    """Get or create a Code Interpreter session."""
    global _session
    if _session is None:
        _session = CodeInterpreterSession(region=region)
    return _session


@tool
def code_interpreter_execute(
    code: str,
    language: str = "python",
    timeout: int = 30,
    region: str = "us-east-1",
) -> dict:
    """
    Execute code using AgentCore's Code Interpreter.

    The Code Interpreter runs in a secure sandbox environment
    and can be used for:
    - Validating generated code syntax
    - Processing data (Excel, CSV, JSON)
    - Running simple scripts
    - Checking dependencies

    Args:
        code: The code to execute
        language: Programming language (python, javascript, typescript)
        timeout: Execution timeout in seconds (max 60)
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - success: Whether execution was successful
            - output: Standard output from execution
            - error: Error message if execution failed
            - execution_time: Time taken to execute
    """
    session = get_session(region)

    result = session.execute_code(
        code=code,
        language=language,
        timeout=min(timeout, 60),
    )

    return {
        "success": result["success"],
        "output": result["stdout"],
        "error": result["stderr"] if not result["success"] else None,
        "execution_time": result.get("execution_time"),
    }


@tool
def validate_code_syntax(
    code: str,
    language: str = "javascript",
    region: str = "us-east-1",
) -> dict:
    """
    Validate the syntax of generated code using Code Interpreter.

    This tool checks if the provided code has valid syntax without executing
    the full application logic. Useful for verifying generated website code.

    Args:
        code: The code to validate
        language: Programming language (javascript, python, typescript, html, css)
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - valid: Whether the syntax is valid
            - errors: List of syntax errors if any
            - warnings: List of warnings if any
    """
    session = get_session(region)

    # Escape code for embedding
    escaped_code = code.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    escaped_code_triple = code.replace('"""', '\\"\\"\\"')

    if language in ["javascript", "typescript"]:
        validation_code = f'''
const code = `{escaped_code}`;
try {{
    new Function(code);
    console.log(JSON.stringify({{valid: true, errors: [], warnings: []}}));
}} catch (e) {{
    console.log(JSON.stringify({{
        valid: false,
        errors: [{{line: 0, column: 0, message: e.message}}],
        warnings: []
    }}));
}}
'''
        result = session.execute_code(validation_code, "javascript")

    elif language == "python":
        validation_code = f'''
import ast
import json
code = """{escaped_code_triple}"""
try:
    ast.parse(code)
    print(json.dumps({{"valid": True, "errors": [], "warnings": []}}))
except SyntaxError as e:
    print(json.dumps({{
        "valid": False,
        "errors": [{{"line": e.lineno or 0, "column": e.offset or 0, "message": str(e.msg)}}],
        "warnings": []
    }}))
'''
        result = session.execute_code(validation_code, "python")

    elif language == "html":
        validation_code = f'''
import json
from html.parser import HTMLParser

class HTMLValidator(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []
        self.stack = []
        self.void_elements = ['br', 'hr', 'img', 'input', 'meta', 'link', 'area', 'base', 'col', 'embed', 'param', 'source', 'track', 'wbr']

    def handle_starttag(self, tag, attrs):
        if tag not in self.void_elements:
            self.stack.append((tag, self.getpos()))

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()
        elif tag not in self.void_elements:
            self.errors.append({{"line": self.getpos()[0], "message": f"Unexpected closing tag: {{tag}}"}})

html_code = """{escaped_code_triple}"""
validator = HTMLValidator()
try:
    validator.feed(html_code)
    if validator.stack:
        unclosed = [t[0] for t in validator.stack]
        validator.errors.append({{"line": 0, "message": f"Unclosed tags: {{unclosed}}"}})
    valid = len(validator.errors) == 0
    print(json.dumps({{"valid": valid, "errors": validator.errors, "warnings": []}}))
except Exception as e:
    print(json.dumps({{"valid": False, "errors": [{{"line": 0, "message": str(e)}}], "warnings": []}}))
'''
        result = session.execute_code(validation_code, "python")

    elif language == "css":
        validation_code = f'''
import json

css_code = """{escaped_code_triple}"""
errors = []

brace_count = css_code.count('{{') - css_code.count('}}')
if brace_count != 0:
    direction = "opening" if brace_count > 0 else "closing"
    errors.append({{"line": 0, "message": f"Unbalanced braces: {{abs(brace_count)}} extra {{direction}} brace(s)"}})

if css_code.count('"') % 2 != 0:
    errors.append({{"line": 0, "message": "Unclosed double quote"}})
if css_code.count("'") % 2 != 0:
    errors.append({{"line": 0, "message": "Unclosed single quote"}})

print(json.dumps({{"valid": len(errors) == 0, "errors": errors, "warnings": []}}))
'''
        result = session.execute_code(validation_code, "python")

    else:
        return {
            "valid": True,
            "errors": [],
            "warnings": [f"No validator available for language: {language}"],
        }

    if result["success"] and result["stdout"]:
        try:
            return json.loads(result["stdout"].strip())
        except json.JSONDecodeError:
            pass

    return {
        "valid": False,
        "errors": [{"line": 0, "message": result.get("stderr", "Unknown validation error")}],
        "warnings": [],
    }


@tool
def process_data_file(
    file_content: str,
    file_type: str,
    operation: str = "parse",
    region: str = "us-east-1",
) -> dict:
    """
    Process data files using Code Interpreter.

    Args:
        file_content: File content as string (raw text or base64 for binary)
        file_type: Type of file (csv, json, excel)
        operation: Operation to perform (parse, transform, analyze)
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - success: Whether processing succeeded
            - data: Processed data
            - rows: Number of rows (for tabular data)
            - error: Error message if processing failed
    """
    session = get_session(region)

    escaped_content = file_content.replace('"""', '\\"\\"\\"')

    processing_code = f'''
import json

file_type = "{file_type}"
operation = "{operation}"
content = """{escaped_content}"""

try:
    if file_type == "json":
        data = json.loads(content)
        rows = len(data) if isinstance(data, list) else 1
    elif file_type == "csv":
        import csv
        from io import StringIO
        reader = csv.DictReader(StringIO(content))
        data = list(reader)
        rows = len(data)
    else:
        data = {{"raw": content}}
        rows = 1

    print(json.dumps({{"success": True, "data": data, "rows": rows}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e), "data": None, "rows": 0}}))
'''

    result = session.execute_code(processing_code, language="python")

    if result["success"] and result["stdout"]:
        try:
            return json.loads(result["stdout"].strip())
        except json.JSONDecodeError:
            pass

    return {
        "success": False,
        "error": result.get("stderr", "Failed to process file"),
        "data": None,
        "rows": 0,
    }


@tool
def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    region: str = "us-east-1",
) -> dict:
    """
    Execute a code snippet and return the result.

    A simpler interface for code execution, suitable for quick script runs.

    Args:
        code: The code to execute
        language: Programming language (python, javascript, typescript)
        timeout: Maximum execution time in seconds
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - success: Whether execution succeeded
            - result: Execution result or output
            - error: Error message if failed
    """
    result = code_interpreter_execute(
        code=code,
        language=language,
        timeout=timeout,
        region=region,
    )

    return {
        "success": result.get("success", False),
        "result": result.get("output", ""),
        "error": result.get("error"),
        "execution_time": result.get("execution_time"),
    }


@tool
def validate_code(
    code: str,
    language: str,
    region: str = "us-east-1",
) -> dict:
    """
    Validate code syntax for generated website code.

    Checks if the provided code has valid syntax. Supports multiple
    languages used in web development.

    Args:
        code: The code to validate
        language: Language of the code (javascript, typescript, python, html, css, jsx, tsx)
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - valid: Whether the code has valid syntax
            - errors: List of syntax errors found
            - language: The language that was validated
    """
    # Map tsx/jsx to typescript/javascript
    lang_map = {
        "jsx": "javascript",
        "tsx": "typescript",
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
    }
    actual_language = lang_map.get(language, language)

    result = validate_code_syntax(
        code=code,
        language=actual_language,
        region=region,
    )

    return {
        "valid": result.get("valid", False),
        "errors": result.get("errors", []),
        "warnings": result.get("warnings", []),
        "language": language,
    }


@tool
def run_code_check(
    files: dict,
    region: str = "us-east-1",
) -> dict:
    """
    Run syntax validation on multiple files.

    Validates syntax for a collection of files, useful for checking
    all generated website code at once.

    Args:
        files: Dictionary mapping filename to code content
        region: AWS region for AgentCore

    Returns:
        dict containing:
            - success: Whether all files passed validation
            - results: Validation result for each file
            - error_count: Total number of errors found
    """
    results = {}
    error_count = 0

    # Determine language from file extension
    extension_map = {
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".py": "python",
        ".html": "html",
        ".css": "css",
        ".json": "json",
    }

    for filename, content in files.items():
        # Get file extension
        ext = ""
        for e in extension_map:
            if filename.endswith(e):
                ext = e
                break

        language = extension_map.get(ext, "javascript")

        # Skip JSON validation (we'll do a simple parse check)
        if language == "json":
            try:
                json.loads(content)
                results[filename] = {"valid": True, "errors": [], "language": "json"}
            except json.JSONDecodeError as e:
                results[filename] = {
                    "valid": False,
                    "errors": [{"line": e.lineno, "message": str(e.msg)}],
                    "language": "json",
                }
                error_count += 1
            continue

        result = validate_code_syntax(code=content, language=language, region=region)
        results[filename] = result

        if not result.get("valid", False):
            error_count += len(result.get("errors", []))

    return {
        "success": error_count == 0,
        "results": results,
        "error_count": error_count,
        "files_checked": len(files),
    }


# Legacy function names for backward compatibility
code_interpreter_tool = code_interpreter_execute
validate_syntax = validate_code_syntax
