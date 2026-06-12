# -----------------------------------------------------------------------------
# sparQ - Signature Recipient Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import secrets
from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class SignatureRecipient(db.Model, WorkspaceMixin):
    """A recipient (signer or viewer) for a signature request."""

    __tablename__ = "signature_recipient"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(
        db.Integer, db.ForeignKey("signature_request.id"), nullable=False
    )

    # Signer info
    email = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="signer")  # signer, viewer
    order = db.Column(db.Integer, default=0)  # For sequential signing

    # Access token (for magic link)
    token = db.Column(db.String(64), unique=True, nullable=False)

    # Status: pending, viewed, signed, declined
    status = db.Column(db.String(20), default="pending")

    # Signature data (filled when signed)
    signed_name = db.Column(db.String(255))
    signed_at = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))

    # Browser/device metadata (JSON) - OS, browser, timezone, screen size, etc.
    device_info = db.Column(db.Text)  # JSON string

    # Geolocation (from browser geolocation API)
    geo_latitude = db.Column(db.Float)
    geo_longitude = db.Column(db.Float)
    geo_accuracy = db.Column(db.Float)  # Accuracy in meters
    geo_location_name = db.Column(db.String(255))  # Human-readable location (optional)

    # Internal user link (optional - if signer is a sparQ user)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    # Notification tracking
    last_notified_at = db.Column(db.DateTime)
    notification_count = db.Column(db.Integer, default=0)

    # Relationships
    user = db.relationship("User", backref=db.backref("signature_recipients", lazy=LAZY), lazy=LAZY)

    @classmethod
    def create(
        cls,
        request_id: int,
        email: str,
        name: str,
        role: str = "signer",
        order: int = 0,
        user_id: int | None = None,
    ) -> "SignatureRecipient":
        """Create a new recipient."""
        recipient = cls(
            request_id=request_id,
            email=email.lower().strip(),
            name=name.strip(),
            role=role,
            order=order,
            token=secrets.token_urlsafe(48),
            user_id=user_id,
        )
        db.session.add(recipient)
        db.session.commit()
        return recipient

    @classmethod
    def get_by_token(cls, token: str) -> "SignatureRecipient | None":
        """Get recipient by access token."""
        return cls.scoped().filter_by(token=token).first()

    @classmethod
    def get_by_id(cls, recipient_id: int) -> "SignatureRecipient | None":
        """Get recipient by ID."""
        return cls.scoped().filter_by(id=recipient_id).first()

    @classmethod
    def set_geo_location_name(cls, recipient_id: int, address: str) -> None:
        """Set the reverse-geocoded location name for a signature recipient.

        Args:
            recipient_id: The ID of the recipient to update.
            address: The human-readable address string.
        """
        recipient = cls.scoped().filter_by(id=recipient_id).first()
        if recipient:
            recipient.geo_location_name = address
            db.session.commit()

    def mark_viewed(self) -> None:
        """Mark recipient as having viewed the document."""
        if self.status == "pending":
            self.status = "viewed"
            db.session.commit()

    def mark_signed(
        self,
        signed_name: str,
        ip_address: str,
        user_agent: str,
        device_info: str | None = None,
        geo_latitude: float | None = None,
        geo_longitude: float | None = None,
        geo_accuracy: float | None = None,
    ) -> None:
        """Mark recipient as having signed."""
        self.status = "signed"
        self.signed_name = signed_name
        self.signed_at = datetime.utcnow()
        self.ip_address = ip_address
        self.user_agent = user_agent[:500] if user_agent else None
        self.device_info = device_info
        self.geo_latitude = geo_latitude
        self.geo_longitude = geo_longitude
        self.geo_accuracy = geo_accuracy
        db.session.commit()

    def mark_declined(self) -> None:
        """Mark recipient as having declined to sign."""
        self.status = "declined"
        db.session.commit()

    def record_notification(self) -> None:
        """Record that a notification was sent."""
        self.last_notified_at = datetime.utcnow()
        self.notification_count += 1
        db.session.commit()

    @property
    def is_signer(self) -> bool:
        """Check if recipient is a signer (not viewer)."""
        return self.role == "signer"

    @property
    def has_signed(self) -> bool:
        """Check if recipient has signed."""
        return self.status == "signed"

    @property
    def can_sign(self) -> bool:
        """Check if recipient can still sign."""
        return self.status in ("pending", "viewed") and self.role == "signer"

    @property
    def device_info_dict(self) -> dict:
        """Get device_info as dictionary."""
        import json

        if self.device_info:
            try:
                return json.loads(self.device_info)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @property
    def has_geolocation(self) -> bool:
        """Check if geolocation data is available."""
        return self.geo_latitude is not None and self.geo_longitude is not None

    @property
    def location_display(self) -> str | None:
        """Get human-readable location string."""
        if self.geo_location_name:
            return self.geo_location_name
        if self.has_geolocation:
            return f"{self.geo_latitude:.4f}, {self.geo_longitude:.4f}"
        return None
