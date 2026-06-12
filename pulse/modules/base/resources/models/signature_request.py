# -----------------------------------------------------------------------------
# sparQ - Signature Request Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Signature request model for electronic document signing.

This module provides the SignatureRequest model for managing e-signature
workflows, tracking document signing status, and handling recipient management.

Example:
    Creating a signature request::

        request = SignatureRequest.create(
            title="Contract Agreement",
            original_attachment_id=attachment.id,
            document_hash=sha256_hash,
            created_by_id=user.id,
            message="Please sign this contract"
        )

    Checking completion status::

        if request.all_signed:
            request.mark_completed(signed_attachment_id)
"""

import uuid as uuid_lib
from datetime import datetime, timedelta

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class SignatureRequest(db.Model, WorkspaceMixin):
    """E-signature request for a document.

    Attributes:
        id: Primary key.
        uuid: Unique identifier for external access (URL-safe).
        title: Title of the signature request.
        message: Optional message to signers.
        original_attachment_id: FK to the original document attachment.
        original_document_hash: SHA-256 hash for document integrity.
        signed_attachment_id: FK to the signed document (after completion).
        status: Workflow status (draft, pending, completed, expired, cancelled).
        created_by_id: FK to the User who created the request.
        created_at: Timestamp when the request was created.
        completed_at: Timestamp when all signatures were collected.
        expires_at: Expiration date for the request.
        context: JSON context data for the calling module.
        callback_url: URL to notify when signing is complete.

    Relationships:
        original_attachment: The document to be signed.
        signed_attachment: The final signed document.
        created_by: The User who initiated the request.
        recipients: Collection of SignatureRecipient records.
        audit_logs: Collection of SignatureAuditLog records.

    Properties:
        is_expired: Whether the request has passed its expiration date.
        all_signed: Whether all required signers have signed.
        pending_recipients: Recipients who haven't signed yet.
        signed_recipients: Recipients who have completed signing.
    """

    __tablename__ = "signature_request"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text)

    # Document references
    original_attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))
    original_document_hash = db.Column(db.String(64), nullable=False)  # SHA-256
    signed_attachment_id = db.Column(db.Integer, db.ForeignKey("attachment.id"))

    # Status: draft, pending, completed, expired, cancelled
    status = db.Column(db.String(20), default="draft")

    # Metadata
    created_by_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    expires_at = db.Column(db.DateTime)

    # Context for calling module (JSON string)
    context = db.Column(db.Text)
    callback_url = db.Column(db.String(255))

    # Relationships
    original_attachment = db.relationship(
        "Attachment",
        foreign_keys=[original_attachment_id],
        backref=db.backref("signature_requests_original", lazy=LAZY),
        lazy=LAZY,
    )
    signed_attachment = db.relationship(
        "Attachment",
        foreign_keys=[signed_attachment_id],
        backref=db.backref("signature_requests_signed", lazy=LAZY),
        lazy=LAZY,
    )
    created_by = db.relationship("WorkspaceUser", backref=db.backref("signature_requests", lazy=LAZY), lazy=LAZY)
    recipients = db.relationship(
        "SignatureRecipient",
        backref=db.backref("request", lazy=LAZY),
        cascade="all, delete-orphan",
        order_by="SignatureRecipient.order",
        lazy=LAZY,
    )
    audit_logs = db.relationship(
        "SignatureAuditLog",
        backref=db.backref("request", lazy=LAZY),
        cascade="all, delete-orphan",
        order_by="SignatureAuditLog.timestamp",
        lazy=LAZY,
    )

    @classmethod
    def create(
        cls,
        title: str,
        original_attachment_id: int,
        document_hash: str,
        created_by_id: int | None = None,
        message: str | None = None,
        context: str | None = None,
        callback_url: str | None = None,
        expires_days: int = 30,
    ) -> "SignatureRequest":
        """Create a new signature request."""
        request = cls(
            uuid=str(uuid_lib.uuid4()),
            title=title,
            message=message,
            original_attachment_id=original_attachment_id,
            original_document_hash=document_hash,
            status="draft",
            created_by_id=created_by_id,
            context=context,
            callback_url=callback_url,
            expires_at=datetime.utcnow() + timedelta(days=expires_days),
        )
        db.session.add(request)
        db.session.commit()
        return request

    @classmethod
    def get_by_id(cls, request_id: int) -> "SignatureRequest | None":
        """Get request by ID."""
        return cls.scoped().filter_by(id=request_id).first()

    @classmethod
    def get_by_uuid(cls, uuid: str) -> "SignatureRequest | None":
        """Get request by UUID."""
        return cls.scoped().filter_by(uuid=uuid).first()

    @classmethod
    def get_all(cls, status: str | None = None) -> list["SignatureRequest"]:
        """Get all requests, optionally filtered by status."""
        query = cls.scoped().order_by(cls.created_at.desc())
        if status:
            query = query.filter_by(status=status)
        return query.all()

    @classmethod
    def get_pending(cls) -> list["SignatureRequest"]:
        """Get all pending requests."""
        return cls.get_all(status="pending")

    def mark_pending(self) -> None:
        """Mark request as pending (sent to signers)."""
        self.status = "pending"
        db.session.commit()

    def mark_completed(self, signed_attachment_id: int) -> None:
        """Mark request as completed with signed document."""
        self.status = "completed"
        self.signed_attachment_id = signed_attachment_id
        self.completed_at = datetime.utcnow()
        db.session.commit()

    def mark_cancelled(self) -> None:
        """Mark request as cancelled."""
        self.status = "cancelled"
        db.session.commit()

    def mark_expired(self) -> None:
        """Mark request as expired."""
        self.status = "expired"
        db.session.commit()

    @property
    def is_expired(self) -> bool:
        """Check if request has expired."""
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return True
        return False

    @property
    def all_signed(self) -> bool:
        """Check if all recipients have signed."""
        signers = [r for r in self.recipients if r.role == "signer"]
        return all(r.status == "signed" for r in signers)

    @property
    def pending_recipients(self) -> list:
        """Get recipients who haven't signed yet."""
        return [r for r in self.recipients if r.status == "pending" and r.role == "signer"]

    @property
    def signed_recipients(self) -> list:
        """Get recipients who have signed."""
        return [r for r in self.recipients if r.status == "signed"]
