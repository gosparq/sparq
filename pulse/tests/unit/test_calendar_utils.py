# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Calendar Utils Unit Tests
#
# Tests for system/utils/calendar_utils.py. Verifies week/month calculations,
# weekday headers, and spanning segment utilities.
# -----------------------------------------------------------------------------

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from system.utils.calendar_utils import (
    assign_spanning_lanes,
    compute_spanning_segments,
    get_month_calendar_weeks,
    get_week_dates_list,
    get_week_start,
    get_weekday_headers,
    get_first_day_of_week,
    get_python_firstweekday,
)


# ---------------------------------------------------------------------------
# Helper to mock the first-day-of-week setting
# ---------------------------------------------------------------------------

def _patch_first_day(value):
    """Patch get_first_day_of_week to return a fixed value."""
    return patch(
        "system.utils.calendar_utils.get_first_day_of_week", return_value=value
    )


# ---------------------------------------------------------------------------
# 1. get_first_day_of_week — setting retrieval
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetFirstDayOfWeek:
    """Test the first-day-of-week setting retrieval."""

    def test_defaults_to_sunday_outside_context(self):
        """Outside a Flask request context, should default to 0 (Sunday)."""
        result = get_first_day_of_week()
        assert result == 0


# ---------------------------------------------------------------------------
# 2. get_python_firstweekday — mapping company → Python calendar
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetPythonFirstweekday:
    """Test mapping from company setting to Python calendar firstweekday."""

    def test_sunday_maps_to_six(self):
        """Company 0 (Sunday) maps to Python calendar 6."""
        with _patch_first_day(0):
            assert get_python_firstweekday() == 6

    def test_monday_maps_to_zero(self):
        """Company 1 (Monday) maps to Python calendar 0."""
        with _patch_first_day(1):
            assert get_python_firstweekday() == 0


# ---------------------------------------------------------------------------
# 3. get_week_start — first day of the week containing a date
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetWeekStart:
    """Test calculation of the first day of the week."""

    def test_sunday_start_on_wednesday(self):
        """Wednesday 2026-06-03 with Sunday start should return Sun 2026-05-31."""
        with _patch_first_day(0):
            result = get_week_start(date(2026, 6, 3))
            assert result == date(2026, 5, 31)
            assert result.weekday() == 6  # Sunday

    def test_sunday_start_on_sunday(self):
        """A Sunday with Sunday-start should return itself."""
        with _patch_first_day(0):
            result = get_week_start(date(2026, 5, 31))
            assert result == date(2026, 5, 31)

    def test_sunday_start_on_saturday(self):
        """Saturday with Sunday start should return the preceding Sunday."""
        with _patch_first_day(0):
            result = get_week_start(date(2026, 6, 6))  # Saturday
            assert result == date(2026, 5, 31)

    def test_monday_start_on_wednesday(self):
        """Wednesday 2026-06-03 with Monday start should return Mon 2026-06-01."""
        with _patch_first_day(1):
            result = get_week_start(date(2026, 6, 3))
            assert result == date(2026, 6, 1)
            assert result.weekday() == 0  # Monday

    def test_monday_start_on_monday(self):
        """A Monday with Monday-start should return itself."""
        with _patch_first_day(1):
            result = get_week_start(date(2026, 6, 1))
            assert result == date(2026, 6, 1)

    def test_monday_start_on_sunday(self):
        """Sunday with Monday start should return the preceding Monday."""
        with _patch_first_day(1):
            result = get_week_start(date(2026, 5, 31))
            assert result == date(2026, 5, 25)


# ---------------------------------------------------------------------------
# 4. get_week_dates_list — seven consecutive dates
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetWeekDatesList:
    """Test generation of seven consecutive week dates."""

    def test_returns_seven_dates(self):
        """Should always return exactly 7 dates."""
        with _patch_first_day(0):
            result = get_week_dates_list(date(2026, 6, 3))
            assert len(result) == 7

    def test_dates_are_consecutive(self):
        """Dates should be consecutive days."""
        with _patch_first_day(0):
            result = get_week_dates_list(date(2026, 6, 3))
            for i in range(6):
                assert result[i + 1] - result[i] == timedelta(days=1)

    def test_starts_on_week_start_sunday(self):
        """First date should be the week start (Sunday)."""
        with _patch_first_day(0):
            result = get_week_dates_list(date(2026, 6, 3))
            assert result[0].weekday() == 6  # Sunday

    def test_starts_on_week_start_monday(self):
        """First date should be the week start (Monday)."""
        with _patch_first_day(1):
            result = get_week_dates_list(date(2026, 6, 3))
            assert result[0].weekday() == 0  # Monday


# ---------------------------------------------------------------------------
# 5. get_month_calendar_weeks — month grid
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetMonthCalendarWeeks:
    """Test month calendar grid generation."""

    def test_each_week_has_seven_days(self):
        """Every week in the grid should have exactly 7 days."""
        with _patch_first_day(0):
            weeks = get_month_calendar_weeks(2026, 6)
            for week in weeks:
                assert len(week) == 7

    def test_covers_all_month_days(self):
        """All days of the month should appear in the grid."""
        with _patch_first_day(0):
            weeks = get_month_calendar_weeks(2026, 6)
            all_dates = [d for week in weeks for d in week]
            for day in range(1, 31):
                assert date(2026, 6, day) in all_dates

    def test_first_day_matches_setting_sunday(self):
        """With Sunday start, each week row should begin on Sunday."""
        with _patch_first_day(0):
            weeks = get_month_calendar_weeks(2026, 6)
            for week in weeks:
                assert week[0].weekday() == 6  # Sunday

    def test_first_day_matches_setting_monday(self):
        """With Monday start, each week row should begin on Monday."""
        with _patch_first_day(1):
            weeks = get_month_calendar_weeks(2026, 6)
            for week in weeks:
                assert week[0].weekday() == 0  # Monday


# ---------------------------------------------------------------------------
# 6. get_weekday_headers — day name labels
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetWeekdayHeaders:
    """Test weekday header generation (needs app context for translation)."""

    def test_short_style_returns_seven(self, app):
        """Short style should return 7 headers."""
        with app.app_context(), _patch_first_day(0):
            headers = get_weekday_headers("short")
            assert len(headers) == 7

    def test_min_style_returns_seven(self, app):
        """Min style should return 7 headers."""
        with app.app_context(), _patch_first_day(0):
            headers = get_weekday_headers("min")
            assert len(headers) == 7

    def test_sunday_start_short_begins_with_sun(self, app):
        """Sunday start short style should start with Sun."""
        with app.app_context(), _patch_first_day(0):
            headers = get_weekday_headers("short")
            assert headers[0] == "Sun"

    def test_monday_start_short_begins_with_mon(self, app):
        """Monday start short style should start with Mon."""
        with app.app_context(), _patch_first_day(1):
            headers = get_weekday_headers("short")
            assert headers[0] == "Mon"


# ---------------------------------------------------------------------------
# 7. compute_spanning_segments — clipping entries to week boundaries
# ---------------------------------------------------------------------------


def _make_entry(id, start, end, label="Test"):
    return {
        "id": id,
        "type": "event",
        "label": label,
        "url": "/test",
        "start_date": start,
        "end_date": end,
    }


@pytest.mark.unit
class TestComputeSpanningSegments:
    """Test spanning segment clipping and position calculation."""

    def test_entry_fully_within_week(self):
        """An entry fully within the week should have correct col_start and span."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 6, 2), date(2026, 6, 4))
        segments = compute_spanning_segments([entry], ws, we)
        assert len(segments) == 1
        assert segments[0]["col_start"] == 2
        assert segments[0]["col_span"] == 3
        assert segments[0]["continues_left"] is False
        assert segments[0]["continues_right"] is False

    def test_entry_spanning_entire_week(self):
        """An entry spanning beyond both ends should be clipped."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 5, 28), date(2026, 6, 10))
        segments = compute_spanning_segments([entry], ws, we)
        assert len(segments) == 1
        assert segments[0]["col_start"] == 1
        assert segments[0]["col_span"] == 7
        assert segments[0]["continues_left"] is True
        assert segments[0]["continues_right"] is True

    def test_entry_before_week_excluded(self):
        """An entry ending before the week starts should be excluded."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 5, 20), date(2026, 5, 25))
        segments = compute_spanning_segments([entry], ws, we)
        assert len(segments) == 0

    def test_entry_after_week_excluded(self):
        """An entry starting after the week ends should be excluded."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 6, 10), date(2026, 6, 15))
        segments = compute_spanning_segments([entry], ws, we)
        assert len(segments) == 0

    def test_entry_clipped_left(self):
        """An entry starting before the week should be clipped on the left."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 5, 28), date(2026, 6, 3))
        segments = compute_spanning_segments([entry], ws, we)
        assert segments[0]["col_start"] == 1
        assert segments[0]["col_span"] == 3
        assert segments[0]["continues_left"] is True
        assert segments[0]["continues_right"] is False

    def test_single_day_entry(self):
        """A single-day entry should have col_span of 1."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        entry = _make_entry(1, date(2026, 6, 4), date(2026, 6, 4))
        segments = compute_spanning_segments([entry], ws, we)
        assert segments[0]["col_span"] == 1

    def test_empty_entries_list(self):
        """An empty entry list should return empty segments."""
        ws = date(2026, 6, 1)
        we = date(2026, 6, 7)
        segments = compute_spanning_segments([], ws, we)
        assert segments == []


# ---------------------------------------------------------------------------
# 8. assign_spanning_lanes — vertical lane assignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAssignSpanningLanes:
    """Test lane assignment for non-overlapping display."""

    def test_non_overlapping_share_lane(self):
        """Non-overlapping segments should share the same lane."""
        segments = [
            {"col_start": 1, "col_span": 2, "row_index": 0},
            {"col_start": 4, "col_span": 2, "row_index": 0},
        ]
        lanes = assign_spanning_lanes(segments)
        assert lanes == 1
        assert segments[0]["row_index"] == 0
        assert segments[1]["row_index"] == 0

    def test_overlapping_get_separate_lanes(self):
        """Overlapping segments should be assigned different lanes."""
        segments = [
            {"col_start": 1, "col_span": 4, "row_index": 0},
            {"col_start": 3, "col_span": 3, "row_index": 0},
        ]
        lanes = assign_spanning_lanes(segments)
        assert lanes == 2
        assert segments[0]["row_index"] != segments[1]["row_index"]

    def test_empty_segments(self):
        """Empty segment list should return 0 lanes."""
        assert assign_spanning_lanes([]) == 0

    def test_three_overlapping_segments(self):
        """Three fully overlapping segments need 3 lanes."""
        segments = [
            {"col_start": 1, "col_span": 5, "row_index": 0},
            {"col_start": 1, "col_span": 5, "row_index": 0},
            {"col_start": 1, "col_span": 5, "row_index": 0},
        ]
        lanes = assign_spanning_lanes(segments)
        assert lanes == 3
        row_indices = {s["row_index"] for s in segments}
        assert row_indices == {0, 1, 2}
