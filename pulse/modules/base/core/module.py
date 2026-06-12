# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core module class that implements the plugin system hooks and handles
#     route registration for the core functionality. Provides essential
#     application features and module management.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl  # Updated import


class CoreModule:
    """Core module providing basic functionality"""

    @hookimpl
    def get_routes(self):
        """Get module routes"""
        from .controllers.routes import blueprint
        from .controllers.oauth_routes import blueprint as oauth_blueprint

        # push_routes.py shares the same blueprint as routes.py
        from .controllers import push_routes  # noqa: F401

        return [(blueprint, ""), (oauth_blueprint, "/auth/oauth")]

    @hookimpl
    def register_ai_tools(self, registry):
        """Register AI tools for contact operations."""
        from .tools import create_contact, search_contacts, update_contact

        registry.register(create_contact)
        registry.register(update_contact)
        registry.register(search_contacts)
