# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Projects module class."""

from system.module.hooks import hookimpl

from .controllers import blueprint


class ProjectsModule:
    """Projects module — lightweight containers for grouping work."""

    def __init__(self) -> None:
        self.blueprint = blueprint

    def get_routes(self):
        """Return routes for this module."""
        return [(self.blueprint, "/projects")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables for this module."""
        from .models.project import Project  # noqa: F401
        from .models.follower import project_follower  # noqa: F401
        from .models.co_owner import project_co_owner  # noqa: F401
