# -----------------------------------------------------------------------------
# sparQ - Sync Nudge Scheduler
#
# Description:
#     Background scheduler that checks every minute for users who haven't
#     posted to scheduled templates and sends SystemNotification reminders.
#     Supports daily (fire after nudge_time + grace) and periodic (fire
#     every N minutes) schedule types.
#
#     Nudge timing anchors to each member's MemberSchedule (per-day start/end
#     times) with MemberScheduleOverride support. Members who are pulse_exempt,
#     have no schedule, or are forecast OUT/PTO are skipped.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging
import threading
import time as _time
from datetime import datetime, time, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import schedule

if TYPE_CHECKING:
    from flask import Flask
    from modules.base.updates.models.template import UpdateTemplate
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser

logger = logging.getLogger(__name__)

_nudge_scheduler_running = False


def check_nudges(app: "Flask") -> None:
    """Check all workspaces for users who need nudge notifications.

    Args:
        app: Flask application instance for app_context.
    """
    with app.app_context():
        try:
            _check_nudges_inner()
        except Exception as e:
            logger.error(f"Nudge check failed: {e}")


def _check_nudges_inner() -> None:
    """Inner nudge check logic (runs inside app_context)."""
    from flask import g

    from modules.base.updates.models.event import Event
    from modules.base.updates.models.template import UpdateTemplate
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user_setting import UserSetting
    from modules.base.presence.queries.schedule import (
        get_team_forecast_statuses,
        get_team_schedules,
    )
    from system.db.database import db

    workspaces = Workspace.query.filter(
        Workspace.is_active.is_(True),
        Workspace.organization_id.isnot(None),
    ).all()

    for ts in workspaces:
        g.workspace_id = ts.id
        g.organization_id = ts.organization_id

        today_date = datetime.now(timezone.utc).date()
        is_holiday_today = bool(
            Event.scoped()
            .filter(Event.is_holiday.is_(True), Event.scheduled_date == today_date)
            .first()
        )
        if is_holiday_today:
            continue

        templates = UpdateTemplate.query.filter(
            UpdateTemplate.nudge_enabled.is_(True),
            UpdateTemplate.schedule_type.isnot(None),
            UpdateTemplate.is_active.is_(True),
            db.or_(
                UpdateTemplate.workspace_id == ts.id,
                UpdateTemplate.workspace_id.is_(None),
            ),
        ).all()

        if not templates:
            continue

        users = WorkspaceUser.get_workspace_users()
        if not users:
            continue

        members_by_user: dict[int, "WorkspaceUser"] = {}
        for member in WorkspaceUser.scoped().all():
            members_by_user[member.user_id] = member

        user_ids = [u.id for u in users]
        tz_map = UserSetting.get_bulk(user_ids, "timezone")

        # Member schedule + forecast lookups (replaces UserSetting start_time)
        schedule_map = get_team_schedules(
            ts.organization_id, ts.id, today_date
        )
        forecast_map = get_team_forecast_statuses(
            ts.organization_id, ts.id, today_date
        )

        ts_settings = WorkspaceSettings.get_instance()
        default_tz = ts_settings.timezone or "America/Chicago"

        now_utc = datetime.now(timezone.utc)

        _check_expirations(
            templates, users, members_by_user, tz_map,
            schedule_map, default_tz, now_utc,
        )

        for template in templates:
            for user in users:
                member = members_by_user.get(user.id)
                if not member:
                    continue

                if getattr(member, "pulse_exempt", False):
                    continue

                forecast_status = forecast_map.get(member.id)
                if forecast_status in ("out", "pto"):
                    continue

                effective_schedule = schedule_map.get(member.id)
                if effective_schedule is None:
                    continue

                effective_start, effective_end = effective_schedule

                user_tz_str = tz_map.get(user.id) or default_tz
                try:
                    user_tz = ZoneInfo(user_tz_str)
                except Exception:
                    user_tz = ZoneInfo(default_tz)

                local_now = now_utc.astimezone(user_tz)

                if not _in_nudge_scope(template, local_now):
                    continue

                if template.schedule_type == "daily":
                    _check_daily(
                        template, user, member, local_now, now_utc,
                        user_tz, effective_start, effective_end,
                    )
                elif template.schedule_type == "periodic":
                    _check_periodic(
                        template, user, member, local_now,
                        effective_start, effective_end,
                    )

        db.session.commit()


def _in_nudge_scope(template: "UpdateTemplate", local_now: datetime) -> bool:
    """Check if the user's local time falls within the template's nudge scope.

    Args:
        template: UpdateTemplate with optional nudge_scope.
        local_now: User's current local datetime (aware).

    Returns:
        True if nudge is allowed, False if outside scope.
    """
    scope = template.nudge_scope
    if scope is None:
        return True

    days = scope.get("days", [0, 1, 2, 3, 4])
    if local_now.weekday() not in days:
        return False

    start_str = scope.get("start", "08:00")
    end_str = scope.get("end", "18:00")
    try:
        start_h, start_m = map(int, start_str.split(":"))
        end_h, end_m = map(int, end_str.split(":"))
    except (ValueError, AttributeError):
        return True

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    now_minutes = local_now.hour * 60 + local_now.minute

    if start_minutes <= end_minutes:
        return start_minutes <= now_minutes < end_minutes
    else:
        return now_minutes >= start_minutes or now_minutes < end_minutes


def _check_daily(
    template: "UpdateTemplate",
    user: "User",
    member: "WorkspaceUser",
    local_now: datetime,
    now_utc: datetime,
    user_tz: ZoneInfo,
    effective_start: time,
    effective_end: time,
) -> None:
    """Check daily schedule: nudge anchored to member's schedule + grace_minutes.

    For nudge_anchor="start" (standup): fires at effective_start + grace.
    For nudge_anchor="end" (EOD): fires at effective_end + grace.

    Args:
        template: UpdateTemplate with schedule_type='daily'.
        user: User model instance.
        member: WorkspaceUser (member) for UpdatePost queries.
        local_now: User's current local datetime (aware).
        now_utc: Current UTC datetime (aware).
        user_tz: ZoneInfo for user's timezone.
        effective_start: Member's effective start time for today.
        effective_end: Member's effective end time for today.
    """
    from modules.base.updates.models.nudge_log import UpdateNudgeLog
    from modules.base.updates.models.post import UpdatePost
    from modules.base.core.models.notification import NotificationCategory, SystemNotification
    from modules.base.core.services.push_notification import send_push

    anchor = template.nudge_anchor or "start"
    anchor_time = effective_start if anchor == "start" else effective_end
    grace = template.grace_minutes or 30

    nudge_deadline = local_now.replace(
        hour=anchor_time.hour, minute=anchor_time.minute,
        second=0, microsecond=0,
    )
    nudge_deadline += timedelta(minutes=grace)

    if local_now < nudge_deadline:
        return

    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_midnight_utc = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)

    if UpdateNudgeLog.was_nudged_today(template.id, user.id, local_midnight_utc):
        return

    post_exists = UpdatePost.scoped().filter(
        UpdatePost.template_id == template.id,
        UpdatePost.member_id == member.id,
        UpdatePost.created_at >= local_midnight_utc,
    ).first()
    if post_exists:
        UpdateNudgeLog.log_completed(
            template.id, user.id, scheduled_at=anchor_time,
        )
        return

    post_url = f"/sync/posts/new/{template.id}"

    SystemNotification.create(
        title=f"Reminder: {template.name}",
        message=f"You haven't posted your {template.name} yet today.",
        type="info",
        target_role="all",
        user_id=user.id,
        icon="fa-clock",
        action_url=post_url,
        category=NotificationCategory.MISSED_CHECKIN,
    )
    send_push(
        user_id=user.id,
        title=f"Reminder: {template.name}",
        body=f"You haven't posted your {template.name} yet today.",
        url=post_url,
    )
    UpdateNudgeLog.log_nudge(template.id, user.id, scheduled_at=anchor_time)

    from modules.base.tasks.models.task import Task
    Task.ensure_checkin_item(template.name, member.id, "missed_checkin")

    logger.debug(f"Nudged user {user.id} for template '{template.name}' (daily)")


def _check_periodic(
    template: "UpdateTemplate",
    user: "User",
    member: "WorkspaceUser",
    local_now: datetime,
    effective_start: time,
    effective_end: time,
) -> None:
    """Check periodic schedule: first nudge at effective_start + interval, rolling.

    Stops firing after effective_end (member's day is over).

    Args:
        template: UpdateTemplate with schedule_type='periodic'.
        user: User model instance.
        member: WorkspaceUser (member) for UpdatePost queries.
        local_now: User's current local datetime (aware).
        effective_start: Member's effective start time for today.
        effective_end: Member's effective end time for today.
    """
    from modules.base.updates.models.nudge_log import UpdateNudgeLog
    from modules.base.updates.models.post import UpdatePost
    from modules.base.core.models.notification import NotificationCategory, SystemNotification
    from modules.base.core.services.push_notification import send_push

    interval = template.interval_minutes
    if not interval or interval <= 0:
        return

    # Don't fire after member's work day ends
    end_dt = local_now.replace(
        hour=effective_end.hour, minute=effective_end.minute,
        second=0, microsecond=0,
    )
    if local_now >= end_dt:
        return

    anchor = local_now.replace(
        hour=effective_start.hour, minute=effective_start.minute,
        second=0, microsecond=0,
    )
    first_fire = anchor + timedelta(minutes=interval)

    if local_now < first_fire:
        return

    anchor_utc = anchor.astimezone(timezone.utc).replace(tzinfo=None)
    now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)

    last_post = UpdatePost.scoped().filter(
        UpdatePost.template_id == template.id,
        UpdatePost.member_id == member.id,
        UpdatePost.created_at >= anchor_utc,
    ).order_by(UpdatePost.created_at.desc()).first()

    last_nudge = UpdateNudgeLog.scoped().filter(
        UpdateNudgeLog.template_id == template.id,
        UpdateNudgeLog.user_id == user.id,
        UpdateNudgeLog.nudged_at >= anchor_utc,
    ).order_by(UpdateNudgeLog.nudged_at.desc()).first()

    baseline = anchor_utc
    if last_post and last_post.created_at > baseline:
        baseline = last_post.created_at
    if last_nudge and last_nudge.nudged_at > baseline:
        baseline = last_nudge.nudged_at

    if (now_utc_naive - baseline).total_seconds() / 60 < interval:
        if last_post and (not last_nudge or last_nudge.nudged_at < last_post.created_at):
            UpdateNudgeLog.log_completed(
                template.id, user.id, scheduled_at=effective_start,
            )
        return

    UpdateNudgeLog.supersede_periodic_nudge(template.id, user.id)

    post_url = f"/sync/posts/new/{template.id}"

    SystemNotification.create(
        title=f"Reminder: {template.name}",
        message=f"Time for your {template.name} check-in.",
        type="info",
        target_role="all",
        user_id=user.id,
        icon="fa-clock",
        action_url=post_url,
        category=NotificationCategory.MISSED_CHECKIN,
    )
    send_push(
        user_id=user.id,
        title=f"Reminder: {template.name}",
        body=f"Time for your {template.name} check-in.",
        url=post_url,
    )
    UpdateNudgeLog.log_nudge(
        template.id, user.id, scheduled_at=effective_start,
    )

    from modules.base.tasks.models.task import Task
    Task.ensure_checkin_item(template.name, member.id, "missed_periodic")

    logger.debug(f"Nudged user {user.id} for template '{template.name}' (periodic)")


def _check_expirations(
    templates: list["UpdateTemplate"],
    users: list["User"],
    members_by_user: dict[int, "WorkspaceUser"],
    tz_map: dict[int, str],
    schedule_map: dict[int, tuple[time, time] | None],
    default_tz: str,
    now_utc: datetime,
) -> None:
    """Expire outstanding daily nudges that have passed their 2-hour window.

    Args:
        templates: Nudge-enabled templates for this workspace.
        users: Active users in this workspace.
        members_by_user: user_id -> WorkspaceUser mapping.
        tz_map: user_id -> timezone string.
        schedule_map: member_id -> (start, end) or None.
        default_tz: Workspace default timezone.
        now_utc: Current UTC datetime (aware).
    """
    from modules.base.updates.models.nudge_log import UpdateNudgeLog

    daily_templates = [t for t in templates if t.schedule_type == "daily"]
    if not daily_templates:
        return

    expiry_pairs: list[tuple[int, datetime]] = []

    for user in users:
        member = members_by_user.get(user.id)
        if not member:
            continue

        effective_schedule = schedule_map.get(member.id)
        if effective_schedule is None:
            continue

        effective_start, effective_end = effective_schedule

        user_tz_str = tz_map.get(user.id) or default_tz
        try:
            user_tz = ZoneInfo(user_tz_str)
        except Exception:
            user_tz = ZoneInfo(default_tz)

        local_now = now_utc.astimezone(user_tz)

        for template in daily_templates:
            if not _in_nudge_scope(template, local_now):
                continue

            anchor = template.nudge_anchor or "start"
            anchor_time = effective_start if anchor == "start" else effective_end
            grace = template.grace_minutes or 30

            nudge_fire_time = local_now.replace(
                hour=anchor_time.hour, minute=anchor_time.minute,
                second=0, microsecond=0,
            )
            nudge_fire_time += timedelta(minutes=grace)
            expiry_time = nudge_fire_time + timedelta(hours=2)

            if local_now >= expiry_time:
                cutoff_utc = (
                    nudge_fire_time.astimezone(timezone.utc).replace(tzinfo=None)
                    + timedelta(minutes=5)
                )
                expiry_pairs.append((user.id, cutoff_utc))

    expired = UpdateNudgeLog.expire_standup_nudges(expiry_pairs)
    if expired:
        logger.debug(f"Expired {expired} standup nudge(s)")


def start_nudge_scheduler(app: "Flask") -> None:
    """Start the background nudge scheduler daemon thread.

    Args:
        app: Flask application instance.
    """
    global _nudge_scheduler_running

    if _nudge_scheduler_running:
        logger.warning("Nudge scheduler is already running")
        return

    nudge_scheduler = schedule.Scheduler()
    nudge_scheduler.every(1).minutes.do(check_nudges, app)

    _nudge_scheduler_running = True

    def _run():
        logger.info("Nudge scheduler thread started")
        while _nudge_scheduler_running:
            nudge_scheduler.run_pending()
            _time.sleep(60)
        logger.info("Nudge scheduler thread stopped")

    thread = threading.Thread(target=_run, daemon=True, name="nudge-scheduler")
    thread.start()

    logger.info("Nudge scheduler started (1-minute check cycle)")
