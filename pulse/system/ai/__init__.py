# -----------------------------------------------------------------------------
# sparQ - AI System
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
AI system for sparQ agent functionality.

This module provides:
- Tool registry for registering and discovering AI tools
- LLM client for OpenAI function calling
- Hook specs for module tool registration
"""

from .hooks import AIHookSpecs
from .llm import LLMProvider, LLMResponse, call_with_tools, get_provider
from .registry import Tool, ToolRegistry

__all__ = [
    "Tool",
    "ToolRegistry",
    "AIHookSpecs",
    "LLMProvider",
    "LLMResponse",
    "call_with_tools",
    "get_provider",
]
