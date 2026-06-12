# -----------------------------------------------------------------------------
# sparQ - MSA Module
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint

from system.module.hooks import hookimpl


class MSAModule:
    """Multi-workspace System Admin module."""

    def get_routes(self) -> list[tuple[Blueprint, str]]:
        """Return the blueprint and URL prefix for this module."""
        from .controllers.routes import blueprint

        return [(blueprint, "/msa")]

    @hookimpl
    def init_database(self) -> None:
        """Ensure instance_settings table exists."""
        from .models.instance_settings import InstanceSettings  # noqa: F401
