"""
Built-in Deployment Tools for Agent

Directly integrates S3+CloudFront and Lambda+WebAdapter deployment,
bypassing MCP Gateway to avoid network timeout issues.

Key benefits:
- No MCP Gateway dependency
- Direct AWS SDK calls
- More reliable deployment
- Demonstrates AgentCore, Lambda Web Adapter, S3+CloudFront

Database Support:
- DynamoDB: Serverless NoSQL (no VPC required)
- RDS/Aurora: Relational databases (requires VPC)
- ElastiCache: Redis cache (requires VPC)

Note: Uses @tool decorator for Strands Agent auto-loading from directory.
Reference: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools
"""

import asyncio
import logging
import os
import re
from typing import Any, Dict, List, Optional

from strands.tools import tool

from tools.lambda_adapter import DatabaseConfig, DEFAULT_DATABASE_CONFIG, DEFAULT_VPC_CONFIG

logger = logging.getLogger(__name__)

# Lazy-loaded deployers
_s3_deployer = None
_lambda_deployer = None

REGION = os.environ.get("AWS_REGION", "us-east-1")


def _get_s3_deployer():
    """Lazy load S3CloudFrontDeployer."""
    global _s3_deployer
    if _s3_deployer is None:
        from tools.s3_cloudfront import S3CloudFrontDeployer
        _s3_deployer = S3CloudFrontDeployer(region=REGION)
    return _s3_deployer


def _get_lambda_deployer():
    """Lazy load LambdaWebAdapterDeployer."""
    global _lambda_deployer
    if _lambda_deployer is None:
        from tools.lambda_adapter import LambdaWebAdapterDeployer
        _lambda_deployer = LambdaWebAdapterDeployer(region=REGION)
    return _lambda_deployer


@tool
def deploy_to_s3(
    project_name: str,
    files: List[Dict[str, Any]],
    index_document: str = "index.html",
    error_document: str = "error.html",
    enable_spa_mode: bool = True,
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
        project_name: Unique project identifier (alphanumeric and hyphens only)
        files: List of files to deploy. Each file should have:
            - path: File path (e.g., "index.html", "css/styles.css")
            - content: File content as string
            - encoding: "utf-8" (default) or "base64" for binary files
        index_document: Main entry file (default: "index.html")
        error_document: Error page file (default: "error.html")
        enable_spa_mode: Enable SPA routing (404->index.html)

    Returns:
        Deployment result with CloudFront URL and S3 website endpoint

    Example:
        deploy_to_s3(
            project_name="my-website",
            files=[
                {"path": "index.html", "content": "<html>...</html>"},
                {"path": "styles.css", "content": "body {...}"},
                {"path": "main.js", "content": "console.log('hello')"}
            ]
        )
    """
    # Validate project name
    if not re.match(r'^[a-zA-Z0-9-]+$', project_name):
        return {
            "status": "failed",
            "error": "Invalid project_name. Use only alphanumeric characters and hyphens."
        }

    if not files:
        return {
            "status": "failed",
            "error": "No files provided for deployment."
        }

    try:
        deployer = _get_s3_deployer()

        # Run async deploy in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                deployer.deploy(
                    project_name=project_name,
                    files=files,
                    index_document=index_document,
                    error_document=error_document,
                    ctx=None,  # No MCP context for progress
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"S3 deployment failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


@tool
def deploy_to_lambda(
    project_name: str,
    files: List[Dict[str, Any]],
    runtime: Optional[str] = None,
    port: Optional[int] = None,
    memory_size: int = 1024,
    timeout: int = 30,
    environment_variables: Optional[Dict[str, str]] = None,
    entry_point: Optional[str] = None,
    database_type: Optional[str] = None,
    database_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Deploy dynamic web application to Lambda with Web Adapter.

    This tool deploys server-side applications to AWS Lambda using
    the Lambda Web Adapter extension. Perfect for:
    - Node.js/Express servers
    - Python/Flask/FastAPI backends
    - Next.js SSR applications
    - Any app with API routes or server-side processing

    Supports database connections:
    - DynamoDB: Serverless NoSQL (recommended, no VPC required)
    - RDS/Aurora: Relational databases (requires VPC)
    - ElastiCache: Redis cache (requires VPC)

    Args:
        project_name: Unique project identifier (alphanumeric and hyphens only)
        files: List of files to deploy. Each file should have:
            - path: File path (e.g., "server.js", "app.py")
            - content: File content as string
            - encoding: "utf-8" (default) or "base64" for binary files
        runtime: Lambda runtime. Auto-detected if not specified.
            Options: "nodejs18.x", "nodejs20.x", "python3.11", "python3.12"
        port: Application port. Auto-detected if not specified.
            Default: 3000 for Node.js, 8000 for Python
        memory_size: Lambda memory in MB (default: 1024)
        timeout: Lambda timeout in seconds (default: 30)
        environment_variables: Additional environment variables
        entry_point: Custom entry point command (auto-detected if not specified)
        database_type: Database type: "dynamodb", "rds", "aurora", "elasticache"
        database_config: Database-specific configuration:
            For DynamoDB:
                - dynamodb_table_name: Table name (auto-generated if not specified)
                - dynamodb_create_table: Whether to create the table (default: True)
                - dynamodb_partition_key: Partition key name (default: "id")
                - dynamodb_sort_key: Optional sort key name
            For RDS/Aurora:
                - rds_endpoint: Database endpoint hostname
                - rds_port: Database port (default: 5432)
                - rds_database: Database name
                - rds_secret_arn: Secrets Manager ARN for credentials
            For ElastiCache:
                - redis_endpoint: Redis endpoint hostname
                - redis_port: Redis port (default: 6379)

    Returns:
        Deployment result with Lambda Function URL and database info

    Example with DynamoDB:
        deploy_to_lambda(
            project_name="todo-api",
            files=[...],
            database_type="dynamodb",
            database_config={
                "dynamodb_table_name": "todos",
                "dynamodb_create_table": True,
                "dynamodb_partition_key": "userId",
                "dynamodb_sort_key": "taskId"
            }
        )

    Example with RDS:
        deploy_to_lambda(
            project_name="user-api",
            files=[...],
            database_type="aurora",
            database_config={
                "rds_endpoint": "my-cluster.cluster-xxx.us-east-1.rds.amazonaws.com",
                "rds_database": "users",
                "rds_secret_arn": "arn:aws:secretsmanager:us-east-1:123456789:secret:db-creds"
            }
        )
    """
    # Validate project name
    if not re.match(r'^[a-zA-Z0-9-]+$', project_name):
        return {
            "status": "failed",
            "error": "Invalid project_name. Use only alphanumeric characters and hyphens."
        }

    if not files:
        return {
            "status": "failed",
            "error": "No files provided for deployment."
        }

    # Auto-detect runtime and port if not specified
    file_paths = [f.get("path", "") for f in files]
    file_contents = " ".join(f.get("content", "")[:500] for f in files).lower()

    if runtime is None:
        # Detect from files
        if any(p.endswith(".py") for p in file_paths) or "flask" in file_contents or "fastapi" in file_contents:
            runtime = "python3.12"
        else:
            runtime = "nodejs20.x"
        logger.info(f"Auto-detected runtime: {runtime}")

    if port is None:
        # Detect from runtime/content
        if runtime.startswith("python"):
            port = 8000
        else:
            port = 3000
        logger.info(f"Auto-detected port: {port}")

    # Auto-detect entry point
    if entry_point is None:
        if runtime.startswith("python"):
            if "app.py" in file_paths:
                entry_point = "python app.py"
            elif "main.py" in file_paths:
                entry_point = "python main.py"
            else:
                entry_point = "python app.py"
        else:
            if "server.js" in file_paths:
                entry_point = "node server.js"
            elif "index.js" in file_paths:
                entry_point = "node index.js"
            else:
                entry_point = "node server.js"
        logger.info(f"Auto-detected entry_point: {entry_point}")

    # Build database config if specified
    # Auto-fill with pre-configured defaults when connection details not provided
    db_config = None
    if database_type:
        db_config_dict = database_config or {}

        # Auto-fill Aurora/RDS defaults if not specified
        if database_type in ("aurora", "rds") and not db_config_dict.get("rds_endpoint"):
            aurora_defaults = DEFAULT_DATABASE_CONFIG.get("aurora", {})
            db_config_dict.setdefault("rds_endpoint", aurora_defaults.get("endpoint"))
            db_config_dict.setdefault("rds_port", aurora_defaults.get("port", 5432))
            db_config_dict.setdefault("rds_database", aurora_defaults.get("database"))
            db_config_dict.setdefault("rds_secret_arn", aurora_defaults.get("secret_arn"))
            logger.info("Using pre-configured Aurora PostgreSQL defaults")

        # Auto-fill ElastiCache/Redis defaults if not specified
        if database_type == "elasticache" and not db_config_dict.get("redis_endpoint"):
            redis_defaults = DEFAULT_DATABASE_CONFIG.get("elasticache", {})
            db_config_dict.setdefault("redis_endpoint", redis_defaults.get("endpoint"))
            db_config_dict.setdefault("redis_port", redis_defaults.get("port", 6379))
            logger.info("Using pre-configured ElastiCache Redis defaults")

        db_config = DatabaseConfig(
            db_type=database_type,
            dynamodb_table_name=db_config_dict.get("dynamodb_table_name"),
            dynamodb_create_table=db_config_dict.get("dynamodb_create_table", True),
            dynamodb_partition_key=db_config_dict.get("dynamodb_partition_key", "id"),
            dynamodb_sort_key=db_config_dict.get("dynamodb_sort_key"),
            rds_endpoint=db_config_dict.get("rds_endpoint"),
            rds_port=db_config_dict.get("rds_port", 5432),
            rds_database=db_config_dict.get("rds_database"),
            rds_secret_arn=db_config_dict.get("rds_secret_arn"),
            redis_endpoint=db_config_dict.get("redis_endpoint"),
            redis_port=db_config_dict.get("redis_port", 6379),
            # Auto-fill VPC config for VPC databases
            vpc_id=db_config_dict.get("vpc_id") or DEFAULT_VPC_CONFIG.get("vpc_id"),
            subnet_ids=db_config_dict.get("subnet_ids") or DEFAULT_VPC_CONFIG.get("private_subnet_ids", []),
            security_group_ids=db_config_dict.get("security_group_ids") or [DEFAULT_VPC_CONFIG.get("lambda_security_group_id")],
        )
        logger.info(f"Database config: type={database_type}, config={db_config_dict}")

    try:
        deployer = _get_lambda_deployer()

        # Run async deploy in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                deployer.deploy(
                    project_name=project_name,
                    files=files,
                    runtime=runtime,
                    port=port,
                    memory_size=memory_size,
                    timeout=timeout,
                    environment_variables=environment_variables,
                    entry_point=entry_point,
                    database_config=db_config,
                )
            )
            return result
        finally:
            loop.close()

    except Exception as e:
        logger.error(f"Lambda deployment failed: {e}")
        return {
            "status": "failed",
            "error": str(e)
        }


@tool
def get_deployment_status(deployment_id: str, deployment_type: str = "static") -> Dict[str, Any]:
    """
    Get status of a deployment.

    Args:
        deployment_id: CloudFront distribution ID (static) or Lambda function name (dynamic)
        deployment_type: "static" or "dynamic"

    Returns:
        Deployment status information
    """
    try:
        if deployment_type == "static":
            deployer = _get_s3_deployer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(deployer.get_status(deployment_id))
            finally:
                loop.close()
        else:
            deployer = _get_lambda_deployer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(deployer.get_status(deployment_id))
            finally:
                loop.close()
    except Exception as e:
        return {"status": "error", "error": str(e)}


@tool
def list_deployments(deployment_type: str = "static", limit: int = 20) -> Dict[str, Any]:
    """
    List all UGC deployments.

    Args:
        deployment_type: "static" or "dynamic"
        limit: Maximum number of results

    Returns:
        List of deployments
    """
    try:
        if deployment_type == "static":
            deployer = _get_s3_deployer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(deployer.list_deployments(limit))
            finally:
                loop.close()
        else:
            deployer = _get_lambda_deployer()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(deployer.list_functions(limit))
            finally:
                loop.close()
    except Exception as e:
        return {"status": "error", "error": str(e)}
