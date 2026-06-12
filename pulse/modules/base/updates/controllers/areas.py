# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Areas controller — admin CRUD for domain categorization tags."""

from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required
from system.i18n.translation import translate as _

from . import blueprint


@blueprint.route("/areas/create", methods=["POST"])
@login_required
def area_create():
    """Create a new area (admin only)."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("sync_bp.settings"))

    from modules.base.updates.models.area import UpdateArea

    name = request.form.get("name", "").strip()
    color = request.form.get("color", "#6b7280").strip()
    emoji = request.form.get("emoji", "").strip()

    if not name:
        flash(_("Area name is required."), "error")
        return redirect(url_for("sync_bp.settings"))

    try:
        UpdateArea.create(name=name, color=color, emoji=emoji or None)
        flash(_("Area '%s' created.") % name, "success")
    except ValueError as e:
        flash(str(e), "error")
    except Exception:
        flash(_("Could not create area. Name may already exist."), "error")

    return redirect(url_for("sync_bp.settings"))


@blueprint.route("/areas/<int:area_id>/update", methods=["POST"])
@login_required
def area_update(area_id):
    """Update an existing area (admin only)."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("sync_bp.settings"))

    from modules.base.updates.models.area import UpdateArea

    area = UpdateArea.get_by_id(area_id)
    if not area:
        flash(_("Area not found."), "error")
        return redirect(url_for("sync_bp.settings"))

    name = request.form.get("name", "").strip()
    color = request.form.get("color", "").strip()
    emoji = request.form.get("emoji", "")

    if not name:
        flash(_("Area name is required."), "error")
        return redirect(url_for("sync_bp.settings"))

    try:
        area.update(name=name, color=color or None, emoji=emoji)
        flash(_("Area '%s' updated.") % name, "success")
    except Exception:
        flash(_("Could not update area."), "error")

    return redirect(url_for("sync_bp.settings"))


@blueprint.route("/areas/<int:area_id>/delete", methods=["POST"])
@login_required
def area_delete(area_id):
    """Soft-delete an area (admin only)."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("sync_bp.settings"))

    from modules.base.updates.models.area import UpdateArea

    area = UpdateArea.get_by_id(area_id)
    if not area:
        flash(_("Area not found."), "error")
        return redirect(url_for("sync_bp.settings"))

    area.delete()
    flash(_("Area '%s' removed.") % area.name, "success")
    return redirect(url_for("sync_bp.settings"))


@blueprint.route("/areas/reorder", methods=["POST"])
@login_required
def area_reorder():
    """Reorder areas by a list of IDs (admin only)."""
    if not current_user.is_admin:
        return {"error": "Permission denied"}, 403

    from modules.base.updates.models.area import UpdateArea

    area_ids = request.json.get("area_ids", [])
    if not area_ids:
        return {"error": "No area IDs provided"}, 400

    try:
        UpdateArea.reorder([int(aid) for aid in area_ids])
        return {"ok": True}
    except Exception:
        return {"error": "Could not reorder areas"}, 500


@blueprint.route("/labels/update", methods=["POST"])
@login_required
def labels_update():
    """Update display labels for Areas and Weekly Plans (admin only)."""
    if not current_user.is_admin:
        flash(_("Permission denied."), "error")
        return redirect(url_for("sync_bp.settings"))

    from modules.base.core.models.workspace_settings import WorkspaceSettings

    settings = WorkspaceSettings.get_instance()
    area_label = request.form.get("area_label", "Area").strip()
    weekly_plan_label = request.form.get("weekly_plan_label", "Weekly Plan").strip()

    settings.update_sync_labels(area_label=area_label, weekly_plan_label=weekly_plan_label)

    flash(_("Labels updated."), "success")
    return redirect(url_for("sync_bp.settings"))
