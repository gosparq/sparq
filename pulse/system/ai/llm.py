# -----------------------------------------------------------------------------
# sparQ - LLM Client
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
LLM client abstraction for AI agent system.

Supports multiple providers (OpenAI, Anthropic) with a unified interface.
Provider is configured via LLM_PROVIDER env var (default: openai).
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Response from LLM call."""

    type: str  # "tool_call", "clarification", "no_action", "error"
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None
    message: str | None = None
    raw_response: dict[str, Any] | None = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def call_with_tools(
        self,
        user_message: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        """Call LLM with tools/functions."""
        pass

    @abstractmethod
    def convert_tool_format(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Convert unified tool format to provider-specific format."""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self._client = OpenAI(api_key=api_key)
        return self._client

    def convert_tool_format(self, tool: dict[str, Any]) -> dict[str, Any]:
        """OpenAI native format - no conversion needed."""
        return tool

    def call_with_tools(
        self,
        user_message: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        try:
            # Build messages with conversation history
            messages = [{"role": "system", "content": system_prompt}]

            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history)

            # Add the current user message
            messages.append({"role": "user", "content": user_message})

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                tool_choice="auto" if tools else None,
            )

            message = response.choices[0].message

            if message.tool_calls:
                tool_call = message.tool_calls[0]
                return LLMResponse(
                    type="tool_call",
                    tool_name=tool_call.function.name,
                    tool_args=json.loads(tool_call.function.arguments),
                    raw_response=response.model_dump(),
                )

            content = message.content or ""
            if "?" in content:
                return LLMResponse(
                    type="clarification",
                    message=content,
                    raw_response=response.model_dump(),
                )

            return LLMResponse(
                type="no_action",
                message=content,
                raw_response=response.model_dump(),
            )

        except Exception as e:
            logger.exception("Error calling OpenAI")
            return LLMResponse(type="error", message=str(e))


class AnthropicProvider(LLMProvider):
    """Anthropic/Claude provider implementation."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not configured")
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def convert_tool_format(self, tool: dict[str, Any]) -> dict[str, Any]:
        """Convert OpenAI format to Anthropic format."""
        # Anthropic uses a slightly different structure
        func = tool.get("function", tool)
        return {
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"],
        }

    def call_with_tools(
        self,
        user_message: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> LLMResponse:
        try:
            # Convert tools to Anthropic format
            anthropic_tools = [self.convert_tool_format(t) for t in tools] if tools else []

            # Build messages with conversation history
            messages = []
            if conversation_history:
                messages.extend(conversation_history)
            messages.append({"role": "user", "content": user_message})

            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                tools=anthropic_tools if anthropic_tools else None,
                messages=messages,
            )

            # Check for tool use in response
            for block in response.content:
                if block.type == "tool_use":
                    return LLMResponse(
                        type="tool_call",
                        tool_name=block.name,
                        tool_args=block.input,
                        raw_response={"id": response.id, "model": response.model},
                    )

            # Text response
            text_content = ""
            for block in response.content:
                if block.type == "text":
                    text_content += block.text

            if "?" in text_content:
                return LLMResponse(
                    type="clarification",
                    message=text_content,
                    raw_response={"id": response.id, "model": response.model},
                )

            return LLMResponse(
                type="no_action",
                message=text_content,
                raw_response={"id": response.id, "model": response.model},
            )

        except Exception as e:
            logger.exception("Error calling Anthropic")
            return LLMResponse(type="error", message=str(e))


# Provider registry
_PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
}

_provider_instance: LLMProvider | None = None


def is_llm_configured() -> bool:
    """Check if LLM provider is configured with valid API key."""
    provider_name = os.environ.get("LLM_PROVIDER", "openai").lower()
    if provider_name == "openai":
        return bool(os.environ.get("OPENAI_API_KEY"))
    elif provider_name == "anthropic":
        return bool(os.environ.get("ANTHROPIC_API_KEY"))
    return False


def get_provider() -> LLMProvider:
    """Get configured LLM provider instance."""
    global _provider_instance
    if _provider_instance is None:
        provider_name = os.environ.get("LLM_PROVIDER", "openai").lower()
        if provider_name not in _PROVIDERS:
            raise ValueError(f"Unknown LLM provider: {provider_name}. Options: {list(_PROVIDERS.keys())}")
        _provider_instance = _PROVIDERS[provider_name]()
    return _provider_instance


def call_with_tools(
    user_message: str,
    tools: list[dict[str, Any]],
    context: dict[str, Any] | None = None,
) -> LLMResponse:
    """
    Call LLM with function calling (provider-agnostic).

    Args:
        user_message: The user's input message
        tools: List of tools in OpenAI format (will be converted if needed)
        context: Optional context (e.g., resolved entity references, conversation history)

    Returns:
        LLMResponse with tool call or message
    """
    provider = get_provider()

    # Extract conversation history from context
    conversation_history = None
    if context:
        conversation_history = context.get("conversation_history")

    system_prompt = _build_system_prompt(context)

    # Convert tools to provider format
    converted_tools = [provider.convert_tool_format(t) for t in tools] if tools else []

    return provider.call_with_tools(
        user_message, converted_tools, system_prompt, conversation_history
    )


def _build_system_prompt(context: dict[str, Any] | None = None) -> str:
    """Build system prompt for the AI agent."""
    prompt = """You are sparQy, sparQ's AI assistant available via the direct message interface.

Your role is to help users capture and manage information by calling the appropriate tools.

CONTACTS:
- When user says "add", "create", or "new" with a full name (first + last), use create_contact.
- When user types just a name (e.g., "larry" or "joe smith") WITHOUT add/create keywords, use search_contacts to find them.
- For CREATING: Requires explicit intent ("add Larry Patterson") AND full name. A full name = first_name:"Larry", last_name:"Patterson".
- For SEARCHING: Just a name, phone, or email is enough. "larry" alone = search for larry. Call search_contacts immediately.
- For CREATING company contacts: You MUST have the company name.

Guidelines:
- Extract as much structured information as possible from the user's message
- If the user mentions a person "knows" or is "connected to" someone, include that in the notes field
- Default to SEARCH when intent is unclear - only create when user explicitly says "add/create/new"
- If the user's message doesn't relate to any available tools, respond helpfully but explain you can only perform certain actions
- Be forgiving of typos and misspellings - infer the user's intent (e.g., "fine joe" likely means "find joe")

Be concise and helpful."""

    if context:
        if context.get("contacts"):
            prompt += "\n\nRelevant existing contacts:\n"
            for ref in context["contacts"]:
                prompt += f"\nReference '{ref['reference']}' matches:\n"
                for match in ref["matches"]:
                    prompt += f"  - {match['name']}"
                    if match.get("company"):
                        prompt += f" ({match['company']})"
                    prompt += f" [ID: {match['id']}]\n"

    return prompt
