# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Projects module — lightweight containers for grouping action items and sync posts.

Routes:
    /projects — Projects hub
"""

from .module import ProjectsModule

# Import all models to ensure they're registered with SQLAlchemy
from .models.project import Project

module_instance = ProjectsModule()

__all__ = [
    "module_instance",
    "Project",
]
