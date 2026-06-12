# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Tasks module class."""

from system.module.hooks import hookimpl

from .controllers import blueprint


class TasksModule:
    """Tasks module — urgent interpersonal accountability units."""

    def __init__(self) -> None:
        self.blueprint = blueprint

    def get_routes(self):
        """Return routes for this module."""
        return [(self.blueprint, "/tasks")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables for this module."""
        from .models.task import Task  # noqa: F401
        from .models.task_log import TaskLog  # noqa: F401
