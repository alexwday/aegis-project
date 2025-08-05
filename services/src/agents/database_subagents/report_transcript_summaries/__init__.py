# services/src/agents/database_subagents/report_transcript_summaries/__init__.py
"""
Report - Transcript Summaries Subagent Module

This module handles queries for pre-generated transcript summary reports
created based on investor relations team requirements.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]