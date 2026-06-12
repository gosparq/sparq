# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Task Model Integration Tests
#
# Tests for Task model CRUD operations, state transitions, and queries.
# -----------------------------------------------------------------------------

from datetime import date, datetime, timedelta

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
        raised_by_id=kw.pop("raised_by_id", member.id),
        **kw,
    )


def _second_member(ws):
    """Create a second workspace member for multi-user tests."""
    import uuid

    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    user2 = User.create(
        email=f"second-{uuid.uuid4().hex[:8]}@test.com",
        password="testpass123",
        first_name="Second",
        last_name="Tester",
    )
    org_user2 = OrganizationUser.create(
        organization_id=ws["organization"].id,
        user_id=user2.id,
        role="member",
    )
    member2 = WorkspaceUser(
        user_id=user2.id,
        workspace_id=ws["workspace"].id,
        organization_id=ws["organization"].id,
        organization_user_id=org_user2.id,
        role="member",
    )
    db.session.add(member2)
    db.session.commit()
    return member2


# ===================================================================
# Task.create
# ===================================================================


@pytest.mark.integration
class TestTaskCreate:
    """Tests for Task.create()."""

    def test_create_basic(self, app, db_session, seeded_workspace):
        """Create a task with required fields."""

        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], title="Fix login bug")

        assert task.id is not None
        assert task.title == "Fix login bug"
        assert task.status == "open"
        assert task.workflow_status == "todo"
        assert task.assignee_id == ws["membership"].id

    def test_create_with_urgency_tier_now(self, app, db_session, seeded_workspace):
        """Create a Tier 1 (Now) task."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], urgency_tier=1)

        assert task.urgency_tier == 1

    def test_create_with_urgency_tier_later(self, app, db_session, seeded_workspace):
        """Create a Tier 2 (Later) task."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], urgency_tier=2)

        assert task.urgency_tier == 2

    def test_create_with_urgency_tier_whenever(self, app, db_session, seeded_workspace):
        """Create a Tier 3 (Whenever) task."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], urgency_tier=3)

        assert task.urgency_tier == 3

    def test_urgency_tier_clamped_low(self, app, db_session, seeded_workspace):
        """Urgency tier below 1 is clamped to 1."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], urgency_tier=0)

        assert task.urgency_tier == 1

    def test_urgency_tier_clamped_high(self, app, db_session, seeded_workspace):
        """Urgency tier above 3 is clamped to 3."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], urgency_tier=99)

        assert task.urgency_tier == 3

    def test_title_truncated_to_200(self, app, db_session, seeded_workspace):
        """Titles longer than 200 chars are silently truncated."""
        ws = seeded_workspace
        _set_scope(ws)

        long_title = "A" * 300
        task = _create_task(ws["membership"], title=long_title)

        assert len(task.title) == 200

    def test_create_with_context_note(self, app, db_session, seeded_workspace):
        """Create a task with a context note."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], context_note="Please review ASAP")

        assert task.context_note == "Please review ASAP"

    def test_create_with_blocker_flag(self, app, db_session, seeded_workspace):
        """Create a blocker task."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], is_blocker=True)

        assert task.is_blocker is True

    def test_create_defaults_to_non_blocker(self, app, db_session, seeded_workspace):
        """Default is_blocker is False."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"])

        assert task.is_blocker is False

    def test_create_system_raised(self, app, db_session, seeded_workspace):
        """A task with no raised_by_id is system-raised."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)

        task = Task.create(
            title="System task",
            urgency_tier=3,
            assignee_id=ws["membership"].id,
            raised_by_id=None,
        )

        assert task.raised_by_id is None
        assert task.is_system_raised is True

    def test_create_with_source(self, app, db_session, seeded_workspace):
        """Create a task with source_type and source_id."""
        ws = seeded_workspace
        _set_scope(ws)

        task = _create_task(ws["membership"], source_type="missed_checkin", source_id=42)

        assert task.source_type == "missed_checkin"
        assert task.source_id == 42


# ===================================================================
# State transitions
# ===================================================================


@pytest.mark.integration
class TestTaskResolve:
    """Tests for Task.resolve()."""

    def test_resolve_open_task(self, app, db_session, seeded_workspace):
        """Resolve an open task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = Task.resolve(task.id, ws["membership"].id, note="Done")

        assert result is not None
        assert result.status == "resolved"
        assert result.workflow_status == "done"
        assert result.resolved_at is not None
        assert result.resolved_by_id == ws["membership"].id
        assert result.resolution_note == "Done"

    def test_resolve_nonexistent_returns_none(self, app, db_session, seeded_workspace):
        """Resolving a non-existent task returns None."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)

        result = Task.resolve(999999, ws["membership"].id)

        assert result is None

    def test_resolve_already_resolved_returns_none(self, app, db_session, seeded_workspace):
        """Cannot resolve an already-resolved task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])
        Task.resolve(task.id, ws["membership"].id)

        result = Task.resolve(task.id, ws["membership"].id)

        assert result is None

    def test_resolve_truncates_note(self, app, db_session, seeded_workspace):
        """Resolution note is truncated to 1024 chars."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        long_note = "X" * 2000
        result = Task.resolve(task.id, ws["membership"].id, note=long_note)

        assert len(result.resolution_note) == 1024


@pytest.mark.integration
class TestTaskDismiss:
    """Tests for Task.dismiss()."""

    def test_dismiss_open_task(self, app, db_session, seeded_workspace):
        """Dismiss an open task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = Task.dismiss(task.id, ws["membership"].id)

        assert result is not None
        assert result.status == "dismissed"
        assert result.workflow_status == "done"
        assert result.resolved_at is not None

    def test_dismiss_nonexistent_returns_none(self, app, db_session, seeded_workspace):
        """Dismissing a non-existent task returns None."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)

        result = Task.dismiss(999999, ws["membership"].id)

        assert result is None


@pytest.mark.integration
class TestTaskCancel:
    """Tests for Task.cancel()."""

    def test_cancel_by_raiser(self, app, db_session, seeded_workspace):
        """Raiser can cancel their own task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        task = _create_task(member2, raised_by_id=ws["membership"].id)

        result = Task.cancel(task.id, ws["membership"].id)

        assert result is not None
        assert result.status == "canceled"
        assert result.workflow_status == "done"
        assert result.resolved_at is not None

    def test_cancel_by_non_raiser_returns_none(self, app, db_session, seeded_workspace):
        """Non-raiser cannot cancel the task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        task = _create_task(member2, raised_by_id=ws["membership"].id)

        result = Task.cancel(task.id, member2.id)

        assert result is None


@pytest.mark.integration
class TestTaskReopen:
    """Tests for Task.reopen()."""

    def test_reopen_resolved_task(self, app, db_session, seeded_workspace):
        """Raiser can reopen a recently resolved task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        task = _create_task(member2, raised_by_id=ws["membership"].id)
        Task.resolve(task.id, member2.id)

        result = Task.reopen(task.id, ws["membership"].id)

        assert result is not None
        assert result.status == "open"
        assert result.workflow_status == "todo"
        assert result.resolved_at is None
        assert result.resolved_by_id is None
        assert result.resolution_note is None

    def test_reopen_by_non_raiser_returns_none(self, app, db_session, seeded_workspace):
        """Non-raiser cannot reopen the task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        task = _create_task(member2, raised_by_id=ws["membership"].id)
        Task.resolve(task.id, member2.id)

        result = Task.reopen(task.id, member2.id)

        assert result is None

    def test_reopen_expired_returns_none(self, app, db_session, seeded_workspace):
        """Cannot reopen after 24 hours."""
        from modules.base.tasks.models.task import Task
        from system.db.database import db

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])
        Task.resolve(task.id, ws["membership"].id)

        # Backdate resolved_at beyond 24h
        resolved_task = Task.query.get(task.id)
        resolved_task.resolved_at = datetime.utcnow() - timedelta(hours=25)
        db.session.commit()

        result = Task.reopen(task.id, ws["membership"].id)

        assert result is None

    def test_can_reopen_within_24h(self, app, db_session, seeded_workspace):
        """can_reopen() returns True within 24h of resolution."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])
        resolved = Task.resolve(task.id, ws["membership"].id)

        assert resolved.can_reopen() is True

    def test_can_reopen_false_for_open_task(self, app, db_session, seeded_workspace):
        """can_reopen() returns False for an open task."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        assert task.can_reopen() is False


@pytest.mark.integration
class TestTaskSetWorkflowStatus:
    """Tests for Task.set_workflow_status()."""

    def test_set_in_progress(self, app, db_session, seeded_workspace):
        """Move a task to in_progress."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = Task.set_workflow_status(task.id, "in_progress")

        assert result is not None
        assert result.workflow_status == "in_progress"

    def test_set_needs_review(self, app, db_session, seeded_workspace):
        """Move a task to needs_review."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = Task.set_workflow_status(task.id, "needs_review")

        assert result.workflow_status == "needs_review"

    def test_set_on_hold(self, app, db_session, seeded_workspace):
        """Move a task to on_hold."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = Task.set_workflow_status(task.id, "on_hold")

        assert result.workflow_status == "on_hold"

    def test_set_workflow_on_resolved_returns_none(self, app, db_session, seeded_workspace):
        """Cannot change workflow_status on a resolved task."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])
        Task.resolve(task.id, ws["membership"].id)

        result = Task.set_workflow_status(task.id, "in_progress")

        assert result is None


# ===================================================================
# Queries
# ===================================================================


@pytest.mark.integration
class TestTaskGetMineOpen:
    """Tests for Task.get_mine_open()."""

    def test_returns_open_tasks(self, app, db_session, seeded_workspace):
        """get_mine_open returns open tasks for the member."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Open one")
        _create_task(ws["membership"], title="Open two")

        result = Task.get_mine_open(ws["membership"].id)

        assert len(result) == 2

    def test_excludes_resolved_tasks(self, app, db_session, seeded_workspace):
        """get_mine_open excludes resolved tasks."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task1 = _create_task(ws["membership"], title="Will resolve")
        _create_task(ws["membership"], title="Still open")
        Task.resolve(task1.id, ws["membership"].id)

        result = Task.get_mine_open(ws["membership"].id)

        assert len(result) == 1
        assert result[0].title == "Still open"

    def test_ordered_by_tier_then_created(self, app, db_session, seeded_workspace):
        """Results are ordered by urgency_tier ASC, created_at ASC."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Whenever", urgency_tier=3)
        _create_task(ws["membership"], title="Now", urgency_tier=1)
        _create_task(ws["membership"], title="Later", urgency_tier=2)

        result = Task.get_mine_open(ws["membership"].id)

        assert result[0].urgency_tier == 1
        assert result[1].urgency_tier == 2
        assert result[2].urgency_tier == 3

    def test_excludes_other_members_tasks(self, app, db_session, seeded_workspace):
        """get_mine_open does not return tasks assigned to other members."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        _create_task(ws["membership"], title="My task")
        _create_task(member2, title="Their task")

        result = Task.get_mine_open(ws["membership"].id)

        assert len(result) == 1
        assert result[0].title == "My task"


@pytest.mark.integration
class TestTaskGetTeamOpen:
    """Tests for Task.get_team_open()."""

    def test_returns_all_open_tasks(self, app, db_session, seeded_workspace):
        """get_team_open returns open tasks across all members."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)
        _create_task(ws["membership"], title="Task A")
        _create_task(member2, title="Task B")

        result = Task.get_team_open()

        assert len(result) == 2

    def test_excludes_resolved(self, app, db_session, seeded_workspace):
        """get_team_open excludes resolved tasks."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], title="Will resolve")
        _create_task(ws["membership"], title="Open")
        Task.resolve(task.id, ws["membership"].id)

        result = Task.get_team_open()

        assert len(result) == 1


@pytest.mark.integration
class TestTaskGetOpenBlockers:
    """Tests for Task.get_open_blockers()."""

    def test_returns_open_blockers(self, app, db_session, seeded_workspace):
        """get_open_blockers returns only open blocker tasks."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Blocker", is_blocker=True)
        _create_task(ws["membership"], title="Normal")

        result = Task.get_open_blockers()

        assert len(result) == 1
        assert result[0].title == "Blocker"

    def test_excludes_resolved_blockers(self, app, db_session, seeded_workspace):
        """get_open_blockers excludes resolved blockers."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        blocker = _create_task(ws["membership"], title="Blocker", is_blocker=True)
        Task.resolve(blocker.id, ws["membership"].id)

        result = Task.get_open_blockers()

        assert len(result) == 0

    def test_open_blockers_count(self, app, db_session, seeded_workspace):
        """get_open_blockers_count returns correct count."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], is_blocker=True)
        _create_task(ws["membership"], is_blocker=True)
        _create_task(ws["membership"], is_blocker=False)

        count = Task.get_open_blockers_count()

        assert count == 2


@pytest.mark.integration
class TestTaskSearch:
    """Tests for Task.search()."""

    def test_search_by_title(self, app, db_session, seeded_workspace):
        """search finds tasks matching title text."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Deploy to production")
        _create_task(ws["membership"], title="Fix login bug")

        result = Task.search("deploy")

        assert len(result) == 1
        assert result[0].title == "Deploy to production"

    def test_search_by_context_note(self, app, db_session, seeded_workspace):
        """search finds tasks matching context_note text."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Generic task", context_note="Check the API endpoint")

        result = Task.search("API endpoint")

        assert len(result) == 1

    def test_search_excludes_resolved(self, app, db_session, seeded_workspace):
        """search only returns open tasks."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], title="Deploy to prod")
        Task.resolve(task.id, ws["membership"].id)

        result = Task.search("deploy")

        assert len(result) == 0

    def test_search_respects_limit(self, app, db_session, seeded_workspace):
        """search respects the limit parameter."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        for i in range(5):
            _create_task(ws["membership"], title=f"Deploy phase {i}")

        result = Task.search("Deploy", limit=2)

        assert len(result) == 2

    def test_search_no_results(self, app, db_session, seeded_workspace):
        """search returns empty list when no match."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="Something else")

        result = Task.search("nonexistent_xyz")

        assert result == []


@pytest.mark.integration
class TestTaskMarkStale:
    """Tests for Task.mark_stale_tasks()."""

    def test_marks_old_todo_tasks_stale(self, app, db_session, seeded_workspace):
        """mark_stale_tasks moves old todo tasks to on_hold."""
        from modules.base.tasks.models.task import Task
        from system.db.database import db

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=2)

        # Backdate updated_at to trigger stale threshold
        task_obj = Task.query.get(task.id)
        task_obj.updated_at = datetime.utcnow() - timedelta(days=10)
        db.session.commit()

        count = Task.mark_stale_tasks(stale_days=7)

        assert count == 1
        refreshed = Task.query.get(task.id)
        assert refreshed.workflow_status == "on_hold"

    def test_does_not_mark_tier1_stale(self, app, db_session, seeded_workspace):
        """mark_stale_tasks skips Tier 1 (Now) tasks."""
        from modules.base.tasks.models.task import Task
        from system.db.database import db

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=1)

        task_obj = Task.query.get(task.id)
        task_obj.updated_at = datetime.utcnow() - timedelta(days=10)
        db.session.commit()

        count = Task.mark_stale_tasks(stale_days=7)

        assert count == 0

    def test_does_not_mark_in_progress_stale(self, app, db_session, seeded_workspace):
        """mark_stale_tasks only targets todo status."""
        from modules.base.tasks.models.task import Task
        from system.db.database import db

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=2)
        Task.set_workflow_status(task.id, "in_progress")

        task_obj = Task.query.get(task.id)
        task_obj.updated_at = datetime.utcnow() - timedelta(days=10)
        db.session.commit()

        count = Task.mark_stale_tasks(stale_days=7)

        assert count == 0

    def test_returns_zero_when_nothing_stale(self, app, db_session, seeded_workspace):
        """mark_stale_tasks returns 0 when no tasks are stale."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], urgency_tier=2)

        count = Task.mark_stale_tasks(stale_days=7)

        assert count == 0


# ===================================================================
# Broadcast
# ===================================================================


@pytest.mark.integration
class TestTaskBroadcast:
    """Tests for Task.create_broadcast()."""

    def test_create_broadcast(self, app, db_session, seeded_workspace):
        """create_broadcast creates tasks for multiple assignees."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        member2 = _second_member(ws)

        items = Task.create_broadcast(
            title="Team reminder",
            urgency_tier=2,
            assignee_ids=[ws["membership"].id, member2.id],
            raised_by_id=ws["membership"].id,
        )

        assert len(items) == 2
        assert items[0].broadcast_group_id is not None
        assert items[0].broadcast_group_id == items[1].broadcast_group_id
        assignee_ids = {i.assignee_id for i in items}
        assert assignee_ids == {ws["membership"].id, member2.id}


# ===================================================================
# Helper properties
# ===================================================================


@pytest.mark.integration
class TestTaskHelpers:
    """Tests for Task helper methods and properties."""

    def test_tier_label_now(self, app, db_session, seeded_workspace):
        """Tier 1 label is 'Now'."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=1)

        assert task.tier_label() == "Now"

    def test_tier_label_later(self, app, db_session, seeded_workspace):
        """Tier 2 label is 'Later'."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=2)

        assert task.tier_label() == "Later"

    def test_tier_label_whenever(self, app, db_session, seeded_workspace):
        """Tier 3 label is 'Whenever'."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"], urgency_tier=3)

        assert task.tier_label() == "Whenever"

    def test_tier_color(self, app, db_session, seeded_workspace):
        """Each tier has a distinct color."""
        ws = seeded_workspace
        _set_scope(ws)
        t1 = _create_task(ws["membership"], urgency_tier=1)
        t2 = _create_task(ws["membership"], urgency_tier=2)
        t3 = _create_task(ws["membership"], urgency_tier=3)

        assert t1.tier_color() == "#dc2626"
        assert t2.tier_color() == "#d97706"
        assert t3.tier_color() == "#16a34a"

    def test_is_system_raised_true(self, app, db_session, seeded_workspace):
        """is_system_raised is True when raised_by_id is None."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = Task.create(
            title="System generated",
            urgency_tier=3,
            assignee_id=ws["membership"].id,
            raised_by_id=None,
        )

        assert task.is_system_raised is True

    def test_is_system_raised_false(self, app, db_session, seeded_workspace):
        """is_system_raised is False when raised_by_id is set."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        assert task.is_system_raised is False

    def test_time_ago(self, app, db_session, seeded_workspace):
        """time_ago returns a human-readable string."""
        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])

        result = task.time_ago()

        assert isinstance(result, str)
        assert "ago" in result or result == "just now"


# ===================================================================
# Date range queries
# ===================================================================


@pytest.mark.integration
class TestTaskDateRangeQueries:
    """Tests for Task date range queries."""

    def test_get_for_date_range(self, app, db_session, seeded_workspace):
        """get_for_date_range returns tasks created within the range."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"], title="In range")

        today = date.today()
        result = Task.get_for_date_range(today, today)

        assert len(result) >= 1

    def test_count_created_in_range(self, app, db_session, seeded_workspace):
        """count_created_in_range returns correct count."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"])
        _create_task(ws["membership"])

        today = date.today()
        count = Task.count_created_in_range(today, today)

        assert count == 2

    def test_count_created_exclude_system(self, app, db_session, seeded_workspace):
        """count_created_in_range with exclude_system=True skips system tasks."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        _create_task(ws["membership"])
        Task.create(
            title="System task",
            urgency_tier=3,
            assignee_id=ws["membership"].id,
            raised_by_id=None,
        )

        today = date.today()
        count = Task.count_created_in_range(today, today, exclude_system=True)

        assert count == 1

    def test_count_resolved_in_range(self, app, db_session, seeded_workspace):
        """count_resolved_in_range returns correct count."""
        from modules.base.tasks.models.task import Task

        ws = seeded_workspace
        _set_scope(ws)
        task = _create_task(ws["membership"])
        Task.resolve(task.id, ws["membership"].id)

        today = date.today()
        count = Task.count_resolved_in_range(today, today)

        assert count == 1
