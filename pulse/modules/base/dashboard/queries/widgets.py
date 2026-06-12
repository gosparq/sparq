# -----------------------------------------------------------------------------
# sparQ — Dashboard: Widget projection queries (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.orm import aliased

from system.db.database import db


# ---------------------------------------------------------------------------
# BLUF Metrics
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlufMetrics:
    slipped: int
    shipped: int
    blocked_member_ids: set[int]
    blocking_member_ids: set[int]
    open_blockers_count: int
    _blocker_assignee_ids: tuple[int, ...]
    blocking_names_map: dict[int, tuple[str, ...]]
    blocked_item_ids_map: dict[int, tuple[int, ...]]
    blocking_item_ids_map: dict[int, tuple[int, ...]]

    def decisions_for(self, member_id: int | None) -> int:
        if member_id is None:
            return 0
        return sum(1 for aid in self._blocker_assignee_ids if aid == member_id)


def get_bluf_metrics(
    organization_id: UUID,
    workspace_id: UUID,
    start_of_week: date,
    today: date,
) -> BlufMetrics:
    """BLUF metrics: slipped count, shipped count, and blocker member IDs.

    Two queries: scalar subqueries for counts + lightweight blocker ID fetch.
    """
    from modules.base.tasks.models.task import Task

    last_week_end = start_of_week - timedelta(days=1)
    start_dt = datetime.combine(start_of_week, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    slipped_sq = (
        select(func.count())
        .select_from(Task)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.status == "open",
            Task.due_date <= last_week_end,
        )
        .correlate(None)
        .scalar_subquery()
    )

    shipped_sq = (
        select(func.count())
        .select_from(Task)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.status == "resolved",
            Task.resolved_at >= start_dt,
            Task.resolved_at <= end_dt,
            Task.raised_by_id.isnot(None),
        )
        .correlate(None)
        .scalar_subquery()
    )

    counts = db.session.execute(
        select(slipped_sq.label("slipped"), shipped_sq.label("shipped"))
    ).one()

    from modules.base.core.models.workspace_user import WorkspaceUser as _TSU
    from modules.base.core.models.user import User as _User

    RaisedByTSU = aliased(_TSU)
    RaisedByUser = aliased(_User)

    blocker_rows = db.session.execute(
        select(
            Task.id,
            Task.assignee_id,
            Task.raised_by_id,
            RaisedByUser.first_name.label("raised_by_first_name"),
        )
        .outerjoin(RaisedByTSU, RaisedByTSU.id == Task.raised_by_id)
        .outerjoin(RaisedByUser, RaisedByUser.id == RaisedByTSU.user_id)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.is_blocker.is_(True),
            Task.status == "open",
        )
    ).all()

    blocked_ids: set[int] = set()
    blocking_ids: set[int] = set()
    blocking_names_map: dict[int, list[str]] = {}
    blocked_item_ids_map: dict[int, list[int]] = {}
    blocking_item_ids_map: dict[int, list[int]] = {}

    for r in blocker_rows:
        if r.raised_by_id:
            blocked_ids.add(r.raised_by_id)
            blocked_item_ids_map.setdefault(r.raised_by_id, []).append(r.id)
        if r.assignee_id:
            blocking_ids.add(r.assignee_id)
            blocking_item_ids_map.setdefault(r.assignee_id, []).append(r.id)
            if r.raised_by_first_name:
                blocking_names_map.setdefault(r.assignee_id, []).append(r.raised_by_first_name)

    return BlufMetrics(
        slipped=counts.slipped or 0,
        shipped=counts.shipped or 0,
        blocked_member_ids=blocked_ids,
        blocking_member_ids=blocking_ids,
        open_blockers_count=len(blocker_rows),
        _blocker_assignee_ids=tuple(r.assignee_id for r in blocker_rows if r.assignee_id),
        blocking_names_map={k: tuple(v) for k, v in blocking_names_map.items()},
        blocked_item_ids_map={k: tuple(v) for k, v in blocked_item_ids_map.items()},
        blocking_item_ids_map={k: tuple(v) for k, v in blocking_item_ids_map.items()},
    )


# ---------------------------------------------------------------------------
# Team Status
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TeamStatusRow:
    """Flat projection of a team member's clock/focus/blocker status."""

    member_id: int
    user_id: int
    first_name: str
    last_name: str
    avatar_color: str | None
    is_clocked_in: bool
    flow_status: str
    is_blocked: bool
    is_blocking: bool
    blocking_names: tuple[str, ...]
    blocked_item_ids: tuple[int, ...]
    blocking_item_ids: tuple[int, ...]
    last_activity_at: datetime | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


def get_team_status(
    organization_id: UUID,
    workspace_id: UUID,
    focus_signal_map: dict[int, str],
    bluf: "BlufMetrics",
) -> list[TeamStatusRow]:
    """Return team members with clock-in, focus, and blocker status."""
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus
    from modules.base.core.models.user import User
    from modules.base.core.models.user_setting import UserSetting
    from modules.base.dashboard.models.activity_log import ActivityLog
    from modules.base.presence.models.clock_punch import ClockPunch

    MemberUser = aliased(User)
    FlowSetting = aliased(UserSetting)

    last_activity_sq = (
        select(
            ActivityLog.member_id,
            func.max(ActivityLog.created_at).label("last_activity_at"),
        )
        .where(
            ActivityLog.organization_id == organization_id,
            ActivityLog.workspace_id == workspace_id,
        )
        .group_by(ActivityLog.member_id)
        .subquery()
    )

    max_punch_sq = (
        select(
            ClockPunch.member_id,
            func.max(ClockPunch.punch_time).label("max_time"),
        )
        .where(
            ClockPunch.organization_id == organization_id,
        )
        .group_by(ClockPunch.member_id)
        .subquery()
    )

    latest_punch = (
        select(
            ClockPunch.member_id,
            ClockPunch.punch_type,
        )
        .join(
            max_punch_sq,
            and_(
                ClockPunch.member_id == max_punch_sq.c.member_id,
                ClockPunch.punch_time == max_punch_sq.c.max_time,
            ),
        )
        .subquery()
    )

    stmt = (
        select(
            WorkspaceUser.id.label("member_id"),
            MemberUser.id.label("user_id"),
            MemberUser.first_name,
            MemberUser.last_name,
            MemberUser._avatar_color.label("avatar_color"),
            latest_punch.c.punch_type,
            FlowSetting.value.label("legacy_flow"),
            last_activity_sq.c.last_activity_at,
        )
        .join(MemberUser, MemberUser.id == WorkspaceUser.user_id)
        .outerjoin(latest_punch, latest_punch.c.member_id == WorkspaceUser.organization_user_id)
        .outerjoin(last_activity_sq, last_activity_sq.c.member_id == WorkspaceUser.id)
        .outerjoin(
            FlowSetting,
            and_(
                FlowSetting.user_id == MemberUser.id,
                FlowSetting.key == "flow_status",
                FlowSetting.organization_id == organization_id,
                FlowSetting.workspace_id == workspace_id,
            ),
        )
        .where(
            WorkspaceUser.organization_id == organization_id,
            WorkspaceUser.workspace_id == workspace_id,
            WorkspaceUser.status == EmployeeStatus.ACTIVE,
        )
    )

    rows = db.session.execute(stmt).all()

    result = []
    for r in rows:
        is_clocked_in = r.punch_type is not None and r.punch_type.value == "in" if hasattr(r.punch_type, "value") else r.punch_type == "in"

        if r.member_id in focus_signal_map:
            flow = focus_signal_map[r.member_id]
        elif r.legacy_flow:
            flow = "focus" if r.legacy_flow == "flow" else "available"
        else:
            flow = "available"

        result.append(TeamStatusRow(
            member_id=r.member_id,
            user_id=r.user_id,
            first_name=r.first_name,
            last_name=r.last_name,
            avatar_color=r.avatar_color,
            is_clocked_in=is_clocked_in,
            flow_status=flow,
            is_blocked=r.member_id in bluf.blocked_member_ids,
            is_blocking=r.member_id in bluf.blocking_member_ids,
            blocking_names=bluf.blocking_names_map.get(r.member_id, ()),
            blocked_item_ids=bluf.blocked_item_ids_map.get(r.member_id, ()),
            blocking_item_ids=bluf.blocking_item_ids_map.get(r.member_id, ()),
            last_activity_at=r.last_activity_at,
        ))

    result.sort(key=lambda x: (not x.is_clocked_in, -(x.last_activity_at.timestamp() if x.last_activity_at else 0)))
    return result


# ---------------------------------------------------------------------------
# BLUF Tab: Overdue Items
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OverdueItemRow:
    """Flat projection of an open action item past its due date."""

    id: int
    title: str
    due_date: date
    assignee_first_name: str | None
    assignee_last_name: str | None
    assignee_avatar_color: str | None

    @property
    def days_overdue(self) -> int:
        return (date.today() - self.due_date).days


def get_overdue_items(
    organization_id: UUID,
    workspace_id: UUID,
    today: date,
    limit: int = 50,
) -> list[OverdueItemRow]:
    """Return open action items whose due date has already passed.

    Args:
        organization_id: Scoping UUID.
        workspace_id: Scoping UUID.
        today: Current date (items with due_date < today are overdue).
        limit: Max results.

    Returns:
        List of OverdueItemRow sorted by due_date ascending (oldest first).
    """
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User

    AssigneeTS = aliased(WorkspaceUser)
    AssigneeUser = aliased(User)

    stmt = (
        select(
            Task.id,
            Task.title,
            Task.due_date,
            AssigneeUser.first_name.label("assignee_first_name"),
            AssigneeUser.last_name.label("assignee_last_name"),
            AssigneeUser._avatar_color.label("assignee_avatar_color"),
        )
        .outerjoin(AssigneeTS, AssigneeTS.id == Task.assignee_id)
        .outerjoin(AssigneeUser, AssigneeUser.id == AssigneeTS.user_id)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.status == "open",
            Task.due_date.isnot(None),
            Task.due_date < today,
        )
        .order_by(Task.due_date.asc())
        .limit(limit)
    )

    rows = db.session.execute(stmt).all()
    return [
        OverdueItemRow(
            id=r.id,
            title=r.title,
            due_date=r.due_date,
            assignee_first_name=r.assignee_first_name,
            assignee_last_name=r.assignee_last_name,
            assignee_avatar_color=r.assignee_avatar_color,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# BLUF Tab: Completed This Week
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompletedItemRow:
    """Flat projection of a resolved action item from the current week."""

    id: int
    title: str
    resolved_at: datetime
    assignee_first_name: str | None
    assignee_last_name: str | None
    assignee_avatar_color: str | None


def get_completed_this_week(
    organization_id: UUID,
    workspace_id: UUID,
    start_of_week: date,
    today: date,
    limit: int = 50,
) -> list[CompletedItemRow]:
    """Return action items resolved during the current week.

    Args:
        organization_id: Scoping UUID.
        workspace_id: Scoping UUID.
        start_of_week: Monday of the current week.
        today: Current date (used as upper bound).
        limit: Max results.

    Returns:
        List of CompletedItemRow sorted by resolved_at descending (most recent first).
    """
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User

    start_dt = datetime.combine(start_of_week, datetime.min.time())
    end_dt = datetime.combine(today, datetime.max.time())

    AssigneeTS = aliased(WorkspaceUser)
    AssigneeUser = aliased(User)

    stmt = (
        select(
            Task.id,
            Task.title,
            Task.resolved_at,
            AssigneeUser.first_name.label("assignee_first_name"),
            AssigneeUser.last_name.label("assignee_last_name"),
            AssigneeUser._avatar_color.label("assignee_avatar_color"),
        )
        .outerjoin(AssigneeTS, AssigneeTS.id == Task.assignee_id)
        .outerjoin(AssigneeUser, AssigneeUser.id == AssigneeTS.user_id)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.status == "resolved",
            Task.resolved_at >= start_dt,
            Task.resolved_at <= end_dt,
        )
        .where(Task.raised_by_id.isnot(None))
        .order_by(Task.resolved_at.desc())
        .limit(limit)
    )

    rows = db.session.execute(stmt).all()
    return [
        CompletedItemRow(
            id=r.id,
            title=r.title,
            resolved_at=r.resolved_at,
            assignee_first_name=r.assignee_first_name,
            assignee_last_name=r.assignee_last_name,
            assignee_avatar_color=r.assignee_avatar_color,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Activity Log
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActivityRow:
    """Flat projection of an activity log entry for the dashboard feed."""

    id: int
    title: str
    description: str | None
    icon: str
    color: str
    url: str | None
    created_at: datetime
    member_id: int | None
    member_first_name: str | None
    model_type: str | None
    record_id: int | None

    @property
    def time_ago(self) -> str:
        delta = datetime.utcnow() - self.created_at
        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            return f"{delta.seconds // 3600}h ago"
        elif delta.seconds >= 60:
            return f"{delta.seconds // 60}m ago"
        return "just now"


def get_recent_activities(
    organization_id: UUID,
    workspace_id: UUID,
    limit: int = 10,
) -> list[ActivityRow]:
    """Return recent activity log entries with member names."""
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.dashboard.models.activity_log import ActivityLog

    MemberTS = aliased(WorkspaceUser)
    MemberUser = aliased(User)

    stmt = (
        select(
            ActivityLog.id,
            ActivityLog.title,
            ActivityLog.description,
            ActivityLog.icon,
            ActivityLog.color,
            ActivityLog.url,
            ActivityLog.created_at,
            ActivityLog.member_id,
            MemberUser.first_name.label("member_first_name"),
            ActivityLog.model_type,
            ActivityLog.record_id,
        )
        .outerjoin(MemberTS, MemberTS.id == ActivityLog.member_id)
        .outerjoin(MemberUser, MemberUser.id == MemberTS.user_id)
        .outerjoin(
            Task,
            and_(
                ActivityLog.model_type == "Task",
                ActivityLog.record_id == Task.id,
            ),
        )
        .where(
            ActivityLog.organization_id == organization_id,
            ActivityLog.workspace_id == workspace_id,
            db.or_(
                ActivityLog.model_type != "Task",
                Task.raised_by_id.isnot(None),
            ),
        )
        .order_by(ActivityLog.created_at.desc())
        .limit(limit)
    )

    rows = db.session.execute(stmt).all()
    return [
        ActivityRow(
            id=r.id,
            title=r.title,
            description=r.description,
            icon=r.icon,
            color=r.color,
            url=r.url,
            created_at=r.created_at,
            member_id=r.member_id,
            member_first_name=r.member_first_name,
            model_type=r.model_type,
            record_id=r.record_id,
        )
        for r in rows
    ]
