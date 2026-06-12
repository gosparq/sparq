# -----------------------------------------------------------------------------
# sparQ - Acknowledgment Models
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Acknowledgment models — 10-4 acknowledgment on direct messages and posts."""

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class DMAck(db.Model, WorkspaceMixin):
    """10-4 acknowledgment on a direct message.

    Attributes:
        message_id: FK to DM.
        member_id: FK to WorkspaceUser who acknowledged.
    """

    __tablename__ = "dm_ack"
    __table_args__ = (
        db.UniqueConstraint("message_id", "member_id", name="uq_dm_ack"),
    )

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("dm.id", ondelete="CASCADE"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)
    message = db.relationship("DM", backref=db.backref("acknowledgments", lazy="dynamic"), lazy=LAZY)


@ModelRegistry.register
class UpdatePostAck(db.Model, WorkspaceMixin):
    """10-4 acknowledgment on an update post (update, win, board, chat message).

    Attributes:
        post_id: FK to UpdatePost.
        member_id: FK to WorkspaceUser who acknowledged.
    """

    __tablename__ = "update_post_ack"
    __table_args__ = (
        db.UniqueConstraint("post_id", "member_id", name="uq_post_ack"),
    )

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("update_post.id", ondelete="CASCADE"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)

    @classmethod
    def acknowledge(cls, post_id: int, member_id: int) -> dict:
        """Acknowledge a sync post (one-way, no undo).

        Raises:
            PermissionError: If the post belongs to a channel locked by a
              closed project.
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
            post_id=post_id, member_id=member_id
        ).first()

        if not existing:
            ack = cls(post_id=post_id, member_id=member_id)
            db.session.add(ack)
            db.session.commit()

        return cls.get_for_post(post_id, member_id)

    @classmethod
    def get_for_post(cls, post_id: int, current_member_id: int | None = None) -> dict:
        """Get acknowledgment data for a post.

        Excludes the post author from the grid.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus
        from .post import UpdatePost

        post = UpdatePost.scoped().filter_by(id=post_id).first()
        author_member_id = post.member_id if post else None

        from sqlalchemy.orm import joinedload

        all_members = WorkspaceUser.scoped().options(joinedload(WorkspaceUser.user)).filter_by(status=EmployeeStatus.ACTIVE).all()
        acked_ids = {
            a.member_id
            for a in cls.scoped().filter_by(post_id=post_id).all()
        }

        acked = []
        pending = []
        for m in all_members:
            if m.id == author_member_id:
                continue

            initials = ""
            name = "Unknown"
            if m.user:
                first = m.user.first_name or ""
                last = m.user.last_name or ""
                initials = (first[:1] + last[:1]).upper()
                name = f"{first} {last}".strip()

            entry = {"member_id": m.id, "initials": initials, "name": name}
            if m.id in acked_ids:
                acked.append(entry)
            else:
                pending.append(entry)

        return {
            "acked": acked,
            "pending": pending,
            "all_acked": len(pending) == 0,
            "current_user_acked": current_member_id in acked_ids if current_member_id else False,
        }

    # Compat alias so chat templates can call get_for_message(post_id, member_id)
    get_for_message = get_for_post

    @classmethod
    def get_for_posts(
        cls,
        posts: list,
        current_member_id: int | None = None,
        member_info: list[tuple[int, str, str]] | None = None,
    ) -> dict[int, dict]:
        """Batched version of get_for_post: returns {post_id: ack_dict}.

        Args:
            posts: list of post-like objects with .id and .member_id.
            current_member_id: Viewer's workspace_user.id.
            member_info: Pre-computed list of (id, initials, name) tuples.
                Pass this to skip the internal active-members query.
        """
        if not posts:
            return {}

        post_ids = [p.id for p in posts]

        if member_info is None:
            from sqlalchemy.orm import joinedload

            from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser

            all_members = (
                WorkspaceUser.scoped()
                .options(joinedload(WorkspaceUser.user))
                .filter_by(status=EmployeeStatus.ACTIVE)
                .all()
            )
            member_info = []
            for m in all_members:
                initials = ""
                name = "Unknown"
                if m.user:
                    first = m.user.first_name or ""
                    last = m.user.last_name or ""
                    initials = (first[:1] + last[:1]).upper()
                    name = f"{first} {last}".strip()
                member_info.append((m.id, initials, name))

        acks = cls.scoped().filter(cls.post_id.in_(post_ids)).all()
        acked_by_post: dict[int, set[int]] = {pid: set() for pid in post_ids}
        for a in acks:
            acked_by_post[a.post_id].add(a.member_id)

        result: dict[int, dict] = {}
        for post in posts:
            author_id = post.member_id
            acked_ids = acked_by_post.get(post.id, set())
            acked = []
            pending = []
            for mid, initials, name in member_info:
                if mid == author_id:
                    continue
                entry = {"member_id": mid, "initials": initials, "name": name}
                if mid in acked_ids:
                    acked.append(entry)
                else:
                    pending.append(entry)
            result[post.id] = {
                "acked": acked,
                "pending": pending,
                "all_acked": len(pending) == 0,
                "current_user_acked": (
                    current_member_id in acked_ids if current_member_id else False
                ),
            }
        return result

    @classmethod
    def member_acknowledged(cls, post_id: int, member_id: int) -> bool:
        """Check if member has acknowledged a specific post."""
        return cls.scoped().filter_by(
            post_id=post_id, member_id=member_id
        ).first() is not None
