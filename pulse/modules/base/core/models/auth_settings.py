# -----------------------------------------------------------------------------
# sparQ - Authentication Settings Model
#
# Description:
#     Singleton model for system-wide authentication configuration including
#     passwordless login (Magic Link, SMS), local authentication, and
#     OAuth provider settings for future API integrations (Google Drive, etc.).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os
from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class AuthSettings(db.Model, WorkspaceMixin):
    """System-wide authentication settings (singleton - one row)."""

    __tablename__ = "auth_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Local authentication (email/password) — disabled by default
    local_auth_enabled = db.Column(db.Boolean, default=False)

    # Passwordless authentication
    magic_link_enabled = db.Column(db.Boolean, default=True)
    sms_enabled = db.Column(db.Boolean, default=False)

    # Google OAuth (for API integrations like Google Drive)
    google_enabled = db.Column(db.Boolean, default=False)
    google_client_id = db.Column(db.String(255), nullable=True)
    google_client_secret = db.Column(db.Text, nullable=True)  # Encrypted

    # Cloud Storage Integrations
    google_drive_enabled = db.Column(db.Boolean, default=False)

    # Microsoft OAuth
    microsoft_enabled = db.Column(db.Boolean, default=False)
    microsoft_client_id = db.Column(db.String(255), nullable=True)
    microsoft_client_secret = db.Column(db.Text, nullable=True)  # Encrypted

    # GitHub OAuth
    github_enabled = db.Column(db.Boolean, default=False)
    github_client_id = db.Column(db.String(255), nullable=True)
    github_client_secret = db.Column(db.Text, nullable=True)  # Encrypted

    # LinkedIn OAuth
    linkedin_enabled = db.Column(db.Boolean, default=False)
    linkedin_client_id = db.Column(db.String(255), nullable=True)
    linkedin_client_secret = db.Column(db.Text, nullable=True)  # Encrypted

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def scoped(cls) -> "_ScopedQuery":  # noqa: F821
        """Always filter by g.workspace_id — auth settings belong to a workspace."""
        from flask import g
        from system.db.workspace import _ScopedQuery

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            raise RuntimeError(
                f"{cls.__name__}.scoped() called without workspace context."
            )
        return _ScopedQuery(cls.query.filter_by(workspace_id=workspace_id), cls)

    @classmethod
    def get_instance(cls) -> "AuthSettings":
        """Get the singleton auth settings instance (creates if not exists)."""
        from flask import g

        ts_id = getattr(g, "workspace_id", None)
        try:
            cache = getattr(g, "_auth_settings_cache", None)
            if cache is None:
                cache = {}
                g._auth_settings_cache = cache
            if ts_id in cache:
                return cache[ts_id]
        except Exception:
            cache = None

        settings = cls.scoped().first()
        if not settings:
            settings = cls()
            if os.environ.get("SPARQ_AUTH_LOCAL_DISABLED", "").lower() == "true":
                settings.local_auth_enabled = False
            db.session.add(settings)
            db.session.commit()

        if cache is not None:
            cache[ts_id] = settings
        return settings

    def should_use_password_login(self) -> bool:
        """Check if password login should be available.

        Returns True when: debug mode, local auth explicitly enabled,
        or email is not configured (password is the only login option).
        """
        from flask import current_app

        if current_app.debug or self.local_auth_enabled:
            return True
        from system.email.service import is_configured
        return not is_configured()

    def update(self, **kwargs) -> "AuthSettings":
        """Update settings fields."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def is_provider_enabled(self, provider: str) -> bool:
        """Check if a specific OAuth provider is enabled.

        Args:
            provider: Provider name (google, microsoft, github, linkedin)

        Returns:
            True if the provider is enabled
        """
        attr_name = f"{provider.lower()}_enabled"
        return getattr(self, attr_name, False)

    def get_provider_credentials(self, provider: str) -> tuple[str | None, str | None]:
        """Get client ID and secret for a provider.

        Note: This returns the encrypted secret. Use TokenManager to decrypt.

        Args:
            provider: Provider name

        Returns:
            Tuple of (client_id, client_secret_encrypted)
        """
        provider = provider.lower()
        client_id = getattr(self, f"{provider}_client_id", None)
        client_secret = getattr(self, f"{provider}_client_secret", None)
        return client_id, client_secret

    def set_provider_credentials(
        self, provider: str, client_id: str, client_secret_encrypted: str
    ) -> None:
        """Set client ID and secret for a provider.

        Args:
            provider: Provider name
            client_id: OAuth client ID
            client_secret_encrypted: Pre-encrypted client secret
        """
        provider = provider.lower()
        setattr(self, f"{provider}_client_id", client_id)
        setattr(self, f"{provider}_client_secret", client_secret_encrypted)
        db.session.commit()

    def get_enabled_providers(self) -> list[str]:
        """Get list of enabled OAuth provider names.

        Returns:
            List of provider names that are enabled
        """
        providers = []
        for provider in ["google", "microsoft", "github", "linkedin"]:
            if self.is_provider_enabled(provider):
                providers.append(provider)
        return providers

    def has_any_oauth_enabled(self) -> bool:
        """Check if any OAuth provider is enabled.

        Returns:
            True if at least one OAuth provider is enabled
        """
        return len(self.get_enabled_providers()) > 0

    def is_any_auth_enabled(self) -> bool:
        """Check if any authentication method is enabled.

        Returns:
            True if local auth, magic link, SMS, or any OAuth is enabled
        """
        return (
            self.local_auth_enabled
            or self.magic_link_enabled
            or self.sms_enabled
            or self.has_any_oauth_enabled()
        )
