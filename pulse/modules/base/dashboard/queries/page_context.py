# -----------------------------------------------------------------------------
# sparQ — Dashboard: Page context projection query (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, case, func, literal, or_, select

from system.db.database import db


@dataclass(frozen=True)
class PageContextRow:
    notification_count: int
    channel_unread_count: int
    dm_unread_count: int
    tasks_open_count: int
    open_blockers_count: int
    my_tasks_inbox_count: int
    focus_signal_value: str | None
    time_clock_enabled: bool
    clock_punch_type: str | None
    clock_punch_time: datetime | None
    clock_outside_geofence: bool
    pending_leave_count: int
    pending_correction_count: int


def get_dashboard_page_context(
    organization_id: UUID,
    workspace_id: UUID,
    user_id: int,
    member_id: int | None,
    is_admin: bool,
    org_member_id: int | None = None,
) -> PageContextRow:
    """Single query with scalar subqueries for all context processor badge/count data.

    Replaces ~15 individual queries from context processors with 1 SQL statement.
    """
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.notification import SystemNotification
    from modules.base.presence.models.clock_punch import ClockPunch
    from modules.base.presence.models.leave_request import LeaveRequest, LeaveRequestStatus
    from modules.base.core.models.user_setting import UserSetting
    from modules.base.presence.models.punch_correction_request import (
        PunchCorrectionRequest,
        PunchCorrectionRequestStatus,
    )
    from modules.base.presence.models.settings import TimeTrackingSettings
    from modules.base.updates.models.dm import DM, DMThread
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState

    # -- Notification count --
    if is_admin:
        notif_sq = (
            select(func.count())
            .select_from(SystemNotification)
            .where(
                SystemNotification.organization_id == organization_id,
                SystemNotification.workspace_id == workspace_id,
                SystemNotification.is_dismissed.is_(False),
                SystemNotification.is_read.is_(False),
                or_(
                    SystemNotification.user_id == user_id,
                    and_(
                        SystemNotification.user_id.is_(None),
                        SystemNotification.target_role.in_(["admin", "all"]),
                    ),
                ),
            )
            .correlate(None)
            .scalar_subquery()
        )
    else:
        notif_sq = (
            select(func.count())
            .select_from(SystemNotification)
            .where(
                SystemNotification.organization_id == organization_id,
                SystemNotification.workspace_id == workspace_id,
                SystemNotification.is_dismissed.is_(False),
                SystemNotification.is_read.is_(False),
                or_(
                    SystemNotification.user_id == user_id,
                    and_(
                        SystemNotification.user_id.is_(None),
                        SystemNotification.target_role == "all",
                    ),
                ),
            )
            .correlate(None)
            .scalar_subquery()
        )

    # -- Action item counts --
    if member_id is not None:
        ai_open_count_sq = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.organization_id == organization_id,
                Task.workspace_id == workspace_id,
                Task.assignee_id == member_id,
                Task.status == "open",
                Task.raised_by_id.isnot(None),
            )
            .correlate(None)
            .scalar_subquery()
        )
        ai_inbox_count_sq = (
            select(func.count())
            .select_from(Task)
            .where(
                Task.organization_id == organization_id,
                Task.workspace_id == workspace_id,
                Task.assignee_id == member_id,
                Task.status == "open",
            )
            .correlate(None)
            .scalar_subquery()
        )
    else:
        ai_open_count_sq = literal(0).label("ai_open")
        ai_inbox_count_sq = literal(0).label("ai_inbox")

    blocker_count_sq = (
        select(func.count())
        .select_from(Task)
        .where(
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
            Task.is_blocker.is_(True),
            Task.status == "open",
        )
        .correlate(None)
        .scalar_subquery()
    )

    # -- Clock punch (latest for current member, org-scoped) --
    if org_member_id is not None:
        clock_sq = (
            select(ClockPunch.punch_type, ClockPunch.punch_time, ClockPunch.outside_geofence)
            .where(
                ClockPunch.organization_id == organization_id,
                ClockPunch.member_id == org_member_id,
            )
            .order_by(ClockPunch.punch_time.desc())
            .limit(1)
            .subquery()
        )
        clock_type_sq = select(clock_sq.c.punch_type).correlate(None).scalar_subquery()
        clock_time_sq = select(clock_sq.c.punch_time).correlate(None).scalar_subquery()
        clock_geofence_sq = select(clock_sq.c.outside_geofence).correlate(None).scalar_subquery()
    else:
        clock_type_sq = literal(None)
        clock_time_sq = literal(None)
        clock_geofence_sq = literal(False)

    # -- Focus status (from UserSetting) --
    if member_id is not None:
        raw_flow_sq = (
            select(UserSetting.value)
            .where(
                UserSetting.organization_id == organization_id,
                UserSetting.workspace_id == workspace_id,
                UserSetting.user_id == user_id,
                UserSetting.key == "flow_status",
            )
            .limit(1)
            .correlate(None)
            .scalar_subquery()
        )
        focus_sq = case(
            (raw_flow_sq == "flow", literal("focus")),
            else_=literal("available"),
        )
    else:
        focus_sq = literal(None)

    # -- Nav badges (admin only) --
    if is_admin:
        leave_pending_sq = (
            select(func.count())
            .select_from(LeaveRequest)
            .where(
                LeaveRequest.organization_id == organization_id,
                LeaveRequest.status == LeaveRequestStatus.PENDING,
            )
            .correlate(None)
            .scalar_subquery()
        )
        correction_pending_sq = (
            select(func.count())
            .select_from(PunchCorrectionRequest)
            .where(
                PunchCorrectionRequest.organization_id == organization_id,
                PunchCorrectionRequest.status == PunchCorrectionRequestStatus.PENDING,
            )
            .correlate(None)
            .scalar_subquery()
        )
    else:
        leave_pending_sq = literal(0)
        correction_pending_sq = literal(0)

    # -- Chat unread: channel unread count --
    # Single query: count posts newer than last-read per channel
    channel_unread_sq = (
        select(func.coalesce(func.sum(
            case(
                (UpdatePost.id > func.coalesce(UpdateChannelReadState.last_read_post_id, 0), 1),
                else_=0,
            )
        ), 0))
        .select_from(UpdatePost)
        .join(UpdateChannel, UpdateChannel.id == UpdatePost.channel_id)
        .outerjoin(
            UpdateChannelReadState,
            and_(
                UpdateChannelReadState.channel_id == UpdatePost.channel_id,
                UpdateChannelReadState.member_id == member_id,
                UpdateChannelReadState.organization_id == organization_id,
                UpdateChannelReadState.workspace_id == workspace_id,
            ),
        )
        .where(
            UpdatePost.organization_id == organization_id,
            UpdatePost.workspace_id == workspace_id,
            UpdatePost.channel_id.isnot(None),
            UpdateChannel.organization_id == organization_id,
            UpdateChannel.workspace_id == workspace_id,
        )
        .correlate(None)
        .scalar_subquery()
    ) if member_id is not None else literal(0)

    # -- Chat unread: DM unread count --
    dm_unread_sq = (
        select(func.count())
        .select_from(DM)
        .join(DMThread, DMThread.id == DM.thread_id)
        .where(
            DM.organization_id == organization_id,
            DM.member_id != member_id,
            DM.read_at.is_(None),
            or_(
                DMThread.member1_id == member_id,
                DMThread.member2_id == member_id,
            ),
        )
        .correlate(None)
        .scalar_subquery()
    ) if member_id is not None else literal(0)

    # -- Time clock enabled --
    time_clock_sq = (
        select(TimeTrackingSettings.time_clock_enabled)
        .where(
            TimeTrackingSettings.organization_id == organization_id,
        )
        .limit(1)
        .correlate(None)
        .scalar_subquery()
    )

    # -- Execute single statement --
    stmt = select(
        notif_sq.label("notification_count"),
        channel_unread_sq.label("channel_unread_count"),
        dm_unread_sq.label("dm_unread_count"),
        ai_open_count_sq.label("tasks_open_count"),
        blocker_count_sq.label("open_blockers_count"),
        ai_inbox_count_sq.label("my_tasks_inbox_count"),
        focus_sq.label("focus_signal_value"),
        func.coalesce(time_clock_sq, False).label("time_clock_enabled"),
        clock_type_sq.label("clock_punch_type"),
        clock_time_sq.label("clock_punch_time"),
        func.coalesce(clock_geofence_sq, False).label("clock_outside_geofence"),
        leave_pending_sq.label("pending_leave_count"),
        correction_pending_sq.label("pending_correction_count"),
    )

    row = db.session.execute(stmt).one()

    return PageContextRow(
        notification_count=row.notification_count or 0,
        channel_unread_count=row.channel_unread_count or 0,
        dm_unread_count=row.dm_unread_count or 0,
        tasks_open_count=row.tasks_open_count or 0,
        open_blockers_count=row.open_blockers_count or 0,
        my_tasks_inbox_count=row.my_tasks_inbox_count or 0,
        focus_signal_value=row.focus_signal_value,
        time_clock_enabled=bool(row.time_clock_enabled),
        clock_punch_type=row.clock_punch_type.value if row.clock_punch_type else None,
        clock_punch_time=row.clock_punch_time,
        clock_outside_geofence=bool(row.clock_outside_geofence),
        pending_leave_count=row.pending_leave_count or 0,
        pending_correction_count=row.pending_correction_count or 0,
    )
