"""
Intelligent Model Router

Routes tasks to optimal models based on task type for cost optimization.
Implements routing strategy from documentation section 6.1-6.2.
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task types for model routing."""
    COPYWRITING = "copywriting"          # Website copy generation
    SEO = "seo"                          # SEO metadata
    TEMPLATE = "template"                # Simple template filling
    PLANNING = "planning"                # Project planning
    CODE_GENERATION = "code_generation"  # Core code generation
    DEBUGGING = "debugging"              # Complex debugging
    IMAGE_PARSING = "image_parsing"      # Image/PDF parsing


@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_id: str
    input_cost_per_1k: float   # Cost per 1K input tokens
    output_cost_per_1k: float  # Cost per 1K output tokens
    max_tokens: int            # Maximum output tokens
    description: str


# Model routing configuration based on documentation 6.1
# Updated for Nova 2.0 models (released Dec 2025)
MODEL_ROUTING: dict[TaskType, ModelConfig] = {
    TaskType.COPYWRITING: ModelConfig(
        model_id="amazon.nova-2-lite-v1:0",
        input_cost_per_1k=0.00006,
        output_cost_per_1k=0.00024,
        max_tokens=5000,
        description="Website copy generation - Nova 2 Lite ~90% cost savings",
    ),
    TaskType.SEO: ModelConfig(
        model_id="amazon.nova-2-lite-v1:0",
        input_cost_per_1k=0.00006,
        output_cost_per_1k=0.00024,
        max_tokens=1000,
        description="SEO metadata - Nova 2 Lite ~90% cost savings",
    ),
    TaskType.TEMPLATE: ModelConfig(
        model_id="amazon.nova-2-lite-v1:0",
        input_cost_per_1k=0.00006,
        output_cost_per_1k=0.00024,
        max_tokens=2000,
        description="Template filling - Nova 2 Lite ~90% cost savings",
    ),
    TaskType.PLANNING: ModelConfig(
        model_id="amazon.nova-2-lite-v1:0",
        input_cost_per_1k=0.00006,
        output_cost_per_1k=0.00024,
        max_tokens=10000,
        description="Project planning - Nova 2 Lite with extended thinking",
    ),
    TaskType.CODE_GENERATION: ModelConfig(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_tokens=8000,
        description="Core code generation - Claude Sonnet highest quality",
    ),
    TaskType.DEBUGGING: ModelConfig(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        input_cost_per_1k=0.003,
        output_cost_per_1k=0.015,
        max_tokens=8000,
        description="Complex debugging - Claude Sonnet deep reasoning",
    ),
    TaskType.IMAGE_PARSING: ModelConfig(
        model_id="amazon.nova-2-lite-v1:0",
        input_cost_per_1k=0.00006,
        output_cost_per_1k=0.00024,
        max_tokens=4000,
        description="Image/PDF parsing - Nova 2 Lite multimodal support",
    ),
}


class ModelRouter:
    """
    Intelligent model router that selects optimal models based on task type.

    Implements cost optimization strategy from documentation section 6.1-6.2:
    - Nova Micro for simple tasks (SEO, templates) - ~95% savings
    - Nova Lite for content generation - ~90% savings
    - Nova Pro for planning - ~60% savings
    - Claude Sonnet for code generation and debugging - highest quality
    """

    def __init__(self, region: str = "us-east-1"):
        """
        Initialize the model router.

        Args:
            region: AWS region for Bedrock
        """
        self.region = region
        config = Config(
            retries={"max_attempts": 3, "mode": "adaptive"},
            read_timeout=300,
        )
        self.bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=config,
        )
        self._usage_stats: dict[str, dict] = {}

    def get_model_for_task(self, task_type: TaskType) -> str:
        """
        Get the optimal model ID for a given task type.

        Args:
            task_type: The type of task to perform

        Returns:
            The model ID to use
        """
        config = MODEL_ROUTING.get(task_type)
        if config is None:
            # Default to Claude Sonnet for unknown tasks
            logger.warning(f"Unknown task type: {task_type}, defaulting to Claude Sonnet")
            return MODEL_ROUTING[TaskType.CODE_GENERATION].model_id
        return config.model_id

    def get_model_config(self, task_type: TaskType) -> ModelConfig:
        """
        Get full model configuration for a task type.

        Args:
            task_type: The type of task

        Returns:
            ModelConfig with all settings
        """
        return MODEL_ROUTING.get(task_type, MODEL_ROUTING[TaskType.CODE_GENERATION])

    def invoke_sync(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Synchronously invoke the appropriate model for a task.

        Args:
            task_type: Type of task to determine model
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Override default max tokens
            temperature: Model temperature (0-1)

        Returns:
            Model response text
        """
        config = self.get_model_config(task_type)
        model_id = config.model_id
        tokens = max_tokens or config.max_tokens

        logger.info(f"Routing {task_type.value} to model: {model_id}")

        # Build request based on model type
        if "anthropic" in model_id:
            response = self._invoke_claude_sync(
                model_id, prompt, system_prompt, tokens, temperature
            )
        else:
            response = self._invoke_nova_sync(
                model_id, prompt, system_prompt, tokens, temperature
            )

        # Track usage
        self._track_usage(task_type, model_id)

        return response

    def _invoke_claude_sync(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Synchronously invoke Claude model via Bedrock."""
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        response = self.bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    def _invoke_nova_sync(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Synchronously invoke Nova 2 model via Bedrock."""
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        body = {
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            body["system"] = [{"text": system_prompt}]

        response = self.bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        response_body = json.loads(response["body"].read())
        return response_body["output"]["message"]["content"][0]["text"]

    async def invoke(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """
        Asynchronously invoke the appropriate model for a task.

        Args:
            task_type: Type of task to determine model
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Override default max tokens
            temperature: Model temperature (0-1)
            **kwargs: Additional model parameters

        Returns:
            Model response text
        """
        # For now, delegate to sync version since boto3 client is sync
        return self.invoke_sync(task_type, prompt, system_prompt, max_tokens, temperature)

    async def _invoke_claude(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Invoke Claude model via Bedrock (async wrapper)."""
        return self._invoke_claude_sync(model_id, prompt, system_prompt, max_tokens, temperature)

    async def _invoke_nova(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Invoke Nova model via Bedrock (async wrapper)."""
        return self._invoke_nova_sync(model_id, prompt, system_prompt, max_tokens, temperature)

    async def invoke_streaming(
        self,
        task_type: TaskType,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.7,
    ):
        """
        Invoke model with streaming response.

        Args:
            task_type: Type of task
            prompt: User prompt
            system_prompt: Optional system prompt
            max_tokens: Override max tokens
            temperature: Model temperature

        Yields:
            Response text chunks
        """
        config = self.get_model_config(task_type)
        model_id = config.model_id
        tokens = max_tokens or config.max_tokens

        logger.info(f"Streaming {task_type.value} with model: {model_id}")

        if model_id.startswith("anthropic."):
            async for chunk in self._stream_claude(
                model_id, prompt, system_prompt, tokens, temperature
            ):
                yield chunk
        else:
            async for chunk in self._stream_nova(
                model_id, prompt, system_prompt, tokens, temperature
            ):
                yield chunk

        self._track_usage(task_type, model_id)

    async def _stream_claude(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ):
        """Stream Claude model response."""
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        response = self.bedrock_client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        for event in response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            if chunk.get("type") == "content_block_delta":
                delta = chunk.get("delta", {})
                if "text" in delta:
                    yield delta["text"]

    async def _stream_nova(
        self,
        model_id: str,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ):
        """Stream Nova model response."""
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        body = {
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            body["system"] = [{"text": system_prompt}]

        response = self.bedrock_client.invoke_model_with_response_stream(
            modelId=model_id,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )

        for event in response["body"]:
            chunk = json.loads(event["chunk"]["bytes"])
            if "contentBlockDelta" in chunk:
                delta = chunk["contentBlockDelta"].get("delta", {})
                if "text" in delta:
                    yield delta["text"]

    def _track_usage(self, task_type: TaskType, model_id: str) -> None:
        """Track model usage for monitoring."""
        key = f"{task_type.value}:{model_id}"
        if key not in self._usage_stats:
            self._usage_stats[key] = {"count": 0, "task_type": task_type.value}
        self._usage_stats[key]["count"] += 1

    def get_usage_stats(self) -> dict[str, dict]:
        """Get usage statistics."""
        return self._usage_stats.copy()

    def estimate_cost(
        self,
        task_type: TaskType,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Estimate cost for a task.

        Args:
            task_type: Type of task
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens

        Returns:
            Estimated cost in USD
        """
        config = self.get_model_config(task_type)
        input_cost = (input_tokens / 1000) * config.input_cost_per_1k
        output_cost = (output_tokens / 1000) * config.output_cost_per_1k
        return input_cost + output_cost


# Convenience function for creating router instance
def create_model_router(region: str = "us-east-1") -> ModelRouter:
    """Create a new ModelRouter instance."""
    return ModelRouter(region=region)
