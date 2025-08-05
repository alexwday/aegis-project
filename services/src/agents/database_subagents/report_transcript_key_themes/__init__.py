# services/src/agents/database_subagents/report_transcript_key_themes/__init__.py
"""
Report - Transcript Key Themes Subagent Module

This module handles queries for pre-generated key themes reports
created based on investor relations team requirements.
"""

from .subagent import query_database_sync

__all__ = ["query_database_sync"]