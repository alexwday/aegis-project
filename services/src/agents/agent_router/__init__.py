# services/src/agents/agent_router/__init__.py
"""
Router agent module for AEGIS project.
Handles request routing and agent orchestration.
"""

from .router import get_routing_decision, load_agent_config, RouterError

__all__ = ["get_routing_decision", "load_agent_config", "RouterError"]
