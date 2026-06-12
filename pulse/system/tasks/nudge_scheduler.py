# -----------------------------------------------------------------------------
# sparQ - Tasks Nudge Scheduler
#
# Description:
#     Background scheduler that checks every minute for open Tasks
#     and sends nudge notifications based on the 3-tier RAG cadence:
#       Tier 1 (Red/Now)     — every 30 minutes
#       Tier 2 (Amber/Later) — every 4 hours
#       Tier 3 (Green/Whenever) — daily at member's schedule start time
#
#     Also handles Tier 1 escalation (notify raiser after 2hrs).
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
from zoneinfo import ZoneInfo

import schedule
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)

_task_nudge_scheduler_running = False

# Nudge cadences per tier (in minutes)
TIER_CADENCE = {
    1: 30,       # Every 30 minutes
    2: 240,      # Every 4 hours
    3: None,     # Daily at schedule start (special handling)
}

TIER_1_ESCALATION_HOURS = 2  # Escalate to raiser after 2 hours


def check_task_nudges(app) -> None:
    """Check all workspaces for Tasks that need nudge notifications.

    Also runs system trigger checks (throttled to every 30 min internally).

    Args:
        app: Flask application instance for app_context.
    """
    with app.app_context():
        try:
            _check_nudges_inner()
        except Exception as e:
            logger.error(f"Tasks nudge check failed: {e}")

    # System triggers piggyback on the same 1-minute cycle
    try:
        from system.tasks.system_triggers import check_system_triggers
        check_system_triggers(app)
    except Exception as e:
        logger.error(f"Tasks system triggers failed: {e}")


def _check_nudges_inner() -> None:
    """Inner nudge check logic (runs inside app_context)."""
    from flask import g

    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from modules.base.core.models.user_setting import UserSetting
    from modules.base.updates.models.event import Event
    from modules.base.presence.queries.schedule import (
        get_team_schedules,
        get_team_forecast_statuses,
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

        from modules.base.core.models.workspace_user import WorkspaceUser
        # Get all open action items
        open_items = (
            Task.scoped()
            .options(
                joinedload(Task.assignee).joinedload(WorkspaceUser.user),
                joinedload(Task.raised_by).joinedload(WorkspaceUser.user),
            )
            .filter(Task.status == "open")
            .all()
        )
        if not open_items:
            continue

        # Bulk-fetch timezone settings for all assignees
        user_ids = list({item.assignee.user_id for item in open_items if item.assignee})
        tz_map = UserSetting.get_bulk(user_ids, "timezone")

        ts_settings = WorkspaceSettings.get_instance()
        default_tz = ts_settings.timezone or "America/Chicago"

        schedule_map = get_team_schedules(
            ts.organization_id, ts.id, today_date
        )
        forecast_map = get_team_forecast_statuses(
            ts.organization_id, ts.id, today_date
        )

        now_utc = datetime.now(timezone.utc)
        now_naive = datetime.utcnow()

        for item in open_items:
            if not item.assignee:
                continue

            # Skip snoozed items
            if item.snoozed and item.snooze_until and item.snooze_until > now_naive:
                continue

            user_id = item.assignee.user_id

            # Resolve timezone
            user_tz_str = tz_map.get(user_id) or default_tz
            try:
                user_tz = ZoneInfo(user_tz_str)
            except Exception:
                user_tz = ZoneInfo(default_tz)

            local_now = now_utc.astimezone(user_tz)

            member_id = item.assignee_id

            forecast_status = forecast_map.get(member_id)
            if forecast_status in ("out", "pto"):
                continue

            if getattr(item.assignee, "pulse_exempt", False):
                continue

            effective_schedule = schedule_map.get(member_id)
            if effective_schedule is None:
                continue

            effective_start, effective_end = effective_schedule

            start_dt = local_now.replace(
                hour=effective_start.hour, minute=effective_start.minute,
                second=0, microsecond=0,
            )
            end_dt = local_now.replace(
                hour=effective_end.hour, minute=effective_end.minute,
                second=0, microsecond=0,
            )
            if local_now < start_dt or local_now >= end_dt:
                continue

            if item.urgency_tier == 3:
                _check_tier3_daily(item, user_id, local_now, now_naive, user_tz, effective_start)
            else:
                cadence = TIER_CADENCE.get(item.urgency_tier, 240)
                _check_periodic_nudge(item, user_id, now_naive, cadence)

            # Tier 1 escalation check
            if item.urgency_tier == 1:
                _check_tier1_escalation(item, now_naive)

        db.session.commit()


def _check_tier3_daily(item, user_id, local_now, now_naive, user_tz, effective_start: time) -> None:
    """Tier 3: nudge once daily at member's effective schedule start time."""
    from modules.base.tasks.models.task_log import TaskLog

    fire_dt = local_now.replace(
        hour=effective_start.hour, minute=effective_start.minute,
        second=0, microsecond=0,
    )
    if local_now < fire_dt:
        return

    # Check if already nudged today (local date)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_midnight_utc = local_midnight.astimezone(timezone.utc).replace(tzinfo=None)

    existing = TaskLog.query.filter(
        TaskLog.task_id == item.id,
        TaskLog.event_type == "nudge_sent",
        TaskLog.created_at >= local_midnight_utc,
    ).first()
    if existing:
        return

    _send_nudge(item, user_id)


def _check_periodic_nudge(item, user_id, now_naive, cadence_minutes) -> None:
    """Tier 1/2: nudge every N minutes since last nudge or creation."""
    from modules.base.tasks.models.task_log import TaskLog

    cutoff = now_naive - timedelta(minutes=cadence_minutes)

    # Check last nudge
    last_nudge = TaskLog.query.filter(
        TaskLog.task_id == item.id,
        TaskLog.event_type == "nudge_sent",
        TaskLog.created_at >= cutoff,
    ).first()
    if last_nudge:
        return

    # Also check if item was created within the cadence window (don't nudge immediately)
    if item.created_at >= cutoff:
        return

    _send_nudge(item, user_id)


def _check_tier1_escalation(item, now_naive) -> None:
    """Tier 1: escalate to raiser if open > 2 hours."""
    from modules.base.tasks.models.task_log import TaskLog
    from modules.base.core.models.notification import SystemNotification
    from modules.base.core.services.push_notification import send_push

    if not item.raised_by_id or not item.raised_by:
        return

    # Check if open > 2 hours
    age = now_naive - item.created_at
    if age < timedelta(hours=TIER_1_ESCALATION_HOURS):
        return

    # Already escalated?
    existing = TaskLog.query.filter(
        TaskLog.task_id == item.id,
        TaskLog.event_type == "escalation_sent",
    ).first()
    if existing:
        return

    # Send escalation to raiser
    raiser_user_id = item.raised_by.user_id
    assignee_name = item.assignee.user.first_name if item.assignee and item.assignee.user else "Someone"

    from modules.base.core.models.notification import NotificationCategory
    SystemNotification.create(
        title=item.title[:100],
        message=f"Not resolved after {TIER_1_ESCALATION_HOURS}h · assigned to {assignee_name}",
        type="warning",
        target_role="user",
        user_id=raiser_user_id,
        icon="fa-exclamation-triangle",
        action_url=f"/tasks/{item.id}",
        category=NotificationCategory.TASK_ASSIGNED,
    )
    send_push(
        user_id=raiser_user_id,
        title=item.title[:80],
        body=f"Not resolved after {TIER_1_ESCALATION_HOURS}h · assigned to {assignee_name}",
        url=f"/tasks/{item.id}",
    )
    TaskLog.log(item.id, "escalation_sent", None, f"Escalated to raiser after {TIER_1_ESCALATION_HOURS}hrs")
    logger.debug(f"Escalated action item {item.id} to raiser (user {raiser_user_id})")


def _send_nudge(item, user_id) -> None:
    """Send a nudge notification for a task."""
    from modules.base.tasks.models.task_log import TaskLog
    from modules.base.core.models.notification import SystemNotification
    from modules.base.core.services.push_notification import send_push

    raiser_name = ""
    if item.raised_by and item.raised_by.user:
        raiser_name = f" from {item.raised_by.user.first_name}"
    elif item.is_system_raised:
        raiser_name = " (System)"

    action_url = item.post_now_url or f"/tasks/{item.id}"

    from modules.base.core.models.notification import NotificationCategory
    SystemNotification.create(
        title=item.title[:100],
        message=f"Reminder{raiser_name}",
        type="warning" if item.urgency_tier == 1 else "info",
        target_role="user",
        user_id=user_id,
        icon="fa-bolt",
        action_url=action_url,
        category=NotificationCategory.TASK_ASSIGNED,
    )
    send_push(
        user_id=user_id,
        title=item.title[:80],
        body=f"Reminder{raiser_name}",
        url=action_url,
    )
    TaskLog.log(item.id, "nudge_sent", None, f"Tier {item.urgency_tier} nudge")
    logger.debug(f"Nudged user {user_id} for action item {item.id} (tier {item.urgency_tier})")


def start_tasks_nudge_scheduler(app) -> None:
    """Start the background Tasks nudge scheduler daemon thread.

    Args:
        app: Flask application instance.
    """
    global _task_nudge_scheduler_running

    if _task_nudge_scheduler_running:
        logger.warning("Tasks nudge scheduler is already running")
        return

    ai_scheduler = schedule.Scheduler()
    ai_scheduler.every(1).minutes.do(check_task_nudges, app)

    _task_nudge_scheduler_running = True

    def _run():
        logger.info("Tasks nudge scheduler thread started")
        while _task_nudge_scheduler_running:
            ai_scheduler.run_pending()
            _time.sleep(60)
        logger.info("Tasks nudge scheduler thread stopped")

    thread = threading.Thread(target=_run, daemon=True, name="ai-nudge-scheduler")
    thread.start()

    logger.info("Tasks nudge scheduler started (1-minute check cycle)")
