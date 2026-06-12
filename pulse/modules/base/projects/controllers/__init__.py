# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

from flask import Blueprint

blueprint = Blueprint(
    "projects_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)

# Import routes after blueprint creation
from . import routes  # noqa: E402, F401
