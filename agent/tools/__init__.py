"""
Agent Tools Module

Contains deployment tools and AgentCore integrations for the Website Generator Agent.

Tools are organized into four categories:
1. Browser Tools - Web browsing and design extraction
2. Code Interpreter Tools - Code validation and execution
3. Memory Tools - Session and user memory management
4. Deployment Tools - Website deployment
"""

from tools.code_interpreter import (
    code_interpreter_execute,
    validate_code_syntax,
    process_data_file,
    CodeInterpreterSession,
    # New tools
    execute_code,
    validate_code,
    run_code_check,
    get_native_code_interpreter_tool,
)
from tools.browser_tool import (
    browse_url,
    extract_design_elements,
    capture_page_screenshot,
    get_native_browser_tool,
)
from tools.memory_tools import (
    # Session memory
    save_session,
    get_session,
    # User preferences
    save_user_preference,
    get_user_preferences,
    # Semantic search
    retrieve_relevant,
    # Code versioning
    save_code_version,
    rollback_code,
    list_code_versions,
    # Utilities
    get_memory_service,
    initialize_memory_service,
)
from tools.code_generator import generate_website_code, edit_website_code
from tools.deploy_tools import (
    deploy_to_s3,
    deploy_to_lambda,
    get_deployment_status,
    list_deployments,
)

__all__ = [
    # Code Interpreter tools
    "code_interpreter_execute",
    "validate_code_syntax",
    "process_data_file",
    "CodeInterpreterSession",
    "execute_code",
    "validate_code",
    "run_code_check",
    "get_native_code_interpreter_tool",
    # Browser tools
    "browse_url",
    "extract_design_elements",
    "capture_page_screenshot",
    "get_native_browser_tool",
    # Memory tools
    "save_session",
    "get_session",
    "save_user_preference",
    "get_user_preferences",
    "retrieve_relevant",
    "save_code_version",
    "rollback_code",
    "list_code_versions",
    "get_memory_service",
    "initialize_memory_service",
    # Code Generator
    "generate_website_code",
    "edit_website_code",
    # Deployment Tools (S3 + CloudFront, Lambda + Web Adapter)
    "deploy_to_s3",
    "deploy_to_lambda",
    "get_deployment_status",
    "list_deployments",
]
