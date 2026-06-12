# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - ClockPunch Model Integration Tests
#
# Tests for ClockPunch model database operations.
# -----------------------------------------------------------------------------

from datetime import datetime, timedelta

import pytest
from flask import g



def _make_org_member(ws):
    """Create an OrganizationUser for clock punch tests.

    ClockPunch uses OrganizationMixin and member_id references organization_user.id.
    """
    from modules.base.core.models.organization_user import OrganizationUser

    org_user = OrganizationUser.query.filter_by(
        user_id=ws["user"].id,
        organization_id=ws["organization"].id,
    ).first()
    return org_user


@pytest.mark.integration
class TestClockIn:
    """Tests for ClockPunch.clock_in()."""

    def test_clock_in_basic(self, app, db_session, seeded_workspace):
        """Test basic clock-in creates a punch record."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        assert punch.id is not None
        assert punch.punch_type == PunchType.IN
        assert punch.member_id == org_member.id
        assert punch.source == "web"
        assert punch.punch_time is not None

    def test_clock_in_with_location(self, app, db_session, seeded_workspace):
        """Test clock-in with geolocation data."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        punch = ClockPunch.clock_in(
            member_id=org_member.id,
            source="mobile",
            latitude=30.2672,
            longitude=-97.7431,
            location_accuracy=10.0,
        )

        assert punch.latitude == 30.2672
        assert punch.longitude == -97.7431
        assert punch.location_accuracy == 10.0

    def test_clock_in_with_ip_address(self, app, db_session, seeded_workspace):
        """Test clock-in records IP address."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        punch = ClockPunch.clock_in(
            member_id=org_member.id,
            ip_address="192.168.1.1",
        )

        assert punch.ip_address == "192.168.1.1"

    def test_clock_in_already_clocked_in_raises(self, app, db_session, seeded_workspace):
        """Test clock-in when already clocked in raises ValueError."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id)

        with pytest.raises(ValueError, match="already clocked in"):
            ClockPunch.clock_in(member_id=org_member.id)


@pytest.mark.integration
class TestClockOut:
    """Tests for ClockPunch.clock_out()."""

    def test_clock_out_basic(self, app, db_session, seeded_workspace):
        """Test basic clock-out creates a punch record."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id, source="web")

        punch = ClockPunch.clock_out(
            member_id=org_member.id,
            source="web",
            auto_create_timeentry=False,
        )

        assert punch.id is not None
        assert punch.punch_type == PunchType.OUT
        assert punch.member_id == org_member.id

    def test_clock_out_not_clocked_in_raises(self, app, db_session, seeded_workspace):
        """Test clock-out when not clocked in raises ValueError."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)

        with pytest.raises(ValueError, match="not clocked in"):
            ClockPunch.clock_out(member_id=org_member.id)

    def test_clock_out_records_source(self, app, db_session, seeded_workspace):
        """Test clock-out records the correct source."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id, source="kiosk")

        punch = ClockPunch.clock_out(
            member_id=org_member.id,
            source="kiosk",
            auto_create_timeentry=False,
        )

        assert punch.source == "kiosk"


@pytest.mark.integration
class TestClockStatus:
    """Tests for clock status checks."""

    def test_is_clocked_in_true(self, app, db_session, seeded_workspace):
        """Test is_clocked_in returns True after clock-in."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id)

        assert ClockPunch.is_clocked_in(org_member.id) is True

    def test_is_clocked_in_false_initially(self, app, db_session, seeded_workspace):
        """Test is_clocked_in returns False when no punches exist."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)

        assert ClockPunch.is_clocked_in(org_member.id) is False

    def test_is_clocked_in_false_after_clock_out(self, app, db_session, seeded_workspace):
        """Test is_clocked_in returns False after clock-out."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id)
        ClockPunch.clock_out(
            member_id=org_member.id, auto_create_timeentry=False,
        )

        assert ClockPunch.is_clocked_in(org_member.id) is False

    def test_get_last_clock_in(self, app, db_session, seeded_workspace):
        """Test get_last_clock_in returns the open clock-in punch."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        clock_in_punch = ClockPunch.clock_in(member_id=org_member.id)

        result = ClockPunch.get_last_clock_in(org_member.id)
        assert result is not None
        assert result.id == clock_in_punch.id
        assert result.punch_type == PunchType.IN

    def test_get_last_clock_in_none_after_clock_out(self, app, db_session, seeded_workspace):
        """Test get_last_clock_in returns None after clock-out."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id)
        ClockPunch.clock_out(
            member_id=org_member.id, auto_create_timeentry=False,
        )

        assert ClockPunch.get_last_clock_in(org_member.id) is None

    def test_get_current_status_clocked_in(self, app, db_session, seeded_workspace):
        """Test get_current_status returns correct data when clocked in."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        ClockPunch.clock_in(member_id=org_member.id)

        status = ClockPunch.get_current_status(org_member.id)

        assert status["is_clocked_in"] is True
        assert status["clock_in_time"] is not None
        assert status["elapsed"] is not None
        assert status["elapsed_str"] is not None

    def test_get_current_status_not_clocked_in(self, app, db_session, seeded_workspace):
        """Test get_current_status returns correct data when not clocked in."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)

        status = ClockPunch.get_current_status(org_member.id)

        assert status["is_clocked_in"] is False
        assert status["clock_in_time"] is None
        assert status["elapsed"] is None


@pytest.mark.integration
class TestPunchPairing:
    """Tests for matching IN/OUT punch pairs."""

    def test_get_matching_out(self, app, db_session, seeded_workspace):
        """Test get_matching_out finds the paired OUT punch."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        in_punch = ClockPunch.clock_in(member_id=org_member.id)
        out_punch = ClockPunch.clock_out(
            member_id=org_member.id, auto_create_timeentry=False,
        )

        matching = in_punch.get_matching_out()
        assert matching is not None
        assert matching.id == out_punch.id

    def test_get_matching_in(self, app, db_session, seeded_workspace):
        """Test get_matching_in finds the paired IN punch."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        in_punch = ClockPunch.clock_in(member_id=org_member.id)
        out_punch = ClockPunch.clock_out(
            member_id=org_member.id, auto_create_timeentry=False,
        )

        matching = out_punch.get_matching_in()
        assert matching is not None
        assert matching.id == in_punch.id

    def test_get_matching_out_none_when_open(self, app, db_session, seeded_workspace):
        """Test get_matching_out returns None for open clock-in."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        in_punch = ClockPunch.clock_in(member_id=org_member.id)

        assert in_punch.get_matching_out() is None

    def test_get_matching_in_returns_none_for_in_punch(self, app, db_session, seeded_workspace):
        """Test get_matching_in returns None when called on an IN punch."""
        from modules.base.presence.models.clock_punch import ClockPunch

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        org_member = _make_org_member(ws)
        in_punch = ClockPunch.clock_in(member_id=org_member.id)

        assert in_punch.get_matching_in() is None


@pytest.mark.integration
class TestRoundTime:
    """Tests for time rounding logic."""

    def test_round_time_employee_friendly_clock_in(self, app, db_session, seeded_workspace):
        """Test employee-friendly rounding rounds clock-in DOWN."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        # 7:07 should round down to 7:00
        punch_time = datetime(2025, 1, 1, 7, 7, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.IN, rounding_minutes=15, rounding_type="employee_friendly",
        )

        assert rounded.hour == 7
        assert rounded.minute == 0

    def test_round_time_employee_friendly_clock_out(self, app, db_session, seeded_workspace):
        """Test employee-friendly rounding rounds clock-out UP."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        # 4:53 should round up to 5:00
        punch_time = datetime(2025, 1, 1, 16, 53, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.OUT, rounding_minutes=15, rounding_type="employee_friendly",
        )

        assert rounded.hour == 17
        assert rounded.minute == 0

    def test_round_time_employer_friendly_clock_in(self, app, db_session, seeded_workspace):
        """Test employer-friendly rounding rounds clock-in UP."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        # 7:07 should round up to 7:15
        punch_time = datetime(2025, 1, 1, 7, 7, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.IN, rounding_minutes=15, rounding_type="employer_friendly",
        )

        assert rounded.hour == 7
        assert rounded.minute == 15

    def test_round_time_employer_friendly_clock_out(self, app, db_session, seeded_workspace):
        """Test employer-friendly rounding rounds clock-out DOWN."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        # 4:53 should round down to 4:45
        punch_time = datetime(2025, 1, 1, 16, 53, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.OUT, rounding_minutes=15, rounding_type="employer_friendly",
        )

        assert rounded.hour == 16
        assert rounded.minute == 45

    def test_round_time_nearest(self, app, db_session, seeded_workspace):
        """Test nearest rounding rounds to nearest interval."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        # 7:07 rounds down to 7:00 (7 < 7.5)
        punch_time = datetime(2025, 1, 1, 7, 7, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.IN, rounding_minutes=15, rounding_type="nearest",
        )
        assert rounded.minute == 0

        # 7:08 rounds up to 7:15 (8 >= 7.5)
        punch_time2 = datetime(2025, 1, 1, 7, 8, 0)
        rounded2 = ClockPunch.round_time(
            punch_time2, PunchType.IN, rounding_minutes=15, rounding_type="nearest",
        )
        assert rounded2.minute == 15

    def test_round_time_already_on_boundary(self, app, db_session, seeded_workspace):
        """Test rounding a time already on a boundary returns the same time."""
        from modules.base.presence.models.clock_punch import ClockPunch, PunchType

        punch_time = datetime(2025, 1, 1, 7, 0, 0)
        rounded = ClockPunch.round_time(
            punch_time, PunchType.IN, rounding_minutes=15, rounding_type="employee_friendly",
        )

        assert rounded.hour == 7
        assert rounded.minute == 0


@pytest.mark.integration
class TestFormatElapsed:
    """Tests for elapsed time formatting."""

    def test_format_elapsed_hours_and_minutes(self, app, db_session, seeded_workspace):
        """Test formatting with hours and minutes."""
        from modules.base.presence.models.clock_punch import ClockPunch

        elapsed = timedelta(hours=3, minutes=25)
        result = ClockPunch._format_elapsed(elapsed)

        assert result == "3h 25m"

    def test_format_elapsed_minutes_only(self, app, db_session, seeded_workspace):
        """Test formatting with only minutes."""
        from modules.base.presence.models.clock_punch import ClockPunch

        elapsed = timedelta(minutes=42)
        result = ClockPunch._format_elapsed(elapsed)

        assert result == "42m"

    def test_format_elapsed_zero(self, app, db_session, seeded_workspace):
        """Test formatting zero elapsed time."""
        from modules.base.presence.models.clock_punch import ClockPunch

        elapsed = timedelta(0)
        result = ClockPunch._format_elapsed(elapsed)

        assert result == "0m"
