"""Agent HTTP 服务器配置

基于 Pydantic 的 Agent HTTP 服务器配置，支持环境变量。
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Agent HTTP 服务器的配置设置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # 服务器设置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False

    # AWS 设置
    AWS_REGION: str = "us-east-1"
    AWS_ACCOUNT_ID: str = "947472889616"

    # AgentCore Runtime 设置
    AGENT_RUNTIME_ARN: str = ""  # AgentCore 部署后通过环境变量设置
    AGENTCORE_QUALIFIER: str = "DEFAULT"

    # 部署资源 - 静态（S3 + CloudFront）
    STATIC_S3_BUCKET: str = "ugc-static-947472889616-us-east-1"
    STATIC_CLOUDFRONT_DOMAIN: str = "d2x3r9mhi9wvmb.cloudfront.net"

    # 部署资源 - 动态（Lambda）
    DYNAMIC_LAMBDA_FUNCTION: str = "ugc-dynamic-example"
    DYNAMIC_FUNCTION_URL: str = "https://r4a7c2xrpqkh7go3cmjazjppsm0uanpm.lambda-url.us-east-1.on.aws/"

    # Bedrock 模型设置
    DEFAULT_MODEL: str = "anthropic.claude-sonnet-4-20250514-v1:0"
    FAST_MODEL: str = "amazon.nova-lite-v1:0"
    REASONING_MODEL: str = "anthropic.claude-sonnet-4-20250514-v1:0"

    # CORS 设置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ]

    # 速率限制
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # 秒

    # 超时设置
    REQUEST_TIMEOUT: int = 300  # 秒
    GENERATION_TIMEOUT: int = 180  # 秒

    @property
    def static_base_url(self) -> str:
        """获取静态部署的基础 URL。"""
        return f"https://{self.STATIC_CLOUDFRONT_DOMAIN}"

    @property
    def bedrock_model_id(self) -> str:
        """获取默认的 Bedrock 模型 ID。"""
        return self.DEFAULT_MODEL

    @property
    def agent_runtime_arn(self) -> str:
        """获取 AgentCore Runtime ARN。"""
        if self.AGENT_RUNTIME_ARN:
            return self.AGENT_RUNTIME_ARN
        # 如果未显式设置，则构造默认 ARN
        return f"arn:aws:bedrock-agentcore:{self.AWS_REGION}:{self.AWS_ACCOUNT_ID}:agent-runtime/ugc-website-generator"


# 单例实例
_config: ServerConfig | None = None


def get_config() -> ServerConfig:
    """获取服务器配置单例。"""
    global _config
    if _config is None:
        _config = ServerConfig()
    return _config
