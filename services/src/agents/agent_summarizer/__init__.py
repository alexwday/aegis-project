# services/src/agents/agent_summarizer/__init__.py
"""
Summarizer agent module for AEGIS project.
Handles research result summarization and response synthesis.
"""

from .summarizer import generate_streaming_summary, load_agent_config, SummarizerError

__all__ = ["generate_streaming_summary", "load_agent_config", "SummarizerError"]
