# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""UpdateChannelReadState — tracks per-member read position in each channel.

Replaces the legacy SyncMessageState model (which referenced sync_message IDs).
"""

from flask import current_app, g

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateChannelReadState(db.Model, WorkspaceMixin):
    """Tracks the last-read post ID per member per channel.

    Attributes:
        member_id: FK to workspace_user.
        channel_id: FK to update_channel.
        last_read_post_id: Highest UpdatePost.id the member has seen.
    """

    __tablename__ = "update_channel_read_state"
    __table_args__ = (
        db.UniqueConstraint(
            "member_id", "channel_id", "workspace_id",
            name="uq_channel_read_state",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id", ondelete="CASCADE"), nullable=False
    )
    channel_id = db.Column(
        db.Integer, db.ForeignKey("update_channel.id", ondelete="CASCADE"), nullable=False
    )
    last_read_post_id = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)
    channel = db.relationship("UpdateChannel", foreign_keys=[channel_id], lazy=LAZY)

    # ── Unread counts ─────────────────────────────────────────────────

    @classmethod
    def get_unread_count(cls, member_id: int, channel_id: int) -> int:
        """Count unread posts in a channel for a member."""
        cache_key = (member_id, channel_id)
        try:
            cache = getattr(g, "_channel_unread_cache", None)
            if cache is None:
                cache = {}
                g._channel_unread_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        try:
            state = cls.scoped().filter_by(
                member_id=member_id, channel_id=channel_id
            ).first()

            last_read = state.last_read_post_id if state else 0

            from .post import UpdatePost
            result = UpdatePost.scoped().filter(
                UpdatePost.channel_id == channel_id,
                UpdatePost.id > last_read,
            ).count()
        except Exception as e:
            current_app.logger.error(f"Error getting unread count: {e}")
            result = 0

        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def get_mention_count(cls, member_id: int, channel_id: int) -> int:
        """Count unread posts that @mention the member in a channel."""
        try:
            state = cls.scoped().filter_by(
                member_id=member_id, channel_id=channel_id
            ).first()

            last_read = state.last_read_post_id if state else 0

            from .post import UpdatePost
            unread_posts = UpdatePost.scoped().filter(
                UpdatePost.channel_id == channel_id,
                UpdatePost.id > last_read,
            ).all()
            return sum(
                1 for p in unread_posts
                if member_id in ((p.payload or {}).get("mentioned_member_ids") or [])
            )
        except Exception as e:
            current_app.logger.error(f"Error getting mention count: {e}")
            return 0

    @classmethod
    def get_total_unread_count(cls, member_id: int) -> int:
        """Total unread count across all channels.

        Uses a batch query (2 SQL statements instead of 2×N) and pre-populates
        the per-channel g-cache so later get_unread_count calls are free.
        """
        try:
            cache = getattr(g, "_channel_unread_cache", None)
            if cache is None:
                cache = {}
                g._channel_unread_cache = cache
        except Exception:
            cache = None

        try:
            from .channel import UpdateChannel
            from .post import UpdatePost

            channels = UpdateChannel.scoped().all()
            if not channels:
                return 0

            channel_ids = [ch.id for ch in channels]

            # Batch-fetch read states for this member across all channels (1 query)
            states = cls.scoped().filter(
                cls.member_id == member_id,
                cls.channel_id.in_(channel_ids),
            ).all()
            last_read_map = {s.channel_id: s.last_read_post_id for s in states}

            # Build per-channel unread filters (each channel has a different last_read)
            unread_filters = []
            for ch_id in channel_ids:
                last_read = last_read_map.get(ch_id, 0) or 0
                unread_filters.append(
                    db.and_(
                        UpdatePost.channel_id == ch_id,
                        UpdatePost.id > last_read,
                    )
                )

            unread_rows = (
                db.session.query(
                    UpdatePost.channel_id,
                    db.func.count(UpdatePost.id),
                )
                .filter(
                    UpdatePost.organization_id == g.organization_id,
                    UpdatePost.workspace_id == g.workspace_id,
                    db.or_(*unread_filters),
                )
                .group_by(UpdatePost.channel_id)
                .all()
            ) if unread_filters else []

            unread_map: dict[int, int] = dict(unread_rows)

            total = 0
            for ch_id in channel_ids:
                count = unread_map.get(ch_id, 0)
                total += count
                if cache is not None:
                    cache[(member_id, ch_id)] = count

            return total
        except Exception as e:
            current_app.logger.error(f"Error getting total unread count: {e}")
            return 0

    @classmethod
    def get_total_mention_count(cls, member_id: int) -> int:
        """Total unread @mention count across all channels."""
        try:
            from .channel import UpdateChannel
            channels = UpdateChannel.scoped().all()
            total = 0
            for ch in channels:
                total += cls.get_mention_count(member_id, ch.id)
            return total
        except Exception as e:
            current_app.logger.error(f"Error getting total mention count: {e}")
            return 0

    # ── Mark read ─────────────────────────────────────────────────────

    @classmethod
    def mark_channel_read(cls, member_id: int, channel_id: int) -> bool:
        """Mark all posts in a channel as read."""
        try:
            from .post import UpdatePost
            last_post = (
                UpdatePost.scoped()
                .filter_by(channel_id=channel_id)
                .order_by(UpdatePost.id.desc())
                .first()
            )
            if not last_post:
                return True

            state = cls.scoped().filter_by(
                member_id=member_id, channel_id=channel_id
            ).first()

            if state:
                state.last_read_post_id = last_post.id
            else:
                state = cls(
                    member_id=member_id,
                    channel_id=channel_id,
                    last_read_post_id=last_post.id,
                )
                db.session.add(state)

            db.session.commit()
            return True
        except Exception as e:
            current_app.logger.error(f"Error marking channel as read: {e}")
            db.session.rollback()
            return False

    @classmethod
    def mark_post_read(cls, member_id: int, post_id: int) -> bool:
        """Mark up to a specific post as read."""
        try:
            from .post import UpdatePost
            post = UpdatePost.scoped().filter_by(id=post_id).first()
            if not post or not post.channel_id:
                return False

            state = cls.scoped().filter_by(
                member_id=member_id, channel_id=post.channel_id
            ).first()

            if state:
                if post_id > (state.last_read_post_id or 0):
                    state.last_read_post_id = post_id
            else:
                state = cls(
                    member_id=member_id,
                    channel_id=post.channel_id,
                    last_read_post_id=post_id,
                )
                db.session.add(state)

            db.session.commit()
            return True
        except Exception as e:
            current_app.logger.error(f"Error marking post as read: {e}")
            db.session.rollback()
            return False

    # ── Initialization ────────────────────────────────────────────────

    @classmethod
    def initialize_member_read_state(cls, member_id: int) -> None:
        """Initialize read state for all channels for a new member.

        Sets last_read_post_id to the latest post so old posts
        don't appear unread.
        """
        from .channel import UpdateChannel
        from .post import UpdatePost

        for channel in UpdateChannel.get_all():
            last_post = (
                UpdatePost.scoped()
                .filter_by(channel_id=channel.id)
                .order_by(UpdatePost.id.desc())
                .first()
            )
            if last_post:
                state = cls(
                    member_id=member_id,
                    channel_id=channel.id,
                    last_read_post_id=last_post.id,
                )
                db.session.add(state)

        db.session.commit()

    @classmethod
    def initialize_user_read_state(cls, user_id: int) -> None:
        """Initialize read state by user ID (compat shim)."""
        from modules.base.core.models.workspace_user import WorkspaceUser
        member = WorkspaceUser.get_by_user_id(user_id)
        if member:
            cls.initialize_member_read_state(member.id)
