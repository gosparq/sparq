# -----------------------------------------------------------------------------
# sparQ - Working Agreement Models
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Working Agreement model — single-record per workspace, versioned with acks."""

from datetime import datetime


from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class WorkingAgreement(db.Model, WorkspaceMixin):
    """Single working agreement per workspace, versioned."""

    __tablename__ = "working_agreement"

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    updated_by = db.relationship("WorkspaceUser", foreign_keys=[updated_by_id], lazy=LAZY)

    @classmethod
    def get_current(cls):
        """Return the current agreement for this workspace (there's only one)."""
        return cls.scoped().first()

    @classmethod
    def get_or_create(cls):
        """Get existing agreement or create an empty placeholder."""
        agreement = cls.get_current()
        if not agreement:
            agreement = cls(content="", version=0)
            db.session.add(agreement)
            db.session.commit()
        return agreement

    @classmethod
    def save(cls, content, updated_by_id):
        """Create or update the agreement, bump version, clear all acks, notify."""
        agreement = cls.get_current()
        if agreement:
            agreement.content = content
            agreement.version += 1
            agreement.updated_by_id = updated_by_id
            agreement.updated_at = datetime.utcnow()
        else:
            agreement = cls(
                content=content,
                version=1,
                updated_by_id=updated_by_id,
            )
            db.session.add(agreement)
            db.session.flush()

        # Clear all existing acks for this agreement
        WorkingAgreementAck.query.filter_by(agreement_id=agreement.id).delete()

        db.session.commit()

        # Notify all active members
        try:
            from modules.base.core.models.workspace_user import (
                EmployeeStatus,
                WorkspaceUser,
            )
            from modules.base.core.models.notification import SystemNotification

            active_members = (
                WorkspaceUser.scoped()
                .filter_by(status=EmployeeStatus.ACTIVE)
                .all()
            )
            for member in active_members:
                SystemNotification.create(
                    title="Working Agreement Updated",
                    message="The team working agreement has been updated. Please review and acknowledge it.",
                    type="info",
                    target_role="all",
                    user_id=member.user_id,
                    icon="fa-handshake",
                    action_url="/resources/working-agreement/",
                    category="system",
                )
        except Exception:
            pass  # Don't break save if notifications fail

        return agreement


@ModelRegistry.register
class WorkingAgreementAck(db.Model, WorkspaceMixin):
    """Per-user acknowledgment of a working agreement version."""

    __tablename__ = "working_agreement_ack"

    id = db.Column(db.Integer, primary_key=True)
    agreement_id = db.Column(
        db.Integer, db.ForeignKey("working_agreement.id"), nullable=False
    )
    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=False
    )
    version = db.Column(db.Integer, nullable=False)
    acknowledged_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)
    agreement = db.relationship(
        "WorkingAgreement",
        backref=db.backref("acks", lazy="dynamic", cascade="all, delete-orphan"),
        lazy=LAZY,
    )

    __table_args__ = (
        db.UniqueConstraint("agreement_id", "member_id", name="uq_agreement_member"),
    )

    @classmethod
    def acknowledge(cls, agreement_id, member_id, version):
        """Create or update an acknowledgment."""
        ack = cls.scoped().filter_by(
            agreement_id=agreement_id, member_id=member_id
        ).first()
        if ack:
            ack.version = version
            ack.acknowledged_at = datetime.utcnow()
        else:
            ack = cls(
                agreement_id=agreement_id,
                member_id=member_id,
                version=version,
            )
            db.session.add(ack)
        db.session.commit()
        return ack

    @classmethod
    def get_ack_status(cls, agreement_id, version):
        """Return ack status dict with acked_count, total_count, acked_members."""
        from modules.base.core.models.workspace_user import (
            EmployeeStatus,
            WorkspaceUser,
        )

        from sqlalchemy.orm import joinedload

        active_members = (
            WorkspaceUser.scoped()
            .options(joinedload(WorkspaceUser.user))
            .filter_by(status=EmployeeStatus.ACTIVE)
            .all()
        )
        total_count = len(active_members)

        acked = (
            cls.scoped()
            .filter_by(agreement_id=agreement_id, version=version)
            .all()
        )
        acked_member_ids = {a.member_id for a in acked}
        acked_members = [m for m in active_members if m.id in acked_member_ids]

        return {
            "acked_count": len(acked_members),
            "total_count": total_count,
            "acked_members": acked_members,
        }

    @classmethod
    def is_acknowledged(cls, agreement_id, member_id, version):
        """Check if a member has acknowledged a specific version."""
        return (
            cls.scoped()
            .filter_by(
                agreement_id=agreement_id,
                member_id=member_id,
                version=version,
            )
            .first()
            is not None
        )
