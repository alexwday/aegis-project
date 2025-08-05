# services/src/agents/agent_direct_response/__init__.py
"""
Direct response agent module for AEGIS project.
Handles direct responses based on conversation context without database research.
"""

from .response_from_conversation import response_from_conversation, load_agent_config, DirectResponseError

__all__ = ["response_from_conversation", "load_agent_config", "DirectResponseError"]
