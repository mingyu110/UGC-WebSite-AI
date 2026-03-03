"""
Memory Tools for AgentCore Runtime

Strands tool wrappers for AgentCore Memory API.
Provides tool-based access to short-term and long-term memory operations.

These tools enable agents to:
- Store and retrieve conversation history
- Save and access user preferences
- Search for relevant memories semantically
"""

import os
from typing import Any, Dict, List, Optional

from strands.tools import tool

from memory.memory_service import (
    AgentCoreMemoryService,
    create_memory_service,
)


# Global memory service instance
_memory_service: Optional[AgentCoreMemoryService] = None


def get_memory_service(
    memory_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AgentCoreMemoryService:
    """Get or create the global memory service instance."""
    global _memory_service
    if _memory_service is None:
        _memory_service = create_memory_service(
            memory_id=memory_id or os.environ.get("AGENTCORE_MEMORY_ID"),
            actor_id=actor_id,
            session_id=session_id,
        )
    return _memory_service


def initialize_memory_service(
    memory_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AgentCoreMemoryService:
    """Initialize a new memory service instance."""
    global _memory_service
    _memory_service = create_memory_service(
        memory_id=memory_id or os.environ.get("AGENTCORE_MEMORY_ID"),
        actor_id=actor_id,
        session_id=session_id,
    )
    return _memory_service


# ==================== Conversation Tools ====================


@tool
def save_conversation_turn(
    role: str,
    content: str,
    metadata: Optional[Dict[str, str]] = None,
) -> dict:
    """
    Save a conversation turn to short-term memory.

    Args:
        role: USER or ASSISTANT
        content: Message content
        metadata: Optional key-value metadata

    Returns:
        dict with success status
    """
    memory = get_memory_service()
    try:
        memory.add_conversation_turn(role, content, metadata)
        return {"success": True, "message": f"Saved {role} turn"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@tool
def get_conversation_history(limit: int = 10) -> dict:
    """
    Get recent conversation history.

    Args:
        limit: Maximum number of turns to return

    Returns:
        dict with conversation history
    """
    memory = get_memory_service()
    try:
        history = memory.get_conversation_history(limit=limit)
        return {
            "success": True,
            "conversation": history,
            "turn_count": len(history),
        }
    except Exception as e:
        return {"success": False, "conversation": [], "error": str(e)}


# ==================== User Preference Tools ====================


@tool
def save_user_preference(
    preference_key: str,
    preference_value: Any,
) -> dict:
    """
    Save a user preference to long-term memory.

    Preferences are extracted by AgentCore's UserPreferenceStrategy.

    Args:
        preference_key: The preference key (e.g., "favorite_color")
        preference_value: The preference value

    Returns:
        dict with success status
    """
    memory = get_memory_service()
    try:
        memory.save_preference(preference_key, preference_value)
        return {
            "success": True,
            "key": preference_key,
            "message": f"Saved preference: {preference_key}",
        }
    except Exception as e:
        return {"success": False, "key": preference_key, "error": str(e)}


@tool
def get_user_preferences() -> dict:
    """
    Get user preferences from long-term memory.

    Returns:
        dict with user preferences
    """
    memory = get_memory_service()
    try:
        preferences = memory.get_user_preferences()
        return {
            "success": True,
            "preferences": preferences,
            "has_preferences": bool(preferences),
        }
    except Exception as e:
        return {"success": False, "preferences": {}, "error": str(e)}


# ==================== Semantic Search Tools ====================


@tool
def search_memories(
    query: str,
    namespace_prefix: Optional[str] = None,
    top_k: int = 5,
) -> dict:
    """
    Search long-term memories using semantic search.

    Args:
        query: Search query
        namespace_prefix: Optional namespace filter
        top_k: Number of results

    Returns:
        dict with search results
    """
    memory = get_memory_service()
    try:
        results = memory.search_memories(query, namespace_prefix, top_k)
        return {
            "success": True,
            "results": results,
            "result_count": len(results),
            "query": query,
        }
    except Exception as e:
        return {"success": False, "results": [], "query": query, "error": str(e)}


# Backward compatibility aliases
save_session = save_conversation_turn
get_session = get_conversation_history
retrieve_relevant = search_memories


# ==================== Code Version Tools (Local Only) ====================
# Note: Code versioning is handled locally, not via AgentCore Memory API

_code_versions: List[Dict[str, Any]] = []


@tool
def save_code_version(
    files: Dict[str, str],
    description: str = "",
) -> dict:
    """
    Save a code version for rollback (local storage).

    Args:
        files: Dictionary of filename to content
        description: Version description

    Returns:
        dict with version_id
    """
    import uuid
    from datetime import datetime, timezone

    version_id = f"v{len(_code_versions) + 1}-{uuid.uuid4().hex[:6]}"
    _code_versions.append({
        "version_id": version_id,
        "files": files,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "description": description,
    })
    return {
        "success": True,
        "version_id": version_id,
        "file_count": len(files),
    }


@tool
def rollback_code(version_id: str) -> dict:
    """
    Rollback to a previous code version.

    Args:
        version_id: Version ID to rollback to

    Returns:
        dict with restored files
    """
    for v in _code_versions:
        if v["version_id"] == version_id:
            return {
                "success": True,
                "version_id": version_id,
                "files": v["files"],
            }
    return {"success": False, "error": "Version not found"}


@tool
def list_code_versions() -> dict:
    """
    List all saved code versions.

    Returns:
        dict with version list
    """
    versions = [
        {
            "version_id": v["version_id"],
            "timestamp": v["timestamp"],
            "description": v["description"],
            "file_count": len(v["files"]),
        }
        for v in _code_versions
    ]
    return {"success": True, "versions": versions, "version_count": len(versions)}
