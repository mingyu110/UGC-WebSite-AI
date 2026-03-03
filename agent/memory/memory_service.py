"""
Memory Service for AgentCore Runtime

Implements AWS Bedrock AgentCore Memory API for:
- Short-term memory: Session-level conversation history
- Long-term memory: User preferences, semantic search

Based on: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3

logger = logging.getLogger(__name__)

# AWS Region
REGION = os.environ.get("AWS_REGION", "us-east-1")


class AgentCoreMemoryService:
    """
    Memory service using AWS Bedrock AgentCore Memory API.

    Provides:
    - Short-term memory: Conversation history within a session
    - Long-term memory: User preferences and semantic search across sessions
    """

    def __init__(
        self,
        memory_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        session_id: Optional[str] = None,
        region: str = REGION,
    ):
        """
        Initialize the Memory Service.

        Args:
            memory_id: AgentCore Memory resource ID (required for API calls)
            actor_id: User/actor identifier
            session_id: Session identifier
            region: AWS region
        """
        self.memory_id = memory_id or os.environ.get("AGENTCORE_MEMORY_ID", "")
        self.actor_id = actor_id
        self.session_id = session_id
        self.region = region

        # Lazy-initialized clients
        self._control_client = None
        self._data_client = None

        # Local fallback storage (when Memory ID not configured)
        self._local_events: List[Dict[str, Any]] = []
        self._local_preferences: Dict[str, Any] = {}

    @property
    def control_client(self):
        """Control plane client for memory resource management."""
        if self._control_client is None:
            self._control_client = boto3.client(
                "bedrock-agentcore-control",
                region_name=self.region
            )
        return self._control_client

    @property
    def data_client(self):
        """Data plane client for memory operations."""
        if self._data_client is None:
            self._data_client = boto3.client(
                "bedrock-agentcore",
                region_name=self.region
            )
        return self._data_client

    # ==================== Short-term Memory (Events) ====================

    def add_conversation_turn(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Add a conversation turn to short-term memory.

        Args:
            role: USER or ASSISTANT
            content: Message content
            metadata: Optional key-value metadata
        """
        if not self.memory_id or not self.actor_id or not self.session_id:
            # Fallback to local storage
            self._local_events.append({
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return

        try:
            payload = [{
                "conversational": {
                    "role": role.upper(),
                    "content": {"text": content}
                }
            }]

            self.data_client.create_event(
                memoryId=self.memory_id,
                actorId=self.actor_id,
                sessionId=self.session_id,
                eventTimestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                payload=payload,
                eventMetadata=metadata or {},
            )
        except Exception as e:
            logger.warning(f"Failed to create event: {e}")
            self._local_events.append({
                "role": role,
                "content": content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def add_conversation_turns(
        self,
        messages: List[Dict[str, str]],
    ) -> None:
        """
        Add multiple conversation turns at once.

        Args:
            messages: List of {"role": "USER/ASSISTANT", "content": "..."}
        """
        if not self.memory_id or not self.actor_id or not self.session_id:
            for msg in messages:
                self._local_events.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            return

        try:
            payload = [
                {
                    "conversational": {
                        "role": msg["role"].upper(),
                        "content": {"text": msg["content"]}
                    }
                }
                for msg in messages
            ]

            self.data_client.create_event(
                memoryId=self.memory_id,
                actorId=self.actor_id,
                sessionId=self.session_id,
                eventTimestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                payload=payload,
            )
        except Exception as e:
            logger.warning(f"Failed to create events: {e}")

    def get_conversation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent conversation history from short-term memory.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of conversation events
        """
        if not self.memory_id or not self.actor_id or not self.session_id:
            return self._local_events[-limit:]

        try:
            response = self.data_client.list_events(
                memoryId=self.memory_id,
                actorId=self.actor_id,
                sessionId=self.session_id,
                maxResults=limit,
            )
            events = response.get("events", [])
            # Convert to simple format
            result = []
            for event in reversed(events):
                payload = event.get("payload", [])
                for item in payload:
                    conv = item.get("conversational", {})
                    if conv:
                        result.append({
                            "role": conv.get("role", ""),
                            "content": conv.get("content", {}).get("text", ""),
                            "timestamp": event.get("eventTimestamp", ""),
                        })
            return result
        except Exception as e:
            logger.warning(f"Failed to list events: {e}")
            return self._local_events[-limit:]

    # ==================== Long-term Memory (Preferences & Search) ====================

    def search_memories(
        self,
        query: str,
        namespace_prefix: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Search long-term memories using semantic search.

        Args:
            query: Search query
            namespace_prefix: Optional namespace filter
            top_k: Number of results to return

        Returns:
            List of matching memory records
        """
        if not self.memory_id:
            return []

        namespace = namespace_prefix or f"/users/{self.actor_id}/preferences/"

        try:
            response = self.data_client.retrieve_memory_records(
                memoryId=self.memory_id,
                namespace=namespace,
                searchCriteria={"searchQuery": query},
            )
            records = response.get("memoryRecordSummaries", [])
            return records[:top_k]
        except Exception as e:
            logger.warning(f"Failed to search memories: {e}")
            return []

    def get_user_preferences(self) -> Dict[str, Any]:
        """
        Get user preferences from long-term memory.

        Returns:
            User preferences dict
        """
        if not self.memory_id or not self.actor_id:
            return self._local_preferences

        try:
            records = self.search_memories(
                query="user preferences",
                namespace_prefix=f"/users/{self.actor_id}/preferences/",
                top_k=10,
            )
            # Aggregate preferences from records
            preferences = {}
            for record in records:
                content = record.get("content", {})
                if isinstance(content, dict):
                    preferences.update(content)
            return preferences
        except Exception as e:
            logger.warning(f"Failed to get preferences: {e}")
            return self._local_preferences

    def save_preference(self, key: str, value: Any) -> None:
        """
        Save a user preference (will be extracted by UserPreferenceStrategy).

        Note: AgentCore Memory extracts preferences automatically from
        conversation. This method adds a preference statement to the
        conversation for extraction.

        Args:
            key: Preference key
            value: Preference value
        """
        # Add preference as conversation turn for extraction
        self.add_conversation_turn(
            role="USER",
            content=f"My preference for {key} is: {value}",
        )
        self.add_conversation_turn(
            role="ASSISTANT",
            content=f"I've noted your preference for {key}: {value}",
        )
        # Also save locally
        self._local_preferences[key] = value


# ==================== Memory Resource Management ====================

def create_memory_resource(
    name: str,
    description: str = "",
    region: str = REGION,
    enable_summary: bool = True,
    enable_preferences: bool = True,
) -> str:
    """
    Create an AgentCore Memory resource.

    Args:
        name: Memory resource name
        description: Description
        region: AWS region
        enable_summary: Enable session summary strategy
        enable_preferences: Enable user preference strategy

    Returns:
        Memory resource ID
    """
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    strategies = []
    if enable_summary:
        strategies.append({
            "summaryMemoryStrategy": {
                "name": "SessionSummarizer",
                "namespaces": ["/summaries/{actorId}/{sessionId}/"]
            }
        })
    if enable_preferences:
        strategies.append({
            "userPreferenceMemoryStrategy": {
                "name": "PreferenceLearner",
                "namespaces": ["/users/{actorId}/preferences/"]
            }
        })

    response = control_client.create_memory(
        name=name,
        description=description,
        memoryStrategies=strategies,
    )

    memory_id = response["memory"]["id"]
    logger.info(f"Created memory resource: {memory_id}")

    # Wait for ACTIVE status
    while True:
        status_response = control_client.get_memory(memoryId=memory_id)
        status = status_response.get("memory", {}).get("status")
        if status == "ACTIVE":
            break
        elif status == "FAILED":
            raise Exception("Memory resource creation failed")
        time.sleep(5)

    return memory_id


def get_or_create_memory(
    name: str,
    region: str = REGION,
) -> str:
    """
    Get existing memory resource or create new one.

    Args:
        name: Memory resource name
        region: AWS region

    Returns:
        Memory resource ID
    """
    control_client = boto3.client("bedrock-agentcore-control", region_name=region)

    try:
        # Try to find existing memory by name
        response = control_client.list_memories()
        for memory in response.get("memories", []):
            if memory.get("name") == name:
                return memory["id"]
    except Exception:
        pass

    # Create new memory
    return create_memory_resource(name=name, region=region)


# ==================== Factory Function ====================

def create_memory_service(
    memory_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    session_id: Optional[str] = None,
    region: str = REGION,
) -> AgentCoreMemoryService:
    """
    Create a memory service instance.

    Args:
        memory_id: AgentCore Memory resource ID
        actor_id: User/actor identifier
        session_id: Session identifier
        region: AWS region

    Returns:
        AgentCoreMemoryService instance
    """
    return AgentCoreMemoryService(
        memory_id=memory_id,
        actor_id=actor_id,
        session_id=session_id,
        region=region,
    )


# Backward compatibility alias
MemoryService = AgentCoreMemoryService
