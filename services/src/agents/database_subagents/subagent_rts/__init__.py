# services/src/agents/database_subagents/rts/__init__.py
"""
RTS Database Subagent Module

This module handles queries to the Report to Shareholders (RTS) / 10-Q/10-K database.
Contains official regulatory filings used as secondary source for context and line items.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]