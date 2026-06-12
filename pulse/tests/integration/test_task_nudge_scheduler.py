# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Task Nudge Scheduler Integration Tests
#
# Tests for system/tasks/nudge_scheduler.py — smoke test for the inner loop
# and notification creation via _send_nudge.
# -----------------------------------------------------------------------------

from unittest.mock import patch

import pytest
from flask import g


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_scope(ws):
    """Set g.organization_id and g.workspace_id from a seeded_workspace dict."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _create_task(member, title="Test task", urgency_tier=2, **kw):
    """Shortcut to create a task assigned to `member`."""
    from modules.base.tasks.models.task import Task

    return Task.create(
        title=title,
        urgency_tier=urgency_tier,
        assignee_id=member.id,
        raised_by_id=kw.pop("raised_by_id", None),
        **kw,
    )


# ===================================================================
# _check_nudges_inner smoke test
# ===================================================================


@pytest.mark.integration
class TestCheckNudgesInner:
    """Smoke tests for _check_nudges_inner with no open tasks."""

    def test_runs_without_error_no_tasks(self, app, db_session, seeded_workspace):
        """The inner loop completes without error when no open tasks exist."""
        from system.tasks.nudge_scheduler import _check_nudges_inner

        ws = seeded_workspace
        _set_scope(ws)

        _check_nudges_inner()

    def test_runs_without_error_with_resolved_task(self, app, db_session, seeded_workspace):
        """Resolved tasks are skipped by the nudge loop."""
        from system.tasks.nudge_scheduler import _check_nudges_inner

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], title="Already done")
        from modules.base.tasks.models.task import Task
        Task.resolve(task.id, ws["membership"].id)

        _check_nudges_inner()


# ===================================================================
# _send_nudge
# ===================================================================


@pytest.mark.integration
class TestSendNudge:
    """Tests for _send_nudge notification creation."""

    @patch("modules.base.core.services.push_notification.send_push")
    def test_send_nudge_creates_notification(self, mock_push, app, db_session, seeded_workspace):
        from modules.base.core.models.notification import SystemNotification
        from system.db.database import db
        from system.tasks.nudge_scheduler import _send_nudge

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], title="Urgent fix", urgency_tier=1)

        initial_count = SystemNotification.query.filter_by(
            user_id=ws["user"].id,
        ).count()
        push_count_before = mock_push.call_count

        _send_nudge(task, ws["user"].id)
        db.session.commit()

        after_count = SystemNotification.query.filter_by(
            user_id=ws["user"].id,
        ).count()
        assert after_count > initial_count
        assert mock_push.call_count == push_count_before + 1

    @patch("modules.base.core.services.push_notification.send_push")
    def test_send_nudge_logs_event(self, mock_push, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_log import TaskLog
        from system.db.database import db
        from system.tasks.nudge_scheduler import _send_nudge

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], title="Log test", urgency_tier=2)

        _send_nudge(task, ws["user"].id)
        db.session.commit()

        log = TaskLog.query.filter_by(
            task_id=task.id,
            event_type="nudge_sent",
        ).first()
        assert log is not None
        assert "Tier 2" in log.detail

    @patch("modules.base.core.services.push_notification.send_push")
    def test_send_nudge_includes_raiser_name(self, mock_push, app, db_session, seeded_workspace):
        from modules.base.core.models.notification import SystemNotification
        from system.db.database import db
        from system.tasks.nudge_scheduler import _send_nudge

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(
            ws["membership"],
            title="With raiser",
            urgency_tier=2,
            raised_by_id=ws["membership"].id,
        )

        _send_nudge(task, ws["user"].id)
        db.session.commit()

        notif = SystemNotification.query.filter_by(
            user_id=ws["user"].id,
        ).order_by(SystemNotification.id.desc()).first()
        assert notif is not None
        assert ws["user"].first_name in notif.message


# ===================================================================
# TIER_CADENCE constants
# ===================================================================


@pytest.mark.integration
class TestTierCadence:
    """Verify tier cadence constants are set correctly."""

    def test_tier_cadence_values(self, app):
        from system.tasks.nudge_scheduler import TIER_CADENCE, TIER_1_ESCALATION_HOURS

        with app.app_context():
            assert TIER_CADENCE[1] == 30
            assert TIER_CADENCE[2] == 240
            assert TIER_CADENCE[3] is None
            assert TIER_1_ESCALATION_HOURS == 2
