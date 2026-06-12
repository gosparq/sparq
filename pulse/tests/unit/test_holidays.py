# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Holiday Calculator Unit Tests
#
# Tests for system/utils/holidays.py. Verifies US federal holiday date
# calculations for fixed-date and floating holidays.
# -----------------------------------------------------------------------------

from datetime import date

import pytest

from system.utils.holidays import (
    _last_weekday,
    _nth_weekday,
    get_us_federal_holidays,
)


# ---------------------------------------------------------------------------
# 1. _nth_weekday — nth occurrence of a weekday in a month
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNthWeekday:
    """Test nth weekday calculation."""

    def test_first_monday_jan_2026(self):
        """First Monday of January 2026 should be Jan 5."""
        assert _nth_weekday(2026, 1, 0, 1) == date(2026, 1, 5)

    def test_third_monday_jan_2026(self):
        """Third Monday of January 2026 (MLK Day) should be Jan 19."""
        assert _nth_weekday(2026, 1, 0, 3) == date(2026, 1, 19)

    def test_second_monday_oct_2026(self):
        """Second Monday of October 2026 (Columbus Day) should be Oct 12."""
        assert _nth_weekday(2026, 10, 0, 2) == date(2026, 10, 12)

    def test_fourth_thursday_nov_2026(self):
        """Fourth Thursday of November 2026 (Thanksgiving) should be Nov 26."""
        assert _nth_weekday(2026, 11, 3, 4) == date(2026, 11, 26)

    def test_invalid_nth_raises(self):
        """Requesting a 5th Monday in a month that doesn't have one should raise."""
        with pytest.raises(ValueError):
            _nth_weekday(2026, 2, 0, 5)  # Feb 2026 has only 4 Mondays


# ---------------------------------------------------------------------------
# 2. _last_weekday — last occurrence of a weekday in a month
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLastWeekday:
    """Test last weekday calculation."""

    def test_last_monday_may_2026(self):
        """Last Monday of May 2026 (Memorial Day) should be May 25."""
        assert _last_weekday(2026, 5, 0) == date(2026, 5, 25)

    def test_last_friday_jan_2026(self):
        """Last Friday of January 2026 should be Jan 30."""
        assert _last_weekday(2026, 1, 4) == date(2026, 1, 30)

    def test_last_sunday_feb_2026(self):
        """Last Sunday of February 2026."""
        result = _last_weekday(2026, 2, 6)
        assert result.weekday() == 6
        assert result.month == 2


# ---------------------------------------------------------------------------
# 3. get_us_federal_holidays — full holiday list
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetUSFederalHolidays:
    """Test US federal holiday list generation."""

    def test_returns_eleven_holidays(self):
        """There should be exactly 11 US federal holidays."""
        holidays = get_us_federal_holidays(2026)
        assert len(holidays) == 11

    def test_holidays_sorted_by_date(self):
        """Holidays should be sorted chronologically."""
        holidays = get_us_federal_holidays(2026)
        dates = [h[0] for h in holidays]
        assert dates == sorted(dates)

    def test_new_years_day(self):
        """New Year's Day should be January 1."""
        holidays = dict(get_us_federal_holidays(2026))
        assert date(2026, 1, 1) in holidays
        assert holidays[date(2026, 1, 1)] == "New Year's Day"

    def test_independence_day(self):
        """Independence Day should be July 4."""
        holidays = dict(get_us_federal_holidays(2026))
        assert date(2026, 7, 4) in holidays

    def test_christmas(self):
        """Christmas should be December 25."""
        holidays = dict(get_us_federal_holidays(2026))
        assert date(2026, 12, 25) in holidays

    def test_juneteenth(self):
        """Juneteenth should be June 19."""
        holidays = dict(get_us_federal_holidays(2026))
        assert date(2026, 6, 19) in holidays

    def test_veterans_day(self):
        """Veterans Day should be November 11."""
        holidays = dict(get_us_federal_holidays(2026))
        assert date(2026, 11, 11) in holidays

    def test_mlk_day_is_third_monday_jan(self):
        """MLK Day should be the third Monday of January."""
        holidays = dict(get_us_federal_holidays(2026))
        mlk = date(2026, 1, 19)
        assert mlk in holidays
        assert mlk.weekday() == 0  # Monday

    def test_thanksgiving_is_fourth_thursday_nov(self):
        """Thanksgiving should be the fourth Thursday of November."""
        holidays = dict(get_us_federal_holidays(2026))
        thanksgiving = date(2026, 11, 26)
        assert thanksgiving in holidays
        assert thanksgiving.weekday() == 3  # Thursday

    def test_labor_day_is_first_monday_sep(self):
        """Labor Day should be the first Monday of September."""
        holidays = dict(get_us_federal_holidays(2026))
        labor = date(2026, 9, 7)
        assert labor in holidays
        assert labor.weekday() == 0  # Monday

    def test_memorial_day_is_last_monday_may(self):
        """Memorial Day should be the last Monday of May."""
        holidays = dict(get_us_federal_holidays(2026))
        memorial = date(2026, 5, 25)
        assert memorial in holidays
        assert memorial.weekday() == 0  # Monday

    def test_different_year(self):
        """Holidays for a different year should have correct dates."""
        holidays = dict(get_us_federal_holidays(2025))
        # MLK Day 2025: 3rd Monday of Jan = Jan 20
        assert date(2025, 1, 20) in holidays
