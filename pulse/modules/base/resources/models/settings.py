# -----------------------------------------------------------------------------
# sparQ - Resources Settings Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


@ModelRegistry.register
class ResourcesSettings(db.Model, WorkspaceMixin):
    """Singleton settings for Resources module including E-Sign configuration."""

    __tablename__ = "resources_settings"

    id = db.Column(db.Integer, primary_key=True)

    # E-Sign settings
    esign_enabled = db.Column(db.Boolean, default=True)
    esign_default_expiry_days = db.Column(db.Integer, default=30)
    esign_reminder_days = db.Column(db.Integer, default=3)
    esign_company_name = db.Column(db.String(255))

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def scoped(cls) -> "_ScopedQuery":  # noqa: F821
        """Always filter by g.workspace_id — settings belong to a workspace."""
        from flask import g
        from system.db.workspace import _ScopedQuery

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            raise RuntimeError(
                f"{cls.__name__}.scoped() called without workspace context."
            )
        return _ScopedQuery(cls.query.filter_by(workspace_id=workspace_id), cls)

    @classmethod
    def get(cls) -> "ResourcesSettings":
        """Get the settings singleton. Creates one if it doesn't exist."""
        settings = cls.scoped().first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()
        return settings

    @classmethod
    def update_settings(cls, **kwargs) -> "ResourcesSettings":
        """Update settings and return the updated instance."""
        settings = cls.get()
        for key, value in kwargs.items():
            if hasattr(settings, key) and value is not None:
                setattr(settings, key, value)
        db.session.commit()
        return settings

    @classmethod
    def is_esign_enabled(cls) -> bool:
        """Check if e-sign feature is enabled."""
        return cls.get().esign_enabled
