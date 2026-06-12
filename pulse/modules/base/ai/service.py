# -----------------------------------------------------------------------------
# sparQ - AI Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
AI service for handling agent messages.

This is the main orchestrator that:
1. Collects tools from all modules
2. Resolves context (entity lookups)
3. Calls the LLM
4. Creates pending actions and posts proposals
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from flask import current_app

if TYPE_CHECKING:
    from modules.base.core.models.user import User

    from system.ai.llm import LLMResponse

from system.ai import ToolRegistry, call_with_tools

from .models import AIPendingAction

logger = logging.getLogger(__name__)


def handle_agent_message(content: str, user: User) -> None:
    """Handle a message sent to sparQy.

    Args:
        content: The message content (not saved to DB)
        user: The User who sent the message
    """
    # 0. Check for commands (messages starting with /)
    from .commands import get_command, parse_command

    parsed = parse_command(content)
    if parsed:
        command_name, args = parsed
        cmd = get_command(command_name)
        if cmd:
            handler, _ = cmd
            result = handler(args, None, user)

            if result.clear_messages:
                _broadcast_clear_messages(user.id)

            if result.message:
                _post_ai_message(result.message, user.id, clear_storage=result.clear_messages)
            return
        else:
            _post_ai_message(f"Unknown command: /{command_name}. Type /help for available commands.", user.id)
            return

    # 1. Check if LLM is configured
    from system.ai.llm import is_llm_configured

    if not is_llm_configured():
        _post_ai_warning(
            "LLM is not configured. Please add your API key to .env to enable AI features.",
            user.id,
        )
        return

    # 2. Collect tools from all modules
    registry = ToolRegistry()
    current_app.module_loader.pm.hook.register_ai_tools(registry=registry)

    if len(registry) == 0:
        _post_ai_message("No AI tools are available. Please contact your administrator.", user.id)
        return

    # 3. Resolve context (find referenced entities)
    context = _resolve_context(content)

    # 4. Note: Conversation history is now managed client-side in localStorage
    context["conversation_history"] = []

    # 5. Call LLM with tools
    tools = registry.to_openai_format()
    response = call_with_tools(content, tools, context)

    # 6. Handle response based on type
    if response.type == "tool_call":
        _handle_tool_call(response, content, user, registry)
    elif response.type == "clarification":
        _post_ai_message(response.message or "Could you please clarify?", user.id)
    elif response.type == "no_action":
        _post_ai_message(response.message or "I'm not sure how to help with that.", user.id)
    elif response.type == "error":
        logger.error(f"LLM error: {response.message}")
        _post_ai_message("I encountered an error processing your request. Please try again.", user.id)


def _handle_tool_call(response: LLMResponse, trigger_content: str, user: User, registry: ToolRegistry) -> None:
    """Handle a tool call response from the LLM."""
    from .models import ActionStatus

    tool_name = response.tool_name
    tool_args = response.tool_args or {}

    AUTO_EXECUTE_TOOLS = {"search_contacts"}

    if tool_name in AUTO_EXECUTE_TOOLS:
        tool = registry.get(tool_name)
        if tool:
            try:
                result = tool.execute(tool_args)
                _post_search_results(result, user.id)
            except Exception as e:
                _post_ai_message(f"Search failed: {e}", user.id)
        return

    pending = AIPendingAction.create(
        channel_id=None,
        trigger_chat_id=None,
        created_by_id=user.id,
        tool_name=tool_name,
        args_json=tool_args,
        status=ActionStatus.PROPOSED,
    )

    _post_proposal_message(pending, user.id)


def _broadcast_clear_messages(target_user_id: int) -> None:
    """Broadcast event to clear the sparQy messages pane for a specific user."""
    room = f"user_{target_user_id}"
    current_app.socketio.emit(
        "clear_messages",
        {"sparqy": True, "user_id": target_user_id},
        room=room,
        namespace="/sync",
    )


def _post_search_results(result: dict[str, Any], target_user_id: int) -> None:
    """Post search results to the user."""
    count = result.get("count", 0)

    if "contacts" in result:
        contacts = result.get("contacts", [])
        if count == 0:
            _post_ai_message("No contacts found matching your search.", target_user_id)
            return

        lines = [f"Found {count} contact(s):"]
        for c in contacts:
            line = f"• **{c['name']}**"
            details = []
            if c.get("company"):
                details.append(c["company"])
            if c.get("phone"):
                details.append(c["phone"])
            if c.get("email"):
                details.append(c["email"])
            if details:
                line += f" - {', '.join(details)}"
            lines.append(line)

        _post_ai_message("\n".join(lines), target_user_id)
        return

    _post_ai_message(result.get("message", "Search completed."), target_user_id)


def _post_ai_message(content: str, target_user_id: int, clear_storage: bool = False) -> None:
    """Post a message from sparQy to the user (no DB save)."""
    import uuid
    from datetime import datetime

    from modules.base.updates.controllers.socketio_events import broadcast_agent_message

    ai_content = f"AI_MESSAGE::{content}"
    temp_id = f"ai-{uuid.uuid4().hex[:8]}"

    message_data = {
        "temp_id": temp_id,
        "content": ai_content,
        "author_id": 1,
        "author_name": "sparQy",
        "avatar_color": "#6E70C0",
        "is_ai": True,
        "timestamp": datetime.now().strftime("%I:%M %p"),
        "clear_storage": clear_storage,
    }

    broadcast_agent_message(
        current_app.socketio,
        message_data,
        target_user_id,
    )


def _post_ai_warning(content: str, target_user_id: int) -> None:
    """Post a warning message from sparQy (styled as warning card)."""
    import uuid
    from datetime import datetime

    from modules.base.updates.controllers.socketio_events import broadcast_agent_message

    ai_content = f"AI_WARNING::{content}"
    temp_id = f"warning-{uuid.uuid4().hex[:8]}"

    message_data = {
        "temp_id": temp_id,
        "content": ai_content,
        "author_id": 1,
        "author_name": "sparQy",
        "avatar_color": "#6E70C0",
        "is_ai": True,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }

    broadcast_agent_message(
        current_app.socketio,
        message_data,
        target_user_id,
    )


def _post_proposal_message(pending: AIPendingAction, target_user_id: int) -> None:
    """Post a proposal message with confirm/edit/cancel buttons."""
    import uuid
    from datetime import datetime

    from modules.base.updates.controllers.socketio_events import broadcast_agent_message

    content = f"AI_PROPOSAL::{pending.id}"
    temp_id = f"proposal-{uuid.uuid4().hex[:8]}"

    message_data = {
        "temp_id": temp_id,
        "content": content,
        "author_id": 1,
        "author_name": "sparQy",
        "avatar_color": "#6E70C0",
        "is_ai": True,
        "timestamp": datetime.now().strftime("%I:%M %p"),
    }

    broadcast_agent_message(
        current_app.socketio,
        message_data,
        target_user_id,
    )


def _resolve_context(content: str) -> dict[str, Any]:
    """
    Pre-scan content for entity references.

    Looks for patterns like "knows Larry Patterson" or mentions of people
    and tries to find matching contacts.
    """
    context: dict[str, Any] = {"contacts": []}

    # Look for "knows X", "connected to X", "met X" patterns
    patterns = [
        r"knows\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"connected to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"met\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"@([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    ]

    name_refs = set()
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        name_refs.update(matches)

    if name_refs:
        from modules.base.core.models.contact import Contact

        for name in name_refs:
            matches = Contact.search(name.strip())
            if matches:
                context["contacts"].append({
                    "reference": name,
                    "matches": [
                        {
                            "id": c.id,
                            "name": c.display_name,
                            "company": c.company_name,
                        }
                        for c in matches[:5]
                    ],
                })

    return context
