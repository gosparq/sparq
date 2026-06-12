# -----------------------------------------------------------------------------
# sparQ - Resources Module - Settings Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from modules.base.core.models.auth_settings import AuthSettings
from system.i18n.translation import translate as _

from ..models.drive_connection import DriveConnection

settings_blueprint = Blueprint(
    "resources_settings_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)


def can_manage_drive() -> bool:
    """Check if current user can manage Drive connection (admin)."""
    if not current_user.is_authenticated:
        return False
    return current_user.is_admin


@settings_blueprint.route("/")
@login_required
def index():
    """Resources settings page."""
    if not current_user.is_admin:
        flash(_("Access denied."), "error")
        return redirect(url_for("docs_blueprint.index"))

    # Get cloud storage settings
    auth_settings = AuthSettings.get_instance()
    google_drive_enabled = auth_settings.google_drive_enabled
    drive_connection = DriveConnection.get_google()

    return render_template(
        "resources/desktop/settings.html",
        active_page="settings",
        module_home="dashboard_bp.index",
        google_drive_enabled=google_drive_enabled,
        drive_connection=drive_connection,
        can_manage_drive=can_manage_drive(),
    )
