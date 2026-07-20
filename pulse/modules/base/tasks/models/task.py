# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Task model — urgent interpersonal accountability units.

Each Task has a 3-tier RAG urgency system:
  Tier 1 (Red/Now)      — nudge every 30 min, one snooze allowed
  Tier 2 (Amber/Later)  — nudge every 4 hours
  Tier 3 (Green/Whenever) — nudge daily at 8am local

Classes:
    Task: Core action item entity.
"""

import uuid
from datetime import date, datetime, timedelta

from flask import g
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

# ── Association table for watchers (notify on completion) ─────────────────
task_watcher = db.Table(
    "task_watcher",
    db.Column("task_id", db.Integer, db.ForeignKey("task.id", ondelete="CASCADE"), primary_key=True),
    db.Column("watcher_id", db.Integer, db.ForeignKey("workspace_user.id", ondelete="CASCADE"), primary_key=True),
)
ModelRegistry.register_table(task_watcher, "tasks")

# Default tier labels (customizable per workspace via settings)
TIER_DEFAULTS = {
    1: {"label": "Now", "color": "#dc2626"},       # Red
    2: {"label": "Later", "color": "#d97706"},      # Amber
    3: {"label": "Whenever", "color": "#16a34a"},   # Green
}

# Hardcoded workflow statuses for kanban board
WORKFLOW_STATUSES = [
    {"key": "todo", "label": "To Do", "color": "#6b7280"},
    {"key": "in_progress", "label": "In Progress", "color": "#2563eb"},
    {"key": "needs_review", "label": "Needs Review", "color": "#8b5cf6"},
    {"key": "on_hold", "label": "On Hold", "color": "#f59e0b"},
    {"key": "done", "label": "Completed", "color": "#16a34a"},
]

WORKFLOW_STATUS_MAP = {s["key"]: s for s in WORKFLOW_STATUSES}


def get_workflow_statuses() -> list[dict]:
    """Return workflow statuses for the current workspace.

    Reads from TaskStatus DB model if available, falling back to the
    hardcoded WORKFLOW_STATUSES constants for dev/test environments where
    the table may not yet exist.

    Returns:
        List of dicts with keys 'key', 'label', 'color' — compatible with
        all existing call sites.
    """
    try:
        from modules.base.tasks.models.task_status import TaskStatus
        rows = TaskStatus.get_for_workspace()
        if rows:
            return [{"key": s.code, "label": s.label, "color": s.color} for s in rows]
    except Exception:
        pass
    return list(WORKFLOW_STATUSES)


def get_done_status_code() -> str:
    """Return the code of the status that resolves tasks (is_done=True).

    Falls back to the hardcoded 'done' key if TaskStatus is unavailable.

    Returns:
        Status code string (e.g. 'done').
    """
    try:
        from modules.base.tasks.models.task_status import TaskStatus
        done = TaskStatus.get_done_status()
        if done:
            return done.code
    except Exception:
        pass
    return "done"


def get_tier_defaults():
    """Get tier defaults with custom labels merged from WorkspaceSettings."""
    merged = {k: dict(v) for k, v in TIER_DEFAULTS.items()}
    try:
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        settings = WorkspaceSettings.get_instance()
        custom = settings.tasks_tier_labels
        if custom:
            for tier_str, label in custom.items():
                tier = int(tier_str)
                if tier in merged and label:
                    merged[tier]["label"] = label
    except Exception:
        pass
    return merged


@ModelRegistry.register
class Task(db.Model, WorkspaceMixin):
    """Urgent interpersonal accountability unit with RAG urgency tiers.

    Attributes:
        title: Short description (max 200 chars).
        urgency_tier: 1 (Red/Now), 2 (Amber/Later), 3 (Green/Whenever).
        assignee_id: FK to workspace_user — who must resolve this.
        raised_by_id: FK to workspace_user — who raised it (null = System).
        context_note: Optional description/context from the raiser.
        source_type: Optional entity type for the originating entity.
        source_id: Optional entity ID for the originating entity.
        status: "open", "resolved", "dismissed", "canceled".
        resolution_note: Optional note from the assignee on resolution.
        broadcast_group_id: Links records from a multi-assignee raise.
        snoozed: Whether Tier 1 snooze has been used.
        snooze_until: When the snooze expires.
        resolved_at: Timestamp of resolution.
        resolved_by_id: FK to workspace_user who resolved/dismissed.
    """

    __tablename__ = "task"
    __table_args__ = (
        db.Index("ix_task_assignee_open", "workspace_id", "assignee_id", "status"),
        db.Index("ix_task_raised_by", "workspace_id", "raised_by_id", "status"),
        db.Index("ix_task_broadcast", "broadcast_group_id"),
        db.Index("ix_task_blocker", "workspace_id", "is_blocker", "status"),
        db.Index("ix_task_project_org", "project_id", "organization_id", "workspace_id"),
    )

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(200), nullable=False)
    urgency_tier = db.Column(db.Integer, nullable=False, default=2)

    assignee_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )
    raised_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    context_note = db.Column(db.Text, nullable=True)
    source_type = db.Column(db.String(50), nullable=True)
    source_id = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="open")
    workflow_status = db.Column(db.String(30), nullable=False, default="todo")
    resolution_note = db.Column(db.String(1024), nullable=True)

    broadcast_group_id = db.Column(db.Uuid, nullable=True)

    area_id = db.Column(
        db.Integer, db.ForeignKey("update_area.id", ondelete="SET NULL"), nullable=True
    )

    project_id = db.Column(
        db.Integer, db.ForeignKey("project.id", ondelete="SET NULL"), nullable=True
    )

    is_blocker = db.Column(db.Boolean, nullable=False, default=False)

    due_date = db.Column(db.Date, nullable=True)

    snoozed = db.Column(db.Boolean, nullable=False, default=False)
    snooze_until = db.Column(db.DateTime, nullable=True)

    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    assignee = db.relationship("WorkspaceUser", foreign_keys=[assignee_id], lazy=LAZY)
    raised_by = db.relationship("WorkspaceUser", foreign_keys=[raised_by_id], lazy=LAZY)
    resolved_by = db.relationship("WorkspaceUser", foreign_keys=[resolved_by_id], lazy=LAZY)
    area = db.relationship("UpdateArea", foreign_keys=[area_id], lazy=LAZY)
    project = db.relationship("Project", foreign_keys=[project_id], lazy=LAZY)
    watchers = db.relationship("WorkspaceUser", secondary=task_watcher, lazy=LAZY)

    # ── Creation ──────────────────────────────────────────────────────────

    @classmethod
    def create(cls, title, urgency_tier, assignee_id, raised_by_id=None,
               context_note=None, source_type=None, source_id=None,
               broadcast_group_id=None, is_blocker=False, project_id=None,
               workflow_status=None, watcher_ids=None):
        """Create a new Task.

        Args:
            title: Short description (max 200 chars).
            urgency_tier: 1, 2, or 3.
            assignee_id: WorkspaceUser.id of the assignee.
            raised_by_id: WorkspaceUser.id of the raiser (None = System).
            context_note: Optional context from the raiser.
            source_type: Optional originating entity type.
            source_id: Optional originating entity ID.
            broadcast_group_id: UUID linking multi-assignee records.
            is_blocker: Whether this item is a blocker (default False).
            project_id: Optional Project.id to associate with.
            workflow_status: Workflow status code. Defaults to workspace default status.
            watcher_ids: Optional list of WorkspaceUser.ids to notify on completion.

        Returns:
            Created Task instance.
        """
        from modules.base.dashboard.models.activity_log import ActivityLog

        if workflow_status is None:
            try:
                from modules.base.tasks.models.task_status import TaskStatus
                default_status = TaskStatus.get_default()
                workflow_status = default_status.code if default_status else "todo"
            except Exception:
                workflow_status = "todo"

        item = cls(
            title=title[:200],
            urgency_tier=max(1, min(3, urgency_tier)),
            assignee_id=assignee_id,
            raised_by_id=raised_by_id,
            context_note=context_note or None,
            source_type=source_type,
            source_id=source_id,
            broadcast_group_id=broadcast_group_id,
            status="open",
            workflow_status=workflow_status,
            is_blocker=is_blocker,
            project_id=project_id,
        )
        db.session.add(item)

        # Keep eager-loaded relationships alive across multiple commits
        # (TaskLog, ActivityLog, SystemNotification all commit).
        _session = db.session()
        prev_expire = _session.expire_on_commit
        _session.expire_on_commit = False
        try:
            db.session.commit()

            # Re-query with eager loads for post-create notifications/email
            from modules.base.core.models.workspace_user import WorkspaceUser
            item = cls.query.options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
            ).filter_by(id=item.id).first()

            # Link any IntegrationRef rows created before this task existed
            # (object_id=0 is written by the trigger when the task has no ID yet).
            import re as _re
            _gh_numbers = _re.findall(r'\[GH-(\d+)\]', title)
            if _gh_numbers:
                try:
                    from modules.integrations.models.integration_ref import IntegrationRef
                    for _num in _gh_numbers:
                        _stale = (
                            IntegrationRef.scoped()
                            .filter_by(
                                provider="github",
                                external_id=str(_num),
                                object_type="task",
                                object_id=0,
                            )
                            .first()
                        )
                        if _stale:
                            _stale.object_id = item.id
                            _stale.linked_task_id = item.id
                    db.session.commit()
                except Exception:
                    pass

            # Log creation — store the full title (TaskLog.log caps at 500,
            # matching the detail column) so the activity entry's "more" toggle
            # can reveal the complete text on the task detail page.
            from .task_log import TaskLog
            TaskLog.log(item.id, "created", raised_by_id, title)

            ActivityLog.log(
                action="tasks.created",
                model_type="Task",
                record_id=item.id,
                member_id=raised_by_id or assignee_id,
                title="Task created",
                description=title[:100],
                icon="fa-bolt",
                color="danger" if urgency_tier == 1 else "warning" if urgency_tier == 2 else "success",
                url=f"/tasks/{item.id}",
            )

            # Immediate notification for Tier 1 (Now) items (skip if unassigned)
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            from modules.base.core.services.push_notification import send_push

            # Immediate notification for Tier 1 (Now) items (skip if unassigned)
            if item.urgency_tier == 1 and item.assignee and item.assignee.user:
                raiser_name = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"

                SystemNotification.create(
                    title=item.title[:100],
                    message=f"Urgent task assigned by {raiser_name}",
                    type="warning",
                    target_role="user",
                    user_id=item.assignee.user_id,
                    icon="fa-bolt",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.TASK_ASSIGNED,
                )
                send_push(
                    user_id=item.assignee.user_id,
                    title=f"Urgent: {item.title[:80]}",
                    body=f"Assigned by {raiser_name}",
                    url=f"/tasks/{item.id}",
                )

            # Notification for Tier 2/3 assignments (Tier 1 already handled above)
            if item.urgency_tier in (2, 3) and item.assignee and item.assignee.user:
                raiser_name = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"

                SystemNotification.create(
                    title=item.title[:100],
                    message=f"New task assigned by {raiser_name}",
                    type="info",
                    target_role="user",
                    user_id=item.assignee.user_id,
                    icon="fa-list-check",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.TASK_ASSIGNED,
                )
                send_push(
                    user_id=item.assignee.user_id,
                    title=item.title[:80],
                    body=f"New task assigned by {raiser_name}",
                    url=f"/tasks/{item.id}",
                )

            # Blocker notification — tell assignee they are blocking someone
            if is_blocker and item.assignee and item.assignee.user:
                blocker_raiser = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"
                SystemNotification.create(
                    title=item.title[:100],
                    message=f"{blocker_raiser} is blocked by this task",
                    type="warning",
                    target_role="user",
                    user_id=item.assignee.user_id,
                    icon="fa-hand",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.BLOCKING,
                )
                send_push(
                    user_id=item.assignee.user_id,
                    title=f"You are blocking {blocker_raiser}",
                    body=item.title[:80],
                    url=f"/tasks/{item.id}",
                )

            # Attach watchers (notify on completion)
            if watcher_ids:
                from modules.base.core.models.workspace_user import WorkspaceUser
                watchers = WorkspaceUser.scoped().filter(WorkspaceUser.id.in_(watcher_ids)).all()
                from sqlalchemy.orm.attributes import set_committed_value
                set_committed_value(item, "watchers", [])
                item.watchers = watchers
                db.session.commit()

            cls._email_assignee(item)
        finally:
            _session.expire_on_commit = prev_expire

        return item

    @classmethod
    def create_broadcast(cls, title, urgency_tier, assignee_ids, raised_by_id=None,
                         context_note=None, source_type=None, source_id=None,
                         watcher_ids=None, is_blocker=False):
        """Create Tasks for multiple assignees sharing a broadcast group.

        Args:
            title: Short description.
            urgency_tier: 1, 2, or 3.
            assignee_ids: List of WorkspaceUser.ids.
            raised_by_id: WorkspaceUser.id of the raiser.
            context_note: Optional context.
            source_type: Optional originating entity type.
            source_id: Optional originating entity ID.
            watcher_ids: Optional list of WorkspaceUser.ids to notify on completion.

        Returns:
            List of created Task instances.
        """
        group_id = uuid.uuid4()
        items = []
        for aid in assignee_ids:
            item = cls.create(
                title=title,
                urgency_tier=urgency_tier,
                assignee_id=aid,
                raised_by_id=raised_by_id,
                context_note=context_note,
                source_type=source_type,
                source_id=source_id,
                broadcast_group_id=group_id,
                watcher_ids=watcher_ids,
                is_blocker=is_blocker,
            )
            items.append(item)
        return items

    # ── Stale Management ────────────────────────────────────────────────

    @classmethod
    def mark_stale_tasks(cls, stale_days: int) -> int:
        """Move open todo tasks (not Now priority) past the stale threshold to on_hold.

        Args:
            stale_days: Number of idle days before a task is considered stale.

        Returns:
            Number of tasks updated.
        """
        cutoff = datetime.utcnow() - timedelta(days=stale_days)
        count = (
            cls.scoped()
            .filter(
                cls.status == "open",
                cls.workflow_status == "todo",
                cls.urgency_tier != 1,
                cls.updated_at < cutoff,
            )
            .update({"workflow_status": "on_hold"}, synchronize_session="fetch")
        )
        if count:
            db.session.commit()
        return count

    # ── Queries ───────────────────────────────────────────────────────────

    @classmethod
    def search(cls, query_text: str, limit: int = 5) -> list["Task"]:
        """Search open action items by title and context note."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        search_term = f"%{query_text}%"
        return (
            cls.scoped()
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(
                cls.status == "open",
                db.or_(
                    cls.title.ilike(search_term),
                    cls.context_note.ilike(search_term),
                ),
            )
            .order_by(cls.urgency_tier.asc(), cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_for_date_range(cls, start_date, end_date):
        """Get action items created within a date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            List of Task instances, newest first.
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        return (
            cls.scoped()
            .filter(
                cls.created_at >= start_dt,
                cls.created_at <= end_dt,
            )
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def get_with_due_date_in_range(cls, start_date: date, end_date: date) -> list["Task"]:
        """Get open action items with a due date within a date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            List of Task instances ordered by due date.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
            )
            .filter(
                cls.due_date.isnot(None),
                cls.due_date >= start_date,
                cls.due_date <= end_date,
                cls.status == "open",
            )
            .order_by(cls.due_date.asc())
            .all()
        )

    @classmethod
    def count_created_in_range(cls, start_date, end_date, exclude_system=False):
        """Count action items created within a date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            exclude_system: If True, exclude system-raised items.

        Returns:
            Integer count.
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        query = cls.scoped().filter(
            cls.created_at >= start_dt,
            cls.created_at <= end_dt,
        )
        if exclude_system:
            query = query.filter(cls.raised_by_id.isnot(None))
        return query.count()

    @classmethod
    def count_resolved_in_range(cls, start_date, end_date):
        """Count action items resolved within a date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Integer count.
        """
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end_date, datetime.max.time())

        return cls.scoped().filter(
            cls.resolved_at >= start_dt,
            cls.resolved_at <= end_dt,
            cls.status == "resolved",
        ).count()

    @classmethod
    def get_my_active_blockers(cls, member_id):
        """Get open blockers assigned to a member for the dashboard My Items widget.

        Args:
            member_id: WorkspaceUser.id of the assignee.

        Returns:
            List of open blocker Task instances ordered by created_at DESC.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
            )
            .filter(
                cls.assignee_id == member_id,
                cls.is_blocker.is_(True),
                cls.status == "open",
            )
            .order_by(cls.created_at.desc())
            .all()
        )

    @classmethod
    def build_dashboard_items(cls, blockers, mentions=None, nudge=None, limit=10):
        """Build the dashboard My Items list sorted by creation time descending.

        Args:
            blockers: List of open blocker Task instances assigned to the user.
            mentions: List of UpdatePost instances that mention the user.
            nudge: Optional pending nudge object.
            limit: Maximum number of entries to return (default 10).

        Returns:
            List of dicts with 'type' ('nudge' | 'blocker' | 'mention') and 'item' keys.
        """
        merged: list[dict] = []
        if nudge:
            merged.append({"type": "nudge", "item": nudge, "_ts": nudge.nudged_at})
        merged += [{"type": "blocker", "item": b, "_ts": b.created_at} for b in blockers]
        merged += [{"type": "mention", "item": m, "_ts": m.created_at} for m in (mentions or [])]
        merged.sort(key=Task.dashboard_sort_key, reverse=True)
        return [{"type": e["type"], "item": e["item"]} for e in merged[:limit]]

    @staticmethod
    def dashboard_sort_key(entry: dict):
        return entry.get("_ts") or datetime.min

    @classmethod
    def count_slipped_in_range(cls, start_date=None, end_date=None):
        """Count open action items whose due date fell within a date range (slipped).

        Args:
            start_date: Start date (inclusive). If None, no lower bound.
            end_date: End date (inclusive).

        Returns:
            Integer count.
        """
        q = cls.scoped().filter(cls.status == "open")
        if start_date is not None:
            q = q.filter(cls.due_date >= start_date)
        if end_date is not None:
            q = q.filter(cls.due_date <= end_date)
        return q.count()

    @classmethod
    def get_mine_open(cls, member_id):
        """Get open Tasks assigned to a member, grouped by tier.

        Args:
            member_id: WorkspaceUser.id of the assignee.

        Returns:
            List of open Task instances ordered by tier ASC, created_at ASC.
        """
        cache_key = ("mine_open", member_id)
        try:
            cache = getattr(g, "_task_cache", None)
            if cache is None:
                cache = {}
                g._task_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        result = (
            cls.scoped()
            .options(joinedload(cls.project))
            .filter(cls.assignee_id == member_id, cls.status == "open")
            .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
            .all()
        )
        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def get_mine_closed(cls, member_id):
        """Get closed Tasks assigned to a member.

        Args:
            member_id: WorkspaceUser.id of the assignee.

        Returns:
            List of closed Task instances ordered by resolved_at DESC.
        """
        return (
            cls.scoped()
            .filter(cls.assignee_id == member_id, cls.status != "open")
            .order_by(cls.resolved_at.desc())
            .all()
        )

    @classmethod
    def get_mine_open_count(cls, member_id):
        """Get count of open Tasks assigned to a member.

        Args:
            member_id: WorkspaceUser.id of the assignee.

        Returns:
            Integer count.
        """
        cache_key = ("mine_open_count", member_id)
        try:
            cache = getattr(g, "_task_cache", None)
            if cache is None:
                cache = {}
                g._task_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        result = (
            cls.scoped()
            .filter(cls.assignee_id == member_id, cls.status == "open", cls.raised_by_id.isnot(None))
            .count()
        )
        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def get_raised_by(cls, member_id):
        """Get all Tasks raised by a member.

        Args:
            member_id: WorkspaceUser.id of the raiser.

        Returns:
            Dict with 'open' and 'closed' lists.
        """
        all_items = (
            cls.scoped()
            .filter(cls.raised_by_id == member_id)
            .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
            .all()
        )
        open_items = [i for i in all_items if i.status == "open"]
        closed_items = sorted(
            [i for i in all_items if i.status != "open"],
            key=lambda i: i.resolved_at or datetime.min,
            reverse=True,
        )
        return {"open": open_items, "closed": closed_items}

    @classmethod
    def get_team_open(cls):
        """Get all open Tasks across the workspace.

        Returns:
            List of open Task instances ordered by assignee, then tier.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(cls.status == "open")
            .order_by(cls.assignee_id, cls.urgency_tier.asc(), cls.created_at.asc())
            .all()
        )

    @classmethod
    def get_team_all(cls, member_ids=None):
        """Get all action items (open + closed) across the workspace, optionally filtered by assignees.

        Args:
            member_ids: Optional list of WorkspaceUser.ids to filter by.

        Returns:
            List of Task instances ordered by urgency tier, then created_at.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        query = cls.scoped().options(
            joinedload(cls.assignee).joinedload(WorkspaceUser.user),
            joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
            joinedload(cls.project),
        )
        if member_ids:
            query = query.filter(cls.assignee_id.in_(member_ids))
        return query.order_by(cls.urgency_tier.asc(), cls.created_at.asc()).all()

    @classmethod
    def get_unassigned(cls):
        """Get all Tasks with no assignee.

        Returns:
            Dict with 'open' and 'closed' lists, each ordered by tier ASC, created_at ASC.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        all_items = (
            cls.scoped()
            .options(
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(cls.assignee_id.is_(None))
            .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
            .all()
        )
        open_items = [i for i in all_items if i.status == "open"]
        closed_items = sorted(
            [i for i in all_items if i.status != "open"],
            key=lambda i: i.resolved_at or datetime.min,
            reverse=True,
        )
        return {"open": open_items, "closed": closed_items}

    @classmethod
    def get_broadcast_summary(cls, group_id):
        """Get resolution summary for a broadcast group.

        Args:
            group_id: UUID of the broadcast group.

        Returns:
            Dict with 'total', 'resolved', 'items' keys.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser

        items = (
            cls.scoped()
            .options(joinedload(cls.assignee).joinedload(WorkspaceUser.user))
            .filter(cls.broadcast_group_id == group_id)
            .order_by(cls.status.asc(), cls.created_at.asc())
            .all()
        )
        resolved = sum(1 for i in items if i.status == "resolved")
        return {"total": len(items), "resolved": resolved, "items": items}

    @classmethod
    def get_by_ids(cls, ids):
        """Bulk lookup action items by a list of IDs (workspace-scoped).

        Args:
            ids: List of Task IDs.

        Returns:
            Dict mapping id -> Task instance.
        """
        if not ids:
            return {}
        from modules.base.core.models.workspace_user import WorkspaceUser

        items = (
            cls.scoped()
            .options(joinedload(cls.assignee).joinedload(WorkspaceUser.user))
            .filter(cls.id.in_(ids))
            .all()
        )
        return {item.id: item for item in items}

    @classmethod
    def get_open_blockers(cls):
        """Get open action items marked as blockers, scoped to workspace.

        Returns:
            List of open blocker Task instances ordered by created_at ASC.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(cls.is_blocker.is_(True), cls.status == "open")
            .order_by(cls.created_at.asc())
            .all()
        )

    @classmethod
    def get_open_blockers_count(cls):
        """Count open action items marked as blockers, scoped to workspace."""
        return (
            cls.scoped()
            .filter(cls.is_blocker.is_(True), cls.status == "open")
            .count()
        )

    @classmethod
    def get_resolved_blockers(cls, limit=20):
        """Get resolved blocker action items, scoped to workspace.

        Args:
            limit: Max number of results (default 20).

        Returns:
            List of resolved blocker Task instances ordered by resolved_at DESC.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        return (
            cls.scoped()
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(cls.is_blocker.is_(True), cls.status == "resolved")
            .order_by(cls.resolved_at.desc())
            .limit(limit)
            .all()
        )

    # ── State Transitions ─────────────────────────────────────────────────

    @classmethod
    def resolve(cls, item_id, resolver_id, note=None):
        """Resolve a Task. Auto-resolves linked blocker if any.

        Args:
            item_id: Task.id to resolve.
            resolver_id: WorkspaceUser.id of the resolver.
            note: Optional resolution note.

        Returns:
            Resolved Task or None if not found.
        """
        from modules.base.dashboard.models.activity_log import ActivityLog

        item = (
            cls.scoped()
            .options(joinedload(cls.assignee), joinedload(cls.raised_by))
            .filter_by(id=item_id, status="open")
            .first()
        )
        if not item:
            return None

        item.status = "resolved"
        item.workflow_status = "done"
        item.resolved_at = datetime.utcnow()
        item.resolved_by_id = resolver_id
        item.resolution_note = note[:1024] if note else None

        # Keep eager-loaded relationships alive across multiple commits
        # (TaskLog, ActivityLog, SystemNotification all commit).
        _session = db.session()
        prev_expire = _session.expire_on_commit
        _session.expire_on_commit = False
        try:
            db.session.commit()

            # Re-fetch with relationships needed by post-commit helpers.
            from sqlalchemy.orm import selectinload

            from modules.base.core.models.workspace_user import WorkspaceUser

            item = (
                cls.scoped()
                .options(
                    joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                    joinedload(cls.raised_by).joinedload(WorkspaceUser.user),
                    joinedload(cls.resolved_by).joinedload(WorkspaceUser.user),
                    selectinload(cls.watchers).joinedload(WorkspaceUser.user),
                )
                .filter_by(id=item_id)
                .first()
            )

            from .task_log import TaskLog
            TaskLog.log(item.id, "resolved", resolver_id, note[:100] if note else None)

            ActivityLog.log(
                action="tasks.resolved",
                model_type="Task",
                record_id=item.id,
                member_id=resolver_id,
                title="Task resolved",
                description=item.title[:100],
                icon="fa-check-circle",
                color="success",
                url=f"/tasks/{item.id}",
            )

            # Auto-dismiss nudge notifications for this action item
            from modules.base.core.models.notification import SystemNotification
            if item.assignee:
                SystemNotification.dismiss_by_url(f"/tasks/{item.id}", user_id=item.assignee.user_id)
            if item.raised_by_id and item.raised_by:
                SystemNotification.dismiss_by_url(f"/tasks/{item.id}", user_id=item.raised_by.user_id)

            # Auto-resolve linked blocker
            cls._auto_resolve_linked_blocker(item, resolver_id)

            # Notify the raiser
            cls._notify_raiser_resolved(item)

            # Notify watchers
            cls._notify_watchers_resolved(item)

            # Notify project followers
            cls._notify_project_followers_resolved(item)
        finally:
            _session.expire_on_commit = prev_expire

        return item

    @classmethod
    def ensure_checkin_item(
        cls,
        template_name: str,
        member_id: int,
        source_type: str,
    ) -> "Task":
        """Ensure exactly one open check-in action item exists for a template + member.

        Quietly resolves any existing open items for the same combo, then creates
        a fresh one so the inbox always shows the current date.

        Args:
            template_name: Sync template name (e.g. "Current").
            member_id: WorkspaceUser.id of the assignee.
            source_type: "missed_checkin" or "missed_periodic".

        Returns:
            The newly created Task.
        """
        suffix = " check-in" if source_type == "missed_checkin" else " update"
        title = f"{template_name}{suffix}"

        cls.scoped().filter(
            cls.source_type == source_type,
            cls.assignee_id == member_id,
            cls.title == title,
            cls.status == "open",
        ).update(
            {"status": "resolved", "workflow_status": "done", "resolved_at": datetime.utcnow()},
            synchronize_session=False,
        )
        db.session.flush()

        return cls.create(
            title=title,
            urgency_tier=3,
            assignee_id=member_id,
            raised_by_id=None,
            context_note=f"You haven't posted your {template_name} yet.",
            source_type=source_type,
        )

    @classmethod
    def resolve_missed_checkins(cls, template_name: str, member_id: int) -> None:
        """Auto-resolve open missed check-in action items for a template.

        Called when a user posts to a sync template, resolving any
        system-generated action items that were created for missing that check-in.

        Args:
            template_name: The sync template name (e.g. "Async - Standup").
            member_id: WorkspaceUser.id of the poster.
        """
        items = cls.scoped().filter(
            cls.source_type.in_(["missed_checkin", "missed_periodic"]),
            cls.assignee_id == member_id,
            cls.status == "open",
            cls.title.in_([f"{template_name} check-in", f"{template_name} update"]),
        ).all()
        for item in items:
            cls.resolve(item.id, member_id, note="Auto-resolved: check-in posted")

    @classmethod
    def suggestions_for(cls, member_id, limit=5):
        """Return up to ``limit`` action item suggestions for the status update pill bar.

        Priority:
          1. In-progress items assigned to the member
          2. Tier 1/2 items assigned to the member to fill remaining slots
          3. Any lower-priority items assigned to the member to fill remaining slots
          4. If nothing assigned, same three passes for unassigned items

        Excludes system-generated items (missed_checkin, missed_periodic).
        """
        _SYSTEM_TYPES = ("missed_checkin", "missed_periodic")

        def _base(assignee_filter):
            return cls.scoped().options(joinedload(cls.project)).filter(
                cls.status == "open",
                or_(cls.source_type.is_(None), cls.source_type.notin_(_SYSTEM_TYPES)),
                assignee_filter,
            )

        def _fill(items, assignee_filter):
            if len(items) >= limit:
                return items
            seen = {i.id for i in items}
            extra = (
                _base(assignee_filter)
                .filter(
                    cls.urgency_tier.in_([1, 2]),
                    cls.id.notin_(seen) if seen else True,
                )
                .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
                .limit(limit - len(items))
                .all()
            )
            items = items + extra
            if len(items) < limit:
                seen = {i.id for i in items}
                items = items + (
                    _base(assignee_filter)
                    .filter(
                        cls.urgency_tier.notin_([1, 2]),
                        cls.id.notin_(seen) if seen else True,
                    )
                    .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
                    .limit(limit - len(items))
                    .all()
                )
            return items

        assigned = cls.assignee_id == member_id
        items = (
            _base(assigned)
            .filter(cls.workflow_status == "in_progress")
            .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
            .limit(limit)
            .all()
        )
        items = _fill(items, assigned)

        if not items:
            unassigned = cls.assignee_id.is_(None)
            items = (
                _base(unassigned)
                .filter(cls.workflow_status == "in_progress")
                .order_by(cls.urgency_tier.asc(), cls.created_at.asc())
                .limit(limit)
                .all()
            )
            items = _fill(items, unassigned)

        return items

    @classmethod
    def dismiss(cls, item_id, member_id):
        """Dismiss a Task (system-generated items).

        Args:
            item_id: Task.id to dismiss.
            member_id: WorkspaceUser.id of the dismisser.

        Returns:
            Dismissed Task or None.
        """
        item = cls.scoped().filter_by(id=item_id, status="open").first()
        if not item:
            return None

        item.status = "dismissed"
        item.workflow_status = "done"
        item.resolved_at = datetime.utcnow()
        item.resolved_by_id = member_id
        db.session.commit()

        from .task_log import TaskLog
        TaskLog.log(item.id, "dismissed", member_id)

        # Auto-dismiss nudge notifications for this action item
        from modules.base.core.models.notification import SystemNotification
        if item.assignee:
            SystemNotification.dismiss_by_url(f"/tasks/{item.id}", user_id=item.assignee.user_id)

        return item

    @classmethod
    def cancel(cls, item_id, raiser_id):
        """Cancel a Task (raiser only).

        Args:
            item_id: Task.id to cancel.
            raiser_id: WorkspaceUser.id of the raiser.

        Returns:
            Canceled Task or None.
        """
        item = cls.scoped().filter_by(id=item_id, status="open", raised_by_id=raiser_id).first()
        if not item:
            return None

        item.status = "canceled"
        item.workflow_status = "done"
        item.resolved_at = datetime.utcnow()
        db.session.commit()

        from .task_log import TaskLog
        TaskLog.log(item.id, "canceled", raiser_id)

        # Notify assignee
        try:
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            raiser_name = item.raised_by.user.first_name if item.raised_by else "Someone"
            SystemNotification.create(
                title=item.title[:100],
                message=f"Canceled by {raiser_name}",
                type="info",
                target_role="user",
                user_id=item.assignee.user_id,
                icon="fa-ban",
                action_url="/tasks/",
                category=NotificationCategory.TASK_ASSIGNED,
            )
        except Exception:
            pass

        return item

    @classmethod
    def reopen(cls, item_id, raiser_id):
        """Reopen a resolved Task (raiser only, within 24hrs).

        Args:
            item_id: Task.id to reopen.
            raiser_id: WorkspaceUser.id of the raiser.

        Returns:
            Reopened Task or None.
        """
        item = cls.scoped().filter_by(id=item_id, status="resolved", raised_by_id=raiser_id).first()
        if not item or not item.can_reopen():
            return None

        item.status = "open"
        item.workflow_status = "todo"
        item.resolved_at = None
        item.resolved_by_id = None
        item.resolution_note = None
        db.session.commit()

        from .task_log import TaskLog
        TaskLog.log(item.id, "reopened", raiser_id)

        return item

    @classmethod
    def set_workflow_status(cls, item_id, status):
        """Set the workflow_status of an open Task.

        Args:
            item_id: Task.id to update.
            status: New workflow_status value (e.g. "in_progress", "todo").

        Returns:
            Updated Task or None if not found.
        """
        item = cls.scoped().filter_by(id=item_id, status="open").first()
        if not item:
            return None
        item.workflow_status = status
        db.session.commit()
        return item

    @classmethod
    def open_tier1_counts_by_assignee(cls) -> dict:
        """Return {assignee_id: count} for open Tier-1 tasks in the current workspace.

        Used by the integrations collaborator picker to display NOW counts.
        """
        from sqlalchemy import func
        rows = (
            cls.scoped()
            .with_entities(cls.assignee_id, func.count().label("cnt"))
            .filter(cls.status == "open", cls.urgency_tier == 1)
            .group_by(cls.assignee_id)
            .all()
        )
        return {r.assignee_id: r.cnt for r in rows}

    @classmethod
    def open_blocker_counts_by_assignee(cls) -> dict:
        """Return {assignee_id: count} for open blocker tasks in the current workspace.

        Used by the integrations collaborator picker to display blocker counts.
        """
        from sqlalchemy import func
        rows = (
            cls.scoped()
            .with_entities(cls.assignee_id, func.count().label("cnt"))
            .filter(cls.status == "open", cls.is_blocker.is_(True))
            .group_by(cls.assignee_id)
            .all()
        )
        return {r.assignee_id: r.cnt for r in rows}

    @classmethod
    def snooze(cls, item_id, member_id):
        """Snooze a Tier 1 Task for 30 minutes (one-time).

        Args:
            item_id: Task.id to snooze.
            member_id: WorkspaceUser.id of the assignee requesting snooze.

        Returns:
            Snoozed Task or None if not found/not eligible.
        """
        item = cls.scoped().filter_by(id=item_id, status="open").first()
        if not item:
            return None

        # Only assignee can snooze, only Tier 1, only once
        if item.assignee_id != member_id:
            return None
        if item.urgency_tier != 1 or item.snoozed:
            return None

        item.snoozed = True
        item.snooze_until = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()

        from .task_log import TaskLog
        TaskLog.log(item.id, "snoozed", member_id, "Snoozed for 30 minutes")

        return item

    # ── Helpers ────────────────────────────────────────────────────────────

    def can_reopen(self):
        """Check if this item can be reopened (within 24hrs of resolution)."""
        if self.status != "resolved" or not self.resolved_at:
            return False
        return datetime.utcnow() - self.resolved_at < timedelta(hours=24)

    def set_watchers(self, watcher_ids: list[int]) -> None:
        """Replace the watchers list for this action item.

        Args:
            watcher_ids: List of WorkspaceUser.ids, or empty list to clear.
        """
        if watcher_ids:
            from modules.base.core.models.workspace_user import WorkspaceUser
            self.watchers = WorkspaceUser.scoped().filter(
                WorkspaceUser.id.in_(watcher_ids)
            ).all()
        else:
            self.watchers = []
        db.session.commit()

    def tier_label(self):
        """Get the display label for this item's urgency tier.

        Reads custom labels from WorkspaceSettings, falls back to TIER_DEFAULTS.
        """
        try:
            from modules.base.core.models.workspace_settings import WorkspaceSettings
            settings = WorkspaceSettings.get_instance()
            custom = settings.tasks_tier_labels
            if custom and str(self.urgency_tier) in custom:
                return custom[str(self.urgency_tier)]
        except Exception:
            pass
        return TIER_DEFAULTS.get(self.urgency_tier, {}).get("label", "Unknown")

    def tier_color(self):
        """Get the hex color for this item's urgency tier."""
        return TIER_DEFAULTS.get(self.urgency_tier, {}).get("color", "#6b7280")

    def time_ago(self):
        """Return human-readable time since creation."""
        now = datetime.utcnow()
        diff = now - self.created_at
        if diff.days > 0:
            return f"{diff.days}d ago" if diff.days > 1 else "1d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago" if hours > 1 else "1h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago" if minutes > 1 else "1m ago"
        return "just now"

    @property
    def is_system_raised(self):
        """Whether this was raised by the system (no raiser)."""
        return self.raised_by_id is None

    @property
    def post_now_url(self) -> str | None:
        """Return the deep-link URL for posting, or None if not applicable."""
        if self.source_type not in ("missed_checkin", "missed_periodic"):
            return None

        template_name = self._extract_template_name()
        if not template_name:
            return None

        try:
            from flask import url_for

            from modules.base.updates.models.template import UpdateTemplate

            template = UpdateTemplate.get_by_name(template_name)
            if not template:
                return None
            return url_for("sync_bp.post_new", template_id=template.id)
        except Exception:
            return None

    def _extract_template_name(self) -> str | None:
        """Extract the UpdateTemplate name from this item's title."""
        if self.source_type == "missed_checkin" and self.title and self.title.endswith(" check-in"):
            return self.title[: -len(" check-in")]
        if self.source_type == "missed_periodic" and self.title and self.title.endswith(" update"):
            return self.title[: -len(" update")]
        return None

    @classmethod
    def _auto_resolve_linked_blocker(cls, item, resolver_id):
        """Auto-resolve a linked blocker when this Task resolves.

        Note: SyncBlocker table has been dropped. This method is now a no-op
        but kept for forward compatibility if blocker resolution is re-added.
        """
        pass

    @classmethod
    def _email_assignee(cls, item):
        """Send an email to the assignee when a Task is created."""
        if not item.raised_by_id:
            return
        try:
            from flask import url_for

            from modules.base.core.models.workspace_settings import WorkspaceSettings
            from system.email.service import is_configured, send_email_async
            from system.email.templates import (
                get_task_assigned_email_html,
                get_task_assigned_email_text,
            )
            if not is_configured():
                return

            company = WorkspaceSettings.get_instance()
            company_name = company.company_name or "Our Company"

            tier_defaults = TIER_DEFAULTS.get(item.urgency_tier, {})
            urgency_label = tier_defaults.get("label", "Task")
            urgency_color = tier_defaults.get("color", "#6b7280")

            raiser_name = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"
            assignee_first_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Team Member"
            assignee_email = item.assignee.user.email if item.assignee and item.assignee.user else None
            if not assignee_email:
                return

            action_url = url_for("tasks_bp.detail", item_id=item.id, _external=True)

            html_body = get_task_assigned_email_html(
                company_name=company_name,
                assignee_first_name=assignee_first_name,
                raiser_name=raiser_name,
                title=item.title,
                urgency_label=urgency_label,
                urgency_color=urgency_color,
                context_note=item.context_note,
                action_url=action_url,
            )
            text_body = get_task_assigned_email_text(
                company_name=company_name,
                assignee_first_name=assignee_first_name,
                raiser_name=raiser_name,
                title=item.title,
                urgency_label=urgency_label,
                context_note=item.context_note,
                action_url=action_url,
            )

            send_email_async(
                to=assignee_email,
                subject=f"Task: {item.title[:80]}",
                html_body=html_body,
                text_body=text_body,
            )
        except Exception:
            pass

    @classmethod
    def _notify_raiser_resolved(cls, item):
        """Send a notification and email to the raiser when their Task is resolved."""
        if not item.raised_by_id:
            return
        try:
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            from modules.base.core.services.push_notification import send_push
            assignee_name = item.assignee.user.first_name if item.assignee else "Someone"
            msg = f"Resolved by {assignee_name}"
            if item.resolution_note:
                msg += f" — {item.resolution_note[:100]}"

            SystemNotification.create(
                title=item.title[:100],
                message=msg,
                type="success",
                target_role="user",
                user_id=item.raised_by.user_id,
                icon="fa-check-circle",
                action_url=f"/tasks/{item.id}",
                category=NotificationCategory.BLOCKER_RESOLVED,
            )
            send_push(
                user_id=item.raised_by.user_id,
                title=item.title[:80],
                body=msg,
                url=f"/tasks/{item.id}",
            )
        except Exception:
            pass

        # Email the raiser
        try:
            from flask import url_for

            from modules.base.core.models.workspace_settings import WorkspaceSettings
            from system.email.service import is_configured, send_email_async
            from system.email.templates import (
                get_task_resolved_email_html,
                get_task_resolved_email_text,
            )
            if not is_configured():
                return

            raiser_email = item.raised_by.user.email if item.raised_by and item.raised_by.user else None
            if not raiser_email:
                return

            company = WorkspaceSettings.get_instance()
            company_name = company.company_name or "Our Company"
            assignee_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Someone"
            raiser_first_name = item.raised_by.user.first_name if item.raised_by.user else "there"
            action_url = url_for("tasks_bp.detail", item_id=item.id, _external=True)

            html_body = get_task_resolved_email_html(
                company_name=company_name,
                raiser_first_name=raiser_first_name,
                assignee_name=assignee_name,
                title=item.title,
                resolution_note=item.resolution_note,
                action_url=action_url,
            )
            text_body = get_task_resolved_email_text(
                company_name=company_name,
                raiser_first_name=raiser_first_name,
                assignee_name=assignee_name,
                title=item.title,
                resolution_note=item.resolution_note,
                action_url=action_url,
            )

            send_email_async(
                to=raiser_email,
                subject=f"Resolved: {item.title[:80]}",
                html_body=html_body,
                text_body=text_body,
            )
        except Exception:
            pass

    @classmethod
    def _notify_watchers_resolved(cls, item: "Task") -> None:
        """Notify watchers when a Task is resolved.

        Sends in-app notification, push notification, and email to each watcher.
        Skips the raiser and resolver (they already receive their own notifications).
        """
        if not item.watchers:
            return

        # Build set of user_ids to skip (already notified via other paths)
        skip_user_ids = set()
        if item.raised_by and item.raised_by.user:
            skip_user_ids.add(item.raised_by.user_id)
        if item.resolved_by and item.resolved_by.user:
            skip_user_ids.add(item.resolved_by.user_id)

        assignee_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Someone"
        msg = f"Resolved by {assignee_name}"
        if item.resolution_note:
            msg += f" — {item.resolution_note[:100]}"

        for watcher in item.watchers:
            if not watcher.user or watcher.user_id in skip_user_ids:
                continue

            # In-app notification
            try:
                from modules.base.core.models.notification import NotificationCategory, SystemNotification
                from modules.base.core.services.push_notification import send_push

                SystemNotification.create(
                    title=item.title[:100],
                    message=msg,
                    type="success",
                    target_role="user",
                    user_id=watcher.user_id,
                    icon="fa-check-circle",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.BLOCKER_RESOLVED,
                )
                send_push(
                    user_id=watcher.user_id,
                    title=item.title[:80],
                    body=msg,
                    url=f"/tasks/{item.id}",
                )
            except Exception:
                pass

            # Email
            try:
                from flask import url_for

                from modules.base.core.models.workspace_settings import WorkspaceSettings
                from system.email.service import is_configured, send_email_async
                from system.email.templates import (
                    get_task_watcher_resolved_email_html,
                    get_task_watcher_resolved_email_text,
                )
                if not is_configured():
                    continue

                watcher_email = watcher.user.email
                if not watcher_email:
                    continue

                company = WorkspaceSettings.get_instance()
                company_name = company.company_name or "Our Company"
                watcher_first_name = watcher.user.first_name or "there"
                raiser_name = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"
                action_url = url_for("tasks_bp.detail", item_id=item.id, _external=True)

                html_body = get_task_watcher_resolved_email_html(
                    company_name=company_name,
                    watcher_first_name=watcher_first_name,
                    assignee_name=assignee_name,
                    raiser_name=raiser_name,
                    title=item.title,
                    resolution_note=item.resolution_note,
                    action_url=action_url,
                )
                text_body = get_task_watcher_resolved_email_text(
                    company_name=company_name,
                    watcher_first_name=watcher_first_name,
                    assignee_name=assignee_name,
                    raiser_name=raiser_name,
                    title=item.title,
                    resolution_note=item.resolution_note,
                    action_url=action_url,
                )

                send_email_async(
                    to=watcher_email,
                    subject=f"Resolved: {item.title[:80]}",
                    html_body=html_body,
                    text_body=text_body,
                )
            except Exception:
                pass

    @classmethod
    def _notify_project_followers_resolved(cls, item: "Task") -> None:
        """Notify project followers (interested parties) when a Task is resolved.

        Fires for items that belong to a project. Skips members who are already
        notified via the raiser, resolver, or watcher paths.

        Args:
            item: The resolved Task instance.
        """
        if not item.project_id:
            return

        try:
            from modules.base.projects.models.project import Project
            project = Project.scoped().filter_by(id=item.project_id).first()
            if not project:
                return
            followers = project.get_followers()
        except Exception:
            return

        if not followers:
            return

        # Build the skip set from already-notified paths
        skip_user_ids = set()
        if item.raised_by and item.raised_by.user:
            skip_user_ids.add(item.raised_by.user_id)
        if item.resolved_by and item.resolved_by.user:
            skip_user_ids.add(item.resolved_by.user_id)
        for watcher in (item.watchers or []):
            if watcher.user:
                skip_user_ids.add(watcher.user_id)

        assignee_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Someone"
        msg = f"Resolved by {assignee_name} in {project.name}"
        if item.resolution_note:
            msg += f" — {item.resolution_note[:100]}"

        for follower in followers:
            if not follower.user or follower.user_id in skip_user_ids:
                continue

            try:
                from modules.base.core.models.notification import NotificationCategory, SystemNotification
                from modules.base.core.services.push_notification import send_push

                SystemNotification.create(
                    title=item.title[:100],
                    message=msg,
                    type="success",
                    target_role="user",
                    user_id=follower.user_id,
                    icon="fa-check-circle",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.PROJECT_UPDATE,
                )
                send_push(
                    user_id=follower.user_id,
                    title=item.title[:80],
                    body=msg,
                    url=f"/tasks/{item.id}",
                )
            except Exception:
                pass

            try:
                from flask import url_for

                from modules.base.core.models.workspace_settings import WorkspaceSettings
                from system.email.service import is_configured, send_email_async
                from system.email.templates import (
                    get_task_watcher_resolved_email_html,
                    get_task_watcher_resolved_email_text,
                )
                if not is_configured():
                    continue

                follower_email = follower.user.email
                if not follower_email:
                    continue

                company = WorkspaceSettings.get_instance()
                company_name = company.company_name or "Our Company"
                follower_first_name = follower.user.first_name or "there"
                raiser_name = item.raised_by.user.first_name if item.raised_by and item.raised_by.user else "Someone"
                action_url = url_for("tasks_bp.detail", item_id=item.id, _external=True)

                html_body = get_task_watcher_resolved_email_html(
                    company_name=company_name,
                    watcher_first_name=follower_first_name,
                    assignee_name=assignee_name,
                    raiser_name=raiser_name,
                    title=item.title,
                    resolution_note=item.resolution_note,
                    action_url=action_url,
                )
                text_body = get_task_watcher_resolved_email_text(
                    company_name=company_name,
                    watcher_first_name=follower_first_name,
                    assignee_name=assignee_name,
                    raiser_name=raiser_name,
                    title=item.title,
                    resolution_note=item.resolution_note,
                    action_url=action_url,
                )

                send_email_async(
                    to=follower_email,
                    subject=f"Resolved: {item.title[:80]}",
                    html_body=html_body,
                    text_body=text_body,
                )
            except Exception:
                pass

    @classmethod
    def _notify_project_owners_review(cls, item: "Task") -> None:
        """Notify project owner + co-owners when a task enters 'Needs Review'.

        In-app + push notification only (no email). Skips the user who moved
        the task into review.

        Args:
            item: The Task that entered needs_review status.
        """
        if not item.project_id:
            return

        try:
            from modules.base.core.models.workspace_user import WorkspaceUser
            from modules.base.projects.models.project import Project
            from sqlalchemy.orm import joinedload as _jl

            project = (
                Project.scoped()
                .options(_jl(Project.owner).joinedload(WorkspaceUser.user))
                .filter_by(id=item.project_id)
                .first()
            )
            if not project:
                return
        except Exception:
            return

        from flask_login import current_user

        skip_user_id = getattr(current_user, "id", None)

        recipients = []
        if project.owner and project.owner.user:
            recipients.append(project.owner)
        for co_owner in project.get_co_owners():
            if co_owner.user:
                recipients.append(co_owner)

        if not recipients:
            return

        assignee_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Someone"
        msg = f"{assignee_name} submitted a task for review in {project.name}"

        for recipient in recipients:
            if recipient.user_id == skip_user_id:
                continue

            try:
                from modules.base.core.models.notification import NotificationCategory, SystemNotification
                from modules.base.core.services.push_notification import send_push

                SystemNotification.create(
                    title=item.title[:100],
                    message=msg,
                    type="info",
                    target_role="user",
                    user_id=recipient.user_id,
                    icon="fa-clipboard-check",
                    action_url=f"/tasks/{item.id}",
                    category=NotificationCategory.REVIEW_REQUEST,
                )
                send_push(
                    user_id=recipient.user_id,
                    title=item.title[:80],
                    body=msg,
                    url=f"/tasks/{item.id}",
                )
            except Exception:
                pass

    @classmethod
    def get_pending_reviews(cls, member_id: int) -> list["Task"]:
        """Get tasks in 'needs_review' where the member is project owner or co-owner.

        Args:
            member_id: WorkspaceUser.id to check ownership for.

        Returns:
            List of Task instances awaiting review.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.projects.models.project import Project
        from modules.base.projects.models.co_owner import project_co_owner

        owner_tasks = (
            cls.scoped()
            .join(Project, cls.project_id == Project.id)
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(
                cls.workflow_status == "needs_review",
                cls.status == "open",
                Project.owner_id == member_id,
            )
            .all()
        )

        co_owner_tasks = (
            cls.scoped()
            .join(Project, cls.project_id == Project.id)
            .join(project_co_owner, project_co_owner.c.project_id == Project.id)
            .options(
                joinedload(cls.assignee).joinedload(WorkspaceUser.user),
                joinedload(cls.project),
            )
            .filter(
                cls.workflow_status == "needs_review",
                cls.status == "open",
                project_co_owner.c.member_id == member_id,
            )
            .all()
        )

        seen = set()
        result = []
        for task in owner_tasks + co_owner_tasks:
            if task.id not in seen:
                seen.add(task.id)
                result.append(task)
        return result


# ── GitHub sync listener ──────────────────────────────────────────────────────

def _task_after_update(mapper, connection, target: Task) -> None:
    """Fire sparQ → GitHub sync when sync-relevant Task fields change.

    Registered as an after_update mapper event so it runs on every flush of
    a dirty Task row. Checks _SYNC_IN_PROGRESS to avoid echoing back a change
    that originated from GitHub. The submit_task call enqueues the sync to a
    thread pool; in practice the thread runs after the request's transaction
    commits, so the background read sees consistent data.

    Sync-relevant fields: workflow_status, urgency_tier, assignee_id.
    """
    try:
        from sqlalchemy import inspect as sa_inspect
        from system.background import submit_task

        try:
            from modules.integrations.github.sync import (
                _SYNC_IN_PROGRESS,
                sync_sparq_to_github,
            )
            _GITHUB_AVAILABLE = True
        except ImportError:
            _GITHUB_AVAILABLE = False
            _SYNC_IN_PROGRESS = {}

        if _SYNC_IN_PROGRESS.get(target.id, False):
            print(f"[sync] _task_after_update: suppressed (in-progress) task={target.id}")
            return

        insp = sa_inspect(target)
        changed: set[str] = set()
        for field in ("workflow_status", "urgency_tier", "assignee_id"):
            hist = getattr(insp.attrs, field).history
            if hist.has_changes() and hist.deleted:
                changed.add(field)

        print(f"[sync] _task_after_update: task={target.id} changed={changed}")
        if not changed:
            return

        # Capture in-memory state now — the background thread starts before the
        # transaction commits, so it would otherwise read stale DB values.
        snapshot = {
            "status": target.status,
            "workflow_status": target.workflow_status,
            "urgency_tier": target.urgency_tier,
            "assignee_id": target.assignee_id,
        }
        if _GITHUB_AVAILABLE:
            submit_task(sync_sparq_to_github, target.id, changed, snapshot)
            print(f"[sync] _task_after_update: submitted sync for task={target.id} snapshot={snapshot}")
    except Exception:
        import logging
        import traceback
        traceback.print_exc()
        logging.getLogger(__name__).exception(
            "_task_after_update: failed to enqueue sync for task_id=%s", target.id
        )


from sqlalchemy import event as _sa_event  # noqa: E402
_sa_event.listen(Task, "after_update", _task_after_update)
