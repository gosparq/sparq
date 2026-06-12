# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Momentum controller — team nudge completion report + per-person drilldown."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING

from flask import abort, request
from flask_login import login_required

from system.device.template import render_device_template

from .updates import updates_bp

if TYPE_CHECKING:
    from modules.base.updates.models.template import UpdateTemplate


VALID_PERIODS = ("daily", "weekly", "monthly", "quarterly")


def _get_holiday_dates(lookback_days: int = 120) -> set[date]:
    """Fetch holiday dates for the current workspace within a lookback window.

    Args:
        lookback_days: How many days back to query for holidays.

    Returns:
        Set of date objects that are holidays.
    """
    from modules.base.updates.models.event import Event

    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=lookback_days)
    return Event.get_holiday_dates_in_range(start, today)


def _date_range(period: str) -> tuple[datetime, datetime, str]:
    """Compute start/end dates for the given reporting period.

    Uses the current user's timezone so "today" aligns with the same
    local day the nudge scheduler uses when sending/expiring nudges.
    Holidays are excluded from business day counting for all periods.

    Args:
        period: 'daily', 'weekly', 'monthly', or 'quarterly'.

    Returns:
        Tuple of (start_date, end_date, validated_period).
    """
    import pytz

    from system.i18n.translation import _resolve_user_timezone

    now_utc = datetime.now(timezone.utc)
    tz_name = _resolve_user_timezone()
    local_tz = pytz.timezone(tz_name)
    local_now = now_utc.astimezone(local_tz)

    local_today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = local_today_start.astimezone(pytz.UTC).replace(tzinfo=None)
    now_utc_naive = now_utc.replace(tzinfo=None)

    holiday_dates = _get_holiday_dates()

    def _count_back_biz_days(origin: datetime, count: int) -> datetime:
        """Walk backwards from origin, skipping weekends and holidays."""
        biz = 0
        cursor = origin
        while biz < count:
            cursor -= timedelta(days=1)
            if cursor.weekday() < 5 and cursor.date() not in holiday_dates:
                biz += 1
        return cursor

    if period == "weekly":
        return _count_back_biz_days(today_start_utc, 5), now_utc_naive, period

    if period == "monthly":
        return _count_back_biz_days(today_start_utc, 22), now_utc_naive, period

    if period == "quarterly":
        return _count_back_biz_days(today_start_utc, 65), now_utc_naive, period

    return today_start_utc, now_utc_naive, "daily"


def _get_templates() -> tuple[list[UpdateTemplate], list[dict]]:
    """Fetch nudge-enabled templates and build per-template groups.

    Returns:
        Tuple of (all_nudge_templates, template_groups) where each group
        is {"id": int, "label": str}.
    """
    from modules.base.updates.models.template import UpdateTemplate

    templates = UpdateTemplate.get_for_workspace()
    nudge_templates = sorted(
        (t for t in templates if t.nudge_enabled and t.schedule_type and t.is_active),
        key=lambda t: (t.nudge_time or "", t.sort_order),
    )
    template_groups = []
    for t in nudge_templates:
        label = t.name
        if label.startswith("Async - "):
            label = label[8:]
        if label.endswith(" (EOD)"):
            label = label[:-6]
        template_groups.append({"id": t.id, "label": label})
    return nudge_templates, template_groups


@updates_bp.route("/pulse")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def pulse() -> str:
    """Team Pulse report — per-person nudge completion rates.

    Returns:
        Rendered HTML page with team pulse summary and per-person breakdown.
    """
    from sqlalchemy.orm import selectinload

    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.nudge_log import UpdateNudgeLog

    period = request.args.get("period", "daily")
    if period not in VALID_PERIODS:
        period = "daily"

    start_date, end_date, period = _date_range(period)

    members = (
        WorkspaceUser.scoped()
        .filter_by(status=EmployeeStatus.ACTIVE)
        .options(selectinload(WorkspaceUser.user))
        .all()
    )
    non_exempt_user_ids = [m.user_id for m in members if not m.pulse_exempt]

    nudge_templates, template_groups = _get_templates()

    summary = UpdateNudgeLog.get_pulse_summary(
        user_ids=non_exempt_user_ids,
        template_ids=[t.id for t in nudge_templates],
        template_groups=template_groups,
        start_date=start_date,
        end_date=end_date,
    )

    people = [
        {"member": m, "pulse_exempt": m.pulse_exempt, **summary["people"].get(m.user_id, {})}
        for m in members
    ]

    return render_device_template(  # type: ignore[no-any-return]
        "updates/desktop/pulse.html",
        period=period,
        people=people,
        template_groups=template_groups,
        team_templates=summary["team_templates"],
        team_overall_pct=summary["team_overall_pct"],
        team_on_time_pct=summary.get("team_on_time_pct"),
        team_schedule_totals=summary.get("team_schedule_totals", {}),
        start_date=start_date,
        end_date=end_date,
        module_home="updates_bp.index",
        active_page="updates",
    )


@updates_bp.route("/pulse/<int:member_id>")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def pulse_detail(member_id: int) -> str:
    """Per-person pulse drilldown — nudge-by-nudge history.

    Args:
        member_id: ID of the WorkspaceUser to show detail for.

    Returns:
        Rendered HTML page with individual nudge history and stats.
    """
    from sqlalchemy.orm import joinedload

    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.nudge_log import UpdateNudgeLog

    member = (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(id=member_id, status=EmployeeStatus.ACTIVE)
        .first()
    )
    if not member:
        abort(404)

    period = request.args.get("period", "daily")
    if period not in VALID_PERIODS:
        period = "daily"

    start_date, end_date, period = _date_range(period)

    nudge_templates, template_groups = _get_templates()

    detail = UpdateNudgeLog.get_member_pulse_detail(
        user_id=member.user_id,
        template_ids=[t.id for t in nudge_templates],
        template_groups=template_groups,
        start_date=start_date,
        end_date=end_date,
        template_map={t.id: t for t in nudge_templates},
    )

    return render_device_template(  # type: ignore[no-any-return]
        "updates/desktop/pulse_detail.html",
        member=member,
        period=period,
        rows=detail["rows"],
        template_groups=template_groups,
        detail_templates=detail["templates"],
        overall_pct=detail["overall_pct"],
        start_date=start_date,
        end_date=end_date,
        module_home="updates_bp.index",
        active_page="updates",
    )
