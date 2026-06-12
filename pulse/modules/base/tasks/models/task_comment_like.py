# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""TaskCommentLike model — reactions on task comments.

Toggle-based: one like per member per comment. Duplicate prevention
enforced by a unique constraint.

Example:
    Toggling a like::

        liked = TaskCommentLike.toggle(comment_id=7, member_id=3)
        # liked=True  → like was added
        # liked=False → like was removed
"""

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class TaskCommentLike(db.Model, WorkspaceMixin):
    """A like on a TaskComment.

    Attributes:
        id: Primary key.
        comment_id: FK to the liked comment.
        member_id: FK to the workspace_user who liked.
        created_at: When the like was created.
    """

    __tablename__ = "task_comment_like"
    __table_args__ = (
        db.UniqueConstraint(
            "comment_id", "member_id", name="_task_comment_like_uc"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(
        db.Integer,
        db.ForeignKey("task_comment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id"),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    member = db.relationship("WorkspaceUser", lazy=LAZY)
    comment = db.relationship(
        "TaskComment",
        backref=db.backref("likes", lazy="dynamic"),
        lazy=LAZY,
    )

    @classmethod
    def toggle(cls, comment_id: int, member_id: int) -> bool:
        """Toggle a like on a comment.

        Args:
            comment_id: The comment to like/unlike.
            member_id: The workspace_user performing the action.

        Returns:
            True if the like was added, False if removed.
        """
        existing = cls.query.filter_by(
            comment_id=comment_id, member_id=member_id
        ).first()
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return False
        like = cls(comment_id=comment_id, member_id=member_id)
        db.session.add(like)
        db.session.commit()
        return True

    @classmethod
    def count_for_comment(cls, comment_id: int) -> int:
        """Return the number of likes on a comment."""
        return cls.query.filter_by(comment_id=comment_id).count()

    @classmethod
    def liked_by_member(cls, comment_id: int, member_id: int) -> bool:
        """Check if a member has liked a comment."""
        return cls.query.filter_by(
            comment_id=comment_id, member_id=member_id
        ).first() is not None

    @classmethod
    def get_like_data(cls, comment_ids: list[int], member_id: int) -> dict:
        """Bulk-fetch like counts, current-user-liked flags, and liker names.

        Args:
            comment_ids: List of comment IDs to query.
            member_id: Current member's ID.

        Returns:
            Dict keyed by comment_id with {count, liked, names} values.
        """
        if not comment_ids:
            return {}

        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        likes = (
            cls.query
            .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
            .filter(cls.comment_id.in_(comment_ids))
            .all()
        )

        data: dict[int, dict] = {
            cid: {"count": 0, "liked": False, "names": []}
            for cid in comment_ids
        }
        for like in likes:
            entry = data[like.comment_id]
            entry["count"] += 1
            if like.member_id == member_id:
                entry["liked"] = True
            name = f"{like.member.user.first_name} {like.member.user.last_name}"
            entry["names"].append(name)

        return data
