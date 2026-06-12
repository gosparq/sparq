# -----------------------------------------------------------------------------
# sparQ - Resources Module - Forms Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, render_template
from flask_login import login_required

forms_blueprint = Blueprint(
    "forms_blueprint",
    __name__,
    template_folder="../views/templates",
)


@forms_blueprint.route("/")
@login_required
def index():
    """Forms index - coming soon page."""
    return render_template(
        "resources/desktop/forms/coming-soon.html",
        active_page="resources",
        module_home="dashboard_bp.index",
    )
