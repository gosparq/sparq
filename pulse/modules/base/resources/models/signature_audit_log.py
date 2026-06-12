# -----------------------------------------------------------------------------
# sparQ - Signature Audit Log Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class SignatureAuditLog(db.Model, WorkspaceMixin):
    """Audit trail for signature request events."""

    __tablename__ = "signature_audit_log"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("signature_request.id"), nullable=False
    )

    # Event types: created, sent, viewed, signed, declined, completed, cancelled, downloaded, reminder_sent
    event_type = db.Column(db.String(30), nullable=False)

    # Actor information
    actor_email = db.Column(db.String(255))
    actor_user_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"))
    recipient_id = db.Column(db.Integer, db.ForeignKey("signature_recipient.id"))

    # Request context
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))

    # Additional details (JSON)
    details = db.Column(db.Text)

    # Relationships
    actor = db.relationship("WorkspaceUser", backref=db.backref("signature_audit_logs", lazy=LAZY), lazy=LAZY)
    recipient = db.relationship("SignatureRecipient", backref=db.backref("audit_logs", lazy=LAZY), lazy=LAZY)

    @classmethod
    def log(
        cls,
        request_id: int,
        event_type: str,
        actor_email: str | None = None,
        actor_user_id: int | None = None,
        recipient_id: int | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict | None = None,
    ) -> "SignatureAuditLog":
        """Create an audit log entry."""
        entry = cls(
            request_id=request_id,
            event_type=event_type,
            actor_email=actor_email,
            actor_user_id=actor_user_id,
            recipient_id=recipient_id,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            details=json.dumps(details) if details else None,
        )
        db.session.add(entry)
        db.session.commit()
        return entry

    @classmethod
    def get_for_request(cls, request_id: int) -> list["SignatureAuditLog"]:
        """Get all audit logs for a request."""
        return cls.scoped().filter_by(request_id=request_id).order_by(cls.timestamp).all()

    @property
    def details_dict(self) -> dict:
        """Get details as dictionary."""
        if self.details:
            return json.loads(self.details)
        return {}

    @property
    def event_description(self) -> str:
        """Get human-readable event description."""
        descriptions = {
            "created": "Request created",
            "sent": "Signature request sent",
            "viewed": "Document viewed",
            "signed": "Document signed",
            "declined": "Signature declined",
            "completed": "All signatures collected",
            "cancelled": "Request cancelled",
            "downloaded": "Signed document downloaded",
            "reminder_sent": "Reminder sent",
            "expired": "Request expired",
        }
        return descriptions.get(self.event_type, self.event_type.replace("_", " ").title())
