# -----------------------------------------------------------------------------
# sparQ - PresenceSignal Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""PresenceSignal model — unified storage for presence signals (focus, energy, etc.).

Duration signals (focus): ended_at set when state changes.
Point-in-time signals (energy, progress): ended_at stays NULL.
"""

from datetime import datetime

from flask import g
from sqlalchemy import and_

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class PresenceSignal(db.Model):
    """A single presence signal record.

    Attributes:
        workspace_id: Tenant scope.
        member_id: Who recorded this signal.
        template_id: Which signal type (SyncTemplate with post_type='presence').
        value: The signal value ('focus', 'available', '3', 'on_track', etc.).
        created_at: When the signal was recorded.
        ended_at: When the signal ended (duration signals only).
        source_post_id: Optional link to a SyncPost that triggered this signal.
    """

    __tablename__ = "presence_signal"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Uuid, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False
    )
    template_id = db.Column(
        db.Integer, db.ForeignKey("update_template.id"), nullable=False
    )
    value = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    source_post_id = db.Column(
        db.Integer, db.ForeignKey("update_post.id"), nullable=True
    )

    __table_args__ = (
        db.Index("ix_presence_signal_member_template", "member_id", "template_id", "created_at"),
        db.Index("ix_presence_signal_ws_template", "workspace_id", "template_id", "created_at"),
    )

    # Relationships
    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)
    template = db.relationship("UpdateTemplate", foreign_keys=[template_id], lazy=LAZY)

    @classmethod
    def record(cls, member_id, template_id, value, source_post_id=None):
        """Create a new signal, closing any previous open duration signal for this template.

        Args:
            member_id: The member recording the signal.
            template_id: The signal type template.
            value: The signal value.
            source_post_id: Optional link to a SyncPost.

        Returns:
            The new PresenceSignal record.
        """
        now = datetime.utcnow()

        # Close any open duration signal for this member+template
        cls.query.filter(
            cls.workspace_id == g.workspace_id,
            cls.member_id == member_id,
            cls.template_id == template_id,
            cls.ended_at.is_(None),
        ).update({"ended_at": now})

        signal = cls(
            workspace_id=g.workspace_id,
            member_id=member_id,
            template_id=template_id,
            value=value,
            created_at=now,
            source_post_id=source_post_id,
        )
        db.session.add(signal)
        db.session.commit()
        return signal

    @classmethod
    def get_current(cls, member_id, template_id):
        """Get the latest signal for a member+template.

        For duration signals, returns the open one (ended_at IS NULL).
        Falls back to latest by created_at.
        """
        # Try open signal first (duration signals)
        signal = cls.query.filter(
            cls.workspace_id == g.workspace_id,
            cls.member_id == member_id,
            cls.template_id == template_id,
            cls.ended_at.is_(None),
        ).order_by(cls.created_at.desc()).first()

        if signal:
            return signal

        # Fall back to latest signal
        return cls.query.filter(
            cls.workspace_id == g.workspace_id,
            cls.member_id == member_id,
            cls.template_id == template_id,
        ).order_by(cls.created_at.desc()).first()

    @classmethod
    def get_team_current(cls, template_id):
        """Get latest signals for all members for a given template.

        Returns a dict of member_id -> PresenceSignal.
        """
        from sqlalchemy import func

        # Subquery: latest signal per member
        latest = (
            db.session.query(
                cls.member_id,
                func.max(cls.created_at).label("max_created"),
            )
            .filter(
                cls.workspace_id == g.workspace_id,
                cls.template_id == template_id,
            )
            .group_by(cls.member_id)
            .subquery()
        )

        signals = (
            cls.query
            .join(
                latest,
                and_(
                    cls.member_id == latest.c.member_id,
                    cls.created_at == latest.c.max_created,
                ),
            )
            .filter(
                cls.workspace_id == g.workspace_id,
                cls.template_id == template_id,
            )
            .all()
        )

        return {s.member_id: s for s in signals}

    @classmethod
    def get_team_current_multi(cls, template_ids):
        """Get latest signals for all members across multiple templates in one query.

        Returns dict of template_id -> {member_id -> PresenceSignal}.
        """
        if not template_ids:
            return {}

        from sqlalchemy import func

        latest = (
            db.session.query(
                cls.member_id,
                cls.template_id,
                func.max(cls.created_at).label("max_created"),
            )
            .filter(
                cls.workspace_id == g.workspace_id,
                cls.template_id.in_(template_ids),
            )
            .group_by(cls.member_id, cls.template_id)
            .subquery()
        )

        signals = (
            cls.query
            .join(
                latest,
                and_(
                    cls.member_id == latest.c.member_id,
                    cls.template_id == latest.c.template_id,
                    cls.created_at == latest.c.max_created,
                ),
            )
            .filter(
                cls.workspace_id == g.workspace_id,
                cls.template_id.in_(template_ids),
            )
            .all()
        )

        result = {tid: {} for tid in template_ids}
        for s in signals:
            result[s.template_id][s.member_id] = s
        return result

    @classmethod
    def get_signals(cls, template_id, since):
        """Get all signals for a template since a given datetime."""
        return cls.query.filter(
            cls.workspace_id == g.workspace_id,
            cls.template_id == template_id,
            cls.created_at >= since,
        ).order_by(cls.created_at.desc()).all()
