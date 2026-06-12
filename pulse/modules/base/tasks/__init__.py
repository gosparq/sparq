# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Tasks module — urgent interpersonal accountability units.

Provides a 3-tier RAG urgency system (Red/Now, Amber/Later, Green/Whenever)
with automated nudge cadences, blocker integration, and system-generated triggers.

Routes:
    /tasks — Tasks hub
"""

from .module import TasksModule

# Import all models to ensure they're registered with SQLAlchemy
from .models.task import Task
from .models.task_log import TaskLog
from .models.canned_task import CannedTask

module_instance = TasksModule()

__all__ = [
    "module_instance",
    "Task",
    "TaskLog",
    "CannedTask",
]
