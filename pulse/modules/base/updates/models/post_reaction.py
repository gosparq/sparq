# -----------------------------------------------------------------------------
# sparQ - UpdatePostReaction Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdatePostReaction model — emoji reactions on posts and chat messages."""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdatePostReaction(db.Model, WorkspaceMixin):
    """Emoji reaction on an UpdatePost.

    Attributes:
        post_id: FK to UpdatePost.
        member_id: FK to WorkspaceUser.
        emoji: Emoji string.
    """

    __tablename__ = "update_post_reaction"
    __table_args__ = (
        db.UniqueConstraint("post_id", "member_id", "emoji", name="uq_post_reaction"),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("update_post.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)

    @classmethod
    def toggle(cls, post_id: int, member_id: int, emoji: str) -> tuple[bool, int]:
        """Toggle a reaction. Returns (added: bool, new_count: int).

        Raises:
            PermissionError: If the post belongs to a channel locked by a
              closed project. Removing existing reactions is also blocked
              while the project is closed — reopening unlocks all writes.
        """
        from .post import UpdatePost
        from .channel import UpdateChannel
        from modules.base.projects.models.project import Project

        post = UpdatePost.scoped().filter_by(id=post_id).first()
        if post and post.channel_id:
            channel = UpdateChannel.get_by_id(post.channel_id)
            if Project.is_channel_locked(channel):
                raise PermissionError(
                    "Channel is locked because its project is closed."
                )

        existing = cls.scoped().filter_by(
            post_id=post_id, member_id=member_id, emoji=emoji
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            count = cls.scoped().filter_by(post_id=post_id, emoji=emoji).count()
            return (False, count)
        else:
            reaction = cls(post_id=post_id, member_id=member_id, emoji=emoji)
            db.session.add(reaction)
            db.session.commit()
            count = cls.scoped().filter_by(post_id=post_id, emoji=emoji).count()
            return (True, count)

    @classmethod
    def get_for_message(cls, post_id: int) -> dict:
        """Get reactions for a post/message grouped by emoji with member info.

        Compat name (get_for_message) so chat templates work unchanged.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        reactions = (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
            .filter_by(post_id=post_id)
            .all()
        )
        result = {}
        for r in reactions:
            if r.emoji not in result:
                result[r.emoji] = {"count": 0, "users": [], "member_ids": [], "user_ids": []}
            result[r.emoji]["count"] += 1
            name = r.member.user.first_name if r.member and r.member.user else "Unknown"
            result[r.emoji]["users"].append(name)
            result[r.emoji]["member_ids"].append(r.member_id)
            if r.member and r.member.user:
                result[r.emoji]["user_ids"].append(r.member.user_id)
        return result

    @classmethod
    def get_for_posts(cls, post_ids: list[int]) -> dict[int, dict]:
        """Batched version of get_for_message: returns {post_id: reactions_dict}.

        Single SELECT instead of one-per-post. Same payload shape as
        get_for_message so feed templates can drop in unchanged.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        if not post_ids:
            return {}

        rows = (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
            .filter(cls.post_id.in_(post_ids))
            .all()
        )

        result: dict[int, dict] = {pid: {} for pid in post_ids}
        for r in rows:
            bucket = result[r.post_id]
            if r.emoji not in bucket:
                bucket[r.emoji] = {"count": 0, "users": [], "member_ids": [], "user_ids": []}
            bucket[r.emoji]["count"] += 1
            name = r.member.user.first_name if r.member and r.member.user else "Unknown"
            bucket[r.emoji]["users"].append(name)
            bucket[r.emoji]["member_ids"].append(r.member_id)
            if r.member and r.member.user:
                bucket[r.emoji]["user_ids"].append(r.member.user_id)
        return result

    @classmethod
    def member_reacted(cls, post_id: int, member_id: int, emoji: str) -> bool:
        """Check if member has reacted with a specific emoji."""
        return cls.scoped().filter_by(
            post_id=post_id, member_id=member_id, emoji=emoji
        ).first() is not None
