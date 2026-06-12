# -----------------------------------------------------------------------------
# sparQ - AI Tool Registry
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Tool registry for AI agent system.

Tools are registered by modules via hooks and collected here for use with
OpenAI function calling.
"""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Tool:
    """
    Definition of an AI tool that can be executed.

    Attributes:
        name: Unique identifier for the tool (e.g., "create_contact")
        description: Human-readable description for the LLM
        parameters: JSON Schema defining the tool's parameters
        execute: Function to execute when tool is called
    """

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Callable[[dict[str, Any]], Any]

    def to_openai_format(self) -> dict[str, Any]:
        """Convert to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """
    Registry for AI tools.

    Modules register their tools here via hooks. The registry provides
    tools in OpenAI function calling format.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def all_tools(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def to_openai_format(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function calling format."""
        return [tool.to_openai_format() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
