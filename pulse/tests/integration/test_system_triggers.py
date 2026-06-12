# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - System Triggers Integration Tests
#
# Tests for system/tasks/system_triggers.py — deduplication, task creation,
# and stale-item detection logic.
# -----------------------------------------------------------------------------

from unittest.mock import MagicMock, patch

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
# _has_open_item
# ===================================================================


@pytest.mark.integration
class TestHasOpenItem:
    """Tests for _has_open_item deduplication check."""

    def test_returns_false_when_no_items(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _has_open_item

        ws = seeded_workspace
        _set_scope(ws)

        assert _has_open_item("timesheet_overdue", 99999) is False

    def test_returns_true_when_open_item_exists(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _has_open_item

        ws = seeded_workspace
        _set_scope(ws)

        _create_task(
            ws["membership"],
            title="Timesheet",
            source_type="timesheet_overdue",
            source_id=12345,
        )

        assert _has_open_item("timesheet_overdue", 12345) is True

    def test_returns_false_for_different_source(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _has_open_item

        ws = seeded_workspace
        _set_scope(ws)

        _create_task(
            ws["membership"],
            title="Timesheet",
            source_type="timesheet_overdue",
            source_id=12345,
        )

        assert _has_open_item("timesheet_overdue", 99999) is False
        assert _has_open_item("onboarding_step", 12345) is False

    def test_returns_false_when_item_resolved(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _has_open_item

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(
            ws["membership"],
            title="Timesheet",
            source_type="timesheet_overdue",
            source_id=12345,
        )
        from modules.base.tasks.models.task import Task
        Task.resolve(task.id, ws["membership"].id)

        assert _has_open_item("timesheet_overdue", 12345) is False


# ===================================================================
# _create_system_item
# ===================================================================


@pytest.mark.integration
class TestCreateSystemItem:
    """Tests for _create_system_item task creation."""

    def test_creates_task_with_correct_metadata(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _create_system_item

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_system_item(
            title="Timesheet overdue",
            assignee_id=ws["membership"].id,
            urgency_tier=2,
            context_note="No entry for Jan 15",
            source_type="timesheet_overdue",
            source_id=55555,
        )

        assert task is not None
        assert task.title == "Timesheet overdue"
        assert task.urgency_tier == 2
        assert task.assignee_id == ws["membership"].id
        assert task.raised_by_id is None
        assert task.source_type == "timesheet_overdue"
        assert task.source_id == 55555
        assert task.context_note == "No entry for Jan 15"

    def test_does_not_duplicate_existing(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _create_system_item

        ws = seeded_workspace
        _set_scope(ws)

        first = _create_system_item(
            title="Timesheet overdue",
            assignee_id=ws["membership"].id,
            urgency_tier=2,
            context_note="No entry",
            source_type="timesheet_overdue",
            source_id=55555,
        )
        second = _create_system_item(
            title="Timesheet overdue again",
            assignee_id=ws["membership"].id,
            urgency_tier=2,
            context_note="Still no entry",
            source_type="timesheet_overdue",
            source_id=55555,
        )

        assert first is not None
        assert second is None

    def test_truncates_long_title(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _create_system_item

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_system_item(
            title="A" * 300,
            assignee_id=ws["membership"].id,
            urgency_tier=2,
            context_note=None,
            source_type="test_long",
            source_id=1,
        )

        assert task is not None
        assert len(task.title) == 200

    def test_truncates_long_context_note(self, app, db_session, seeded_workspace):
        from system.tasks.system_triggers import _create_system_item

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_system_item(
            title="Task",
            assignee_id=ws["membership"].id,
            urgency_tier=2,
            context_note="B" * 600,
            source_type="test_long_note",
            source_id=2,
        )

        assert task is not None
        assert len(task.context_note) == 500


# ===================================================================
# _check_stale_items
# ===================================================================


@pytest.mark.integration
class TestCheckStaleItems:
    """Tests for _check_stale_items detecting stale projects."""

    def test_detects_stale_project_and_moves_to_on_hold(
        self, app, db_session, seeded_workspace
    ):
        """When get_stale_upcoming returns a project, it is moved to On Hold."""
        from system.tasks.system_triggers import _check_stale_items

        ws = seeded_workspace
        _set_scope(ws)

        stale_project = MagicMock()

        with patch("modules.base.projects.models.project.Project") as MockProject, \
             patch("modules.base.tasks.models.task.Task") as MockTask, \
             patch("modules.base.core.models.workspace_settings.WorkspaceSettings") as MockWS:

            mock_settings = MagicMock()
            mock_settings.stale_days = 3
            MockWS.get_instance.return_value = mock_settings
            MockProject.get_stale_upcoming.return_value = [stale_project]
            MockProject.STATUS_ON_HOLD = "on_hold"
            MockTask.mark_stale_tasks.return_value = 0

            _check_stale_items(ws["workspace"])

        stale_project.set_status.assert_called_once_with("on_hold")

    def test_ignores_recent_project(self, app, db_session, seeded_workspace):
        """When get_stale_upcoming returns empty, nothing is moved."""
        from system.tasks.system_triggers import _check_stale_items

        ws = seeded_workspace
        _set_scope(ws)

        with patch("modules.base.projects.models.project.Project") as MockProject, \
             patch("modules.base.tasks.models.task.Task") as MockTask, \
             patch("modules.base.core.models.workspace_settings.WorkspaceSettings") as MockWS:

            mock_settings = MagicMock()
            mock_settings.stale_days = 3
            MockWS.get_instance.return_value = mock_settings
            MockProject.get_stale_upcoming.return_value = []
            MockTask.mark_stale_tasks.return_value = 0

            _check_stale_items(ws["workspace"])

        MockProject.get_stale_upcoming.assert_called_once()

    def test_does_not_crash_on_exception(self, app, db_session, seeded_workspace):
        """_check_stale_items catches exceptions gracefully."""
        from system.tasks.system_triggers import _check_stale_items

        ws = seeded_workspace
        _set_scope(ws)

        _check_stale_items(ws["workspace"])
