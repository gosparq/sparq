# -----------------------------------------------------------------------------
# sparQ - UpdateTemplate Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdateTemplate model — defines post types for updates, wins, and pulse.

Templates drive the secondary nav and the post creation forms. Built-in
templates have workspace_id=NULL (available to all workspaces). Custom
templates are scoped to a single workspace.

Classes:
    UpdateTemplate: Template definition model.
"""

import json
from datetime import datetime

from flask import g
from sqlalchemy import or_

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class UpdateTemplate(db.Model):
    """Template for update posts (updates, wins, pulse, generic posts).

    Attributes:
        workspace_id: NULL for built-in, UUID for custom templates.
        post_type: 'update', 'win', or 'board'.
        name: Display name.
        description: Short description.
        fields: JSON array of field definitions.
        anonymous: Whether posts hide member_id.
        nudge_enabled: Whether to send nudge notifications.
        nudge_time: Time of day for nudge (HH:MM).
        nudge_scope: JSON scope restricting when nudges fire.
            Format: {"start": "HH:MM", "end": "HH:MM", "days": [0-6]}.
            Days use Python weekday(): 0=Mon, 6=Sun. NULL = always active.
        schedule_type: 'daily' or 'periodic' (NULL = no scheduled nudge).
        interval_minutes: Minutes between periodic nudges.
        grace_minutes: Minutes after nudge_time before daily reminder fires.
        is_active: Whether template is available for new posts.
        sort_order: Display order within post_type.
    """

    __tablename__ = "update_template"

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Uuid, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True
    )

    post_type = db.Column(db.String(50), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)

    _fields = db.Column("fields", db.JSON, nullable=False, default=list)

    @property
    def fields(self):
        """Return fields as a list of dicts, auto-deserializing if double-serialized."""
        val = self._fields
        if isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                val = []
        return val if isinstance(val, list) else []

    @fields.setter
    def fields(self, value):
        self._fields = value

    anonymous = db.Column(db.Boolean, default=False)
    nudge_enabled = db.Column(db.Boolean, default=False)
    nudge_time = db.Column(db.String(5), default="17:00")

    schedule_type = db.Column(db.String(10), nullable=True)
    interval_minutes = db.Column(db.Integer, nullable=True)
    grace_minutes = db.Column(db.Integer, default=30)

    _nudge_scope = db.Column("nudge_scope", db.JSON, nullable=True)

    @property
    def nudge_scope(self):
        """Return nudge scope as a dict, with defaults for missing keys.

        Format: {"start": "HH:MM", "end": "HH:MM", "days": [0-6]}
        Days use Python weekday() convention: 0=Monday, 6=Sunday.
        None means always active (no scope restriction).
        """
        val = self._nudge_scope
        if val is None:
            return None
        if isinstance(val, str):
            try:
                import json as _json
                val = _json.loads(val)
            except (ValueError, TypeError):
                return None
        if not isinstance(val, dict):
            return None
        return {
            "start": val.get("start", "08:00"),
            "end": val.get("end", "18:00"),
            "days": val.get("days", [0, 1, 2, 3, 4]),
        }

    @nudge_scope.setter
    def nudge_scope(self, value):
        self._nudge_scope = value

    nudge_anchor = db.Column(db.String(10), nullable=True, default="start")

    is_active = db.Column(db.Boolean, default=True)
    sort_order = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    posts = db.relationship("UpdatePost", backref=db.backref("template", lazy=LAZY), lazy="dynamic")

    @classmethod
    def get_for_workspace(cls, post_type=None):
        """Get templates available to the current workspace.

        Returns built-in (workspace_id=NULL) and custom templates.

        Args:
            post_type: Optional filter by post_type.
        """
        # Per-request memoization keyed by (workspace_id, post_type). Multiple
        # context processors and the feed controller all call this with the
        # same args; without a cache one page render issues 6+ identical
        # queries for the update/win/board template lists.
        cache_key = (getattr(g, "workspace_id", None), post_type)
        try:
            cache = getattr(g, "_update_template_cache", None)
            if cache is None:
                cache = {}
                g._update_template_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        query = cls.query.filter(
            or_(
                cls.workspace_id == g.workspace_id,
                cls.workspace_id.is_(None),
            ),
            cls.is_active.is_(True),
        )
        if post_type:
            query = query.filter(cls.post_type == post_type)
        result = query.order_by(cls.sort_order, cls.name).all()
        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def get_by_id(cls, template_id):
        """Get template by ID, scoped to current workspace or built-in."""
        return cls.query.filter(
            cls.id == template_id,
            or_(
                cls.workspace_id == g.workspace_id,
                cls.workspace_id.is_(None),
            ),
        ).first()

    @classmethod
    def get_by_name(cls, name, post_type=None):
        """Get template by name, scoped to current workspace or built-in.

        Built-in templates (workspace_id=NULL) are always included. Custom
        templates are filtered to the current workspace. If both a custom
        and a built-in template match, the custom one is preferred.

        Args:
            name: Template name to match exactly.
            post_type: Optional filter by post_type.

        Returns:
            UpdateTemplate instance, or None if not found.
        """
        cache_key = ("by_name", getattr(g, "workspace_id", None), name, post_type)
        try:
            cache = getattr(g, "_update_template_cache", None)
            if cache is None:
                cache = {}
                g._update_template_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        query = cls.query.filter(
            cls.name == name,
            or_(
                cls.workspace_id == g.workspace_id,
                cls.workspace_id.is_(None),
            ),
        )
        if post_type:
            query = query.filter(cls.post_type == post_type)
        # Prefer custom (non-NULL workspace_id) over built-in (NULL).
        result = query.order_by(cls.workspace_id.desc().nullslast()).first()

        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def seed_builtin_templates(cls):
        """Seed built-in templates with workspace_id=NULL.

        Idempotent — skips if templates already exist.
        """
        existing = cls.query.filter(cls.workspace_id.is_(None)).count()
        if existing > 0:
            return

        templates = [
            # Updates
            {
                "post_type": "update",
                "name": "Current",
                "description": "What are you focused on right now?",
                "fields": [
                    {"key": "body", "label": "Current", "type": "structured_list", "required": True, "placeholder": "What are you focused on?"},
                    {"key": "focus", "label": "Focus", "type": "choice", "required": False, "options": ["focus", "available"]},
                    {"key": "progress", "label": "Progress", "type": "choice", "required": False, "options": ["on_track", "off_track"]},
                ],
                "nudge_enabled": True,
                "nudge_time": "17:00",
                "nudge_scope": {"start": "08:00", "end": "18:00", "days": [0, 1, 2, 3, 4]},
                "schedule_type": "periodic",
                "interval_minutes": 120,
                "nudge_anchor": "start",
                "sort_order": 0,
            },
            {
                "post_type": "update",
                "name": "Standup",
                "description": "What's on your mind for today's work?",
                "fields": [
                    {
                        "key": "body",
                        "label": "What's on your mind for today's work?",
                        "type": "text_audio",
                        "required": True,
                        "placeholders": [
                            "Website relaunch is the main thing today. Still working through the CMS structure — expect clarity by afternoon. Nothing blocking me but may need to loop in Jackson on the taxonomy question.",
                            "Heads down on the GitHub integration this morning. The facade pattern is close — if it lands by noon the rest of the integrations get much easier. No blockers but keeping an eye on the API rate limit behavior.",
                            "Bit of a mixed bag today — finishing the spec review from yesterday, then switching to onboarding docs. Feeling good about the week overall. Might need a quick sync with Sara on the pricing copy before EOD.",
                        ],
                    },
                    {"key": "blockers", "label": "Any blockers?", "type": "structured_list", "blocker": True, "required": False, "placeholder": "Anything slowing you down?"},
                ],
                "nudge_enabled": True,
                "nudge_time": "09:00",
                "nudge_scope": {"start": "08:00", "end": "18:00", "days": [0, 1, 2, 3, 4]},
                "schedule_type": "daily",
                "grace_minutes": 30,
                "nudge_anchor": "start",
                "sort_order": 1,
            },
            {
                "post_type": "update",
                "name": "Async - End of Day (EOD)",
                "description": "End of day — what you shipped, what's rolling, optional shoutout",
                "fields": [
                    {"key": "shipped", "label": "What I shipped today", "type": "structured_list", "no_tasks": True, "required": True, "placeholder": "What did you get done?"},
                    {"key": "rolling", "label": "Rolling to tomorrow", "type": "text", "required": False, "placeholder": "What carries over?"},
                    {"key": "shoutout", "label": "Shoutout", "type": "text", "required": False, "placeholder": "Recognize someone who helped..."},
                    {"key": "focus", "label": "Focus", "type": "choice", "required": False, "options": ["focus", "available"]},
                    {"key": "progress", "label": "Progress", "type": "choice", "required": False, "options": ["on_track", "off_track"]},
                ],
                "nudge_enabled": True,
                "nudge_time": "17:00",
                "nudge_scope": {"start": "08:00", "end": "18:00", "days": [0, 1, 2, 3, 4]},
                "schedule_type": "daily",
                "grace_minutes": 30,
                "nudge_anchor": "end",
                "sort_order": 2,
            },
            {
                "post_type": "update",
                "name": "I'm blocked",
                "description": "What's blocking your progress?",
                "fields": [{"key": "body", "label": "What I'm stuck on", "type": "text", "required": True, "placeholder": "What are you stuck on? Who can help?"}],
                "nudge_enabled": False,
                "nudge_time": "17:00",
                "sort_order": 3,
            },
            {
                "post_type": "update",
                "name": "Heads up",
                "description": "Give the team a heads up about something",
                "fields": [{"key": "body", "label": "Heads up", "type": "text", "required": True, "placeholder": "Something the team should know..."}],
                "nudge_enabled": False,
                "nudge_time": "17:00",
                "sort_order": 4,
            },
            # Wins
            {
                "post_type": "update",
                "name": "Win",
                "description": "Celebrate a team or personal win",
                "fields": [
                    {"key": "title", "label": "What's the win?", "type": "title", "required": True, "placeholder": ""},
                    {"key": "description", "label": "Tell us more", "type": "text", "required": False, "placeholder": ""},
                ],
                "sort_order": 0,
            },
        ]

        templates_added = []
        for t in templates:
            template = cls(workspace_id=None, **t)
            db.session.add(template)
            templates_added.append(template)

        db.session.flush()
        # Undo auto_set_workspace_id — built-in templates must stay NULL
        for template in templates_added:
            template.workspace_id = None
        db.session.commit()

    @classmethod
    def seed_board_templates(cls):
        """Seed built-in board templates with workspace_id=NULL.

        Idempotent — skips if board templates already exist.
        """
        existing = cls.query.filter(
            cls.workspace_id.is_(None),
            cls.post_type == "board",
        ).count()
        if existing > 0:
            return

        templates = [
            {
                "post_type": "board",
                "name": "Announcement",
                "description": "Share a company-wide announcement",
                "fields": [
                    {"key": "title", "label": "Title", "type": "title", "required": True, "placeholder": "What's the announcement?"},
                    {"key": "body", "label": "Details", "type": "text", "required": True, "placeholder": "Share the details..."},
                ],
                "sort_order": 0,
            },
            {
                "post_type": "board",
                "name": "For Sale",
                "description": "Post something for sale",
                "fields": [
                    {"key": "title", "label": "What are you selling?", "type": "title", "required": True, "placeholder": "Item name"},
                    {"key": "body", "label": "Details & price", "type": "text", "required": True, "placeholder": "Description, price, contact info..."},
                ],
                "sort_order": 1,
            },
            {
                "post_type": "board",
                "name": "Event",
                "description": "Share an upcoming event",
                "fields": [
                    {"key": "title", "label": "Event name", "type": "title", "required": True, "placeholder": "What's happening?"},
                    {"key": "body", "label": "Details", "type": "text", "required": True, "placeholder": "When, where, and other details..."},
                ],
                "sort_order": 2,
            },
        ]

        templates_added = []
        for t in templates:
            template = cls(workspace_id=None, **t)
            db.session.add(template)
            templates_added.append(template)

        db.session.flush()
        for template in templates_added:
            template.workspace_id = None
        db.session.commit()
