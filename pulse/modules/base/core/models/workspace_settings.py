# -----------------------------------------------------------------------------
# sparQ - Workspace Settings Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import enum
import json
from datetime import datetime

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin


class Industry(enum.Enum):
    """Industry types for terminology customization"""

    FIELD_SERVICE = "field_service"
    PROFESSIONAL_SERVICES = "professional_services"
    WORKFORCE = "workforce"


@ModelRegistry.register
class WorkspaceSettings(db.Model, WorkspaceMixin, SerializableMixin):
    """Workspace-wide settings (singleton per workspace)"""

    __tablename__ = "workspace_settings"

    _serialize_exclude = {
        'email_password', 'sidebar_config',
    }

    id = db.Column(db.Integer, primary_key=True)

    # Company Details
    company_name = db.Column(db.String(255))

    # Regional Settings
    default_language = db.Column(db.String(5), default="en")
    timezone = db.Column(db.String(50), default="America/Chicago")
    date_format = db.Column(db.String(20), default="MM/DD/YYYY")
    time_format = db.Column(db.String(20), default="12-hour")
    currency = db.Column(db.String(10), default="USD")
    first_day_of_week = db.Column(db.Integer, default=0)  # 0=Sunday, 1=Monday

    # Industry (for terminology customization)
    industry = db.Column(db.Enum(Industry), default=Industry.WORKFORCE)

    # Email Settings (SMTP)
    email_provider = db.Column(db.String(50), nullable=True)  # gmail, sparqmail, etc.
    email_host = db.Column(db.String(255), nullable=True)
    email_port = db.Column(db.Integer, nullable=True, default=587)
    email_username = db.Column(db.String(255), nullable=True)
    email_password = db.Column(db.String(255), nullable=True)  # SMTP password (App Password for Gmail)
    email_from = db.Column(db.String(255), nullable=True)

    # SMS Settings
    sms_provider = db.Column(db.String(50), nullable=True)

    # Onboarding
    onboarding_completed = db.Column(db.Boolean, default=False)

    # Email verification (set True when test email succeeds, reset on settings change)
    email_verified = db.Column(db.Boolean, default=False)

    # Initial setup wizard completed
    setup_completed = db.Column(db.Boolean, default=False)

    # Sidebar configuration (JSON)
    # Format: {"sections": ["sales", "service", ...], "visible": ["sales", "service"]}
    sidebar_config = db.Column(db.Text, nullable=True)

    # Tasks tier label customization (JSON)
    # Format: {"1": "Urgent", "2": "Soon", "3": "Backlog"} — overrides TIER_DEFAULTS labels
    tasks_tier_labels = db.Column(db.JSON, nullable=True)

    # Sync label customization (JSON)
    # Format: {"area": "Area", "weekly_plan": "Weekly Plan"}
    sync_label_config = db.Column(db.JSON, nullable=True)

    # Stale threshold in days (1–30). Items idle longer than this move to On Hold.
    stale_days = db.Column(db.Integer, nullable=False, default=3)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def scoped(cls) -> "_ScopedQuery":  # noqa: F821
        """Always filter by g.workspace_id — settings belong to a workspace.

        Override preserves historical workspace-only scoping so the singleton
        lookup still works under org-first mixin semantics.
        """
        from flask import g
        from system.db.workspace import _ScopedQuery

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            raise RuntimeError(
                f"{cls.__name__}.scoped() called without workspace context."
            )
        return _ScopedQuery(cls.query.filter_by(workspace_id=workspace_id), cls)

    @classmethod
    def get_instance(cls):
        """Get the singleton workspace settings instance (creates if not exists)."""
        from flask import g
        ts_id = getattr(g, "workspace_id", None)
        try:
            cache = getattr(g, "_workspace_settings_cache", None)
            if cache is None:
                cache = {}
                g._workspace_settings_cache = cache
            if ts_id in cache:
                return cache[ts_id]
        except Exception:
            cache = None

        settings = cls.scoped().first()
        if not settings:
            settings = cls()
            db.session.add(settings)
            db.session.commit()

        if cache is not None:
            cache[ts_id] = settings
        return settings

    def update(self, **kwargs):
        """Update settings fields"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        db.session.commit()
        return self

    def complete_setup(self, timezone: str = "America/Chicago") -> None:
        """Mark initial setup as completed and apply timezone."""
        self.timezone = timezone
        self.setup_completed = True
        db.session.commit()

    def get_sidebar_config(self):
        """Get sidebar configuration as dict"""
        if self.sidebar_config:
            return json.loads(self.sidebar_config)
        return None  # Use defaults when None

    def set_sidebar_config(self, config):
        """Set sidebar configuration from dict"""
        self.sidebar_config = json.dumps(config)
        db.session.commit()

    def get_pinned_modules(self):
        """Get list of modules pinned to sidebar. Returns default if not configured."""
        from system.nav.sections import get_default_pinned_modules

        config = self.get_sidebar_config()
        if config and "pinned_modules" in config:
            return config["pinned_modules"]
        return get_default_pinned_modules()

    def is_module_pinned(self, module_id):
        """Check if a module is pinned to the sidebar."""
        return module_id in self.get_pinned_modules()

    def pin_module(self, module_id):
        """Pin a module to the sidebar."""
        config = self.get_sidebar_config() or {}
        pinned = config.get("pinned_modules", self.get_pinned_modules())
        if module_id not in pinned:
            pinned.append(module_id)
            config["pinned_modules"] = pinned
            self.set_sidebar_config(config)
        return pinned

    def unpin_module(self, module_id):
        """Unpin a module from the sidebar."""
        config = self.get_sidebar_config() or {}
        pinned = config.get("pinned_modules", self.get_pinned_modules())
        if module_id in pinned:
            pinned.remove(module_id)
            config["pinned_modules"] = pinned
            self.set_sidebar_config(config)
        return pinned

    def get_area_label(self):
        """Get the display label for Areas (default 'Area')."""
        config = self.sync_label_config or {}
        return config.get("area", "Area")

    def get_weekly_plan_label(self):
        """Get the display label for Weekly Plans (default 'Weekly Plan')."""
        config = self.sync_label_config or {}
        return config.get("weekly_plan", "Weekly Plan")

    def update_sync_labels(self, area_label="Area", weekly_plan_label="Weekly Plan"):
        """Update the display labels for Areas and Weekly Plans.

        Args:
            area_label: Display label for Areas.
            weekly_plan_label: Display label for Weekly Plans.
        """
        self.sync_label_config = {
            "area": area_label or "Area",
            "weekly_plan": weekly_plan_label or "Weekly Plan",
        }
        db.session.commit()
