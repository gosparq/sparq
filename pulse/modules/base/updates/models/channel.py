# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Channel model for team communication.

Chat messages are now stored as UpdatePost records (post_type='channel').
This module contains only the UpdateChannel model.
"""

from flask import current_app

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateChannel(db.Model, WorkspaceMixin, SerializableMixin):
    """Chat channel model for organizing conversations."""

    __tablename__ = "update_channel"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "workspace_id",
            "name",
            name="uq_channel_org_workspace_name",
            postgresql_nulls_not_distinct=True,
        ),
    )

    # Channel limits: 1 system (#general) + 4 custom = 5 total
    MAX_CHANNELS = 5
    SYSTEM_CHANNELS = ("general",)
    RETIRED_CHANNELS = ("agent",)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.now())
    created_by_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"))
    is_private = db.Column(db.Boolean, default=False)
    require_ten_four = db.Column(db.Boolean, default=False)
    project_id = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="SET NULL"), nullable=True
    )
    # Org-wide channels (workspace_id IS NULL) set is_default=TRUE to auto-subscribe
    # new organization members. Meaningless for workspace channels.
    is_default = db.Column(db.Boolean, nullable=True)

    # Relationships
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], lazy=LAZY)
    posts = db.relationship("UpdatePost", back_populates="channel", lazy="dynamic")
    project = db.relationship("Project", foreign_keys=[project_id], lazy=LAZY)

    def __init__(
        self,
        name: str,
        description: str | None = None,
        created_by_id: int | None = None,
        is_private: bool = False,
        require_ten_four: bool = False,
        project_id: int | None = None,
        is_default: bool | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.created_by_id = created_by_id
        self.is_private = is_private
        self.require_ten_four = require_ten_four
        self.project_id = project_id
        self.is_default = is_default

    @classmethod
    def create_default_channels(cls) -> None:
        """Create default channels if they don't exist and clean up retired ones."""
        default_channels = [
            {"name": "general", "description": "General discussion channel", "require_ten_four": True},
        ]

        for channel_data in default_channels:
            channel = cls.scoped().filter_by(name=channel_data["name"]).first()
            if not channel:
                channel = cls(
                    name=channel_data["name"],
                    description=channel_data["description"],
                    require_ten_four=channel_data["require_ten_four"],
                )
                db.session.add(channel)

        cls._cleanup_retired_channels()

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating default channels: {str(e)}")

    @classmethod
    def _cleanup_retired_channels(cls) -> None:
        """Remove channels that are no longer part of the system."""
        for name in cls.RETIRED_CHANNELS:
            channel = cls.scoped().filter_by(name=name).first()
            if channel:
                from .channel_read_state import UpdateChannelReadState

                UpdateChannelReadState.scoped().filter_by(channel_id=channel.id).delete()
                from modules.base.ai.models.pending_action import AIPendingAction
                AIPendingAction.scoped().filter_by(channel_id=channel.id).update({"channel_id": None})
                db.session.delete(channel)

    @classmethod
    def get_all(cls) -> list["UpdateChannel"]:
        """Get all channels ordered by name (excludes retired channels)."""
        return cls.scoped().filter(
            cls.name.notin_(cls.RETIRED_CHANNELS)
        ).order_by(cls.name).all()

    @classmethod
    def get_by_name(cls, name: str) -> "UpdateChannel | None":
        """Get channel by name."""
        from sqlalchemy.orm import joinedload

        return cls.scoped().options(joinedload(cls.project)).filter_by(name=name).first()

    @classmethod
    def get_by_id(cls, channel_id: int) -> "UpdateChannel | None":
        """Get channel by ID."""
        return cls.scoped().filter_by(id=channel_id).first()

    @classmethod
    def create(
        cls,
        name: str,
        description: str | None = None,
        created_by_id: int | None = None,
        is_private: bool = False,
        require_ten_four: bool = False,
    ) -> "UpdateChannel":
        """Create a new channel."""
        channel = cls(
            name=name,
            description=description,
            created_by_id=created_by_id,
            is_private=is_private,
            require_ten_four=require_ten_four,
        )
        db.session.add(channel)
        db.session.commit()
        return channel

    @classmethod
    def get_or_create_default(cls) -> "UpdateChannel":
        """Get or create the general channel."""
        channel = cls.get_by_name("general")
        if not channel:
            channel = cls.create(
                name="general",
                description="Day-to-day conversation",
            )
        return channel

    @classmethod
    def custom_channel_count(cls) -> int:
        """Count custom (non-system, non-project) channels."""
        query = cls.scoped().filter(cls.name.notin_(cls.SYSTEM_CHANNELS))
        try:
            from modules.base.projects.models.project import Project
            project_channel_ids = [
                p.channel_id for p in Project.scoped().filter(Project.channel_id.isnot(None)).all()
            ]
            if project_channel_ids:
                query = query.filter(cls.id.notin_(project_channel_ids))
        except Exception:
            pass
        return query.count()

    @classmethod
    def remaining_channel_slots(cls) -> int:
        """Return how many custom channels can still be created."""
        return max(0, cls.MAX_CHANNELS - len(cls.SYSTEM_CHANNELS) - cls.custom_channel_count())

    @classmethod
    def can_create_channel(cls) -> bool:
        """Check if the channel limit allows creating another channel."""
        return cls.remaining_channel_slots() > 0

    def get_posts_feed(self, limit=20, offset=0):
        """Get posts in this channel ordered by creation date."""
        from .post import UpdatePost
        return UpdatePost.get_channel_feed(self.id, limit=limit, offset=offset)

    @classmethod
    def delete_channel(cls, channel_id: int) -> bool:
        """Delete a channel and all associated data."""
        from .post import UpdatePost
        from .channel_read_state import UpdateChannelReadState

        channel = cls.scoped().filter_by(id=channel_id).first()
        if not channel:
            return False

        UpdateChannelReadState.scoped().filter_by(channel_id=channel_id).delete()
        UpdatePost.scoped().filter_by(channel_id=channel_id).delete()

        db.session.delete(channel)
        db.session.commit()
        return True

    # ------------------------------------------------------------------
    # Org-wide channel helpers (absorbed from the retired OrganizationChannel
    # model). Org-wide channels have workspace_id IS NULL and are managed by
    # organization admins.
    # ------------------------------------------------------------------

    @classmethod
    def list_org_wide(cls) -> list["UpdateChannel"]:
        """All org-wide channels in the current org, alphabetically."""
        return cls.org_wide().order_by(cls.name).all()

    @classmethod
    def get_org_wide_by_name(cls, name: str) -> "UpdateChannel | None":
        """Look up an org-wide channel by name in the current org."""
        cleaned = (name or "").strip().lstrip("#").lower()
        return cls.org_wide().filter_by(name=cleaned).first()

    @classmethod
    def create_org_wide(
        cls,
        name: str,
        description: str | None = None,
        is_default: bool = False,
    ) -> "UpdateChannel":
        """Create an org-wide channel (workspace_id=NULL) in the current org.

        organization_id is stamped by auto_set_organization_id. Explicitly
        passes workspace_id=None on the insert so it doesn't pick up
        g.workspace_id via the listener.
        """
        from flask import g

        cleaned = (name or "").strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Channel name is required.")
        if len(cleaned) > 50:
            raise ValueError("Channel name is too long (max 50 chars).")

        organization_id = getattr(g, "organization_id", None)
        if organization_id is None:
            raise RuntimeError("create_org_wide called without organization context.")

        existing = (
            cls.query
            .filter_by(organization_id=organization_id, workspace_id=None, name=cleaned)
            .first()
        )
        if existing is not None:
            raise ValueError(
                f"A channel named #{cleaned} already exists in this organization."
            )

        channel = cls(
            name=cleaned,
            description=description,
            is_private=False,
            require_ten_four=False,
            is_default=bool(is_default),
        )
        channel.workspace_id = None
        channel.organization_id = organization_id
        db.session.add(channel)
        db.session.commit()
        return channel

    def rename(self, new_name: str) -> None:
        """Rename this channel; raises ValueError on collision."""
        cleaned = (new_name or "").strip().lstrip("#").lower()
        if not cleaned:
            raise ValueError("Channel name is required.")
        if cleaned == self.name:
            return
        collision = (
            UpdateChannel.query
            .filter_by(
                organization_id=self.organization_id,
                workspace_id=self.workspace_id,
                name=cleaned,
            )
            .filter(UpdateChannel.id != self.id)
            .first()
        )
        if collision is not None:
            raise ValueError(f"A channel named #{cleaned} already exists here.")
        self.name = cleaned
        db.session.commit()

    def set_default(self, is_default: bool) -> None:
        """Toggle whether new org members auto-subscribe (org-wide channels only)."""
        self.is_default = bool(is_default)
        db.session.commit()

    def hard_delete(self) -> None:
        """Permanently delete this channel and its posts."""
        db.session.delete(self)
        db.session.commit()

    @property
    def is_org_wide(self) -> bool:
        """True for org-wide channels (workspace_id IS NULL)."""
        return self.workspace_id is None
