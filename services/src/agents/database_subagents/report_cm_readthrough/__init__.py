# services/src/agents/database_subagents/report_cm_readthrough/__init__.py
"""
Report - CM Readthrough Subagent Module

This module handles queries for pre-generated CM readthrough reports
combining all US Capital Markets entities.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]