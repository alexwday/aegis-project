# services/src/chat_model/__init__.py
"""
Chat model module for AEGIS project.
Contains chat model implementations and conversation handling.
"""

from .model import model, process_request_async

__all__ = ["model", "process_request_async"]
