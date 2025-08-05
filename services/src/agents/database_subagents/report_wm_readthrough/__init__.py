# services/src/agents/database_subagents/report_wm_readthrough/__init__.py
"""
Report - WM Readthrough Subagent Module

This module handles queries for pre-generated WM readthrough reports
combining all US Wealth Management entities.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]