# services/src/agents/database_subagents/ir_quarterly_newsletter/__init__.py
"""
Investor Relations Quarterly Newsletter Subagent Module

This module handles queries for pre-generated quarterly newsletters
combining insights from all global banks.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]