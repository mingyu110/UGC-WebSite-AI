"""
AgentCore Runtime 客户端

提供用于调用部署在 AWS Bedrock AgentCore Runtime 上的 Agent 的客户端。
支持同步和流式响应。
"""

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


def ensure_valid_session_id(session_id: Optional[str]) -> str:
    """
    确保会话 ID 满足 AgentCore Runtime 的要求（最少 33 个字符）。

    如果提供的会话 ID 过短，则使用哈希生成确定性的填充版本，
    确保相同的输入始终产生相同的输出。
    """
    MIN_LENGTH = 33

    if not session_id:
        # 生成基于 UUID 的新会话 ID
        return f"agentcore-session-{uuid.uuid4()}"

    if len(session_id) >= MIN_LENGTH:
        return session_id

    # 使用哈希确定性地填充过短的会话 ID
    # 确保相同的短 ID 始终产生相同的填充 ID
    hash_suffix = hashlib.sha256(session_id.encode()).hexdigest()[:16]
    return f"agentcore-{session_id}-{hash_suffix}"


@dataclass
class AgentCoreResponse:
    """AgentCore Runtime 调用的响应。"""
    content: str
    session_id: str
    raw_response: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentCoreClient:
    """
    用于调用 AWS Bedrock AgentCore Runtime 中 Agent 的客户端。

    用法:
        client = AgentCoreClient()

        # 同步调用
        response = client.invoke(prompt="Create a website", session_id="abc123")
        print(response.content)

        # 流式调用
        for chunk in client.invoke_stream(prompt="Create a website"):
            print(chunk, end="")
    """

    def __init__(
        self,
        agent_runtime_arn: Optional[str] = None,
        qualifier: str = "DEFAULT",
        region: Optional[str] = None,
    ):
        """
        初始化 AgentCore 客户端。

        参数:
            agent_runtime_arn: AgentCore Runtime Agent 的 ARN。
                              回退到 AGENT_RUNTIME_ARN 环境变量。
            qualifier: Agent 限定符（默认: "DEFAULT"）
            region: AWS 区域。回退到 AWS_REGION 环境变量。
        """
        self.agent_runtime_arn = agent_runtime_arn or os.environ.get("AGENT_RUNTIME_ARN", "")
        self.qualifier = qualifier or os.environ.get("AGENTCORE_QUALIFIER", "DEFAULT")
        self.region = region or os.environ.get("AWS_REGION", "us-east-1")

        if not self.agent_runtime_arn:
            logger.warning("AGENT_RUNTIME_ARN not configured. AgentCore calls will fail.")

        self._client = None

    @property
    def client(self):
        """延迟初始化 boto3 客户端，为长时间运行的 Agent 任务配置扩展超时。"""
        if self._client is None:
            # AgentCore 同步请求最长可达 15 分钟
            # 为网站生成任务配置 boto3 扩展超时
            config = Config(
                connect_timeout=60,
                read_timeout=900,  # AgentCore 同步请求最长 15 分钟
                retries={"max_attempts": 3, "mode": "adaptive"}
            )
            self._client = boto3.client(
                "bedrock-agentcore",
                region_name=self.region,
                config=config
            )
        return self._client

    def invoke(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        payload_extra: Optional[Dict[str, Any]] = None,
    ) -> AgentCoreResponse:
        """
        同步调用 AgentCore Runtime Agent。

        参数:
            prompt: 用户的提示/消息
            session_id: 可选的会话 ID，用于对话连续性
            payload_extra: 可选的额外载荷字段

        返回:
            包含 Agent 响应的 AgentCoreResponse
        """
        if not self.agent_runtime_arn:
            raise ValueError("AGENT_RUNTIME_ARN is not configured")

        # 确保会话 ID 满足 AgentCore Runtime 要求（最少 33 个字符）
        session_id = ensure_valid_session_id(session_id)

        # 构建载荷
        payload = {"prompt": prompt}
        if payload_extra:
            payload.update(payload_extra)

        logger.info(f"Invoking AgentCore Runtime - session: {session_id}")

        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_runtime_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload).encode("utf-8"),
                qualifier=self.qualifier,
            )

            # 收集响应分块 - 先累积bytes再统一解码
            # 这样可以处理跨分块边界的UTF-8多字节字符
            raw_bytes = b""
            for chunk in response.get("response", []):
                if isinstance(chunk, bytes):
                    raw_bytes += chunk
                elif isinstance(chunk, str):
                    raw_bytes += chunk.encode("utf-8")
                else:
                    raw_bytes += str(chunk).encode("utf-8")

            content = raw_bytes.decode("utf-8", errors="replace")

            # 尝试解析为 JSON
            try:
                parsed = json.loads(content)
                return AgentCoreResponse(
                    content=parsed.get("response", content),
                    session_id=session_id,
                    raw_response=parsed,
                    metadata={
                        "phase": parsed.get("phase"),
                        "status": parsed.get("status"),
                        "code": parsed.get("code"),
                        "deployment_url": parsed.get("deployment_url"),
                        "deployment_type": parsed.get("deployment_type"),
                    }
                )
            except json.JSONDecodeError:
                return AgentCoreResponse(
                    content=content,
                    session_id=session_id,
                )

        except Exception as e:
            logger.error(f"AgentCore invocation failed: {e}")
            raise

    def invoke_stream(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        payload_extra: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """
        流式调用 AgentCore Runtime Agent。

        参数:
            prompt: 用户的提示/消息
            session_id: 可选的会话 ID，用于对话连续性
            payload_extra: 可选的额外载荷字段

        生成:
            响应的字符串分块
        """
        if not self.agent_runtime_arn:
            raise ValueError("AGENT_RUNTIME_ARN is not configured")

        # 确保会话 ID 满足 AgentCore Runtime 要求（最少 33 个字符）
        session_id = ensure_valid_session_id(session_id)

        # 构建载荷 - 包含 session_id 用于应用层会话跟踪
        payload = {
            "prompt": prompt,
            "session_id": session_id,  # 传递 session_id 给处理器以保持上下文
        }
        if payload_extra:
            payload.update(payload_extra)

        logger.info(f"Invoking AgentCore Runtime (stream) - session: {session_id}")

        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.agent_runtime_arn,
                runtimeSessionId=session_id,
                payload=json.dumps(payload).encode("utf-8"),
                qualifier=self.qualifier,
            )

            # 使用增量解码器处理跨分块边界的UTF-8字符
            import codecs
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

            for chunk in response.get("response", []):
                if isinstance(chunk, bytes):
                    decoded = decoder.decode(chunk, final=False)
                    if decoded:
                        yield decoded
                else:
                    yield str(chunk)

            # 刷新解码器缓冲区
            final = decoder.decode(b"", final=True)
            if final:
                yield final

        except Exception as e:
            logger.error(f"AgentCore streaming invocation failed: {e}")
            raise

    async def invoke_stream_async(
        self,
        prompt: str,
        session_id: Optional[str] = None,
        payload_extra: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        用于流式 AgentCore 响应的异步生成器。
        适用于 FastAPI SSE 端点。

        使用线程池执行同步的 boto3 调用，避免阻塞事件循环。
        这样可以确保健康检查端点在长时间运行的请求期间仍能响应。

        参数:
            prompt: 用户的提示/消息
            session_id: 可选的会话 ID，用于对话连续性
            payload_extra: 可选的额外载荷字段

        生成:
            响应的字符串分块
        """
        import asyncio
        import queue
        import threading

        # 使用线程安全的队列在线程和异步生成器之间传递数据
        chunk_queue: queue.Queue = queue.Queue()
        done_event = threading.Event()
        error_holder: list = []

        def run_sync_stream():
            """在单独的线程中运行同步流式调用。"""
            try:
                for chunk in self.invoke_stream(prompt, session_id, payload_extra):
                    chunk_queue.put(chunk)
            except Exception as e:
                error_holder.append(e)
            finally:
                done_event.set()

        # 启动后台线程执行同步调用
        thread = threading.Thread(target=run_sync_stream, daemon=True)
        thread.start()

        # 异步地从队列中获取数据，不阻塞事件循环
        while not done_event.is_set() or not chunk_queue.empty():
            try:
                # 非阻塞地尝试获取数据
                chunk = chunk_queue.get_nowait()
                yield chunk
            except queue.Empty:
                # 队列为空，短暂让出控制权给事件循环
                await asyncio.sleep(0.01)

        # 检查是否有错误
        if error_holder:
            raise error_holder[0]


# 单例实例
_client: Optional[AgentCoreClient] = None


def get_agentcore_client() -> AgentCoreClient:
    """获取 AgentCore 客户端单例。"""
    global _client
    if _client is None:
        _client = AgentCoreClient()
    return _client
