# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Push subscription model for storing browser Web Push subscriptions.
#     Enables mobile push notifications when browser is closed.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


class PushSubscription(db.Model, WorkspaceMixin):
    """Browser push subscription for Web Push notifications."""

    __tablename__ = "push_subscription"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    endpoint = db.Column(db.String(500), unique=True, nullable=False)
    auth_key = db.Column(db.String(100), nullable=False)
    p256dh_key = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = db.relationship("User", backref=db.backref("push_subscriptions", lazy="dynamic"), lazy=LAZY)

    @classmethod
    def create(
        cls,
        user_id: int,
        endpoint: str,
        auth_key: str,
        p256dh_key: str,
    ) -> "PushSubscription":
        """Create or update a push subscription.

        If the endpoint already exists, update the keys and reactivate it.
        Uses unscoped query because browser push endpoints are globally
        unique — the same browser produces the same endpoint regardless
        of workspace.
        """
        from sqlalchemy.exc import IntegrityError

        # Unscoped: endpoint is globally unique per browser, not per workspace
        existing = cls.query.filter_by(endpoint=endpoint).first()
        if existing:
            existing.user_id = user_id
            existing.auth_key = auth_key
            existing.p256dh_key = p256dh_key
            existing.is_active = True
            existing.updated_at = datetime.utcnow()
            db.session.commit()
            return existing

        subscription = cls(
            user_id=user_id,
            endpoint=endpoint,
            auth_key=auth_key,
            p256dh_key=p256dh_key,
        )
        db.session.add(subscription)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = cls.query.filter_by(endpoint=endpoint).first()
            if existing:
                existing.user_id = user_id
                existing.auth_key = auth_key
                existing.p256dh_key = p256dh_key
                existing.is_active = True
                existing.updated_at = datetime.utcnow()
                db.session.commit()
                return existing
            raise
        return subscription

    @classmethod
    def get_active_for_user(cls, user_id: int) -> list["PushSubscription"]:
        """Get all active subscriptions for a user.

        Unscoped: push subscriptions are per-browser, not per-workspace.
        A user's browser has the same endpoint regardless of which
        workspace they're in.
        """
        return cls.query.filter_by(user_id=user_id, is_active=True).all()

    @classmethod
    def deactivate_by_endpoint(cls, endpoint: str) -> bool:
        """Deactivate a subscription by its endpoint."""
        subscription = cls.query.filter_by(endpoint=endpoint).first()
        if subscription:
            subscription.is_active = False
            db.session.commit()
            return True
        return False

    @classmethod
    def delete_by_endpoint(cls, endpoint: str) -> bool:
        """Delete a subscription by its endpoint."""
        subscription = cls.query.filter_by(endpoint=endpoint).first()
        if subscription:
            db.session.delete(subscription)
            db.session.commit()
            return True
        return False

    @classmethod
    def deactivate_by_id(cls, subscription_id: int) -> bool:
        """Deactivate a subscription by its ID.

        Re-fetches from database to ensure clean session state.
        Used by push service when webpush() fails with 404/410.
        """
        subscription = cls.query.get(subscription_id)
        if subscription:
            subscription.is_active = False
            db.session.commit()
            return True
        return False

    def deactivate(self) -> None:
        """Deactivate this subscription (e.g., when push fails)."""
        self.is_active = False
        db.session.commit()

    def to_subscription_info(self) -> dict:
        """Return the subscription info dict for pywebpush."""
        return {
            "endpoint": self.endpoint,
            "keys": {
                "auth": self.auth_key,
                "p256dh": self.p256dh_key,
            },
        }
