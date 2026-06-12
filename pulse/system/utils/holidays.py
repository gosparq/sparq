# -----------------------------------------------------------------------------
# sparQ - US Federal Holiday Calculator
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""US federal holiday date calculator.

Computes the exact dates for all US federal holidays in a given year,
handling both fixed-date and floating (nth weekday) holidays.
"""

from __future__ import annotations

import calendar
from datetime import date


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of a weekday in a given month.

    Args:
        year: Calendar year.
        month: Month (1-12).
        weekday: Day of week (0=Monday, 6=Sunday).
        n: Which occurrence (1=first, 2=second, etc.).

    Returns:
        The date of the nth weekday in the month.
    """
    count = 0
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        if date(year, month, day).weekday() == weekday:
            count += 1
            if count == n:
                return date(year, month, day)
    raise ValueError(f"No {n}th weekday {weekday} in {year}-{month:02d}")


def _last_weekday(year: int, month: int, weekday: int) -> date:
    """Return the last occurrence of a weekday in a given month.

    Args:
        year: Calendar year.
        month: Month (1-12).
        weekday: Day of week (0=Monday, 6=Sunday).

    Returns:
        The date of the last weekday in the month.
    """
    last_day = calendar.monthrange(year, month)[1]
    for day in range(last_day, 0, -1):
        if date(year, month, day).weekday() == weekday:
            return date(year, month, day)
    raise ValueError(f"No weekday {weekday} in {year}-{month:02d}")


def get_us_federal_holidays(year: int) -> list[tuple[date, str]]:
    """Compute US federal holiday dates for a given year.

    Includes all 11 federal holidays:
    - New Year's Day (Jan 1)
    - Martin Luther King Jr. Day (3rd Monday, Jan)
    - Presidents' Day (3rd Monday, Feb)
    - Memorial Day (last Monday, May)
    - Juneteenth (Jun 19)
    - Independence Day (Jul 4)
    - Labor Day (1st Monday, Sep)
    - Columbus Day (2nd Monday, Oct)
    - Veterans Day (Nov 11)
    - Thanksgiving (4th Thursday, Nov)
    - Christmas Day (Dec 25)

    Args:
        year: Calendar year to compute holidays for.

    Returns:
        List of (date, holiday_name) tuples sorted by date.
    """
    MON = 0
    THU = 3

    holidays = [
        (date(year, 1, 1), "New Year's Day"),
        (_nth_weekday(year, 1, MON, 3), "Martin Luther King Jr. Day"),
        (_nth_weekday(year, 2, MON, 3), "Presidents' Day"),
        (_last_weekday(year, 5, MON), "Memorial Day"),
        (date(year, 6, 19), "Juneteenth"),
        (date(year, 7, 4), "Independence Day"),
        (_nth_weekday(year, 9, MON, 1), "Labor Day"),
        (_nth_weekday(year, 10, MON, 2), "Columbus Day"),
        (date(year, 11, 11), "Veterans Day"),
        (_nth_weekday(year, 11, THU, 4), "Thanksgiving"),
        (date(year, 12, 25), "Christmas Day"),
    ]

    holidays.sort(key=lambda h: h[0])
    return holidays
