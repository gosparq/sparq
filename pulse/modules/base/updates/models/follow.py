# -----------------------------------------------------------------------------
# sparQ - Sync Follow Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdateFollow model — generic follow system for Sync entities.

Users can follow channels, status templates, and board templates to receive
email notifications when new content is posted. Status templates are
auto-followed for all members; channels and boards are opt-in.
"""

from datetime import datetime

from flask import g
from sqlalchemy import or_

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateFollow(db.Model, WorkspaceMixin):
    """Follow record linking a member to a Sync entity.

    Attributes:
        entity_type: Type of entity ('channel', 'status_template', 'board_template').
        entity_id: ID of the entity being followed.
        member_id: FK to WorkspaceUser who follows.
    """

    __tablename__ = "update_follow"
    __table_args__ = (
        db.UniqueConstraint("entity_type", "entity_id", "member_id", name="uq_content_follow"),
    )

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer, nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)

    @classmethod
    def toggle(cls, entity_type: str, entity_id: int, member_id: int) -> tuple[bool, dict | None]:
        """Toggle follow state. Returns (is_following, follow_data).

        Raises:
            PermissionError: If following a channel whose linked project is
              closed. Other entity types are unaffected.
        """
        if entity_type == "channel":
            from .channel import UpdateChannel
            from modules.base.projects.models.project import Project

            channel = UpdateChannel.get_by_id(entity_id)
            if Project.is_channel_locked(channel):
                raise PermissionError(
                    "Channel is locked because its project is closed."
                )

        existing = cls.scoped().filter_by(
            entity_type=entity_type, entity_id=entity_id, member_id=member_id
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            return False, None
        else:
            follow = cls(entity_type=entity_type, entity_id=entity_id, member_id=member_id)
            db.session.add(follow)
            db.session.commit()
            return True, {"id": follow.id, "entity_type": entity_type, "entity_id": entity_id}

    @classmethod
    def is_following(cls, entity_type: str, entity_id: int, member_id: int) -> bool:
        """Check if a member follows an entity."""
        return cls.scoped().filter_by(
            entity_type=entity_type, entity_id=entity_id, member_id=member_id
        ).first() is not None

    @classmethod
    def get_followers(cls, entity_type: str, entity_id: int) -> list:
        """Get all WorkspaceUser records that follow an entity."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        follows = cls.scoped().filter_by(
            entity_type=entity_type, entity_id=entity_id
        ).all()
        member_ids = [f.member_id for f in follows]
        if not member_ids:
            return []
        from sqlalchemy.orm import joinedload

        return WorkspaceUser.query.options(joinedload(WorkspaceUser.user)).filter(WorkspaceUser.id.in_(member_ids)).all()

    @classmethod
    def get_follower_emails(cls, entity_type: str, entity_id: int, exclude_member_id: int | None = None) -> list[str]:
        """Get email addresses of all followers, optionally excluding one member."""
        followers = cls.get_followers(entity_type, entity_id)
        emails = []
        for member in followers:
            if exclude_member_id and member.id == exclude_member_id:
                continue
            if member.user and member.user.email:
                emails.append(member.user.email)
        return emails

    @classmethod
    def auto_follow_all(cls, entity_type: str, entity_id: int) -> int:
        """Create follow records for all active workspace members. Returns count created."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        members = WorkspaceUser.scoped().filter_by(status="ACTIVE").all()
        count = 0
        for member in members:
            existing = cls.scoped().filter_by(
                entity_type=entity_type, entity_id=entity_id, member_id=member.id
            ).first()
            if not existing:
                follow = cls(entity_type=entity_type, entity_id=entity_id, member_id=member.id)
                db.session.add(follow)
                count += 1
        if count:
            db.session.commit()
        return count

    @classmethod
    def auto_follow_member(cls, member_id: int) -> int:
        """Auto-follow all status templates for a new member. Returns count created."""
        from modules.base.updates.models.template import UpdateTemplate

        templates = UpdateTemplate.query.filter(
            UpdateTemplate.post_type.in_(["update", "win"]),
            or_(
                UpdateTemplate.workspace_id == g.workspace_id,
                UpdateTemplate.workspace_id.is_(None),
            ),
        ).all()
        count = 0
        for tmpl in templates:
            existing = cls.scoped().filter_by(
                entity_type="status_template", entity_id=tmpl.id, member_id=member_id
            ).first()
            if not existing:
                follow = cls(entity_type="status_template", entity_id=tmpl.id, member_id=member_id)
                db.session.add(follow)
                count += 1
        if count:
            db.session.commit()
        return count

    @classmethod
    def get_followed_ids(cls, entity_type: str, member_id: int) -> set[int]:
        """Get set of entity IDs that a member follows for a given type."""
        follows = cls.scoped().filter_by(
            entity_type=entity_type, member_id=member_id
        ).all()
        return {f.entity_id for f in follows}

    @classmethod
    def get_followed_ids_batch(
        cls, entity_types: list[str], member_id: int
    ) -> dict[str, set[int]]:
        """Get followed entity IDs for multiple types in a single query."""
        follows = (
            cls.scoped()
            .filter(cls.entity_type.in_(entity_types), cls.member_id == member_id)
            .all()
        )
        result: dict[str, set[int]] = {t: set() for t in entity_types}
        for f in follows:
            result[f.entity_type].add(f.entity_id)
        return result
