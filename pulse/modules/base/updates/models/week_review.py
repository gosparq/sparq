# -----------------------------------------------------------------------------
# sparQ - UpdateWeekReview Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdateWeekReview model — AI-generated weekly summary.

Stores one review per week (Mon-Fri). Reviews start as drafts, can be
edited by admins, and then sent to the team as a pinned UpdatePost.

Classes:
    UpdateWeekReview: Weekly review model.
"""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateWeekReview(db.Model, WorkspaceMixin):
    """AI-generated weekly summary for the team.

    Attributes:
        week_start: Monday of the week.
        week_end: Friday of the week.
        content: Markdown summary (AI-generated or manually edited).
        status: 'draft' or 'sent'.
        sent_at: When the review was sent to the team.
        sent_by_id: FK to workspace_user who sent it.
        post_id: FK to the UpdatePost created on send.
    """

    __tablename__ = "update_week_review"

    id = db.Column(db.Integer, primary_key=True)

    week_start = db.Column(db.Date, nullable=False)
    week_end = db.Column(db.Date, nullable=False)

    content = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft")

    sent_at = db.Column(db.DateTime, nullable=True)
    sent_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("update_post.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    sent_by = db.relationship("WorkspaceUser", foreign_keys=[sent_by_id], lazy=LAZY)
    post = db.relationship("UpdatePost", foreign_keys=[post_id], lazy=LAZY)

    @classmethod
    def get_or_create_for_week(cls, week_start):
        """Get existing or create new draft review for the given week.

        Args:
            week_start: date object for Monday of the target week.

        Returns:
            UpdateWeekReview instance.
        """
        from datetime import timedelta

        week_end = week_start + timedelta(days=4)

        review = cls.scoped().filter_by(week_start=week_start).first()
        if review:
            return review

        review = cls(
            week_start=week_start,
            week_end=week_end,
            status="draft",
        )
        db.session.add(review)
        db.session.commit()
        return review

    @classmethod
    def get_all(cls):
        """List all reviews for the current workspace, newest first.

        Returns:
            List of UpdateWeekReview instances.
        """
        return (
            cls.scoped()
            .order_by(cls.week_start.desc())
            .all()
        )

    @classmethod
    def get_for_week_start(cls, week_start):
        """Get a review by its week start date.

        Args:
            week_start: date object for Monday of the week.

        Returns:
            UpdateWeekReview instance or None.
        """
        return cls.scoped().filter_by(week_start=week_start).first()

    @classmethod
    def get_by_id(cls, review_id):
        """Get a single review by ID, scoped to current workspace.

        Args:
            review_id: Integer primary key.

        Returns:
            UpdateWeekReview instance or None.
        """
        return cls.scoped().filter_by(id=review_id).first()

    @classmethod
    def send(cls, review_id, sent_by_id, content):
        """Save edits, create a pinned UpdatePost, and mark the review as sent.

        Args:
            review_id: ID of the review to send.
            sent_by_id: WorkspaceUser.id of the admin sending it.
            content: Final markdown content (may have been edited).

        Returns:
            The updated UpdateWeekReview instance, or None if not found.
        """
        from modules.base.dashboard.models.activity_log import ActivityLog
        from modules.base.updates.models.post import UpdatePost
        from modules.base.updates.models.template import UpdateTemplate

        review = cls.scoped().filter_by(id=review_id).first()
        if not review:
            return None

        review.content = content
        review.status = "sent"
        review.sent_at = datetime.utcnow()
        review.sent_by_id = sent_by_id

        # Create an UpdatePost for the review — use the first "update" template
        # as a generic container for the week-in-review post.
        template = UpdateTemplate.get_for_workspace(post_type="update")
        if template:
            template = template[0]
            week_label = (
                f"{review.week_start.strftime('%b %d')} - "
                f"{review.week_end.strftime('%b %d, %Y')}"
            )
            post = UpdatePost.create(
                template=template,
                member_id=sent_by_id,
                payload={
                    "title": f"Week in Review: {week_label}",
                    "body": content,
                },
            )
            review.post_id = post.id

        db.session.commit()

        ActivityLog.log(
            action="sync.week_review_sent",
            model_type="UpdateWeekReview",
            record_id=review.id,
            member_id=sent_by_id,
            title="Week in Review sent",
            description=f"Week of {review.week_start.strftime('%b %d')}",
            icon="fa-newspaper",
            color="info",
        )

        return review
