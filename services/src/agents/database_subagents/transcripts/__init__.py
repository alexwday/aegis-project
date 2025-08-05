# services/src/agents/database_subagents/transcripts/__init__.py
"""
Transcripts Database Subagent Module

This module handles queries to the earnings call transcripts database.
Contains management discussion, guidance, context, and reasoning around financial results.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]