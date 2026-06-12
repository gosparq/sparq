# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Calendar utility functions for week/month calculations using
#     the company's "first day of week" setting.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Calendar utilities that respect WorkspaceSettings.first_day_of_week.

Centralizes week-start and month-grid logic so every module renders
calendars consistently.

Functions:
    get_first_day_of_week: Read the company setting (0=Sunday, 1=Monday).
    get_python_firstweekday: Convert company setting to Python calendar constant.
    get_week_start: First day of the week containing a given date.
    get_week_dates_list: Seven consecutive dates for the week.
    get_month_calendar_weeks: Full month grid as list-of-weeks.
    get_weekday_headers: Ordered day-name headers.

Example:
    Using week helpers in a controller::

        from system.utils.calendar_utils import get_week_start, get_weekday_headers

        start = get_week_start(date.today())
        headers = get_weekday_headers("short")  # ["Sun", "Mon", ...] or ["Mon", "Tue", ...]
"""

from __future__ import annotations

import calendar as _calendar
from datetime import date, timedelta
from typing import Any

from system.i18n.translation import translate as _


def get_first_day_of_week() -> int:
    """Return the company's first-day-of-week setting.

    Reads from ``flask.g.company_settings`` (set by request hooks).
    Falls back to a direct DB query when ``g`` is unavailable (e.g.
    background jobs), and ultimately defaults to ``0`` (Sunday).

    Returns:
        0 for Sunday, 1 for Monday.
    """
    try:
        from flask import g

        settings = getattr(g, "company_settings", None)
        if settings is not None:
            return settings.first_day_of_week or 0
    except RuntimeError:
        pass

    # Fallback: outside request context (background job, CLI)
    try:
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        settings = WorkspaceSettings.get_instance()
        return settings.first_day_of_week or 0
    except Exception:
        return 0


def get_python_firstweekday() -> int:
    """Map the company setting to Python's ``calendar.firstweekday`` value.

    Python's ``calendar`` module uses 0=Monday … 6=Sunday, while the
    company setting uses 0=Sunday, 1=Monday.

    Returns:
        6 when the company starts on Sunday, 0 when Monday.
    """
    company_val = get_first_day_of_week()
    # company 0 (Sunday) → python 6; company 1 (Monday) → python 0
    return 6 if company_val == 0 else 0


def get_week_start(target_date: date) -> date:
    """Return the first day of the week containing *target_date*.

    Args:
        target_date: Any date within the desired week.

    Returns:
        The date of the week's first day (Sunday or Monday).
    """
    first_day = get_first_day_of_week()
    if first_day == 0:
        # Sunday start: weekday() gives Mon=0…Sun=6 → shift by +1
        days_since_start = (target_date.weekday() + 1) % 7
    else:
        # Monday start: weekday() already gives Mon=0
        days_since_start = target_date.weekday()
    return target_date - timedelta(days=days_since_start)


def get_week_dates_list(target_date: date) -> list[date]:
    """Return seven consecutive dates for the week containing *target_date*.

    Args:
        target_date: Any date within the desired week.

    Returns:
        A list of seven ``date`` objects starting from the configured
        first day of the week.
    """
    start = get_week_start(target_date)
    return [start + timedelta(days=i) for i in range(7)]


def get_month_calendar_weeks(year: int, month: int) -> list[list[date]]:
    """Return a month grid as a list of week-lists.

    Each inner list contains exactly 7 ``date`` objects (including
    leading/trailing days from adjacent months).

    Args:
        year: Calendar year.
        month: Calendar month (1-12).

    Returns:
        A list of weeks, where each week is a list of 7 ``date`` objects.
    """
    cal = _calendar.Calendar(firstweekday=get_python_firstweekday())
    return cal.monthdatescalendar(year, month)


def get_weekday_headers(style: str = "short") -> list[str]:
    """Return ordered, translated day-name headers.

    Args:
        style: ``"short"`` for 3-letter names (Mon, Tue …) or
               ``"min"`` for single-letter names (M, T …).

    Returns:
        A list of 7 translated day-name strings, ordered according
        to the company's first-day-of-week setting.
    """
    if style == "min":
        # Single-letter day abbreviations
        names = [_("M"), _("T"), _("W"), _("T"), _("F"), _("S"), _("S")]
    else:
        names = [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]

    # names is ordered Mon(0)…Sun(6) — rotate for Sunday-start
    if get_first_day_of_week() == 0:
        # Move Sunday to front
        return names[-1:] + names[:-1]
    return names


# ── Spanning segment utilities for unified calendar ───────────────────────


def compute_spanning_segments(
    entries: list[dict[str, Any]], week_start: date, week_end: date
) -> list[dict[str, Any]]:
    """Clip spanning entries to a week boundary and compute grid positions.

    Each entry dict must have: id, type, label, url, start_date, end_date.

    Args:
        entries: Spanning entry dicts with start_date/end_date.
        week_start: First day of the week row.
        week_end: Last day of the week row.

    Returns:
        List of segment dicts with col_start (1-7), col_span,
        continues_left, continues_right, plus the original fields.
    """
    segments = []
    for entry in entries:
        e_start = entry["start_date"]
        e_end = entry["end_date"]

        if e_end < week_start or e_start > week_end:
            continue

        clipped_start = max(e_start, week_start)
        clipped_end = min(e_end, week_end)

        col_start = (clipped_start - week_start).days + 1
        col_span = (clipped_end - clipped_start).days + 1

        segments.append({
            "id": entry["id"],
            "type": entry["type"],
            "label": entry["label"],
            "url": entry["url"],
            "col_start": col_start,
            "col_span": col_span,
            "continues_left": e_start < week_start,
            "continues_right": e_end > week_end,
            "row_index": 0,
        })

    return segments


def assign_spanning_lanes(segments: list[dict[str, Any]]) -> int:
    """Assign row_index values to spanning segments to avoid vertical overlap.

    Uses a greedy approach: sort by col_start, assign to the lowest
    available lane where the previous occupant ends before this starts.

    Args:
        segments: List of segment dicts (mutated in-place with row_index).

    Returns:
        Total number of lanes used.
    """
    segments.sort(key=lambda s: (s["col_start"], -s["col_span"]))
    lanes: list[int] = []

    for seg in segments:
        placed = False
        for i, lane_end in enumerate(lanes):
            if lane_end < seg["col_start"]:
                seg["row_index"] = i
                lanes[i] = seg["col_start"] + seg["col_span"] - 1
                placed = True
                break
        if not placed:
            seg["row_index"] = len(lanes)
            lanes.append(seg["col_start"] + seg["col_span"] - 1)

    return len(lanes)
