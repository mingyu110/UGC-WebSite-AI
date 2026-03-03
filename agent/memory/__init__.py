"""
Memory Module for AgentCore Runtime

Provides AWS Bedrock AgentCore Memory integration for:
- Short-term memory (session conversation history)
- Long-term memory (user preferences, semantic search)

Usage:
    from agent.memory import create_memory_service

    # Create service with existing memory resource
    service = create_memory_service(
        memory_id="mem-xxx",
        actor_id="user-123",
        session_id="session-456",
    )

    # Add conversation
    service.add_conversation_turn("USER", "Hello")
    service.add_conversation_turn("ASSISTANT", "Hi there!")

    # Get history
    history = service.get_conversation_history(limit=10)

    # Search long-term memories
    results = service.search_memories("user preferences")
"""

from memory.memory_service import (
    AgentCoreMemoryService,
    MemoryService,
    create_memory_service,
    create_memory_resource,
    get_or_create_memory,
)

__all__ = [
    "AgentCoreMemoryService",
    "MemoryService",
    "create_memory_service",
    "create_memory_resource",
    "get_or_create_memory",
]
