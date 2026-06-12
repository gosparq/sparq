# -----------------------------------------------------------------------------
# sparQ - Sync Module Webhook Model
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import secrets
import string

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateWebhook(db.Model, WorkspaceMixin):
    """Incoming webhook for posting messages to channels or DM threads."""

    __tablename__ = "update_webhook"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    channel_id = db.Column(db.Integer, db.ForeignKey("update_channel.id", ondelete="CASCADE"), nullable=True)
    dm_thread_id = db.Column(db.Integer, db.ForeignKey("dm_thread.id", ondelete="CASCADE"), nullable=True)
    webhook_type = db.Column(db.String(20), nullable=False, default="generic")
    github_secret = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    enable_ten_four = db.Column(db.Boolean, default=False, nullable=False, server_default="0")
    created_by_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (
        db.CheckConstraint(
            "(channel_id IS NOT NULL AND dm_thread_id IS NULL) OR "
            "(channel_id IS NULL AND dm_thread_id IS NOT NULL)",
            name="webhook_target_check",
        ),
    )

    # Relationships
    channel = db.relationship("UpdateChannel", backref=db.backref("webhooks", lazy="dynamic"), lazy=LAZY)
    dm_thread = db.relationship("DMThread", backref=db.backref("webhooks", lazy="dynamic"), lazy=LAZY)
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], lazy=LAZY)

    @staticmethod
    def _generate_token() -> str:
        alphabet = string.ascii_lowercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(8))

    @classmethod
    def create(
        cls,
        created_by_id: int,
        channel_id: int | None = None,
        dm_thread_id: int | None = None,
        github_secret: str | None = None,
        enable_ten_four: bool = False,
    ) -> "UpdateWebhook":
        """Create a new webhook."""
        webhook = cls(
            token=cls._generate_token(),
            channel_id=channel_id,
            dm_thread_id=dm_thread_id,
            github_secret=github_secret,
            enable_ten_four=enable_ten_four,
            created_by_id=created_by_id,
        )
        db.session.add(webhook)
        db.session.commit()
        return webhook

    @classmethod
    def get_by_token(cls, token: str) -> "UpdateWebhook | None":
        """Get webhook by token (global lookup — token is the auth)."""
        return cls.query.filter_by(token=token).first()

    @classmethod
    def get_for_channel(cls, channel_id: int) -> list["UpdateWebhook"]:
        """Get all webhooks for a channel."""
        return cls.scoped().filter_by(channel_id=channel_id).order_by(cls.created_at.desc()).all()

    @classmethod
    def get_for_dm_thread(cls, dm_thread_id: int) -> list["UpdateWebhook"]:
        """Get all webhooks for a DM thread."""
        return cls.scoped().filter_by(dm_thread_id=dm_thread_id).order_by(cls.created_at.desc()).all()

    @classmethod
    def delete_webhook(cls, webhook_id: int) -> bool:
        """Delete a webhook."""
        webhook = cls.scoped().filter_by(id=webhook_id).first()
        if not webhook:
            return False
        db.session.delete(webhook)
        db.session.commit()
        return True

    def regenerate_token(self) -> str:
        """Regenerate the webhook token. Returns new token."""
        self.token = self._generate_token()
        db.session.commit()
        return self.token

    def toggle_ten_four(self) -> bool:
        """Toggle 10-4 acknowledgment. Returns new value."""
        self.enable_ten_four = not self.enable_ten_four
        db.session.commit()
        return self.enable_ten_four
