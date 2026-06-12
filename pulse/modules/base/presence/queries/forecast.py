# -----------------------------------------------------------------------------
# sparQ - Presence: Forecast projection query
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time
from uuid import UUID

from sqlalchemy import select

from system.db.database import db


@dataclass(frozen=True)
class ForecastRow:
    """Projection row for a single member-day forecast."""

    member_id: int
    forecast_date: date
    status: str
    available_from: time | None
    available_until: time | None
    note: str | None


def get_team_forecast(
    org_id: UUID,
    ts_id: UUID,
    start_date: date,
    end_date: date,
) -> dict[int, dict[date, ForecastRow]]:
    """Fetch all member forecasts for a date range in a single SELECT.

    Args:
        org_id: Organization UUID.
        ts_id: Workspace UUID.
        start_date: Inclusive start of the window.
        end_date: Inclusive end of the window.

    Returns:
        Nested dict keyed {member_id: {forecast_date: ForecastRow}}.

    Example:
        forecasts = get_team_forecast(g.organization_id, g.workspace_id, mon, sun)
        row = forecasts.get(member_id, {}).get(some_date)
    """
    from modules.base.presence.models.presence_forecast import PresenceForecast

    stmt = select(
        PresenceForecast.member_id,
        PresenceForecast.forecast_date,
        PresenceForecast.status,
        PresenceForecast.available_from,
        PresenceForecast.available_until,
        PresenceForecast.note,
    ).where(
        PresenceForecast.organization_id == org_id,
        PresenceForecast.workspace_id == ts_id,
        PresenceForecast.forecast_date >= start_date,
        PresenceForecast.forecast_date <= end_date,
    )

    result: dict[int, dict[date, ForecastRow]] = {}
    for row in db.session.execute(stmt).all():
        r = ForecastRow(*row)
        result.setdefault(r.member_id, {})[r.forecast_date] = r
    return result


@dataclass(frozen=True)
class ScheduleDayRow:
    """Projection row for a member's default schedule on one day of week."""

    day_of_week: int
    default_status: str | None
    start_time: time | None
    end_time: time | None


def get_team_schedules_for_board(
    org_id: UUID,
    ws_id: UUID,
) -> dict[int, dict[int, ScheduleDayRow]]:
    """Fetch all member schedules for a workspace, keyed by OrganizationUser.id.

    The board uses OrganizationUser.id for member lookups, but MemberSchedule
    is keyed by workspace_user.id. This query joins through workspace_user
    to return results keyed by organization_user_id for board compatibility.

    Returns:
        Nested dict keyed {org_user_id: {day_of_week: ScheduleDayRow}}.
    """
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.presence.models.member_schedule import MemberSchedule

    stmt = select(
        WorkspaceUser.organization_user_id,
        MemberSchedule.day_of_week,
        MemberSchedule.default_status,
        MemberSchedule.start_time,
        MemberSchedule.end_time,
    ).join(
        WorkspaceUser, WorkspaceUser.id == MemberSchedule.member_id,
    ).where(
        MemberSchedule.organization_id == org_id,
        MemberSchedule.workspace_id == ws_id,
        WorkspaceUser.organization_user_id.isnot(None),
    )

    result: dict[int, dict[int, ScheduleDayRow]] = {}
    for row in db.session.execute(stmt).all():
        org_user_id = row[0]
        r = ScheduleDayRow(row[1], row[2], row[3], row[4])
        result.setdefault(org_user_id, {})[r.day_of_week] = r
    return result
