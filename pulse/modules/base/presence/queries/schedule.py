# -----------------------------------------------------------------------------
# sparQ - Presence: Schedule projection queries
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from uuid import UUID

from sqlalchemy import select

from system.db.database import db


@dataclass(frozen=True)
class ScheduleRow:
    """Projection row for a single member's effective schedule on a date."""

    member_id: int
    start_time: time
    end_time: time


def get_team_schedules(
    org_id: UUID,
    ws_id: UUID,
    target_date: date,
) -> dict[int, tuple[time, time] | None]:
    """Fetch effective schedules for all members on a given date.

    Uses a single query: member_schedule LEFT JOIN member_schedule_override.
    Override wins when present for the target date.

    Args:
        org_id: Organization UUID.
        ws_id: Workspace UUID.
        target_date: The date to resolve schedules for.

    Returns:
        Dict keyed by member_id → (start_time, end_time) or None.
    """
    from modules.base.presence.models.member_schedule import (
        MemberSchedule,
        MemberScheduleOverride,
    )

    day_of_week = target_date.weekday()

    # Fetch overrides for this date
    override_stmt = select(
        MemberScheduleOverride.member_id,
        MemberScheduleOverride.start_time,
        MemberScheduleOverride.end_time,
    ).where(
        MemberScheduleOverride.organization_id == org_id,
        MemberScheduleOverride.workspace_id == ws_id,
        MemberScheduleOverride.override_date == target_date,
    )

    overrides: dict[int, tuple[time, time]] = {}
    for row in db.session.execute(override_stmt).all():
        overrides[row[0]] = (row[1], row[2])

    # Fetch default schedules for this day of week
    default_stmt = select(
        MemberSchedule.member_id,
        MemberSchedule.start_time,
        MemberSchedule.end_time,
    ).where(
        MemberSchedule.organization_id == org_id,
        MemberSchedule.workspace_id == ws_id,
        MemberSchedule.day_of_week == day_of_week,
    )

    result: dict[int, tuple[time, time] | None] = {}
    for row in db.session.execute(default_stmt).all():
        mid = row[0]
        if mid in overrides:
            result[mid] = overrides[mid]
        else:
            result[mid] = (row[1], row[2])

    # Members with only overrides (no default for this day) still get scheduled
    for mid, times in overrides.items():
        if mid not in result:
            result[mid] = times

    return result


def get_team_forecast_statuses(
    org_id: UUID,
    ws_id: UUID,
    target_date: date,
) -> dict[int, str]:
    """Fetch forecast statuses for all members on a given date.

    Args:
        org_id: Organization UUID.
        ws_id: Workspace UUID.
        target_date: The date to check.

    Returns:
        Dict keyed by member_id → status string (e.g. "in", "out", "remote", "pto").
    """
    from modules.base.presence.models.presence_forecast import PresenceForecast

    stmt = select(
        PresenceForecast.member_id,
        PresenceForecast.status,
    ).where(
        PresenceForecast.organization_id == org_id,
        PresenceForecast.workspace_id == ws_id,
        PresenceForecast.forecast_date == target_date,
    )

    return {row[0]: row[1] for row in db.session.execute(stmt).all()}
