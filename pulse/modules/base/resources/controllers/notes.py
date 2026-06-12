# -----------------------------------------------------------------------------
# sparQ - Resources Module - Notes Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Notes controller — personal and team notes in Resources."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from system.device.template import render_device_template
from system.i18n.translation import translate as _

from ..models.note import Note

notes_blueprint = Blueprint(
    "notes_blueprint",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)


def _current_member():
    """Get current user's WorkspaceUser record in the active workspace.

    Returns None for org-only members (no g.workspace_id) instead of crashing
    on WorkspaceUser.scoped() — callers handle the None case for org scope.
    """
    from flask import g
    from modules.base.core.models.workspace_user import WorkspaceUser

    if getattr(g, "workspace_id", None) is None:
        return None
    return WorkspaceUser.scoped().filter_by(user_id=current_user.id).first()


def is_htmx_request() -> bool:
    """Check if request is from HTMX."""
    return request.headers.get("HX-Request") == "true"


# -----------------------------------------------------------------------------
# List
# -----------------------------------------------------------------------------


@notes_blueprint.route("/organization/")
@notes_blueprint.route("/organization")
@login_required
def index_organization():
    """Organization-scoped notes (Phase 6 §5)."""
    return index()


@notes_blueprint.route("/")
@login_required
def index():
    """List notes — scope-aware.

    - Workspace scope: shows the caller's personal + team notes, filtered by
      their WorkspaceUser membership.
    - Organization scope: shows all org-scoped notes (no per-member filter;
      org notes are team-visibility by nature).
    """
    from flask import g
    from sqlalchemy.orm import joinedload

    from modules.base.core.models.workspace_user import WorkspaceUser

    tab = request.args.get("tab", "all")
    scope = getattr(g, "scope", "workspace")

    if scope == "organization":
        # Org scope — Note.scoped() already filters by organization_id via the
        # scope-aware helper (Phase 6). No member filter in this view.
        notes = (
            Note.scoped()
            .options(joinedload(Note.member).joinedload(WorkspaceUser.user))
            .order_by(Note.updated_at.desc())
            .all()
        )
    else:
        member = _current_member()
        if not member:
            flash(_("No member record found"), "error")
            return redirect(url_for("dashboard_bp.index"))

        if tab == "team":
            notes = Note.get_for_member(member.id, visibility="team")
        elif tab == "personal":
            notes = Note.get_for_member(member.id, visibility="personal")
        else:
            notes = Note.get_for_member(member.id)

    pinned = [n for n in notes if n.is_pinned]
    recent = [n for n in notes if not n.is_pinned]

    return render_device_template(
        "resources/desktop/notes.html",
        active_page="resources",
        notes=notes,
        pinned=pinned,
        recent=recent,
        tab=tab,
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# Detail / Editor
# -----------------------------------------------------------------------------


@notes_blueprint.route("/<int:note_id>")
@login_required
def detail(note_id: int):
    """Show note editor."""
    member = _current_member()
    note = Note.get_by_id(note_id)
    if not note:
        flash(_("Note not found"), "error")
        return redirect(url_for("notes_blueprint.index"))

    # Personal notes: only the author can view them
    if note.visibility == "personal" and note.member_id != (member.id if member else -1):
        flash(_("Not authorised"), "error")
        return redirect(url_for("notes_blueprint.index"))

    return render_device_template(
        "resources/desktop/note_detail.html",
        active_page="resources",
        note=note,
        member=member,
        module_home="dashboard_bp.index",
    )


# -----------------------------------------------------------------------------
# Create
# -----------------------------------------------------------------------------


@notes_blueprint.route("/create", methods=["POST"])
@login_required
def create():
    """Create a new note and redirect to its editor."""
    member = _current_member()
    if not member:
        flash(_("No member record found"), "error")
        return redirect(url_for("notes_blueprint.index"))

    visibility = request.form.get("visibility", "personal")
    note = Note.create(member_id=member.id, content="", visibility=visibility)
    return redirect(url_for("notes_blueprint.detail", note_id=note.id))


# -----------------------------------------------------------------------------
# Auto-save (HTMX)
# -----------------------------------------------------------------------------


@notes_blueprint.route("/<int:note_id>/save", methods=["POST"])
@login_required
def save(note_id: int):
    """Auto-save note content via HTMX."""
    member = _current_member()
    note = Note.get_by_id(note_id)
    if not note:
        return ("Note not found", 404)

    # Only the author may save
    if member and note.member_id != member.id:
        return ("Not authorised", 403)

    content = request.form.get("content", "")
    visibility = request.form.get("visibility", note.visibility)

    note.update_content(content)
    if visibility != note.visibility:
        note.visibility = visibility
        from system.db.database import db
        db.session.commit()

    # Return a small saved-indicator partial for HTMX swap
    if is_htmx_request():
        return render_template("resources/desktop/partials/_note_saved.html", note=note)

    flash(_("Note saved"), "success")
    return redirect(url_for("notes_blueprint.detail", note_id=note_id))


# -----------------------------------------------------------------------------
# Delete
# -----------------------------------------------------------------------------


@notes_blueprint.route("/<int:note_id>/delete", methods=["POST"])
@login_required
def delete(note_id: int):
    """Delete a note."""
    member = _current_member()
    note = Note.get_by_id(note_id)
    if not note:
        flash(_("Note not found"), "error")
        return redirect(url_for("notes_blueprint.index"))

    # Only the author may delete (admin can delete team notes)
    if not current_user.is_admin and (not member or note.member_id != member.id):
        flash(_("Not authorised"), "error")
        return redirect(url_for("notes_blueprint.index"))

    from system.db.database import db
    db.session.delete(note)
    db.session.commit()

    flash(_("Note deleted"), "success")
    return redirect(url_for("notes_blueprint.index"))


# -----------------------------------------------------------------------------
# Pin toggle
# -----------------------------------------------------------------------------


@notes_blueprint.route("/<int:note_id>/pin", methods=["POST"])
@login_required
def pin(note_id: int):
    """Toggle note pin."""
    member = _current_member()
    note = Note.get_by_id(note_id)
    if not note:
        flash(_("Note not found"), "error")
        return redirect(url_for("notes_blueprint.index"))

    if not current_user.is_admin and (not member or note.member_id != member.id):
        flash(_("Not authorised"), "error")
        return redirect(url_for("notes_blueprint.detail", note_id=note_id))

    note.is_pinned = not note.is_pinned
    from system.db.database import db
    db.session.commit()

    if is_htmx_request():
        return render_template("resources/desktop/partials/_note_pin.html", note=note)

    return redirect(url_for("notes_blueprint.detail", note_id=note_id))
