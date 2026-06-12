# -----------------------------------------------------------------------------
# sparQ - Sync Module: Week in Review Controller
#
# Routes for generating and sending weekly review summaries.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import date, timedelta

from flask import abort, redirect, request, url_for
from flask_login import current_user, login_required

from system.device.template import render_device_template

from . import blueprint
from ..models.week_review import UpdateWeekReview


def _current_week_monday():
    """Return the Monday of the current week."""
    today = date.today()
    return today - timedelta(days=today.weekday())


@blueprint.route("/week-review/")
@login_required
def week_review_index():
    """List week reviews. Members see sent only; admins see drafts + generate."""
    reviews = UpdateWeekReview.get_all()

    current_draft = None
    if current_user.is_admin:
        monday = _current_week_monday()
        for r in reviews:
            if r.week_start == monday and r.status == "draft":
                current_draft = r
                break

    # Members only see sent reviews
    if not current_user.is_admin:
        reviews = [r for r in reviews if r.status == "sent"]

    return render_device_template(
        "updates/desktop/week_review/index.html",
        reviews=reviews,
        current_draft=current_draft,
        active_page="week_review",
        module_home="sync_bp.index",
    )


@blueprint.route("/week-review/<int:review_id>/")
@login_required
def week_review_detail(review_id: int):
    """Detail view. Members see sent reviews read-only; admins can edit drafts."""
    review = UpdateWeekReview.get_by_id(review_id)
    if not review:
        abort(404)

    # Members can only view sent reviews
    if not current_user.is_admin and review.status != "sent":
        abort(403)

    return render_device_template(
        "updates/desktop/week_review/detail.html",
        review=review,
        active_page="week_review",
        module_home="sync_bp.index",
    )


@blueprint.route("/week-review/<int:review_id>/send", methods=["POST"])
@login_required
def week_review_send(review_id: int):
    """Save edits, create pinned sync post, mark sent (admin only)."""
    if not current_user.is_admin:
        abort(403)

    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    content = request.form.get("content", "").strip()
    if not content:
        abort(400)

    review = UpdateWeekReview.send(review_id, sent_by_id=member.id, content=content)
    if not review:
        abort(404)

    return redirect(url_for("sync_bp.week_review_index"))


@blueprint.route("/week-review/generate", methods=["POST"])
@login_required
def week_review_generate():
    """Trigger generation for current week (admin only)."""
    if not current_user.is_admin:
        abort(403)

    from system.background import submit_task
    from system.sync.week_review_job import generate_week_review

    submit_task(generate_week_review)

    return redirect(url_for("sync_bp.week_review_index"))
