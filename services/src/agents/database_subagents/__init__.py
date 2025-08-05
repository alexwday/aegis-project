# services/src/agents/database_subagents/__init__.py
"""
Database subagents module for AEGIS project.
Contains specialized agents for database search and retrieval operations.
"""

from .database_router import route_query_sync

__all__ = ["route_query_sync"]
