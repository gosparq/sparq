# -----------------------------------------------------------------------------
# sparQ - 1:1 Tracker Controller
#
# Routes for managing 1:1 pairs, sessions, and agenda items.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import date, datetime

from flask import flash, redirect, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from system.db.database import db
from system.device.template import render_device_template
from system.i18n.translation import translate as _

from ..decorators import admin_required
from . import blueprint


@blueprint.route("/one-on-ones/")
@login_required
def one_on_one_index():
    """List 1:1 pairs for the current user (or all pairs for admins)."""
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.people.models.one_on_one import OneOnOnePair

    member = WorkspaceUser.get_by_user_id(current_user.id)

    _pair_opts = (
        joinedload(OneOnOnePair.lead).joinedload(WorkspaceUser.user),
        joinedload(OneOnOnePair.report).joinedload(WorkspaceUser.user),
    )
    if current_user.is_admin:
        pairs = (
            OneOnOnePair.scoped()
            .options(*_pair_opts)
            .filter(OneOnOnePair.active.is_(True))
            .order_by(OneOnOnePair.next_meeting_date.asc().nullslast(), OneOnOnePair.created_at.desc())
            .all()
        )
    else:
        if member:
            from system.db.database import db as _db
            pairs = (
                OneOnOnePair.scoped()
                .options(*_pair_opts)
                .filter(
                    OneOnOnePair.active.is_(True),
                    _db.or_(OneOnOnePair.lead_id == member.id, OneOnOnePair.report_id == member.id),
                )
                .order_by(OneOnOnePair.next_meeting_date.asc().nullslast(), OneOnOnePair.created_at.desc())
                .all()
            )
        else:
            pairs = []

    # Get all active members for the create form
    active_members = (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )

    return render_device_template(
        "people/desktop/one_on_one/index.html",
        pairs=pairs,
        member=member,
        active_members=active_members,
        active_page="one_on_ones",
    )


@blueprint.route("/one-on-ones/<int:pair_id>/")
@login_required
def one_on_one_detail(pair_id):
    """Detail view for a 1:1 pair — sessions, agenda items."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.people.models.one_on_one import (
        OneOnOneAgendaItem,
        OneOnOnePair,
    )

    pair = (
        OneOnOnePair.scoped()
        .options(
            joinedload(OneOnOnePair.lead).joinedload(WorkspaceUser.user),
            joinedload(OneOnOnePair.report).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=pair_id).first_or_404()
    )
    member = WorkspaceUser.get_by_user_id(current_user.id)

    # Only lead, report, or admin can view
    if not current_user.is_admin and member:
        if pair.lead_id != member.id and pair.report_id != member.id:
            flash(_("You do not have access to this 1:1."), "error")
            return redirect(url_for("people_bp.one_on_one_index"))

    sessions = pair.sessions.all()

    # Get open agenda items (not linked to a session yet, and not completed)
    open_items = (
        OneOnOneAgendaItem.scoped()
        .options(joinedload(OneOnOneAgendaItem.added_by).joinedload(WorkspaceUser.user))
        .filter_by(pair_id=pair_id, session_id=None, completed=False)
        .order_by(OneOnOneAgendaItem.created_at.desc())
        .all()
    )

    # Completed items
    completed_items = (
        OneOnOneAgendaItem.scoped()
        .options(joinedload(OneOnOneAgendaItem.added_by).joinedload(WorkspaceUser.user))
        .filter_by(pair_id=pair_id, completed=True)
        .order_by(OneOnOneAgendaItem.created_at.desc())
        .limit(20)
        .all()
    )

    return render_device_template(
        "people/desktop/one_on_one/detail.html",
        pair=pair,
        member=member,
        sessions=sessions,
        open_items=open_items,
        completed_items=completed_items,
        active_page="one_on_ones",
    )


@blueprint.route("/one-on-ones/create", methods=["POST"])
@login_required
@admin_required
def one_on_one_create():
    """Create a new 1:1 pair (admin only)."""
    from modules.base.people.models.one_on_one import OneOnOnePair

    lead_id = request.form.get("lead_id", type=int)
    report_id = request.form.get("report_id", type=int)
    cadence = request.form.get("cadence", "biweekly")

    if not lead_id or not report_id:
        flash(_("Both lead and report are required."), "error")
        return redirect(url_for("people_bp.one_on_one_index"))

    if lead_id == report_id:
        flash(_("Lead and report must be different people."), "error")
        return redirect(url_for("people_bp.one_on_one_index"))

    # Check for existing pair
    existing = (
        OneOnOnePair.scoped()
        .filter_by(lead_id=lead_id, report_id=report_id, active=True)
        .first()
    )
    if existing:
        flash(_("This 1:1 pair already exists."), "error")
        return redirect(url_for("people_bp.one_on_one_index"))

    try:
        pair = OneOnOnePair.create(lead_id=lead_id, report_id=report_id, cadence=cadence)
        flash(_("1:1 pair created."), "success")
        return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair.id))
    except Exception as e:
        db.session.rollback()
        flash(_("Error creating 1:1 pair: %(error)s") % {"error": str(e)}, "error")
        return redirect(url_for("people_bp.one_on_one_index"))


@blueprint.route("/one-on-ones/<int:pair_id>/agenda", methods=["POST"])
@login_required
def one_on_one_add_agenda(pair_id):
    """Add an agenda item to a 1:1 pair."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.people.models.one_on_one import OneOnOneAgendaItem, OneOnOnePair

    pair = OneOnOnePair.scoped().get_or_404(pair_id)
    member = WorkspaceUser.get_by_user_id(current_user.id)

    # Only lead, report, or admin can add items
    if not current_user.is_admin and member:
        if pair.lead_id != member.id and pair.report_id != member.id:
            flash(_("You do not have access to this 1:1."), "error")
            return redirect(url_for("people_bp.one_on_one_index"))

    content = request.form.get("content", "").strip()
    is_task = request.form.get("is_task") == "on"

    if not content:
        flash(_("Content is required."), "error")
        return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair_id))

    try:
        OneOnOneAgendaItem.create(
            pair_id=pair_id,
            added_by_id=member.id if member else pair.lead_id,
            content=content,
            is_task=is_task,
        )
        flash(_("Agenda item added."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error adding item: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair_id))


@blueprint.route("/one-on-ones/<int:pair_id>/session", methods=["POST"])
@login_required
def one_on_one_log_session(pair_id):
    """Log a 1:1 session."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.people.models.one_on_one import OneOnOnePair, OneOnOneSession

    pair = OneOnOnePair.scoped().get_or_404(pair_id)
    member = WorkspaceUser.get_by_user_id(current_user.id)

    # Only lead, report, or admin
    if not current_user.is_admin and member:
        if pair.lead_id != member.id and pair.report_id != member.id:
            flash(_("You do not have access to this 1:1."), "error")
            return redirect(url_for("people_bp.one_on_one_index"))

    meeting_date_str = request.form.get("meeting_date", "")
    notes = request.form.get("notes", "").strip()

    if meeting_date_str:
        meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    else:
        meeting_date = date.today()

    try:
        OneOnOneSession.create(
            pair_id=pair_id,
            meeting_date=meeting_date,
            notes=notes,
        )
        flash(_("Session logged."), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("Error logging session: %(error)s") % {"error": str(e)}, "error")

    return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair_id))


@blueprint.route("/one-on-ones/<int:pair_id>/agenda/<int:item_id>/complete", methods=["POST"])
@login_required
def one_on_one_complete_item(pair_id, item_id):
    """Toggle completion of an agenda item."""
    from modules.base.people.models.one_on_one import OneOnOneAgendaItem

    item = OneOnOneAgendaItem.scoped().get_or_404(item_id)

    if item.pair_id != pair_id:
        flash(_("Invalid item."), "error")
        return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair_id))

    if item.completed:
        item.mark_incomplete()
    else:
        item.mark_complete()

    return redirect(url_for("people_bp.one_on_one_detail", pair_id=pair_id))
