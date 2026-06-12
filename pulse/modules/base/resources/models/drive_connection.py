# -----------------------------------------------------------------------------
# sparQ - Drive Connection Model
#
# Description:
#     Stores OAuth connections to cloud storage providers (Google Drive, OneDrive).
#     One connection per workspace - business admin connects their account and selects
#     folders to share with all users.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import json
from datetime import datetime, timezone

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class DriveConnection(db.Model, WorkspaceMixin):
    """Cloud storage connection (Google Drive, OneDrive)."""

    __tablename__ = "drive_connection"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(20), nullable=False)  # "google" or "onedrive"
    connected_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # OAuth tokens (encrypted)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)

    # Email of the connected Google/Microsoft account
    connected_email = db.Column(db.String(255), nullable=True)

    # Selected folders to expose (JSON array of folder objects: [{id, name}, ...])
    selected_folders = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    connected_by = db.relationship("User", backref=db.backref("drive_connections", lazy="dynamic"), lazy=LAZY)

    # Only one connection per provider
    __table_args__ = (db.UniqueConstraint("provider", name="uq_drive_connection_provider"),)

    @classmethod
    def get_by_provider(cls, provider: str) -> "DriveConnection | None":
        """Get connection for a provider (singleton per provider)."""
        return cls.scoped().filter_by(provider=provider.lower()).first()

    @classmethod
    def get_google(cls) -> "DriveConnection | None":
        """Get Google Drive connection."""
        return cls.get_by_provider("google")

    @classmethod
    def create(
        cls,
        provider: str,
        connected_by_id: int,
        access_token: str,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
        connected_email: str | None = None,
    ) -> "DriveConnection":
        """Create a new drive connection."""
        connection = cls(
            provider=provider.lower(),
            connected_by_id=connected_by_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_expires_at=token_expires_at,
            connected_email=connected_email,
        )
        db.session.add(connection)
        db.session.commit()
        return connection

    def update_tokens(
        self,
        access_token: str,
        refresh_token: str | None = None,
        token_expires_at: datetime | None = None,
    ) -> "DriveConnection":
        """Update OAuth tokens."""
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if token_expires_at:
            self.token_expires_at = token_expires_at
        db.session.commit()
        return self

    def is_token_expired(self, buffer_minutes: int = 5) -> bool:
        """Check if access token is expired (with buffer).

        Args:
            buffer_minutes: Consider expired if within this many minutes of expiry

        Returns:
            True if token is expired or will expire soon
        """
        if not self.token_expires_at:
            return False

        from datetime import timedelta

        now = datetime.now(timezone.utc)
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now >= (expires - timedelta(minutes=buffer_minutes))

    def get_selected_folders(self) -> list[dict]:
        """Get list of selected folder objects.

        Returns:
            List of dicts with 'id' and 'name' keys
        """
        if not self.selected_folders:
            return []
        try:
            return json.loads(self.selected_folders)
        except json.JSONDecodeError:
            return []

    def set_selected_folders(self, folders: list[dict]) -> "DriveConnection":
        """Set selected folders.

        Args:
            folders: List of folder dicts with 'id' and 'name' keys
        """
        self.selected_folders = json.dumps(folders)
        db.session.commit()
        return self

    def get_selected_folder_ids(self) -> list[str]:
        """Get list of selected folder IDs only."""
        return [f.get("id") for f in self.get_selected_folders() if f.get("id")]

    def disconnect(self) -> None:
        """Delete this connection."""
        db.session.delete(self)
        db.session.commit()
