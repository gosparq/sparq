# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module class that implements core team and employee management.
#     Handles route registration and database initialization for the
#     employee management system.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl

from .controllers import blueprint
from .hooks import TeamHookSpecs


class PeopleModule:
    def __init__(self) -> None:
        self.blueprint = blueprint

    @hookimpl
    def get_routes(self):
        """Return list of routes to register"""
        return [(self.blueprint, "/people")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables and default data."""
        # Schema creation is handled centrally by app.py
        pass

    def register_specs(self, plugin_manager):
        """Register hook specifications and implementations"""
        plugin_manager.add_hookspecs(TeamHookSpecs)
        plugin_manager.register(self)

    def replace_url(self, match):
        url = match.group(0)
        display_url = url[:50] + "..." if len(url) > 50 else url
        full_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
        return f'<a href="{full_url}" target="_blank" rel="noopener noreferrer" class="chat-link">{display_url}</a>'
