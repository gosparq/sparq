# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Presence Model Integration Tests
#
# Tests for Presence module models: leave requests, member schedules,
# clock punch adjustments, punch correction requests, presence signals,
# presence forecasts, and time tracking settings.
# (ClockPunch and TimeEntry already have tests -- not duplicated here.)
# -----------------------------------------------------------------------------

from datetime import date, time, timedelta

import pytest
from flask import g

from system.db.database import db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_context(ws):
    """Set g.organization_id and g.workspace_id from seeded_workspace."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _get_org_member(ws):
    """Return the OrganizationUser for the seeded workspace user."""
    from modules.base.core.models.organization_user import OrganizationUser

    return OrganizationUser.query.filter_by(
        user_id=ws["user"].id,
        organization_id=ws["organization"].id,
    ).first()


def _get_membership(ws):
    """Return the WorkspaceUser membership from seeded_workspace."""
    return ws["membership"]


# ===========================================================================
# LeaveRequest
# ===========================================================================


@pytest.mark.integration
class TestLeaveRequest:
    """Tests for LeaveRequest model."""

    def test_create_leave_request(self, app, db_session, seeded_workspace):
        """Test creating a leave request in draft status."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 5),
            employee_notes="Family trip",
        )

        assert req.id is not None
        assert req.status == LeaveRequestStatus.DRAFT
        assert req.leave_type == LeaveType.VACATION
        assert req.employee_notes == "Family trip"

    def test_total_days(self, app, db_session, seeded_workspace):
        """Test total_days calculation (inclusive)."""
        from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 7, 1),
            end_date=date(2025, 7, 3),
        )

        assert req.total_days == 3

    def test_submit(self, app, db_session, seeded_workspace):
        """Test submitting a draft request."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.SICK,
            start_date=date(2025, 8, 1),
            end_date=date(2025, 8, 1),
        )

        req.submit()
        assert req.status == LeaveRequestStatus.PENDING
        assert req.submitted_at is not None

    def test_submit_non_draft_raises(self, app, db_session, seeded_workspace):
        """Test submitting a non-draft request raises ValueError."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.PERSONAL,
            start_date=date(2025, 8, 5),
            end_date=date(2025, 8, 5),
        )
        req.submit()

        with pytest.raises(ValueError, match="Only draft requests"):
            req.submit()

    def test_approve(self, app, db_session, seeded_workspace):
        """Test approving a pending request."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 9, 1),
            end_date=date(2025, 9, 5),
        )
        req.submit()

        req.approve(user_id=org_member.id, notes="Enjoy!")
        assert req.status == LeaveRequestStatus.APPROVED
        assert req.reviewed_by_id == org_member.id
        assert req.admin_notes == "Enjoy!"

    def test_approve_non_pending_raises(self, app, db_session, seeded_workspace):
        """Test approving a non-pending request raises ValueError."""
        from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 9, 10),
            end_date=date(2025, 9, 10),
        )

        with pytest.raises(ValueError, match="Only pending requests can be approved"):
            req.approve(user_id=org_member.id)

    def test_deny(self, app, db_session, seeded_workspace):
        """Test denying a pending request."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 3),
        )
        req.submit()

        req.deny(user_id=org_member.id, notes="Blackout period")
        assert req.status == LeaveRequestStatus.DENIED
        assert req.admin_notes == "Blackout period"

    def test_cancel(self, app, db_session, seeded_workspace):
        """Test cancelling a request."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.PERSONAL,
            start_date=date(2025, 11, 1),
            end_date=date(2025, 11, 1),
        )

        assert req.can_cancel is True
        req.cancel()
        assert req.status == LeaveRequestStatus.CANCELLED

    def test_cancel_approved_raises(self, app, db_session, seeded_workspace):
        """Test cancelling an approved request raises ValueError."""
        from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 11, 5),
            end_date=date(2025, 11, 5),
        )
        req.submit()
        req.approve(user_id=org_member.id)

        assert req.can_cancel is False
        with pytest.raises(ValueError, match="cannot be cancelled"):
            req.cancel()

    def test_unapprove(self, app, db_session, seeded_workspace):
        """Test unapproving reverts to pending."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date.today() + timedelta(days=30),
            end_date=date.today() + timedelta(days=35),
        )
        req.submit()
        req.approve(user_id=org_member.id)

        req.unapprove(user_id=org_member.id)
        assert req.status == LeaveRequestStatus.PENDING
        assert "[Reverted to pending]" in req.admin_notes

    def test_is_editable_by_member(self, app, db_session, seeded_workspace):
        """Test is_editable_by_member for various statuses."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 12, 1),
            end_date=date(2025, 12, 1),
        )

        # Draft is editable
        assert req.is_editable_by_member is True

        # Pending is editable
        req.submit()
        assert req.is_editable_by_member is True

        # Approved is NOT editable
        req.approve(user_id=org_member.id)
        assert req.is_editable_by_member is False

    def test_update_request(self, app, db_session, seeded_workspace):
        """Test updating a draft request."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 12, 10),
            end_date=date(2025, 12, 12),
        )

        req.update(
            leave_type=LeaveType.PERSONAL,
            start_date=date(2025, 12, 11),
            employee_notes="Changed plans",
        )
        assert req.leave_type == LeaveType.PERSONAL
        assert req.start_date == date(2025, 12, 11)
        assert req.employee_notes == "Changed plans"

    def test_update_non_editable_raises(self, app, db_session, seeded_workspace):
        """Test updating a non-editable request raises ValueError."""
        from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 12, 20),
            end_date=date(2025, 12, 20),
        )
        req.submit()
        req.approve(user_id=org_member.id)

        with pytest.raises(ValueError, match="cannot be edited"):
            req.update(employee_notes="Too late")

    def test_admin_update(self, app, db_session, seeded_workspace):
        """Test admin_update bypasses editability checks."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2025, 12, 25),
            end_date=date(2025, 12, 25),
        )
        req.submit()
        req.approve(user_id=org_member.id)

        # Admin can update even after approval
        req.admin_update(
            leave_type=LeaveType.PERSONAL,
            status=LeaveRequestStatus.PENDING,
        )
        assert req.leave_type == LeaveType.PERSONAL
        assert req.status == LeaveRequestStatus.PENDING

    def test_status_badge_class(self, app, db_session, seeded_workspace):
        """Test status_badge_class returns correct Bootstrap classes."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 1),
        )

        assert "secondary" in req.status_badge_class  # DRAFT

        req.submit()
        assert "warning" in req.status_badge_class  # PENDING

    def test_find_overlapping(self, app, db_session, seeded_workspace):
        """Test find_overlapping detects date range overlaps."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 5),
        )
        req.submit()

        # Overlapping range
        overlaps = LeaveRequest.find_overlapping(
            member_id=org_member.id,
            start_date=date(2026, 3, 3),
            end_date=date(2026, 3, 7),
        )
        assert len(overlaps) >= 1

        # Non-overlapping range
        no_overlap = LeaveRequest.find_overlapping(
            member_id=org_member.id,
            start_date=date(2026, 3, 10),
            end_date=date(2026, 3, 15),
        )
        assert len(no_overlap) == 0

    def test_pending_count(self, app, db_session, seeded_workspace):
        """Test pending_count returns correct number."""
        from modules.base.presence.models.leave_request import LeaveRequest, LeaveType

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 1),
        )
        req.submit()

        assert LeaveRequest.pending_count() >= 1

    def test_request_changes(self, app, db_session, seeded_workspace):
        """Test request_changes adds admin notes without changing status."""
        from modules.base.presence.models.leave_request import (
            LeaveRequest, LeaveType, LeaveRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        req = LeaveRequest.create(
            member_id=org_member.id,
            leave_type=LeaveType.VACATION,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 5),
        )
        req.submit()

        req.request_changes(user_id=org_member.id, notes="Please shorten to 3 days")
        assert req.status == LeaveRequestStatus.PENDING
        assert req.admin_notes == "Please shorten to 3 days"


# ===========================================================================
# MemberSchedule & MemberScheduleOverride
# ===========================================================================


@pytest.mark.integration
class TestMemberSchedule:
    """Tests for MemberSchedule and MemberScheduleOverride models."""

    def test_set_weekly_schedule(self, app, db_session, seeded_workspace):
        """Test setting a weekly schedule."""
        from modules.base.presence.models.member_schedule import MemberSchedule

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        schedule_data = [
            {"day": 0, "start": time(9, 0), "end": time(17, 0)},
            {"day": 1, "start": time(9, 0), "end": time(17, 0)},
            {"day": 2, "start": time(9, 0), "end": time(17, 0)},
            {"day": 3, "start": time(9, 0), "end": time(17, 0)},
            {"day": 4, "start": time(9, 0), "end": time(17, 0)},
        ]

        results = MemberSchedule.set_weekly_schedule(member.id, schedule_data)
        assert len(results) == 5

        weekly = MemberSchedule.get_weekly_schedule(member.id)
        assert len(weekly) == 5
        assert 0 in weekly  # Monday
        assert 5 not in weekly  # Saturday not set

    def test_set_weekly_schedule_upsert(self, app, db_session, seeded_workspace):
        """Test updating an existing weekly schedule upserts correctly."""
        from modules.base.presence.models.member_schedule import MemberSchedule

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        MemberSchedule.set_weekly_schedule(member.id, [
            {"day": 0, "start": time(9, 0), "end": time(17, 0)},
            {"day": 1, "start": time(9, 0), "end": time(17, 0)},
        ])

        # Update with different times and remove Tuesday
        MemberSchedule.set_weekly_schedule(member.id, [
            {"day": 0, "start": time(8, 0), "end": time(16, 0)},
        ])

        weekly = MemberSchedule.get_weekly_schedule(member.id)
        assert len(weekly) == 1
        assert weekly[0].start_time == time(8, 0)

    def test_get_effective_schedule_default(self, app, db_session, seeded_workspace):
        """Test get_effective_schedule returns default schedule."""
        from modules.base.presence.models.member_schedule import MemberSchedule

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        # Set Monday schedule
        MemberSchedule.set_weekly_schedule(member.id, [
            {"day": 0, "start": time(9, 0), "end": time(17, 0)},
        ])

        # Find a Monday
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        result = MemberSchedule.get_effective_schedule(member.id, monday)
        assert result is not None
        assert result == (time(9, 0), time(17, 0))

    def test_get_effective_schedule_override_wins(self, app, db_session, seeded_workspace):
        """Test that override takes precedence over default schedule."""
        from modules.base.presence.models.member_schedule import (
            MemberSchedule, MemberScheduleOverride,
        )

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        today = date.today()
        monday = today - timedelta(days=today.weekday())

        MemberSchedule.set_weekly_schedule(member.id, [
            {"day": 0, "start": time(9, 0), "end": time(17, 0)},
        ])

        MemberScheduleOverride.set_override(
            member_id=member.id,
            override_date=monday,
            start_time=time(10, 0),
            end_time=time(14, 0),
        )

        result = MemberSchedule.get_effective_schedule(member.id, monday)
        assert result == (time(10, 0), time(14, 0))

    def test_get_effective_schedule_none(self, app, db_session, seeded_workspace):
        """Test get_effective_schedule returns None when no schedule."""
        from modules.base.presence.models.member_schedule import MemberSchedule

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        # Sunday with no schedule
        today = date.today()
        sunday = today + timedelta(days=(6 - today.weekday()))

        result = MemberSchedule.get_effective_schedule(member.id, sunday)
        assert result is None

    def test_override_set_and_clear(self, app, db_session, seeded_workspace):
        """Test setting and clearing a schedule override."""
        from modules.base.presence.models.member_schedule import MemberScheduleOverride

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        target = date(2025, 7, 15)

        override = MemberScheduleOverride.set_override(
            member_id=member.id,
            override_date=target,
            start_time=time(10, 0),
            end_time=time(14, 0),
        )

        assert override.id is not None
        assert override.start_time == time(10, 0)

        MemberScheduleOverride.clear_override(member.id, target)
        overrides = MemberScheduleOverride.get_overrides_for_range(
            member.id, target, target,
        )
        assert len(overrides) == 0

    def test_override_upsert(self, app, db_session, seeded_workspace):
        """Test that set_override updates existing override."""
        from modules.base.presence.models.member_schedule import MemberScheduleOverride

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        target = date(2025, 7, 20)

        MemberScheduleOverride.set_override(
            member_id=member.id,
            override_date=target,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        updated = MemberScheduleOverride.set_override(
            member_id=member.id,
            override_date=target,
            start_time=time(10, 0),
            end_time=time(15, 0),
        )

        assert updated.start_time == time(10, 0)
        assert updated.end_time == time(15, 0)

    def test_get_bulk_effective(self, app, db_session, seeded_workspace):
        """Test batch schedule lookup for multiple members."""
        from modules.base.presence.models.member_schedule import MemberSchedule

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        today = date.today()
        monday = today - timedelta(days=today.weekday())

        MemberSchedule.set_weekly_schedule(member.id, [
            {"day": 0, "start": time(9, 0), "end": time(17, 0)},
        ])

        result = MemberSchedule.get_bulk_effective(
            [member.id], monday,
            org_id=ws["organization"].id,
            ws_id=ws["workspace"].id,
        )

        assert member.id in result
        assert result[member.id] == (time(9, 0), time(17, 0))


# ===========================================================================
# ClockPunchAdjustment
# ===========================================================================


@pytest.mark.integration
class TestClockPunchAdjustment:
    """Tests for ClockPunchAdjustment model."""

    def test_record_adjustment(self, app, db_session, seeded_workspace):
        """Test recording a clock punch adjustment."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.clock_punch_adjustment import ClockPunchAdjustment

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        original_time = punch.punch_time
        new_time = original_time - timedelta(minutes=15)

        adjustment = ClockPunchAdjustment.record(
            clock_punch_id=punch.id,
            adjusted_by_id=org_member.id,
            original_punch_time=original_time,
            new_punch_time=new_time,
            reason="Member reported late clock-in",
        )

        assert adjustment.id is not None
        assert adjustment.clock_punch_id == punch.id
        assert adjustment.original_punch_time == original_time
        assert adjustment.new_punch_time == new_time
        assert adjustment.reason == "Member reported late clock-in"
        assert adjustment.created_at is not None

    def test_record_adjustment_without_reason(self, app, db_session, seeded_workspace):
        """Test recording an adjustment without a reason."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.clock_punch_adjustment import ClockPunchAdjustment

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        adjustment = ClockPunchAdjustment.record(
            clock_punch_id=punch.id,
            adjusted_by_id=org_member.id,
            original_punch_time=punch.punch_time,
            new_punch_time=punch.punch_time + timedelta(minutes=5),
        )

        assert adjustment.id is not None
        assert adjustment.reason is None


# ===========================================================================
# PunchCorrectionRequest
# ===========================================================================


@pytest.mark.integration
class TestPunchCorrectionRequest:
    """Tests for PunchCorrectionRequest model."""

    def test_create_correction_request(self, app, db_session, seeded_workspace):
        """Test creating a punch correction request."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import (
            PunchCorrectionRequest, PunchCorrectionRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")
        requested_time = punch.punch_time - timedelta(minutes=30)

        req = PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=requested_time,
            reason="Forgot to clock in on time",
        )

        assert req.id is not None
        assert req.status == PunchCorrectionRequestStatus.PENDING
        assert req.is_pending is True
        assert req.original_time == punch.punch_time
        assert req.requested_time == requested_time
        assert req.reason == "Forgot to clock in on time"

    def test_duplicate_pending_raises(self, app, db_session, seeded_workspace):
        """Test creating a duplicate pending request raises ValueError."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=10),
        )

        with pytest.raises(ValueError, match="pending correction request already exists"):
            PunchCorrectionRequest.create(
                clock_punch_id=punch.id,
                member_id=org_member.id,
                requested_time=punch.punch_time - timedelta(minutes=20),
            )

    def test_deny_request(self, app, db_session, seeded_workspace):
        """Test denying a correction request."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import (
            PunchCorrectionRequest, PunchCorrectionRequestStatus,
        )

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        req = PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=10),
        )

        req.deny(user_id=org_member.id)
        assert req.status == PunchCorrectionRequestStatus.DENIED
        assert req.is_pending is False
        assert req.reviewed_at is not None

    def test_deny_non_pending_raises(self, app, db_session, seeded_workspace):
        """Test denying a non-pending request raises ValueError."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        req = PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=10),
        )
        req.deny(user_id=org_member.id)

        with pytest.raises(ValueError, match="Only pending requests can be denied"):
            req.deny(user_id=org_member.id)

    def test_pending_count(self, app, db_session, seeded_workspace):
        """Test pending_count returns correct number."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=5),
        )

        assert PunchCorrectionRequest.pending_count() >= 1

    def test_get_pending_for_punch(self, app, db_session, seeded_workspace):
        """Test get_pending_for_punch returns the pending request."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=5),
        )

        found = PunchCorrectionRequest.get_pending_for_punch(punch.id)
        assert found is not None
        assert found.clock_punch_id == punch.id

    def test_get_pending_map_for_punches(self, app, db_session, seeded_workspace):
        """Test get_pending_map_for_punches returns correct mapping."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=5),
        )

        mapping = PunchCorrectionRequest.get_pending_map_for_punches([punch.id])
        assert punch.id in mapping

    def test_status_badge_class(self, app, db_session, seeded_workspace):
        """Test status_badge_class returns correct Bootstrap classes."""
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

        ws = seeded_workspace
        _set_context(ws)
        org_member = _get_org_member(ws)

        punch = ClockPunch.clock_in(member_id=org_member.id, source="web")

        req = PunchCorrectionRequest.create(
            clock_punch_id=punch.id,
            member_id=org_member.id,
            requested_time=punch.punch_time - timedelta(minutes=5),
        )

        assert "warning" in req.status_badge_class


# ===========================================================================
# PresenceSignal
# ===========================================================================


@pytest.mark.integration
class TestPresenceSignal:
    """Tests for PresenceSignal model."""

    def _make_template(self, ws):
        """Create an UpdateTemplate for signal tests."""
        from modules.base.updates.models.template import UpdateTemplate

        template = UpdateTemplate(
            workspace_id=ws["workspace"].id,
            post_type="presence",
            name="Focus Status",
            _fields=[],
        )
        db.session.add(template)
        db.session.commit()
        return template

    def test_record_signal(self, app, db_session, seeded_workspace):
        """Test recording a presence signal."""
        from modules.base.presence.models.presence_signal import PresenceSignal

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        template = self._make_template(ws)

        signal = PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="focus",
        )

        assert signal.id is not None
        assert signal.value == "focus"
        assert signal.workspace_id == ws["workspace"].id
        assert signal.ended_at is None

    def test_record_closes_previous_open_signal(self, app, db_session, seeded_workspace):
        """Test that recording a new signal closes the previous open one."""
        from modules.base.presence.models.presence_signal import PresenceSignal

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        template = self._make_template(ws)

        signal1 = PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="focus",
        )

        signal2 = PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="available",
        )

        db.session.refresh(signal1)
        assert signal1.ended_at is not None
        assert signal2.ended_at is None

    def test_get_current(self, app, db_session, seeded_workspace):
        """Test get_current returns the latest signal."""
        from modules.base.presence.models.presence_signal import PresenceSignal

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        template = self._make_template(ws)

        PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="focus",
        )
        PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="available",
        )

        current = PresenceSignal.get_current(member.id, template.id)
        assert current is not None
        assert current.value == "available"

    def test_get_current_none(self, app, db_session, seeded_workspace):
        """Test get_current returns None when no signals exist."""
        from modules.base.presence.models.presence_signal import PresenceSignal

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        template = self._make_template(ws)

        result = PresenceSignal.get_current(member.id, template.id)
        assert result is None

    def test_get_team_current(self, app, db_session, seeded_workspace):
        """Test get_team_current returns a dict of member signals."""
        from modules.base.presence.models.presence_signal import PresenceSignal

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        template = self._make_template(ws)

        PresenceSignal.record(
            member_id=member.id,
            template_id=template.id,
            value="deep_work",
        )

        team = PresenceSignal.get_team_current(template.id)
        assert member.id in team
        assert team[member.id].value == "deep_work"


# ===========================================================================
# PresenceForecast
# ===========================================================================


@pytest.mark.integration
class TestPresenceForecast:
    """Tests for PresenceForecast model."""

    def test_set_forecast(self, app, db_session, seeded_workspace):
        """Test setting a forecast for a date."""
        from modules.base.presence.models.presence_forecast import PresenceForecast

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        forecast = PresenceForecast.set_forecast(
            member_id=member.id,
            forecast_date=date(2025, 7, 1),
            status="in",
            available_from=time(9, 0),
            available_until=time(17, 0),
            note="Office day",
        )

        assert forecast.id is not None
        assert forecast.status == "in"
        assert forecast.available_from == time(9, 0)
        assert forecast.note == "Office day"

    def test_set_forecast_upsert(self, app, db_session, seeded_workspace):
        """Test that set_forecast updates existing forecast."""
        from modules.base.presence.models.presence_forecast import PresenceForecast

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        target = date(2025, 7, 2)

        PresenceForecast.set_forecast(
            member_id=member.id,
            forecast_date=target,
            status="in",
        )

        updated = PresenceForecast.set_forecast(
            member_id=member.id,
            forecast_date=target,
            status="remote",
            note="Changed to WFH",
        )

        assert updated.status == "remote"
        assert updated.note == "Changed to WFH"

        # Should still be just one record
        forecasts = PresenceForecast.get_for_member(member.id, target, target)
        assert len(forecasts) == 1

    def test_clear_forecast(self, app, db_session, seeded_workspace):
        """Test clearing a forecast."""
        from modules.base.presence.models.presence_forecast import PresenceForecast

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)
        target = date(2025, 7, 3)

        PresenceForecast.set_forecast(
            member_id=member.id,
            forecast_date=target,
            status="out",
        )

        PresenceForecast.clear_forecast(member.id, target)
        forecasts = PresenceForecast.get_for_member(member.id, target, target)
        assert len(forecasts) == 0

    def test_get_for_member_range(self, app, db_session, seeded_workspace):
        """Test get_for_member with a date range."""
        from modules.base.presence.models.presence_forecast import PresenceForecast

        ws = seeded_workspace
        _set_context(ws)
        member = _get_membership(ws)

        for i in range(5):
            PresenceForecast.set_forecast(
                member_id=member.id,
                forecast_date=date(2025, 8, 1 + i),
                status="in" if i % 2 == 0 else "remote",
            )

        forecasts = PresenceForecast.get_for_member(
            member.id,
            date(2025, 8, 1),
            date(2025, 8, 5),
        )
        assert len(forecasts) == 5
        # Ordered by date
        assert forecasts[0].forecast_date == date(2025, 8, 1)
        assert forecasts[4].forecast_date == date(2025, 8, 5)


# ===========================================================================
# TimeTrackingSettings
# ===========================================================================


@pytest.mark.integration
class TestTimeTrackingSettings:
    """Tests for TimeTrackingSettings model."""

    def test_get_creates_singleton(self, app, db_session, seeded_workspace):
        """Test get() creates settings if they do not exist."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.get()
        assert settings is not None
        assert settings.id is not None
        assert settings.time_clock_enabled is True
        assert settings.rounding_minutes == 15

    def test_get_returns_same_singleton(self, app, db_session, seeded_workspace):
        """Test get() returns the same settings object."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        s1 = TimeTrackingSettings.get()
        s2 = TimeTrackingSettings.get()
        assert s1.id == s2.id

    def test_update_settings(self, app, db_session, seeded_workspace):
        """Test update_settings changes values."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.update_settings(
            rounding_enabled=False,
            rounding_minutes=30,
            rounding_type="nearest",
        )

        assert settings.rounding_enabled is False
        assert settings.rounding_minutes == 30
        assert settings.rounding_type == "nearest"

    def test_update_settings_invalid_rounding_minutes(self, app, db_session, seeded_workspace):
        """Test update_settings rejects invalid rounding minutes."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        with pytest.raises(ValueError, match="Invalid rounding interval"):
            TimeTrackingSettings.update_settings(rounding_minutes=7)

    def test_update_settings_invalid_rounding_type(self, app, db_session, seeded_workspace):
        """Test update_settings rejects invalid rounding type."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        with pytest.raises(ValueError, match="Invalid rounding type"):
            TimeTrackingSettings.update_settings(rounding_type="invalid")

    def test_update_settings_invalid_auto_close_hours(self, app, db_session, seeded_workspace):
        """Test update_settings rejects invalid auto-close hours."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        with pytest.raises(ValueError, match="must be between 1 and 24"):
            TimeTrackingSettings.update_settings(auto_close_after_hours=0)

        with pytest.raises(ValueError, match="must be between 1 and 24"):
            TimeTrackingSettings.update_settings(auto_close_after_hours=25)

    def test_feature_checks(self, app, db_session, seeded_workspace):
        """Test feature check class methods."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        assert TimeTrackingSettings.is_time_clock_enabled() is True
        assert TimeTrackingSettings.is_board_enabled() is True

    def test_geofence_disabled_by_default(self, app, db_session, seeded_workspace):
        """Test geofence is disabled by default."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        assert TimeTrackingSettings.is_geofence_enabled() is False
        assert TimeTrackingSettings.get_geofence_coords() is None

    def test_geofence_check_disabled(self, app, db_session, seeded_workspace):
        """Test check_geofence returns (False, False) when disabled."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        blocked, outside = TimeTrackingSettings.check_geofence(30.0, -97.0)
        assert blocked is False
        assert outside is False

    def test_geofence_within(self, app, db_session, seeded_workspace):
        """Test geofence check when within radius."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.get()
        settings.geofence_enabled = True
        settings.geofence_latitude = 30.2672
        settings.geofence_longitude = -97.7431
        settings.geofence_radius_meters = 500
        settings.geofence_enforcement = "hard"
        db.session.commit()

        # Same coordinates -> within
        result = TimeTrackingSettings.is_within_geofence(30.2672, -97.7431)
        assert result is True

        blocked, outside = TimeTrackingSettings.check_geofence(30.2672, -97.7431)
        assert blocked is False
        assert outside is False

    def test_geofence_outside_hard_enforcement(self, app, db_session, seeded_workspace):
        """Test geofence hard enforcement blocks punches outside radius."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.get()
        settings.geofence_enabled = True
        settings.geofence_latitude = 30.2672
        settings.geofence_longitude = -97.7431
        settings.geofence_radius_meters = 100
        settings.geofence_enforcement = "hard"
        db.session.commit()

        # Far away coordinates
        blocked, outside = TimeTrackingSettings.check_geofence(40.0, -74.0)
        assert blocked is True
        assert outside is True

    def test_geofence_outside_soft_enforcement(self, app, db_session, seeded_workspace):
        """Test geofence soft enforcement does not block but flags."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.get()
        settings.geofence_enabled = True
        settings.geofence_latitude = 30.2672
        settings.geofence_longitude = -97.7431
        settings.geofence_radius_meters = 100
        settings.geofence_enforcement = "soft"
        db.session.commit()

        blocked, outside = TimeTrackingSettings.check_geofence(40.0, -74.0)
        assert blocked is False
        assert outside is True

    def test_public_board_token(self, app, db_session, seeded_workspace):
        """Test get_or_create_public_token and validate_public_token."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        token = TimeTrackingSettings.get_or_create_public_token()
        assert token is not None
        assert len(token) > 10

        assert TimeTrackingSettings.validate_public_token(token) is True
        assert TimeTrackingSettings.validate_public_token("wrong") is False

    def test_haversine_distance(self, app, db_session, seeded_workspace):
        """Test haversine distance calculation."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        # Same point should be 0
        dist = TimeTrackingSettings._haversine_distance(30.0, -97.0, 30.0, -97.0)
        assert dist == pytest.approx(0.0, abs=0.1)

        # Austin to NYC approx 2440 km
        dist = TimeTrackingSettings._haversine_distance(30.2672, -97.7431, 40.7128, -74.0060)
        assert 2400000 < dist < 2500000  # meters

    def test_update_geofence(self, app, db_session, seeded_workspace):
        """Test update_geofence method."""
        from modules.base.presence.models.settings import TimeTrackingSettings

        ws = seeded_workspace
        _set_context(ws)

        settings = TimeTrackingSettings.get()
        settings.update_geofence(
            enabled=True,
            enforcement="hard",
            use_company_address=False,
            radius_meters=200,
            address="123 Main St",
            city="Austin",
            state="TX",
            zip_code="78701",
            latitude=30.27,
            longitude=-97.74,
        )

        assert settings.geofence_enabled is True
        assert settings.geofence_enforcement == "hard"
        assert settings.geofence_radius_meters == 200
        assert settings.geofence_address == "123 Main St"
        assert settings.geofence_latitude == 30.27
