# Copyright (c) 2025-2026 remarQable LLC

import os

from flask import Blueprint

# Static assets live in the github integration module; served under integrations_bp
# so existing templates use url_for('integrations_bp.static', ...) without changes.
_github_assets = os.path.join(
    os.path.dirname(__file__),
    "../github/views/assets",
)

blueprint = Blueprint(
    "integrations_bp",
    __name__,
    template_folder="../views/templates",
    static_folder=_github_assets,
    static_url_path="/assets",
)

from . import routes  # noqa: E402, F401
