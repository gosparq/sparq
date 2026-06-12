# -----------------------------------------------------------------------------
# sparQ - Sync Module Routes
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import redirect, url_for
from flask_login import current_user, login_required

from system.device.template import render_device_template

from . import blueprint


@blueprint.route("/")
@login_required
def index():
    """Sync landing — redirect to /updates/."""
    return redirect(url_for("updates_bp.index"), code=302)


@blueprint.route("/settings")
@login_required
def settings():
    """Sync settings page."""
    if not current_user.is_admin:
        return redirect(url_for("sync_bp.index"))

    from ..models import UpdateChannel
    from ..models.dm import DMThread
    from modules.base.core.models.workspace_user import WorkspaceUser

    channels = UpdateChannel.get_all()

    # Build DM thread options: all active users (for creating DM webhooks)
    all_users = WorkspaceUser.get_workspace_users()
    dm_users = [u for u in all_users if "admin" not in u.email.lower()]

    # Get existing DM threads for dropdown
    threads = DMThread.get_threads_for_user(current_user.id)

    # Areas for management
    from ..models.area import UpdateArea
    areas = UpdateArea.get_all()

    # Label config
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    ts_settings = WorkspaceSettings.get_instance()
    area_label = ts_settings.get_area_label()
    weekly_plan_label = ts_settings.get_weekly_plan_label()

    return render_device_template(
        "updates/desktop/settings.html",
        active_page="settings",
        module_home="sync_bp.index",
        channels=channels,
        dm_users=dm_users,
        dm_threads=threads,
        areas=areas,
        area_label=area_label,
        weekly_plan_label=weekly_plan_label,
    )
