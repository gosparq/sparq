# -----------------------------------------------------------------------------
# sparQ — API Models
#
# RefreshToken model for JWT refresh token storage. Tokens are stored as
# SHA-256 hashes — raw tokens are never persisted. Supports multi-device
# sessions with per-token revocation.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class RefreshToken(db.Model):
    """Stores hashed refresh tokens for JWT authentication.

    Raw tokens are never stored — only SHA-256 hashes. Each token is
    associated with a user and optionally a device identifier for
    multi-device support.
    """

    __tablename__ = "refresh_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    device_info = db.Column(db.String(255), nullable=True)

    user = db.relationship("User", backref=db.backref("refresh_tokens", lazy="dynamic"), lazy=LAZY)

    @classmethod
    def create_for_user(cls, user_id: int, device_info: str | None = None, expires_days: int = 30) -> str:
        """Create a new refresh token for a user.

        Args:
            user_id: ID of the user.
            device_info: Optional device identifier string.
            expires_days: Token lifetime in days (default 30).

        Returns:
            The raw token string (only returned once, never stored).
        """
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        record = cls(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=expires_days),
            device_info=device_info,
        )
        db.session.add(record)
        db.session.commit()

        return raw_token

    @classmethod
    def verify(cls, raw_token: str) -> "RefreshToken | None":
        """Verify a raw refresh token against stored hashes.

        Args:
            raw_token: The raw token string to verify.

        Returns:
            RefreshToken record if valid, None if invalid/expired/revoked.
        """
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        record = cls.query.filter_by(token_hash=token_hash).first()

        if not record:
            return None
        if record.revoked_at is not None:
            return None

        now = datetime.now(timezone.utc)
        expires = record.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < now:
            return None

        return record

    def revoke(self) -> None:
        """Revoke this refresh token."""
        self.revoked_at = datetime.now(timezone.utc)
        db.session.commit()

    @classmethod
    def revoke_all_for_user(cls, user_id: int) -> int:
        """Revoke all active refresh tokens for a user.

        Args:
            user_id: ID of the user.

        Returns:
            Number of tokens revoked.
        """
        now = datetime.now(timezone.utc)
        tokens = cls.query.filter_by(user_id=user_id).filter(cls.revoked_at.is_(None)).all()
        count = 0
        for token in tokens:
            token.revoked_at = now
            count += 1
        db.session.commit()
        return count

    @classmethod
    def cleanup_expired(cls) -> int:
        """Delete expired and revoked tokens older than 7 days.

        Returns:
            Number of tokens deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        count = cls.query.filter(
            db.or_(
                cls.expires_at < cutoff,
                db.and_(cls.revoked_at.isnot(None), cls.revoked_at < cutoff),
            )
        ).delete()
        db.session.commit()
        return count
