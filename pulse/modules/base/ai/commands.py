# -----------------------------------------------------------------------------
# sparQ - AI Agent Commands
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Extensible command system for sparQy.

Commands start with "/" and are handled before being sent to the LLM.
To add a new command, register it with the @command decorator.
"""

from dataclasses import dataclass
from typing import Callable



@dataclass
class CommandResult:
    """Result of a command execution."""

    success: bool
    message: str | None = None
    post_marker: str | None = None  # Special marker to post (e.g., AI_CONTEXT_CLEAR::)
    clear_messages: bool = False  # Clear the message pane visually


# Command registry
_commands: dict[str, tuple[Callable, str]] = {}


def command(name: str, description: str):
    """Decorator to register a command."""

    def decorator(func: Callable[[str, any, any], CommandResult]):
        _commands[name.lower()] = (func, description)
        return func

    return decorator


def get_command(name: str) -> tuple[Callable, str] | None:
    """Get a command by name."""
    return _commands.get(name.lower())


def get_all_commands() -> dict[str, str]:
    """Get all commands with their descriptions."""
    return {name: desc for name, (_, desc) in _commands.items()}


def parse_command(content: str) -> tuple[str, str] | None:
    """
    Parse a command from message content.

    Returns (command_name, args) if content is a command, None otherwise.
    """
    content = content.strip()
    if not content.startswith("/"):
        return None

    parts = content[1:].split(maxsplit=1)
    if not parts:
        return None

    command_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    return (command_name, args)


# -----------------------------------------------------------------------------
# Built-in Commands
# -----------------------------------------------------------------------------


@command("clear", "Clear conversation context and messages")
def cmd_clear(args: str, channel, user) -> CommandResult:
    """Clear the conversation context and message pane."""
    return CommandResult(
        success=True,
        message="Ready for a fresh conversation!",
        post_marker="AI_CONTEXT_CLEAR::",
        clear_messages=True,
    )


@command("help", "Show available commands")
def cmd_help(args: str, channel, user) -> CommandResult:
    """Show help for available commands."""
    commands = get_all_commands()

    help_lines = ["Available commands:"]
    for name, description in sorted(commands.items()):
        help_lines.append(f"  /{name} - {description}")

    return CommandResult(
        success=True,
        message="\n".join(help_lines),
    )
