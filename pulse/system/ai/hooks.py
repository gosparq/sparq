# -----------------------------------------------------------------------------
# sparQ - AI Hook Specifications
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""
Hook specifications for AI tool registration.

Modules implement these hooks to register their tools with the AI system.
"""

from system.module.hooks import hookspec

from .registry import ToolRegistry


class AIHookSpecs:
    """Hook specifications for AI system."""

    @hookspec
    def register_ai_tools(self, registry: ToolRegistry) -> None:
        """
        Register AI tools with the registry.

        Modules implement this hook to register their tools. Example:

            @hookimpl
            def register_ai_tools(self, registry):
                from .tools.contacts import create_contact, update_contact
                registry.register(create_contact)
                registry.register(update_contact)
        """
        pass
