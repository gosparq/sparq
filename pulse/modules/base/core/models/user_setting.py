# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     User-specific settings model for preferences.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from datetime import datetime

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UserSetting(db.Model, WorkspaceMixin):
    """User settings model"""

    __tablename__ = "user_setting"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Create a composite unique constraint on user_id and key
    __table_args__ = (db.UniqueConstraint("user_id", "key", name="_user_setting_uc"),)

    # Relationship to User model
    user = db.relationship("User", backref=db.backref("settings", lazy=LAZY), lazy=LAZY)

    @staticmethod
    def get(user_id, key, default=None):
        from flask import g
        ts_id = getattr(g, "workspace_id", None)
        cache_key = (ts_id, user_id, key)
        try:
            cache = getattr(g, "_user_setting_cache", None)
            if cache is None:
                cache = {}
                g._user_setting_cache = cache
            if cache_key in cache:
                cached = cache[cache_key]
                return cached.value if cached else default
        except Exception:
            cache = None

        setting = UserSetting.scoped().filter_by(user_id=user_id, key=key).first()

        if cache is not None:
            cache[cache_key] = setting
        return setting.value if setting else default

    @classmethod
    def get_bulk(cls, user_ids, key, default=None):
        """Get a setting value for multiple users at once.

        Args:
            user_ids: List of user IDs to query.
            key: The setting key.
            default: Default value for users without the setting.

        Returns:
            Dict mapping user_id to setting value.
        """
        if not user_ids:
            return {}
        settings = cls.scoped().filter(
            cls.user_id.in_(user_ids),
            cls.key == key,
        ).all()
        result = {uid: default for uid in user_ids}
        for s in settings:
            result[s.user_id] = s.value
        return result

    @staticmethod
    def set(user_id, key, value):
        # Unique constraint is (user_id, key) — bypass the session-level tenant
        # filter so we always find the existing row regardless of which org/
        # workspace originally created it.
        setting = (
            UserSetting.query
            .execution_options(skip_tenant_filter=True)
            .filter_by(user_id=user_id, key=key)
            .first()
        )
        if setting:
            setting.value = value
            from flask import g
            org_id = getattr(g, "organization_id", None)
            ts_id = getattr(g, "workspace_id", None)
            if org_id and setting.organization_id != org_id:
                setting.organization_id = org_id
            if ts_id and setting.workspace_id != ts_id:
                setting.workspace_id = ts_id
        else:
            setting = UserSetting(user_id=user_id, key=key, value=value)
            db.session.add(setting)
        db.session.commit()
