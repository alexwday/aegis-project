# services/src/agents/database_subagents/benchmarking/__init__.py
"""
Benchmarking Database Subagent Module

This module handles queries to the financial benchmarking database containing
income statement, balance sheet, and business-specific line items from all major banks.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]