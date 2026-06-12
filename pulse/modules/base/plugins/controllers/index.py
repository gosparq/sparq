# -----------------------------------------------------------------------------
# sparQ - Plugins Index Controller
#
# Description:
#     Main controller for the Plugins module. Provides the plugins listing
#     page and individual plugin info pages.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from flask import Blueprint, render_template
from flask_login import login_required

plugins_blueprint = Blueprint(
    "plugins_bp",
    __name__,
    template_folder="../views/templates",
)


@plugins_blueprint.route("/")
@login_required
def index():
    """List all available plugins."""
    from modules.base.plugins import module_instance

    plugins = module_instance.get_discovered_plugins()
    return render_template("plugins/desktop/index.html", plugins=plugins)


@plugins_blueprint.route("/<slug>/info")
@login_required
def plugin_info(slug: str):
    """Show info page for a specific plugin."""
    from modules.base.plugins import module_instance

    plugins = module_instance.get_discovered_plugins()
    plugin = next((p for p in plugins if p["slug"] == slug), None)

    if not plugin:
        return render_template("plugins/desktop/errors/404.html"), 404

    return render_template("plugins/desktop/info.html", plugin=plugin)
