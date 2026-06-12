# -----------------------------------------------------------------------------
# sparQ - Resources Module - Working Agreement Controller
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Routes for viewing and managing the team working agreement."""

import markdown as md

from flask import Blueprint, abort, flash, redirect, request, url_for
from flask_login import current_user, login_required

from system.device.template import render_device_template
from system.i18n.translation import translate as _

from ..models.working_agreement import WorkingAgreement, WorkingAgreementAck

working_agreement_bp = Blueprint(
    "working_agreement_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@working_agreement_bp.route("/")
@login_required
def index():
    """Read view — all members can see the working agreement."""
    agreement = WorkingAgreement.get_current()

    # If no agreement exists yet, show empty state
    if not agreement or agreement.version == 0:
        return render_device_template(
            "resources/desktop/working_agreement/index.html",
            agreement=None,
            rendered_content=None,
            ack_status=None,
            user_acknowledged=False,
            active_page="resources",
            module_home="working_agreement_bp.index",
        )

    # Render markdown to HTML
    rendered_content = md.markdown(
        agreement.content,
        extensions=["tables", "fenced_code", "nl2br"],
    )

    # Get ack status
    ack_status = WorkingAgreementAck.get_ack_status(agreement.id, agreement.version)

    # Check if current user has acknowledged
    member = current_user.workspace_membership
    user_acknowledged = False
    if member:
        user_acknowledged = WorkingAgreementAck.is_acknowledged(
            agreement.id, member.id, agreement.version
        )

    return render_device_template(
        "resources/desktop/working_agreement/index.html",
        agreement=agreement,
        rendered_content=rendered_content,
        ack_status=ack_status,
        user_acknowledged=user_acknowledged,
        active_page="resources",
        module_home="working_agreement_bp.index",
    )


@working_agreement_bp.route("/edit")
@login_required
def edit():
    """Edit form — admin only."""
    if not current_user.is_admin:
        abort(403)

    agreement = WorkingAgreement.get_or_create()

    return render_device_template(
        "resources/desktop/working_agreement/edit.html",
        agreement=agreement,
        active_page="resources",
        module_home="working_agreement_bp.index",
    )


@working_agreement_bp.route("/save", methods=["POST"])
@login_required
def save():
    """Save content, bump version, clear acks, notify all active members."""
    if not current_user.is_admin:
        abort(403)

    content = request.form.get("content", "").strip()

    if not content:
        flash(_("Working agreement content cannot be empty."), "error")
        return redirect(url_for("working_agreement_bp.edit"))

    member = current_user.workspace_membership
    updated_by_id = member.id if member else None

    WorkingAgreement.save(content=content, updated_by_id=updated_by_id)

    flash(_("Working agreement updated. All members must re-acknowledge."), "success")
    return redirect(url_for("working_agreement_bp.index"))


@working_agreement_bp.route("/ack", methods=["POST"])
@login_required
def ack():
    """Current user acknowledges the current version."""
    agreement = WorkingAgreement.get_current()
    if not agreement or agreement.version == 0:
        flash(_("No working agreement to acknowledge."), "error")
        return redirect(url_for("working_agreement_bp.index"))

    member = current_user.workspace_membership
    if not member:
        flash(_("Could not find your membership."), "error")
        return redirect(url_for("working_agreement_bp.index"))

    WorkingAgreementAck.acknowledge(agreement.id, member.id, agreement.version)
    flash(_("Thank you for acknowledging the working agreement."), "success")
    return redirect(url_for("working_agreement_bp.index"))
