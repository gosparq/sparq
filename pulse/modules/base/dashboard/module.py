# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dashboard module class that provides the main business dashboard.
#     Handles route registration for the dashboard views.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl

from .controllers import blueprint


class DashboardModule:
    def __init__(self) -> None:
        self.blueprint = blueprint

    @hookimpl
    def get_routes(self):
        """Return list of routes to register"""
        return [(self.blueprint, "/dashboard")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize dashboard database tables."""
        # Schema creation is handled centrally by app.py
        # Import models to ensure they are registered
        from .models import ActivityLog  # noqa: F401
