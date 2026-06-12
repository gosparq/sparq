# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Tasks & Projects Extras Integration Tests
#
# Tests for TaskComment, TaskCommentLike, TaskLog, CannedTask,
# ProjectStatus, ProjectCoOwner (table), and ProjectFollower (table).
# -----------------------------------------------------------------------------


import pytest
from flask import g

from system.db.database import db


def _setup_g(ws):
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _make_task(ws):
    from modules.base.tasks.models.task import Task

    task = Task(
        title="Test task",
        raised_by_id=ws["membership"].id,
        assignee_id=ws["membership"].id,
    )
    db.session.add(task)
    db.session.commit()
    return task


# ═════════════════════════════════════════════════════════════════════════════
# TaskComment
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTaskComment:
    """Tests for TaskComment CRUD and content truncation."""

    def test_create_comment(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        comment = TaskComment.create(
            task_id=task.id,
            content="Looks good to me!",
            author_id=ws["membership"].id,
            user_id=ws["user"].id,
        )
        assert comment.id is not None
        assert comment.content == "Looks good to me!"
        assert comment.task_id == task.id

    def test_content_truncated_to_2000(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        long_content = "A" * 3000
        comment = TaskComment.create(
            task_id=task.id,
            content=long_content,
            author_id=ws["membership"].id,
            user_id=ws["user"].id,
        )
        assert len(comment.content) == 2000

    def test_get_for_item(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        TaskComment.create(task_id=task.id, content="First", author_id=ws["membership"].id, user_id=ws["user"].id)
        TaskComment.create(task_id=task.id, content="Second", author_id=ws["membership"].id, user_id=ws["user"].id)

        comments = TaskComment.get_for_item(task.id)
        assert len(comments) == 2
        assert comments[0].content == "First"

    def test_update_content(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        comment = TaskComment.create(
            task_id=task.id,
            content="Original",
            author_id=ws["membership"].id,
            user_id=ws["user"].id,
        )
        comment.update_content("Edited", user_id=ws["user"].id)
        assert comment.content == "Edited"


# ═════════════════════════════════════════════════════════════════════════════
# TaskCommentLike
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTaskCommentLike:
    """Tests for TaskCommentLike toggle and aggregation."""

    def test_toggle_like(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment
        from modules.base.tasks.models.task_comment_like import TaskCommentLike

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        comment = TaskComment.create(
            task_id=task.id,
            content="Likeable",
            author_id=ws["membership"].id,
            user_id=ws["user"].id,
        )

        result = TaskCommentLike.toggle(comment.id, ws["membership"].id)
        assert result is True
        assert TaskCommentLike.count_for_comment(comment.id) == 1

        result = TaskCommentLike.toggle(comment.id, ws["membership"].id)
        assert result is False
        assert TaskCommentLike.count_for_comment(comment.id) == 0

    def test_liked_by_member(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment
        from modules.base.tasks.models.task_comment_like import TaskCommentLike

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        comment = TaskComment.create(
            task_id=task.id,
            content="Check liked",
            author_id=ws["membership"].id,
            user_id=ws["user"].id,
        )

        assert TaskCommentLike.liked_by_member(comment.id, ws["membership"].id) is False
        TaskCommentLike.toggle(comment.id, ws["membership"].id)
        assert TaskCommentLike.liked_by_member(comment.id, ws["membership"].id) is True

    def test_get_like_data(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_comment import TaskComment
        from modules.base.tasks.models.task_comment_like import TaskCommentLike

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        c1 = TaskComment.create(task_id=task.id, content="C1", author_id=ws["membership"].id, user_id=ws["user"].id)
        c2 = TaskComment.create(task_id=task.id, content="C2", author_id=ws["membership"].id, user_id=ws["user"].id)
        TaskCommentLike.toggle(c1.id, ws["membership"].id)

        data = TaskCommentLike.get_like_data([c1.id, c2.id], ws["membership"].id)
        assert data[c1.id]["count"] == 1
        assert data[c1.id]["liked"] is True
        assert data[c2.id]["count"] == 0


# ═════════════════════════════════════════════════════════════════════════════
# TaskLog
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTaskLog:
    """Tests for TaskLog event recording and retrieval."""

    def test_log_event(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_log import TaskLog

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        entry = TaskLog.log(
            task_id=task.id,
            event_type="created",
            actor_id=ws["membership"].id,
            detail="Task created by test",
        )
        assert entry.id is not None
        assert entry.event_type == "created"
        assert entry.detail == "Task created by test"

    def test_log_system_event(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_log import TaskLog

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        entry = TaskLog.log(
            task_id=task.id,
            event_type="auto_resolved",
            actor_id=None,
            detail="System auto-resolved",
        )
        assert entry.actor_id is None

    def test_get_for_item(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_log import TaskLog

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        TaskLog.log(task_id=task.id, event_type="created")
        TaskLog.log(task_id=task.id, event_type="nudge_sent")

        logs = TaskLog.get_for_item(task.id)
        assert len(logs) == 2
        assert logs[0].event_type == "nudge_sent"

    def test_detail_truncated_to_500(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_log import TaskLog

        ws = seeded_workspace
        _setup_g(ws)

        task = _make_task(ws)
        long_detail = "X" * 600
        entry = TaskLog.log(task_id=task.id, event_type="created", detail=long_detail)
        assert len(entry.detail) == 500


# ═════════════════════════════════════════════════════════════════════════════
# CannedTask
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestCannedTask:
    """Tests for CannedTask CRUD, deduplication, and limits."""

    def test_create_canned_task(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask

        ws = seeded_workspace
        _setup_g(ws)

        action = CannedTask.create(
            title="Follow up with client",
            default_tier=2,
            created_by_id=ws["membership"].id,
        )
        assert action is not None
        assert action.title == "Follow up with client"
        assert action.default_tier == 2

    def test_create_deduplicates(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask

        ws = seeded_workspace
        _setup_g(ws)

        a1 = CannedTask.create(title="Unique Task")
        a2 = CannedTask.create(title="unique task")
        assert a1.id == a2.id

    def test_max_limit(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask, MAX_CANNED_TASKS

        ws = seeded_workspace
        _setup_g(ws)

        for i in range(MAX_CANNED_TASKS):
            CannedTask.create(title=f"Canned {i}")

        result = CannedTask.create(title="Over Limit")
        assert result is None

    def test_update_canned_task(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask

        ws = seeded_workspace
        _setup_g(ws)

        action = CannedTask.create(title="Old Title")
        updated = CannedTask.update(action.id, title="New Title", default_tier=1)
        assert updated.title == "New Title"
        assert updated.default_tier == 1

    def test_delete_canned_task(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask

        ws = seeded_workspace
        _setup_g(ws)

        action = CannedTask.create(title="Delete Me")
        assert CannedTask.delete(action.id) is True
        assert CannedTask.delete(action.id) is False

    def test_get_all(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.canned_task import CannedTask

        ws = seeded_workspace
        _setup_g(ws)

        CannedTask.create(title="Task A")
        CannedTask.create(title="Task B")
        actions = CannedTask.get_all()
        assert len(actions) >= 2


# ═════════════════════════════════════════════════════════════════════════════
# ProjectStatus
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestProjectStatus:
    """Tests for ProjectStatus seeding, defaults, and reorder."""

    def test_seed_defaults(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        statuses = ProjectStatus.get_for_workspace()
        assert len(statuses) >= 4

    def test_get_default(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        default = ProjectStatus.get_default()
        assert default is not None
        assert default.is_default is True

    def test_get_archived_status(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        archived = ProjectStatus.get_archived_status()
        assert archived is not None
        assert archived.is_archived is True

    def test_get_codes(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        codes = ProjectStatus.get_codes()
        assert "current" in codes
        assert "archived" in codes

    def test_add_status(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        ps, err = ProjectStatus.add(label="Blocked", code="blocked", color="#ff0000")
        assert ps is not None
        assert err is None
        assert ps.label == "Blocked"

    def test_add_duplicate_code_fails(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        ps, err = ProjectStatus.add(label="Dup", code="current")
        assert ps is None
        assert "already exists" in err

    def test_set_default(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        statuses = ProjectStatus.get_for_workspace()
        non_default = next(s for s in statuses if not s.is_default)

        ok, err = ProjectStatus.set_default(non_default.id)
        assert ok is True
        db.session.refresh(non_default)
        assert non_default.is_default is True

    def test_bulk_reorder(self, app, db_session, seeded_workspace):
        from modules.base.projects.models.project_status import ProjectStatus

        ws = seeded_workspace
        _setup_g(ws)

        ProjectStatus.seed_defaults()
        statuses = ProjectStatus.get_for_workspace()
        items = [{"id": s.id, "sort_order": 100 - s.sort_order} for s in statuses]
        ProjectStatus.bulk_reorder(items)

        refreshed = ProjectStatus.scoped().order_by(ProjectStatus.sort_order).all()
        assert refreshed[0].sort_order < refreshed[-1].sort_order


# ═════════════════════════════════════════════════════════════════════════════
# TaskStatus
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTaskStatus:
    """Tests for TaskStatus model: seeding, CRUD, and invariant enforcement."""

    def test_seed_defaults(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        statuses = TaskStatus.get_for_workspace()
        assert len(statuses) == 5
        codes = [s.code for s in statuses]
        assert "todo" in codes
        assert "done" in codes

    def test_seed_defaults_idempotent(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()
        TaskStatus.seed_defaults()
        db.session.commit()

        assert TaskStatus.scoped().count() == 5

    def test_get_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        default = TaskStatus.get_default()
        assert default is not None
        assert default.is_default is True

    def test_get_done_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        done = TaskStatus.get_done_status()
        assert done is not None
        assert done.is_done is True
        assert done.code == "done"

    def test_get_codes(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        codes = TaskStatus.get_codes()
        assert "todo" in codes
        assert "in_progress" in codes
        assert "done" in codes

    def test_add_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        # Seed only 4 so there is room to add one more
        from modules.base.tasks.models.task_status import _DEFAULT_STATUSES
        from system.db.database import db as _db
        from flask import g
        for row in _DEFAULT_STATUSES[:4]:
            _db.session.add(TaskStatus(
                workspace_id=g.workspace_id,
                organization_id=g.organization_id,
                code=row["code"], label=row["label"], color=row["color"],
                sort_order=row["sort_order"], is_done=row["is_done"],
                is_default=row["is_default"],
            ))
        _db.session.commit()

        ts, err = TaskStatus.add(label="Blocked", code="blocked", color="#cc0000")
        assert err is None
        assert ts is not None
        assert ts.label == "Blocked"
        assert ts.code == "blocked"

    def test_add_enforces_max_cap(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        # All 5 slots used — adding another must fail
        ts, err = TaskStatus.add(label="Extra", code="extra")
        assert ts is None
        assert "Maximum" in err

    def test_add_rejects_duplicate_code(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        # Remove one first to make room, then try a duplicate
        done = TaskStatus.get_done_status()
        # Designate another as done before deleting
        other = TaskStatus.scoped().filter(TaskStatus.id != done.id).first()
        other.is_done = True
        done.is_done = False
        db.session.commit()
        TaskStatus.delete(done.id)

        ts, err = TaskStatus.add(label="Dup", code="todo")
        assert ts is None
        assert "already exists" in err

    def test_update_label_and_color(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        target = TaskStatus.scoped().filter_by(code="on_hold").first()
        ok, err = TaskStatus.update(
            target.id, label="Paused", color="#aabbcc",
            is_done=False, is_default=False,
        )
        assert ok is True
        assert err is None
        db.session.refresh(target)
        assert target.label == "Paused"
        assert target.color == "#aabbcc"

    def test_update_cannot_remove_only_done(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        done = TaskStatus.get_done_status()
        ok, err = TaskStatus.update(
            done.id, label=done.label, color=done.color,
            is_done=False, is_default=False,
        )
        assert ok is False
        assert "done flag" in err

    def test_update_cannot_remove_only_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        default = TaskStatus.get_default()
        ok, err = TaskStatus.update(
            default.id, label=default.label, color=default.color,
            is_done=False, is_default=False,
        )
        assert ok is False
        assert "default" in err

    def test_delete_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        # Designate another status as done before deleting the current done status
        done = TaskStatus.get_done_status()
        other = TaskStatus.scoped().filter(
            TaskStatus.id != done.id, TaskStatus.is_done == False  # noqa: E712
        ).first()
        other.is_done = True
        done.is_done = False
        db.session.commit()

        ok, err = TaskStatus.delete(done.id)
        assert ok is True
        assert err is None
        assert TaskStatus.scoped().filter_by(id=done.id).first() is None

    def test_delete_blocks_if_in_use(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus
        from modules.base.tasks.models.task import Task
        from flask import g

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        # Create a task using "on_hold"
        task = Task(
            title="Blocked task",
            raised_by_id=seeded_workspace["membership"].id,
            assignee_id=seeded_workspace["membership"].id,
            workspace_id=g.workspace_id,
            organization_id=g.organization_id,
            workflow_status="on_hold",
        )
        db.session.add(task)
        db.session.commit()

        on_hold = TaskStatus.scoped().filter_by(code="on_hold").first()
        ok, err = TaskStatus.delete(on_hold.id)
        assert ok is False
        assert "task(s)" in err

    def test_delete_blocks_last_status(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus
        from flask import g

        _setup_g(seeded_workspace)
        # Add only one status manually
        ts = TaskStatus(
            workspace_id=g.workspace_id,
            organization_id=g.organization_id,
            code="solo", label="Solo", color="#000000",
            sort_order=1, is_done=True, is_default=True,
        )
        db.session.add(ts)
        db.session.commit()

        ok, err = TaskStatus.delete(ts.id)
        assert ok is False
        assert "last" in err

    def test_delete_blocks_only_done(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        done = TaskStatus.get_done_status()
        ok, err = TaskStatus.delete(done.id)
        assert ok is False
        assert "done status" in err

    def test_set_default(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        non_default = TaskStatus.scoped().filter_by(is_default=False).first()
        ok, err = TaskStatus.set_default(non_default.id)
        assert ok is True
        db.session.refresh(non_default)
        assert non_default.is_default is True
        # Previous default cleared
        assert TaskStatus.scoped().filter_by(is_default=True).count() == 1

    def test_set_done(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        non_done = TaskStatus.scoped().filter_by(is_done=False).first()
        ok, err = TaskStatus.set_done(non_done.id)
        assert ok is True
        db.session.refresh(non_done)
        assert non_done.is_done is True
        # Previous done status cleared
        assert TaskStatus.scoped().filter_by(is_done=True).count() == 1

    def test_bulk_reorder(self, app, db_session, seeded_workspace):
        from modules.base.tasks.models.task_status import TaskStatus

        _setup_g(seeded_workspace)
        TaskStatus.seed_defaults()
        db.session.commit()

        statuses = TaskStatus.get_for_workspace()
        # Reverse the order
        items = [{"id": s.id, "sort_order": len(statuses) - i} for i, s in enumerate(statuses)]
        TaskStatus.bulk_reorder(items)

        refreshed = TaskStatus.scoped().order_by(TaskStatus.sort_order).all()
        assert refreshed[0].sort_order < refreshed[-1].sort_order
