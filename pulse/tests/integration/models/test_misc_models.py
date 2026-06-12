# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Misc Model Integration Tests
#
# Tests for IntegrationConnection, IntegrationRef, ActivityLog,
# and AIPendingAction models.
# -----------------------------------------------------------------------------

from datetime import datetime, timedelta

import pytest
from flask import g

from system.db.database import db


def _setup_g(ws):
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _make_task(ws):
    from modules.base.tasks.models.task import Task

    task = Task(
        title="Misc test task",
        raised_by_id=ws["membership"].id,
        assignee_id=ws["membership"].id,
    )
    db.session.add(task)
    db.session.commit()
    return task


# ═════════════════════════════════════════════════════════════════════════════
# IntegrationConnection
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestIntegrationConnection:
    """Tests for IntegrationConnection lifecycle and token management."""

    def test_get_or_create(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        assert conn.id is not None
        assert conn.provider == "github"
        assert conn.status == "disconnected"

        conn2 = IntegrationConnection.get_or_create("github")
        assert conn2.id == conn.id

    def test_finalize_connection(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        conn.finalize_connection(
            installation_id="12345",
            repo="acme/my-repo",
            member_id=ws["membership"].id,
        )
        assert conn.status == "connected"
        assert conn.installation_id == "12345"
        assert conn.external_repo == "acme/my-repo"

    def test_get_active(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        assert IntegrationConnection.get_active("github") is None

        conn.finalize_connection(
            installation_id="999",
            repo="acme/repo",
            member_id=ws["membership"].id,
        )
        active = IntegrationConnection.get_active("github")
        assert active is not None
        assert active.id == conn.id

    def test_mark_error(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        conn.mark_error("Token expired")
        assert conn.status == "error"
        assert conn.error_message == "Token expired"

    def test_is_token_expired(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        assert conn.is_token_expired() is True

        from datetime import timezone
        conn.token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()
        assert conn.is_token_expired() is False

    def test_get_by_installation_id(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_connection import IntegrationConnection

        ws = seeded_workspace
        _setup_g(ws)

        conn = IntegrationConnection.get_or_create("github")
        conn.finalize_connection(
            installation_id="77777",
            repo="acme/repo",
            member_id=ws["membership"].id,
        )
        found = IntegrationConnection.get_by_installation_id("77777")
        assert found is not None
        assert found.id == conn.id


# ═════════════════════════════════════════════════════════════════════════════
# IntegrationRef
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestIntegrationRef:
    """Tests for IntegrationRef external ID mapping and caching."""

    def test_get_or_create(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        ref = IntegrationRef.get_or_create(
            provider="github",
            external_id="42",
            external_repo="acme/repo",
            object_type="task",
            object_id=1,
        )
        assert ref.id is not None
        assert ref.external_id == "42"

        ref2 = IntegrationRef.get_or_create(
            provider="github",
            external_id="42",
            external_repo="acme/repo",
            object_type="task",
            object_id=1,
        )
        assert ref2.id == ref.id

    def test_get_for_object(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        IntegrationRef.get_or_create(
            provider="github",
            external_id="100",
            external_repo="acme/repo",
            object_type="task",
            object_id=task.id,
        )
        refs = IntegrationRef.get_for_object("task", task.id)
        assert len(refs) == 1
        assert refs[0].external_id == "100"

    def test_update_cached_state(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        ref = IntegrationRef.get_or_create(
            provider="github",
            external_id="200",
            external_repo="acme/repo",
            object_type="task",
            object_id=1,
        )
        ref.update_cached_state({"title": "Fix bug", "state": "open"})
        assert ref.cached_state["title"] == "Fix bug"
        assert ref.cached_at is not None

    def test_link_task(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        ref = IntegrationRef.get_or_create(
            provider="github",
            external_id="300",
            external_repo="acme/repo",
            object_type="task",
            object_id=task.id,
        )
        ref.link_task(task.id)
        assert ref.linked_task_id == task.id

    def test_get_all_external_ids(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        IntegrationRef.get_or_create(
            provider="github", external_id="10", external_repo="acme/repo",
            object_type="task", object_id=1,
        )
        IntegrationRef.get_or_create(
            provider="github", external_id="20", external_repo="acme/repo",
            object_type="task", object_id=2,
        )
        ids = IntegrationRef.get_all_external_ids("github")
        assert "10" in ids
        assert "20" in ids

    def test_get_by_external(self, app, db_session, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef

        ws = seeded_workspace
        _setup_g(ws)

        ref = IntegrationRef.get_or_create(
            provider="github", external_id="50", external_repo="acme/repo",
            object_type="task", object_id=1,
        )
        found = IntegrationRef.get_by_external("github", "50", ws["workspace"].id)
        assert len(found) == 1
        assert found[0].id == ref.id


# ═════════════════════════════════════════════════════════════════════════════
# ActivityLog
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestActivityLog:
    """Tests for ActivityLog recording and retrieval."""

    def test_log_activity(self, app, db_session, seeded_workspace):
        from modules.base.dashboard.models.activity_log import ActivityLog

        ws = seeded_workspace
        _setup_g(ws)

        activity = ActivityLog.log(
            action="test.created",
            model_type="Test",
            title="Test Activity",
            description="Something happened",
            member_id=ws["membership"].id,
            icon="fa-check",
            color="success",
        )
        assert activity.id is not None
        assert activity.action == "test.created"

    def test_get_recent(self, app, db_session, seeded_workspace):
        from modules.base.dashboard.models.activity_log import ActivityLog

        ws = seeded_workspace
        _setup_g(ws)

        ActivityLog.log(
            action="test.a",
            model_type="Test",
            title="A",
            description="Activity A",
        )
        ActivityLog.log(
            action="test.b",
            model_type="Test",
            title="B",
            description="Activity B",
        )

        recent = ActivityLog.get_recent(limit=10)
        assert len(recent) >= 2

    def test_time_ago_property(self, app, db_session, seeded_workspace):
        from modules.base.dashboard.models.activity_log import ActivityLog

        ws = seeded_workspace
        _setup_g(ws)

        activity = ActivityLog.log(
            action="test.now",
            model_type="Test",
            title="Now",
            description="Just happened",
        )
        assert activity.time_ago in ("just now", "0m ago", "1m ago")

    def test_get_today_count(self, app, db_session, seeded_workspace):
        from modules.base.dashboard.models.activity_log import ActivityLog

        ws = seeded_workspace
        _setup_g(ws)

        ActivityLog.log(
            action="test.count",
            model_type="Test",
            title="Count",
            description="Countable",
        )
        count = ActivityLog.get_today_count()
        assert count >= 1


# ═════════════════════════════════════════════════════════════════════════════
# AIPendingAction
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestAIPendingAction:
    """Tests for AIPendingAction state machine and CRUD."""

    def test_create_pending_action(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction, ActionStatus

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="create_task",
            args_json={"title": "Buy groceries", "assignee": "me"},
        )
        assert action.id is not None
        assert action.status == ActionStatus.PROPOSED
        assert action.tool_name == "create_task"

    def test_confirm_action(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction, ActionStatus

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="create_contact",
            args_json={"name": "Test"},
        )
        action.confirm()
        assert action.status == ActionStatus.CONFIRMED

    def test_cancel_action(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction, ActionStatus

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="create_contact",
            args_json={"name": "Cancel"},
        )
        action.cancel()
        assert action.status == ActionStatus.CANCELLED

    def test_mark_executed(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction, ActionStatus

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="create_task",
            args_json={"title": "Done"},
        )
        action.confirm()
        action.mark_executed(result={"task_id": 42})
        assert action.status == ActionStatus.EXECUTED
        assert action.result_json == {"task_id": 42}

    def test_mark_failed(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction, ActionStatus

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="broken_tool",
            args_json={},
        )
        action.mark_failed("Something went wrong")
        assert action.status == ActionStatus.FAILED
        assert action.error == "Something went wrong"

    def test_update_args(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="create_task",
            args_json={"title": "Draft"},
        )
        action.update_args({"title": "Final"})
        assert action.args_json["title"] == "Final"

    def test_get_pending_for_user(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction

        ws = seeded_workspace
        _setup_g(ws)

        AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="tool_a",
            args_json={},
        )
        AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="tool_b",
            args_json={},
        )

        pending = AIPendingAction.get_pending_for_user(ws["user"].id)
        assert len(pending) >= 2

    def test_get_by_id(self, app, db_session, seeded_workspace):
        from modules.base.ai.models.pending_action import AIPendingAction

        ws = seeded_workspace
        _setup_g(ws)

        action = AIPendingAction.create(
            channel_id=None,
            trigger_chat_id=None,
            created_by_id=ws["user"].id,
            tool_name="find_me",
            args_json={},
        )
        found = AIPendingAction.get_by_id(action.id)
        assert found is not None
        assert found.tool_name == "find_me"
