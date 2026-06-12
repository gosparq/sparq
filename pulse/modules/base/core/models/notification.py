# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     System notification model for admin alerts, module errors, and system
#     messages. Notifications appear in the header bell dropdown.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select

from system.db.database import db
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

if TYPE_CHECKING:
    from modules.base.core.models.user import User


class NotificationCategory:
    """Notification type categories for inbox filtering."""

    TASK_ASSIGNED = "task_assigned"
    COMMENT = "comment"
    MENTION = "mention"
    TASK_SLIPPED = "task_slipped"
    MISSED_CHECKIN = "missed_checkin"
    BLOCKING = "blocking"
    BLOCKER_RESOLVED = "blocker_resolved"
    REVIEW_REQUEST = "review_request"
    PROJECT_UPDATE = "project_update"
    SYSTEM = "system"


class SystemNotification(db.Model, WorkspaceMixin):
    """System-wide notifications for admins and users."""

    __tablename__ = "system_notification"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Targeting: "admin" for admin-only, "all" for everyone, or specific user_id
    target_role = db.Column(db.String(50), default="admin")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Notification content
    type = db.Column(db.String(50), default="info")  # info, warning, error, success
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text)
    icon = db.Column(db.String(50), default="fa-bell")
    color = db.Column(db.String(20))
    action_url = db.Column(db.String(500))  # Optional link to navigate to
    category = db.Column(db.String(30), default="system", nullable=False, index=True)

    # State
    is_read = db.Column(db.Boolean, default=False)
    is_dismissed = db.Column(db.Boolean, default=False)

    # Relationship
    user = db.relationship("User", backref=db.backref("notifications", lazy=LAZY), lazy=LAZY)

    @classmethod
    def create(
        cls,
        title: str,
        message: str = None,
        type: str = "info",
        target_role: str = "admin",
        user_id: int = None,
        icon: str = None,
        color: str = None,
        action_url: str = None,
        category: str = "system",
    ) -> "SystemNotification":
        """Create a new notification."""
        # Set default icon based on type if not provided
        if icon is None:
            icon_map = {
                "error": "fa-exclamation-triangle",
                "warning": "fa-exclamation-circle",
                "success": "fa-check-circle",
                "info": "fa-info-circle",
            }
            icon = icon_map.get(type, "fa-bell")

        # Set default color based on type if not provided
        if color is None:
            color_map = {
                "error": "#dc3545",
                "warning": "#ffc107",
                "success": "#28a745",
                "info": "#0d6efd",
            }
            color = color_map.get(type, "#6c757d")

        notification = cls(
            title=title,
            message=message,
            type=type,
            target_role=target_role,
            user_id=user_id,
            icon=icon,
            color=color,
            action_url=action_url,
            category=category,
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    @classmethod
    def get_for_user(cls, user, limit: int = 20) -> list["SystemNotification"]:
        """Get notifications visible to a user.

        Notifications with a specific user_id are only visible to that user.
        Broadcast notifications (user_id=NULL) use target_role for visibility.
        """
        query = cls.scoped().filter(cls.is_dismissed == False)

        if user.is_admin:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role.in_(["admin", "all"])),
                )
            )
        else:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role == "all"),
                )
            )

        return query.order_by(cls.created_at.desc()).limit(limit).all()

    @classmethod
    def get_unread_count(cls, user) -> int:
        """Get count of unread notifications for badge."""
        from flask import g

        cache_key = ("unread", user.id, user.is_admin)
        try:
            cache = getattr(g, "_notification_cache", None)
            if cache is None:
                cache = {}
                g._notification_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        query = cls.scoped().filter(cls.is_dismissed == False, cls.is_read == False)

        if user.is_admin:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role.in_(["admin", "all"])),
                )
            )
        else:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role == "all"),
                )
            )

        result = query.count()
        if cache is not None:
            cache[cache_key] = result
        return result

    def mark_read(self) -> None:
        """Mark this notification as read."""
        self.is_read = True
        db.session.commit()

    def dismiss(self) -> None:
        """Dismiss this notification (hide from list)."""
        self.is_dismissed = True
        db.session.commit()

    @classmethod
    def dismiss_by_url(cls, url_fragment: str, user_id: int) -> None:
        """Dismiss all notifications for a user whose action_url contains the fragment."""
        cls.scoped().filter(
            cls.user_id == user_id,
            cls.is_dismissed == False,
            cls.action_url.isnot(None),
            cls.action_url.contains(url_fragment),
        ).update({"is_dismissed": True}, synchronize_session=False)
        db.session.commit()

    @classmethod
    def dismiss_by_title(cls, title: str, user_id: int) -> None:
        """Dismiss all notifications for a user matching an exact title."""
        cls.scoped().filter(
            cls.user_id == user_id,
            cls.is_dismissed == False,
            cls.title == title,
        ).update({"is_dismissed": True}, synchronize_session=False)
        db.session.commit()

    @classmethod
    def mark_all_read(cls, user) -> None:
        """Mark all notifications as read for a user."""
        query = cls.scoped().filter(cls.is_dismissed == False, cls.is_read == False)

        if user.is_admin:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role.in_(["admin", "all"])),
                )
            )
        else:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role == "all"),
                )
            )

        query.update({"is_read": True}, synchronize_session=False)
        db.session.commit()

    @classmethod
    def dismiss_all(cls, user) -> None:
        """Dismiss all notifications for a user."""
        query = cls.scoped().filter(cls.is_dismissed == False)

        if user.is_admin:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role.in_(["admin", "all"])),
                )
            )
        else:
            query = query.filter(
                db.or_(
                    cls.user_id == user.id,
                    db.and_(cls.user_id.is_(None), cls.target_role == "all"),
                )
            )

        query.update({"is_dismissed": True}, synchronize_session=False)
        db.session.commit()

    def time_ago(self) -> str:
        """Return human-readable time since notification."""
        now = datetime.utcnow()
        diff = now - self.created_at

        if diff.days > 0:
            if diff.days == 1:
                return "1 day ago"
            return f"{diff.days} days ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            if hours == 1:
                return "1 hour ago"
            return f"{hours} hours ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            if minutes == 1:
                return "1 minute ago"
            return f"{minutes} minutes ago"
        else:
            return "just now"

    @classmethod
    def get_system_alerts(cls) -> list[dict]:
        """Get dynamic system alerts based on current system state.

        These are not stored in the database - they're generated based on
        system configuration status and appear until the issue is resolved.

        Returns:
            List of alert dictionaries with notification-like structure.
        """
        alerts = []
        return alerts

    @classmethod
    def get_system_alerts_count(cls) -> int:
        """Get count of active system alerts for badge."""
        return len(cls.get_system_alerts())

    # -------------------------------------------------------------------------
    # Inbox query methods
    # -------------------------------------------------------------------------

    CATEGORY_LABELS: dict[str, str] = {
        "task_assigned": "Task",
        "comment": "Comment",
        "mention": "Mention",
        "task_slipped": "Task",
        "missed_checkin": "Check-in",
        "blocking": "Blocker",
        "blocker_resolved": "Resolved",
        "review_request": "Review",
        "project_update": "Project",
        "system": "System",
    }

    FILTER_GROUPS: dict[str, list[str] | None] = {
        "all": None,
        "comments": ["comment"],
        "mentions": ["mention"],
        "tasks": ["task_assigned", "task_slipped", "blocking", "blocker_resolved"],
        "projects": ["project_update"],
        "check-ins": ["missed_checkin"],
        "reviews": ["review_request"],
    }

    @staticmethod
    def _user_visibility_clause(user: User) -> db.BinaryExpression:
        """Return an OR clause restricting rows to those visible to the user."""
        if user.is_admin:
            return db.or_(
                SystemNotification.user_id == user.id,
                db.and_(
                    SystemNotification.user_id.is_(None),
                    SystemNotification.target_role.in_(["admin", "all"]),
                ),
            )
        return db.or_(
            SystemNotification.user_id == user.id,
            db.and_(
                SystemNotification.user_id.is_(None),
                SystemNotification.target_role == "all",
            ),
        )

    @classmethod
    def get_inbox_items(
        cls, user: User, category: list[str] | None = None, limit: int = 50
    ) -> list[InboxItem]:
        """Get notification items for inbox, optionally filtered by category list."""
        from flask import g

        stmt = (
            select(
                cls.id,
                cls.created_at,
                cls.category,
                cls.type,
                cls.title,
                cls.message,
                cls.icon,
                cls.color,
                cls.action_url,
                cls.is_read,
            )
            .where(
                cls.is_dismissed == False,
                cls.organization_id == g.organization_id,
                cls.workspace_id == g.workspace_id,
                cls._user_visibility_clause(user),
            )
        )

        if category is not None:
            stmt = stmt.where(cls.category.in_(category))

        stmt = stmt.order_by(cls.created_at.desc()).limit(limit)
        rows = db.session.execute(stmt).all()

        now = datetime.utcnow()
        return [
            InboxItem(
                id=r.id,
                created_at=r.created_at,
                category=r.category,
                type=r.type,
                title=r.title,
                message=r.message,
                icon=r.icon,
                color=r.color,
                action_url=r.action_url,
                is_read=r.is_read,
                time_ago=cls._compute_time_ago(now, r.created_at),
            )
            for r in rows
        ]

    @classmethod
    def get_unread_counts_by_group(cls, user: User) -> dict[str, int]:
        """Get unread counts per filter-group tab via a single GROUP BY query."""
        from flask import g

        stmt = (
            select(cls.category, func.count())
            .where(
                cls.is_dismissed == False,
                cls.is_read == False,
                cls.organization_id == g.organization_id,
                cls.workspace_id == g.workspace_id,
                cls._user_visibility_clause(user),
            )
        )

        stmt = stmt.group_by(cls.category)
        raw_counts = {cat: cnt for cat, cnt in db.session.execute(stmt).all()}

        result = {}
        total = 0
        for tab_name, categories in cls.FILTER_GROUPS.items():
            if categories is None:
                continue
            result[tab_name] = sum(raw_counts.get(c, 0) for c in categories)
            total += result[tab_name]
        result["all"] = total
        return result

    @staticmethod
    def _compute_time_ago(now: datetime, created_at: datetime) -> str:
        """Compute human-readable time ago string."""
        diff = now - created_at
        if diff.days > 0:
            if diff.days == 1:
                return "1 day ago"
            return f"{diff.days} days ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            if hours == 1:
                return "1 hour ago"
            return f"{hours} hours ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            if minutes == 1:
                return "1 minute ago"
            return f"{minutes} minutes ago"
        return "just now"


@dataclass(frozen=True)
class InboxItem:
    """Projection dataclass for inbox list rendering."""

    id: int
    created_at: datetime
    category: str
    type: str
    title: str
    message: str | None
    icon: str
    color: str
    action_url: str | None
    is_read: bool
    time_ago: str
