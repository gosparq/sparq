# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - TimeEntry Model Integration Tests
#
# Tests for TimeEntry model CRUD operations, validation, approval workflow,
# and timer functionality.
# -----------------------------------------------------------------------------

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from flask import g


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_scope(ws):
    """Set g.organization_id and g.workspace_id from a seeded_workspace dict."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _org_user(ws):
    """Return the OrganizationUser for the seeded workspace member."""
    from modules.base.core.models.organization_user import OrganizationUser

    return OrganizationUser.get_for_user(ws["user"].id, ws["organization"].id)


def _create_entry(org_user, **overrides):
    """Shortcut to create a TimeEntry with sensible defaults."""
    from modules.base.presence.models.time_entry import TimeEntry

    defaults = dict(
        member_id=org_user.id,
        date=date.today(),
        hours=4.0,
        description="Test work",
        is_billable=False,
    )
    defaults.update(overrides)
    return TimeEntry.create(**defaults)


# ===================================================================
# TimeEntry.create
# ===================================================================


@pytest.mark.integration
class TestTimeEntryCreate:
    """Tests for TimeEntry.create()."""

    def test_create_basic(self, app, db_session, seeded_workspace):
        """Create a time entry with required fields."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou)

        assert entry.id is not None
        assert float(entry.hours) == 4.0
        assert entry.description == "Test work"
        assert entry.is_billable is False
        assert entry.member_id == ou.id

    def test_create_billable(self, app, db_session, seeded_workspace):
        """Create a billable time entry."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou, is_billable=True)

        assert entry.is_billable is True

    def test_create_with_category(self, app, db_session, seeded_workspace):
        """Create a time entry with a category."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou, category="Admin")

        assert entry.category == "Admin"

    def test_create_with_timer_range(self, app, db_session, seeded_workspace):
        """Create a time entry with timer_start and timer_end."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        start = datetime(2026, 6, 4, 9, 0, 0)
        end = datetime(2026, 6, 4, 13, 0, 0)
        entry = _create_entry(ou, timer_start=start, timer_end=end)

        assert entry.timer_start == start
        assert entry.timer_end == end

    def test_auto_populates_rates(self, app, db_session, seeded_workspace):
        """Rates are auto-populated from the OrganizationUser."""
        from system.db.database import db as _db

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        # Set known rates on the org user
        ou.labor_cost_rate = Decimal("25.00")
        ou.bill_rate = Decimal("75.00")
        _db.session.commit()

        entry = _create_entry(ou, hours=2.0, is_billable=True)

        assert entry.labor_cost_rate == Decimal("25.00")
        assert entry.bill_rate == Decimal("75.00")
        assert entry.labor_cost == Decimal("50.00")  # 2 * 25
        assert entry.billing_amount == Decimal("150.00")  # 2 * 75

    def test_non_billable_billing_amount_zero(self, app, db_session, seeded_workspace):
        """Non-billable entries have billing_amount of zero."""
        from system.db.database import db as _db

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        ou.bill_rate = Decimal("100.00")
        _db.session.commit()

        entry = _create_entry(ou, hours=1.0, is_billable=False)

        assert entry.billing_amount == Decimal("0.00")

    def test_default_status_submitted(self, app, db_session, seeded_workspace):
        """New entries default to SUBMITTED status."""
        from modules.base.presence.models.time_entry import TimeEntryStatus

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou)

        assert entry.status == TimeEntryStatus.SUBMITTED

    def test_submitted_at_set(self, app, db_session, seeded_workspace):
        """submitted_at is auto-populated on creation."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou)

        assert entry.submitted_at is not None

    def test_create_invalid_member_raises(self, app, db_session, seeded_workspace):
        """Creating with an invalid member_id raises ValueError."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)

        with pytest.raises(ValueError, match="not found"):
            TimeEntry.create(
                member_id=999999,
                date=date.today(),
                hours=1.0,
            )


# ===================================================================
# Validation
# ===================================================================


@pytest.mark.integration
class TestTimeEntryValidation:
    """Tests for TimeEntry validation logic."""

    def test_hours_zero_raises(self, app, db_session, seeded_workspace):
        """Hours of 0 raises ValueError."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        with pytest.raises(ValueError, match="Hours must be between"):
            _create_entry(ou, hours=0)

    def test_hours_negative_raises(self, app, db_session, seeded_workspace):
        """Negative hours raises ValueError."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        with pytest.raises(ValueError, match="Hours must be between"):
            _create_entry(ou, hours=-1.0)

    def test_hours_over_24_raises(self, app, db_session, seeded_workspace):
        """Hours over 24 raises ValueError."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        with pytest.raises(ValueError, match="Hours must be between"):
            _create_entry(ou, hours=25.0)

    def test_daily_total_exceeds_24_raises(self, app, db_session, seeded_workspace):
        """Adding hours that push daily total over 24 raises ValueError."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        _create_entry(ou, hours=20.0)

        with pytest.raises(ValueError, match="Daily hours cannot exceed 24"):
            _create_entry(ou, hours=5.0)

    def test_time_overlap_raises(self, app, db_session, seeded_workspace):
        """Overlapping timer ranges raise ValueError."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        start1 = datetime(2026, 6, 4, 9, 0, 0)
        end1 = datetime(2026, 6, 4, 12, 0, 0)
        _create_entry(ou, hours=3.0, timer_start=start1, timer_end=end1)

        start2 = datetime(2026, 6, 4, 11, 0, 0)
        end2 = datetime(2026, 6, 4, 14, 0, 0)
        with pytest.raises(ValueError, match="overlaps"):
            _create_entry(ou, hours=3.0, timer_start=start2, timer_end=end2)

    def test_non_overlapping_ranges_ok(self, app, db_session, seeded_workspace):
        """Non-overlapping timer ranges are accepted."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        start1 = datetime(2026, 6, 4, 9, 0, 0)
        end1 = datetime(2026, 6, 4, 12, 0, 0)
        _create_entry(ou, hours=3.0, timer_start=start1, timer_end=end1)

        start2 = datetime(2026, 6, 4, 13, 0, 0)
        end2 = datetime(2026, 6, 4, 15, 0, 0)
        entry2 = _create_entry(ou, hours=2.0, timer_start=start2, timer_end=end2)

        assert entry2.id is not None


# ===================================================================
# Approval workflow
# ===================================================================


@pytest.mark.integration
class TestTimeEntryApproval:
    """Tests for TimeEntry approval/rejection/invoicing workflow."""

    def test_approve(self, app, db_session, seeded_workspace):
        """Approve a submitted entry."""
        from modules.base.presence.models.time_entry import TimeEntryStatus

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)

        entry.approve(approved_by_id=ou.id)

        assert entry.status == TimeEntryStatus.APPROVED
        assert entry.approved_at is not None
        assert entry.approved_by_id == ou.id

    def test_approve_non_submitted_raises(self, app, db_session, seeded_workspace):
        """Cannot approve an entry that is not in SUBMITTED status."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.approve(approved_by_id=ou.id)

        with pytest.raises(ValueError, match="Only submitted"):
            entry.approve(approved_by_id=ou.id)

    def test_reject(self, app, db_session, seeded_workspace):
        """Reject a submitted entry with a reason."""
        from modules.base.presence.models.time_entry import TimeEntryStatus

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)

        entry.reject(reason="Incorrect hours", rejected_by_id=ou.id)

        assert entry.status == TimeEntryStatus.REJECTED
        assert entry.rejected_reason == "Incorrect hours"

    def test_reject_non_submitted_raises(self, app, db_session, seeded_workspace):
        """Cannot reject an entry that is not in SUBMITTED status."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.approve(approved_by_id=ou.id)

        with pytest.raises(ValueError, match="Only submitted"):
            entry.reject(reason="Too late", rejected_by_id=ou.id)

    def test_mark_invoiced(self, app, db_session, seeded_workspace):
        """Mark an approved billable entry as invoiced."""
        from modules.base.presence.models.time_entry import TimeEntryStatus

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou, is_billable=True)
        entry.approve(approved_by_id=ou.id)

        entry.mark_invoiced(invoice_id=42)

        assert entry.status == TimeEntryStatus.INVOICED
        assert entry.invoice_id == 42

    def test_mark_invoiced_not_approved_raises(self, app, db_session, seeded_workspace):
        """Cannot invoice a non-approved entry."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou, is_billable=True)

        with pytest.raises(ValueError, match="Only approved"):
            entry.mark_invoiced(invoice_id=42)

    def test_mark_invoiced_non_billable_raises(self, app, db_session, seeded_workspace):
        """Cannot invoice a non-billable entry."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou, is_billable=False)
        entry.approve(approved_by_id=ou.id)

        with pytest.raises(ValueError, match="Only billable"):
            entry.mark_invoiced(invoice_id=42)

    def test_approve_all_for_member(self, app, db_session, seeded_workspace):
        """approve_all_for_member approves all submitted entries."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        _create_entry(ou, hours=2.0, date=date.today())
        _create_entry(ou, hours=3.0, date=date.today() - timedelta(days=1))

        count = TimeEntry.approve_all_for_member(ou.id, approved_by_id=ou.id)

        assert count == 2

    def test_approve_all_no_entries_raises(self, app, db_session, seeded_workspace):
        """approve_all_for_member raises when no pending entries exist."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        with pytest.raises(ValueError, match="No pending entries"):
            TimeEntry.approve_all_for_member(ou.id, approved_by_id=ou.id)


# ===================================================================
# Timer
# ===================================================================


@pytest.mark.integration
class TestTimeEntryTimer:
    """Tests for TimeEntry timer functionality."""

    def test_timer_duration_with_start_and_end(self, app, db_session, seeded_workspace):
        """timer_duration calculates hours between start and end."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        start = datetime(2026, 6, 4, 9, 0, 0)
        end = datetime(2026, 6, 4, 11, 30, 0)
        entry = _create_entry(ou, hours=2.5, timer_start=start, timer_end=end)

        assert entry.timer_duration == 2.5

    def test_is_timer_running(self, app, db_session, seeded_workspace):
        """is_timer_running is True when timer_start set and timer_end is None."""
        from system.db.database import db as _db

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou, hours=0.01)

        # Manually set timer state (bypassing start_timer to avoid extra commits)
        entry.timer_start = datetime.utcnow()
        entry.timer_end = None
        _db.session.commit()

        assert entry.is_timer_running is True

    def test_is_timer_not_running(self, app, db_session, seeded_workspace):
        """is_timer_running is False when both start and end are set."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        start = datetime(2026, 6, 4, 9, 0, 0)
        end = datetime(2026, 6, 4, 10, 0, 0)
        entry = _create_entry(ou, hours=1.0, timer_start=start, timer_end=end)

        assert entry.is_timer_running is False

    def test_timer_duration_no_start(self, app, db_session, seeded_workspace):
        """timer_duration returns 0 when timer_start is None."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)

        entry = _create_entry(ou)

        assert entry.timer_duration == 0


# ===================================================================
# Delete
# ===================================================================


@pytest.mark.integration
class TestTimeEntryDelete:
    """Tests for TimeEntry.delete()."""

    def test_delete_submitted_entry(self, app, db_session, seeded_workspace):
        """Can delete a submitted entry."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry_id = entry.id

        entry.delete()

        assert TimeEntry.query.get(entry_id) is None

    def test_delete_approved_raises(self, app, db_session, seeded_workspace):
        """Cannot delete an approved entry."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.approve(approved_by_id=ou.id)

        with pytest.raises(ValueError, match="Approved or invoiced"):
            entry.delete()

    def test_delete_rejected_entry(self, app, db_session, seeded_workspace):
        """Can delete a rejected entry."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.reject(reason="Wrong", rejected_by_id=ou.id)
        entry_id = entry.id

        entry.delete()

        assert TimeEntry.query.get(entry_id) is None


# ===================================================================
# Queries
# ===================================================================


@pytest.mark.integration
class TestTimeEntryQueries:
    """Tests for TimeEntry query methods."""

    def test_get_by_member(self, app, db_session, seeded_workspace):
        """get_by_member returns entries for the member."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        _create_entry(ou, hours=2.0)
        _create_entry(ou, hours=3.0)

        result = TimeEntry.get_by_member(ou.id)

        assert len(result) == 2

    def test_get_by_member_date_range(self, app, db_session, seeded_workspace):
        """get_by_member with date range filters correctly."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        today = date.today()
        yesterday = today - timedelta(days=1)
        _create_entry(ou, hours=2.0, date=today)
        _create_entry(ou, hours=3.0, date=yesterday)

        result = TimeEntry.get_by_member(ou.id, start_date=today, end_date=today)

        assert len(result) == 1
        assert float(result[0].hours) == 2.0

    def test_get_total_hours_for_date(self, app, db_session, seeded_workspace):
        """get_total_hours_for_date sums hours for the date."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        today = date.today()
        _create_entry(ou, hours=3.0, date=today)
        _create_entry(ou, hours=2.5, date=today)

        total = TimeEntry.get_total_hours_for_date(ou.id, today)

        assert total == 5.5

    def test_submitted_count(self, app, db_session, seeded_workspace):
        """submitted_count returns number of submitted entries."""
        from modules.base.presence.models.time_entry import TimeEntry

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        _create_entry(ou, hours=1.0)
        _create_entry(ou, hours=2.0)

        count = TimeEntry.submitted_count()

        assert count == 2


# ===================================================================
# Update fields and recalculate
# ===================================================================


@pytest.mark.integration
class TestTimeEntryUpdate:
    """Tests for TimeEntry.update_fields() and recalculate_costs()."""

    def test_update_fields(self, app, db_session, seeded_workspace):
        """update_fields changes editable fields."""
        from modules.base.presence.models.time_entry import TimeEntry
        from sqlalchemy.orm import joinedload

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou, hours=2.0, description="Original")

        # Re-query with clock_punch eager-loaded to avoid raise_on_sql
        entry = TimeEntry.query.options(
            joinedload(TimeEntry.clock_punch),
        ).filter_by(id=entry.id).first()

        entry.update_fields(
            hours=4.0,
            category="Dev",
            job_id=None,
            description="Updated",
            is_billable=True,
        )

        assert float(entry.hours) == 4.0
        assert entry.description == "Updated"
        assert entry.category == "Dev"
        assert entry.is_billable is True

    def test_update_approved_raises(self, app, db_session, seeded_workspace):
        """Cannot update an approved entry."""
        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.approve(approved_by_id=ou.id)

        with pytest.raises(ValueError, match="Approved or invoiced"):
            entry.update_fields(
                hours=5.0, category=None, job_id=None,
                description="Nope", is_billable=False,
            )

    def test_update_rejected_resubmits(self, app, db_session, seeded_workspace):
        """Updating a rejected entry moves it back to SUBMITTED."""
        from modules.base.presence.models.time_entry import TimeEntry, TimeEntryStatus
        from sqlalchemy.orm import joinedload

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        entry = _create_entry(ou)
        entry.reject(reason="Wrong", rejected_by_id=ou.id)

        # Re-query with clock_punch eager-loaded to avoid raise_on_sql
        entry = TimeEntry.query.options(
            joinedload(TimeEntry.clock_punch),
        ).filter_by(id=entry.id).first()

        entry.update_fields(
            hours=3.0, category=None, job_id=None,
            description="Fixed", is_billable=False,
        )

        assert entry.status == TimeEntryStatus.SUBMITTED
        assert entry.rejected_reason is None

    def test_recalculate_costs(self, app, db_session, seeded_workspace):
        """recalculate_costs updates labor_cost and billing_amount."""
        from system.db.database import db as _db

        ws = seeded_workspace
        _set_scope(ws)
        ou = _org_user(ws)
        ou.labor_cost_rate = Decimal("30.00")
        ou.bill_rate = Decimal("90.00")
        _db.session.commit()

        entry = _create_entry(ou, hours=2.0, is_billable=True)

        # Manually change hours, then recalculate
        entry.hours = Decimal("5.0")
        entry.recalculate_costs()

        assert entry.labor_cost == Decimal("150.00")
        assert entry.billing_amount == Decimal("450.00")
