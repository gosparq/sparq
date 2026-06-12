# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     AI module class. Provides the sparQy agent system for natural
#     language actions via the DM interface.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl

from .controllers import blueprint


class AIModule:
    """AI module - Agent system for natural language actions."""

    def __init__(self) -> None:
        self.blueprint = blueprint

    def get_routes(self):
        """Return routes for this module."""
        return [(self.blueprint, "/ai")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables for this module."""
        from .models import AIPendingAction  # noqa: F401
