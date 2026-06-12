# -----------------------------------------------------------------------------
# sparQ — Tasks: Raised by Me projection queries (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import select

from system.db.database import db


@dataclass(frozen=True)
class RaisedTaskRow:
    """Flat projection of a task raised by the current member."""

    id: int
    title: str
    urgency_tier: int
    is_blocker: bool
    context_note: str | None
    due_date: date | None
    created_at: datetime
    status: str
    raised_by_id: int | None
    raised_by_first_name: str | None
    raised_by_last_name: str | None
    assignee_id: int | None
    assignee_first_name: str | None
    assignee_last_name: str | None
    project_id: int | None
    project_name: str | None
    broadcast_group_id: str | None

    @property
    def is_system_raised(self) -> bool:
        return self.raised_by_id is None

    def time_ago(self) -> str:
        diff = datetime.utcnow() - self.created_at
        if diff.days > 0:
            return f"{diff.days}d ago" if diff.days > 1 else "1d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago" if hours > 1 else "1h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago" if minutes > 1 else "1m ago"
        return "just now"


def get_raised_open(member_id: int, organization_id: UUID, workspace_id: UUID) -> list[RaisedTaskRow]:
    """Return open action items raised by the given member."""
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.projects.models.project import Project

    RaisedBy = db.aliased(WorkspaceUser)
    RaisedByUser = db.aliased(User)
    Assignee = db.aliased(WorkspaceUser)
    AssigneeUser = db.aliased(User)

    stmt = (
        select(
            Task.id,
            Task.title,
            Task.urgency_tier,
            Task.is_blocker,
            Task.context_note,
            Task.due_date,
            Task.created_at,
            Task.status,
            Task.raised_by_id,
            RaisedByUser.first_name.label("raised_by_first_name"),
            RaisedByUser.last_name.label("raised_by_last_name"),
            Task.assignee_id,
            AssigneeUser.first_name.label("assignee_first_name"),
            AssigneeUser.last_name.label("assignee_last_name"),
            Task.project_id,
            Project.name.label("project_name"),
            Task.broadcast_group_id,
        )
        .outerjoin(RaisedBy, Task.raised_by_id == RaisedBy.id)
        .outerjoin(RaisedByUser, RaisedBy.user_id == RaisedByUser.id)
        .outerjoin(Assignee, Task.assignee_id == Assignee.id)
        .outerjoin(AssigneeUser, Assignee.user_id == AssigneeUser.id)
        .outerjoin(Project, Task.project_id == Project.id)
        .where(
            Task.raised_by_id == member_id,
            Task.status == "open",
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
        )
        .order_by(Task.urgency_tier.asc(), Task.created_at.asc())
    )

    return [RaisedTaskRow(*row) for row in db.session.execute(stmt).all()]


def get_raised_closed(member_id: int, organization_id: UUID, workspace_id: UUID) -> list[RaisedTaskRow]:
    """Return closed action items raised by the given member."""
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.projects.models.project import Project

    RaisedBy = db.aliased(WorkspaceUser)
    RaisedByUser = db.aliased(User)
    Assignee = db.aliased(WorkspaceUser)
    AssigneeUser = db.aliased(User)

    stmt = (
        select(
            Task.id,
            Task.title,
            Task.urgency_tier,
            Task.is_blocker,
            Task.context_note,
            Task.due_date,
            Task.created_at,
            Task.status,
            Task.raised_by_id,
            RaisedByUser.first_name.label("raised_by_first_name"),
            RaisedByUser.last_name.label("raised_by_last_name"),
            Task.assignee_id,
            AssigneeUser.first_name.label("assignee_first_name"),
            AssigneeUser.last_name.label("assignee_last_name"),
            Task.project_id,
            Project.name.label("project_name"),
            Task.broadcast_group_id,
        )
        .outerjoin(RaisedBy, Task.raised_by_id == RaisedBy.id)
        .outerjoin(RaisedByUser, RaisedBy.user_id == RaisedByUser.id)
        .outerjoin(Assignee, Task.assignee_id == Assignee.id)
        .outerjoin(AssigneeUser, Assignee.user_id == AssigneeUser.id)
        .outerjoin(Project, Task.project_id == Project.id)
        .where(
            Task.raised_by_id == member_id,
            Task.status != "open",
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
        )
        .order_by(Task.resolved_at.desc())
    )

    return [RaisedTaskRow(*row) for row in db.session.execute(stmt).all()]
