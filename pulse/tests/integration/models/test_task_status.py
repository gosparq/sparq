# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - TaskStatus Model Integration Tests
#
# Tests for TaskStatus CRUD, seed_defaults, invariants (exactly-one is_done,
# exactly-one is_default), deletion guards, and bulk reorder.
# -----------------------------------------------------------------------------

import pytest
from flask import g


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_scope(ws):
    """Set g.organization_id and g.workspace_id from a seeded_workspace dict."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _seed(ws):
    """Set scope and seed default statuses, then commit."""
    from modules.base.tasks.models.task_status import TaskStatus
    from system.db.database import db

    _set_scope(ws)
    TaskStatus.seed_defaults()
    db.session.commit()


def _clear_cache():
    """Remove the g-cached status list so get_for_workspace re-queries."""
    try:
        delattr(g, "_task_status_list_cache")
    except AttributeError:
        pass


def _create_task(member, workflow_status="todo", **kw):
    """Shortcut to create a task with a specific workflow_status."""
    from modules.base.tasks.models.task import Task

    return Task.create(
        title=kw.pop("title", "Test task"),
        urgency_tier=kw.pop("urgency_tier", 2),
        assignee_id=member.id,
        raised_by_id=kw.pop("raised_by_id", member.id),
        workflow_status=workflow_status,
        **kw,
    )


# ===================================================================
# seed_defaults
# ===================================================================


@pytest.mark.integration
class TestSeedDefaults:
    """Tests for TaskStatus.seed_defaults()."""

    def test_seeds_five_default_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)

        rows = TaskStatus.scoped().all()
        assert len(rows) == 5

        codes = [r.code for r in rows]
        assert "todo" in codes
        assert "in_progress" in codes
        assert "needs_review" in codes
        assert "on_hold" in codes
        assert "done" in codes

    def test_idempotent_second_call_noop(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus
        from system.db.database import db

        ws = seeded_workspace
        _seed(ws)

        TaskStatus.seed_defaults()
        db.session.commit()

        assert TaskStatus.scoped().count() == 5

    def test_skips_without_workspace_context(self, app, db_session):
        from modules.base.tasks.models.task_status import TaskStatus
        from system.db.database import db

        with app.app_context():
            g.workspace_id = None
            g.organization_id = None

            TaskStatus.seed_defaults()
            db.session.commit()

            assert TaskStatus.query.count() == 0

    def test_default_flags_are_set_correctly(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)

        rows = TaskStatus.scoped().all()
        defaults = [r for r in rows if r.is_default]
        dones = [r for r in rows if r.is_done]

        assert len(defaults) == 1
        assert defaults[0].code == "todo"
        assert len(dones) == 1
        assert dones[0].code == "done"


# ===================================================================
# get_for_workspace
# ===================================================================


@pytest.mark.integration
class TestGetForWorkspace:
    """Tests for TaskStatus.get_for_workspace()."""

    def test_returns_ordered_by_sort_order(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        rows = TaskStatus.get_for_workspace()
        orders = [r.sort_order for r in rows]
        assert orders == sorted(orders)

    def test_caches_on_g(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        first_call = TaskStatus.get_for_workspace()
        second_call = TaskStatus.get_for_workspace()

        assert first_call is second_call

    def test_returns_empty_when_no_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)
        _clear_cache()

        rows = TaskStatus.get_for_workspace()
        assert rows == []


# ===================================================================
# get_default
# ===================================================================


@pytest.mark.integration
class TestGetDefault:
    """Tests for TaskStatus.get_default()."""

    def test_returns_is_default_row(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        default = TaskStatus.get_default()
        assert default is not None
        assert default.is_default is True
        assert default.code == "todo"

    def test_falls_back_to_first_if_none_marked(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus
        from system.db.database import db

        ws = seeded_workspace
        _seed(ws)

        TaskStatus.scoped().update({"is_default": False})
        db.session.commit()
        _clear_cache()

        default = TaskStatus.get_default()
        assert default is not None
        first = TaskStatus.scoped().order_by(TaskStatus.sort_order).first()
        assert default.id == first.id

    def test_returns_none_when_no_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)
        _clear_cache()

        assert TaskStatus.get_default() is None


# ===================================================================
# get_done_status
# ===================================================================


@pytest.mark.integration
class TestGetDoneStatus:
    """Tests for TaskStatus.get_done_status()."""

    def test_returns_is_done_row(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        done = TaskStatus.get_done_status()
        assert done is not None
        assert done.is_done is True
        assert done.code == "done"

    def test_returns_none_when_no_done_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus
        from system.db.database import db

        ws = seeded_workspace
        _seed(ws)

        TaskStatus.scoped().update({"is_done": False})
        db.session.commit()
        _clear_cache()

        assert TaskStatus.get_done_status() is None

    def test_returns_none_when_no_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)
        _clear_cache()

        assert TaskStatus.get_done_status() is None


# ===================================================================
# get_codes
# ===================================================================


@pytest.mark.integration
class TestGetCodes:
    """Tests for TaskStatus.get_codes()."""

    def test_returns_ordered_list_of_codes(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        codes = TaskStatus.get_codes()
        assert codes == ["todo", "in_progress", "needs_review", "on_hold", "done"]

    def test_returns_empty_when_no_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)
        _clear_cache()

        assert TaskStatus.get_codes() == []


# ===================================================================
# add
# ===================================================================


@pytest.mark.integration
class TestAdd:
    """Tests for TaskStatus.add()."""

    def test_creates_status_successfully(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="Blocked", code="blocked", color="#ef4444")

        assert err is None
        assert status is not None
        assert status.code == "blocked"
        assert status.label == "Blocked"
        assert status.color == "#ef4444"
        assert status.is_done is False

    def test_rejects_empty_label(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="", code="empty_label")
        assert status is None
        assert "Label is required" in err

    def test_rejects_invalid_code_format_uppercase(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="Bad", code="BadCode")
        assert status is None
        assert "lowercase" in err

    def test_rejects_invalid_code_format_spaces(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="Bad", code="bad code")
        assert status is None
        assert "lowercase" in err

    def test_rejects_invalid_code_format_special_chars(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="Bad", code="bad-code!")
        assert status is None
        assert "lowercase" in err

    def test_rejects_duplicate_code(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        TaskStatus.add(label="First", code="alpha")
        _clear_cache()
        status, err = TaskStatus.add(label="Duplicate Alpha", code="alpha")
        assert status is None
        assert "already exists" in err

    def test_enforces_max_limit(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        status, err = TaskStatus.add(label="Sixth", code="sixth")
        assert status is None
        assert "Maximum" in err

    def test_is_default_clears_others(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        TaskStatus.add(label="First", code="first", is_default=True)
        _clear_cache()
        TaskStatus.add(label="Second", code="second", is_default=True)
        _clear_cache()

        rows = TaskStatus.get_for_workspace()
        defaults = [r for r in rows if r.is_default]
        assert len(defaults) == 1
        assert defaults[0].code == "second"

    def test_auto_sort_order_increments(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        s1, _ = TaskStatus.add(label="Alpha", code="alpha")
        s2, _ = TaskStatus.add(label="Beta", code="beta")

        assert s2.sort_order > s1.sort_order

    def test_invalid_color_falls_back_to_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        status, err = TaskStatus.add(label="Colorless", code="colorless", color="not-a-color")
        assert err is None
        assert status.color == "#6b7280"


# ===================================================================
# update
# ===================================================================


@pytest.mark.integration
class TestUpdate:
    """Tests for TaskStatus.update()."""

    def test_updates_label_and_color(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        todo = TaskStatus.scoped().filter_by(code="todo").first()
        ok, err = TaskStatus.update(
            todo.id, label="Backlog", color="#111111", is_done=False, is_default=True,
        )

        assert ok is True
        assert err is None
        _clear_cache()
        updated = TaskStatus.scoped().filter_by(id=todo.id).first()
        assert updated.label == "Backlog"
        assert updated.color == "#111111"

    def test_enforces_one_is_done_setting_clears_others(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        in_progress = TaskStatus.scoped().filter_by(code="in_progress").first()
        ok, err = TaskStatus.update(
            in_progress.id, label="In Progress", color="#2563eb",
            is_done=True, is_default=False,
        )

        assert ok is True
        _clear_cache()
        rows = TaskStatus.get_for_workspace()
        done_rows = [r for r in rows if r.is_done]
        assert len(done_rows) == 1
        assert done_rows[0].id == in_progress.id

    def test_cannot_remove_only_done(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        done_status = TaskStatus.scoped().filter_by(code="done").first()
        ok, err = TaskStatus.update(
            done_status.id, label="Completed", color="#16a34a",
            is_done=False, is_default=False,
        )

        assert ok is False
        assert "resolution" in err

    def test_enforces_one_is_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        in_progress = TaskStatus.scoped().filter_by(code="in_progress").first()
        ok, err = TaskStatus.update(
            in_progress.id, label="In Progress", color="#2563eb",
            is_done=False, is_default=True,
        )

        assert ok is True
        _clear_cache()
        rows = TaskStatus.get_for_workspace()
        default_rows = [r for r in rows if r.is_default]
        assert len(default_rows) == 1
        assert default_rows[0].id == in_progress.id

    def test_cannot_remove_only_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        todo = TaskStatus.scoped().filter_by(code="todo").first()
        ok, err = TaskStatus.update(
            todo.id, label="To Do", color="#6b7280",
            is_done=False, is_default=False,
        )

        assert ok is False
        assert "default" in err

    def test_not_found_returns_error(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        ok, err = TaskStatus.update(
            999999, label="Ghost", color="#000000", is_done=False, is_default=False,
        )
        assert ok is False
        assert "not found" in err


# ===================================================================
# delete
# ===================================================================


@pytest.mark.integration
class TestDelete:
    """Tests for TaskStatus.delete()."""

    def test_deletes_unused_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        on_hold = TaskStatus.scoped().filter_by(code="on_hold").first()
        ok, err = TaskStatus.delete(on_hold.id)

        assert ok is True
        assert err is None
        _clear_cache()
        assert TaskStatus.scoped().filter_by(code="on_hold").first() is None

    def test_cannot_delete_in_use_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        _create_task(ws["membership"], workflow_status="on_hold")

        on_hold = TaskStatus.scoped().filter_by(code="on_hold").first()
        ok, err = TaskStatus.delete(on_hold.id)

        assert ok is False
        assert "task(s) are using" in err

    def test_cannot_delete_last_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _set_scope(ws)

        s, _ = TaskStatus.add(label="Only", code="only", is_default=True)
        _clear_cache()

        ok, err = TaskStatus.delete(s.id)

        assert ok is False
        assert "last task status" in err

    def test_cannot_delete_only_done_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        done = TaskStatus.scoped().filter_by(code="done").first()
        ok, err = TaskStatus.delete(done.id)

        assert ok is False
        assert "only done status" in err

    def test_promotes_next_when_deleting_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        todo = TaskStatus.scoped().filter_by(code="todo").first()
        ok, err = TaskStatus.delete(todo.id)

        assert ok is True
        _clear_cache()
        rows = TaskStatus.get_for_workspace()
        defaults = [r for r in rows if r.is_default]
        assert len(defaults) == 1

    def test_not_found_returns_error(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)

        ok, err = TaskStatus.delete(999999)
        assert ok is False
        assert "not found" in err


# ===================================================================
# set_default
# ===================================================================


@pytest.mark.integration
class TestSetDefault:
    """Tests for TaskStatus.set_default()."""

    def test_sets_default_and_clears_others(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        in_progress = TaskStatus.scoped().filter_by(code="in_progress").first()
        ok, err = TaskStatus.set_default(in_progress.id)

        assert ok is True
        assert err is None
        _clear_cache()
        rows = TaskStatus.get_for_workspace()
        defaults = [r for r in rows if r.is_default]
        assert len(defaults) == 1
        assert defaults[0].id == in_progress.id

    def test_not_found_returns_error(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)

        ok, err = TaskStatus.set_default(999999)
        assert ok is False
        assert "not found" in err


# ===================================================================
# set_done
# ===================================================================


@pytest.mark.integration
class TestSetDone:
    """Tests for TaskStatus.set_done()."""

    def test_sets_done_and_clears_others(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        in_progress = TaskStatus.scoped().filter_by(code="in_progress").first()
        ok, err = TaskStatus.set_done(in_progress.id)

        assert ok is True
        assert err is None
        _clear_cache()
        rows = TaskStatus.get_for_workspace()
        done_rows = [r for r in rows if r.is_done]
        assert len(done_rows) == 1
        assert done_rows[0].id == in_progress.id

    def test_not_found_returns_error(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)

        ok, err = TaskStatus.set_done(999999)
        assert ok is False
        assert "not found" in err


# ===================================================================
# bulk_reorder
# ===================================================================


@pytest.mark.integration
class TestBulkReorder:
    """Tests for TaskStatus.bulk_reorder()."""

    def test_reorders_statuses(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        rows = TaskStatus.get_for_workspace()
        reorder_items = [
            {"id": rows[0].id, "sort_order": 50},
            {"id": rows[1].id, "sort_order": 40},
            {"id": rows[2].id, "sort_order": 30},
            {"id": rows[3].id, "sort_order": 20},
            {"id": rows[4].id, "sort_order": 10},
        ]

        TaskStatus.bulk_reorder(reorder_items)
        _clear_cache()

        updated = TaskStatus.get_for_workspace()
        assert updated[0].sort_order == 10
        assert updated[-1].sort_order == 50

    def test_skips_invalid_items(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        rows = TaskStatus.get_for_workspace()
        original_order = rows[0].sort_order

        TaskStatus.bulk_reorder([
            {"bad_key": "no_id"},
            {"id": "not_a_number", "sort_order": 10},
            {"id": rows[0].id, "sort_order": "not_a_number"},
        ])
        _clear_cache()

        refreshed = TaskStatus.scoped().filter_by(id=rows[0].id).first()
        assert refreshed.sort_order == original_order

    def test_empty_list_is_noop(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        ws = seeded_workspace
        _seed(ws)
        _clear_cache()

        rows_before = TaskStatus.get_for_workspace()
        orders_before = [r.sort_order for r in rows_before]

        TaskStatus.bulk_reorder([])
        _clear_cache()

        rows_after = TaskStatus.get_for_workspace()
        orders_after = [r.sort_order for r in rows_after]
        assert orders_before == orders_after
