# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Sync Nudge Scheduler Integration Tests
#
# Tests for system/sync/nudge_scheduler.py — nudge scope checking and
# basic smoke test for the inner check loop.
# -----------------------------------------------------------------------------

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from flask import g


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_scope(ws):
    """Set g.organization_id and g.workspace_id from a seeded_workspace dict."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _make_template(nudge_scope=None):
    """Create a mock UpdateTemplate with a nudge_scope dict."""
    tpl = MagicMock()
    tpl.nudge_scope = nudge_scope
    return tpl


def _local_dt(year, month, day, hour, minute, weekday=None):
    """Build a timezone-aware datetime. weekday is ignored — use a real date."""
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ===================================================================
# _in_nudge_scope
# ===================================================================


@pytest.mark.integration
class TestInNudgeScope:
    """Tests for _in_nudge_scope time/day checking."""

    def test_no_scope_always_returns_true(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope=None)
            local_now = _local_dt(2026, 6, 9, 10, 0)  # Tuesday
            assert _in_nudge_scope(tpl, local_now) is True

    def test_within_schedule_returns_true(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            # 2026-06-09 is a Tuesday (weekday=1)
            local_now = _local_dt(2026, 6, 9, 10, 30)
            assert _in_nudge_scope(tpl, local_now) is True

    def test_outside_hours_returns_false(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            # 2026-06-09 is Tuesday, 19:00 is after end
            local_now = _local_dt(2026, 6, 9, 19, 0)
            assert _in_nudge_scope(tpl, local_now) is False

    def test_before_start_returns_false(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            # 2026-06-09 is Tuesday, 06:30 is before start
            local_now = _local_dt(2026, 6, 9, 6, 30)
            assert _in_nudge_scope(tpl, local_now) is False

    def test_weekend_returns_false(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            # 2026-06-13 is a Saturday (weekday=5)
            local_now = _local_dt(2026, 6, 13, 10, 0)
            assert _in_nudge_scope(tpl, local_now) is False

    def test_sunday_returns_false(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            # 2026-06-14 is a Sunday (weekday=6)
            local_now = _local_dt(2026, 6, 14, 10, 0)
            assert _in_nudge_scope(tpl, local_now) is False

    def test_custom_days_includes_saturday(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4, 5],
                "start": "09:00",
                "end": "13:00",
            })
            # 2026-06-13 is Saturday (weekday=5)
            local_now = _local_dt(2026, 6, 13, 10, 0)
            assert _in_nudge_scope(tpl, local_now) is True

    def test_at_exact_start_returns_true(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            local_now = _local_dt(2026, 6, 9, 8, 0)
            assert _in_nudge_scope(tpl, local_now) is True

    def test_at_exact_end_returns_false(self, app):
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "days": [0, 1, 2, 3, 4],
                "start": "08:00",
                "end": "18:00",
            })
            local_now = _local_dt(2026, 6, 9, 18, 0)
            assert _in_nudge_scope(tpl, local_now) is False

    def test_default_scope_days_when_missing(self, app):
        """When days key is absent, defaults to Mon-Fri (0-4)."""
        from system.sync.nudge_scheduler import _in_nudge_scope

        with app.app_context():
            tpl = _make_template(nudge_scope={
                "start": "08:00",
                "end": "18:00",
            })
            # Tuesday at 10am
            local_now = _local_dt(2026, 6, 9, 10, 0)
            assert _in_nudge_scope(tpl, local_now) is True


# ===================================================================
# _check_nudges_inner smoke test
# ===================================================================


@pytest.mark.integration
class TestCheckNudgesInner:
    """Smoke test for _check_nudges_inner with no active templates."""

    def test_runs_without_error_no_active_members(self, app, db_session, seeded_workspace):
        """The inner loop completes without error when workspace has no templates."""
        from system.sync.nudge_scheduler import _check_nudges_inner

        ws = seeded_workspace
        _set_scope(ws)

        _check_nudges_inner()
