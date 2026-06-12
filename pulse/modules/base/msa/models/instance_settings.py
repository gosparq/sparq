# -----------------------------------------------------------------------------
# sparQ - Instance Settings Model
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Server-wide instance settings (singleton, no tenant scoping).

Stores configuration that applies to the entire sparQ instance,
such as email/SMTP settings. Not tied to any workspace or organization.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.oauth.token_manager import TokenManager

_EMAIL_FIELDS = {
    "email_provider",
    "email_host",
    "email_port",
    "email_username",
    "email_password",
    "email_from",
    "email_use_tls",
}

_ENV_VAR_MAP = {
    "email_host": "SMTP_HOST",
    "email_port": "SMTP_PORT",
    "email_username": "SMTP_USERNAME",
    "email_password": "SMTP_PASSWORD",
    "email_from": "SMTP_FROM_EMAIL",
    "email_provider": "SMTP_PROVIDER",
}


@ModelRegistry.register
class InstanceSettings(db.Model):
    """Server-wide instance settings (singleton)."""

    __tablename__ = "instance_settings"

    id = db.Column(db.Integer, primary_key=True)

    # Email / SMTP
    email_provider = db.Column(db.String(50), nullable=True)
    email_host = db.Column(db.String(255), nullable=True)
    email_port = db.Column(db.Integer, nullable=True, default=587)
    email_username = db.Column(db.String(255), nullable=True)
    email_password = db.Column(db.String(255), nullable=True)
    email_from = db.Column(db.String(255), nullable=True)
    email_use_tls = db.Column(db.Boolean, default=True)
    email_verified = db.Column(db.Boolean, default=False)

    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @classmethod
    def get_instance(cls) -> InstanceSettings:
        """Return the singleton row, creating it if absent."""
        instance = cls.query.first()
        if not instance:
            instance = cls()
            db.session.add(instance)
            db.session.commit()
        return instance

    def update(self, **kwargs: Any) -> InstanceSettings:
        """Update fields. Resets email_verified when email config changes."""
        email_changed = False
        for k, v in kwargs.items():
            if k not in _EMAIL_FIELDS:
                continue
            if k == "email_password":
                if v:
                    email_changed = True
            elif getattr(self, k) != v:
                email_changed = True

        for key, value in kwargs.items():
            if not hasattr(self, key):
                continue
            if key == "email_password" and value:
                value = TokenManager.encrypt(value)
            setattr(self, key, value)

        if email_changed and "email_verified" not in kwargs:
            self.email_verified = False
        db.session.commit()
        return self

    def get_email_password(self) -> str:
        """Return decrypted email password."""
        if not self.email_password:
            return ""
        return TokenManager.decrypt(self.email_password)

    def is_email_configured(self) -> bool:
        """True if minimum SMTP fields are populated (or overridden by env)."""
        host = os.environ.get("SMTP_HOST") or self.email_host
        password = os.environ.get("SMTP_PASSWORD") or self.email_password
        return bool(host and password)

    @classmethod
    def get_env_overrides(cls) -> dict[str, bool]:
        """Return which email fields are overridden by environment variables."""
        return {
            field: bool(os.environ.get(env_var))
            for field, env_var in _ENV_VAR_MAP.items()
        }

    @classmethod
    def any_env_overrides(cls) -> bool:
        """True if any SMTP environment variables are set."""
        return any(os.environ.get(v) for v in _ENV_VAR_MAP.values())
