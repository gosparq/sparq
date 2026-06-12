# -----------------------------------------------------------------------------
# sparQ - OAuth Connection Model
#
# Description:
#     Stores OAuth connections between users and identity providers.
#     Each connection stores encrypted access/refresh tokens for future
#     API access (e.g., Google Drive, OneDrive integration).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

if TYPE_CHECKING:
    from modules.base.core.models.workspace_user import WorkspaceUser


@ModelRegistry.register
class OAuthConnection(db.Model, WorkspaceMixin):
    """User's OAuth connection to an identity provider."""

    __tablename__ = "oauth_connection"

    id = db.Column(db.Integer, primary_key=True)

    # Link to user
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Provider info
    provider = db.Column(db.String(50), nullable=False)  # google, microsoft, github, linkedin
    provider_user_id = db.Column(db.String(255), nullable=False)  # User's ID at provider
    email = db.Column(db.String(255), nullable=True)  # Email from provider

    # Tokens (encrypted)
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_type = db.Column(db.String(50), default="Bearer")
    token_expires_at = db.Column(db.DateTime, nullable=True)

    # Granted scopes
    scopes = db.Column(db.String(500), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = db.relationship("User", backref=db.backref("oauth_connections", lazy="dynamic"), lazy=LAZY)

    # Constraints
    __table_args__ = (
        db.UniqueConstraint("user_id", "provider", name="uq_user_provider"),
        db.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user_id"),
        db.Index("ix_oauth_provider", "provider"),
    )

    @classmethod
    def get_by_provider_user(
        cls, provider: str, provider_user_id: str
    ) -> Optional["OAuthConnection"]:
        """Find connection by provider and provider's user ID.

        Args:
            provider: Provider name (e.g., 'google')
            provider_user_id: User's ID at the provider

        Returns:
            OAuthConnection or None
        """
        return cls.scoped().filter_by(
            provider=provider.lower(), provider_user_id=str(provider_user_id)
        ).first()

    @classmethod
    def get_by_user_and_provider(
        cls, user_id: int, provider: str
    ) -> Optional["OAuthConnection"]:
        """Find connection for a user and provider.

        Args:
            user_id: User's ID
            provider: Provider name

        Returns:
            OAuthConnection or None
        """
        return cls.scoped().filter_by(user_id=user_id, provider=provider.lower()).first()

    @classmethod
    def get_user_connections(cls, user_id: int) -> list["OAuthConnection"]:
        """Get all OAuth connections for a user.

        Args:
            user_id: User's ID

        Returns:
            List of OAuthConnection objects
        """
        return cls.scoped().filter_by(user_id=user_id).all()

    @classmethod
    def create_or_update(
        cls,
        user_id: int,
        provider: str,
        provider_user_id: str,
        email: Optional[str] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
        scopes: Optional[str] = None,
    ) -> "OAuthConnection":
        """Create or update an OAuth connection.

        Args:
            user_id: User's ID
            provider: Provider name
            provider_user_id: User's ID at provider
            email: Email from provider
            access_token: Encrypted access token
            refresh_token: Encrypted refresh token
            token_expires_at: Token expiration time
            scopes: Granted scopes

        Returns:
            Created or updated OAuthConnection
        """
        provider = provider.lower()
        connection = cls.get_by_user_and_provider(user_id, provider)

        if connection:
            # Update existing
            connection.provider_user_id = str(provider_user_id)
            if email:
                connection.email = email
            if access_token:
                connection.access_token = access_token
            if refresh_token:
                connection.refresh_token = refresh_token
            if token_expires_at:
                connection.token_expires_at = token_expires_at
            if scopes:
                connection.scopes = scopes
        else:
            # Create new
            connection = cls(
                user_id=user_id,
                provider=provider,
                provider_user_id=str(provider_user_id),
                email=email,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                scopes=scopes,
            )
            db.session.add(connection)

        db.session.commit()
        return connection

    # ── GitHub identity mapping (token-less) ────────────────────────────────
    # Maps a GitHub account to a sparQ user by the immutable GitHub numeric id,
    # without an OAuth flow. Used by the PAT-based GitHub integration so repo
    # activity and assignee sync can resolve "who did this" to a member. These
    # rows carry no token — only (user_id, provider="github", provider_user_id).

    @classmethod
    def set_github_mapping(cls, github_user_id: "str | int", user_id: int) -> "OAuthConnection":
        """Map a GitHub account to a sparQ user (admin- or self-assigned).

        Reassigns the GitHub account away from any other user first, so a
        self-override moves the identity cleanly. ``create_or_update`` cannot do
        this — keyed on (user_id, provider), it would try to insert a duplicate
        and violate the (provider, provider_user_id) unique constraint.

        Args:
            github_user_id: GitHub numeric user id (immutable, rename-proof).
            user_id: sparQ ``user.id`` to map the GitHub account to.

        Returns:
            The created or updated OAuthConnection row.
        """
        gid = str(github_user_id)

        # Detach this GitHub account from whoever currently holds it.
        existing = cls.query.filter_by(provider="github", provider_user_id=gid).first()
        if existing and existing.user_id != user_id:
            db.session.delete(existing)
            db.session.flush()

        # Upsert the target user's GitHub row (one github per user).
        row = cls.query.filter_by(user_id=user_id, provider="github").first()
        if row:
            row.provider_user_id = gid
        else:
            row = cls(user_id=user_id, provider="github", provider_user_id=gid)
            db.session.add(row)
        db.session.commit()
        return row

    @classmethod
    def clear_github_mapping(cls, github_user_id: "str | int") -> None:
        """Remove the mapping for a GitHub account, if one exists.

        Args:
            github_user_id: GitHub numeric user id.
        """
        gid = str(github_user_id)
        row = cls.query.filter_by(provider="github", provider_user_id=gid).first()
        if row:
            db.session.delete(row)
            db.session.commit()

    @classmethod
    def get_member_for_github_id(cls, github_user_id: "str | int") -> "WorkspaceUser | None":
        """Resolve a GitHub numeric user id to a WorkspaceUser in the current workspace.

        Args:
            github_user_id: GitHub numeric user id from a webhook payload.

        Returns:
            The WorkspaceUser for the current workspace, or None if unmapped.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser

        gid = str(github_user_id)
        row = cls.query.filter_by(provider="github", provider_user_id=gid).first()
        if not row:
            return None
        return WorkspaceUser.scoped().filter_by(user_id=row.user_id).first()

    @classmethod
    def github_mappings_for_workspace(cls) -> "dict[str, WorkspaceUser]":
        """Return ``{github_user_id: WorkspaceUser}`` for the current workspace.

        Used to render the admin mapping table against the live collaborator
        roster, matched by GitHub numeric id.

        Returns:
            Dict of GitHub numeric id (str) → WorkspaceUser.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser

        result: "dict[str, WorkspaceUser]" = {}
        for row in cls.query.filter_by(provider="github").all():
            member = WorkspaceUser.scoped().filter_by(user_id=row.user_id).first()
            if member:
                result[str(row.provider_user_id)] = member
        return result

    def update_tokens(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        token_expires_at: Optional[datetime] = None,
    ) -> None:
        """Update tokens for this connection.

        Args:
            access_token: New encrypted access token
            refresh_token: New encrypted refresh token (optional)
            token_expires_at: New expiration time (optional)
        """
        self.access_token = access_token
        if refresh_token:
            self.refresh_token = refresh_token
        if token_expires_at:
            self.token_expires_at = token_expires_at
        db.session.commit()

    def is_token_expired(self, buffer_minutes: int = 5) -> bool:
        """Check if the access token is expired or will expire soon.

        Args:
            buffer_minutes: Consider expired if within this many minutes

        Returns:
            True if token is expired or expiring soon
        """
        if not self.token_expires_at:
            return False  # No expiry means doesn't expire

        from datetime import timedelta

        now = datetime.now(timezone.utc)
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        buffer = timedelta(minutes=buffer_minutes)
        return now + buffer >= expires

    def delete(self) -> None:
        """Delete this OAuth connection."""
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def count_by_provider(cls, provider: str) -> int:
        """Count connections for a provider.

        Args:
            provider: Provider name

        Returns:
            Number of connections
        """
        return cls.scoped().filter_by(provider=provider.lower()).count()

    def __repr__(self) -> str:
        return f"<OAuthConnection {self.provider}:{self.user_id}>"
