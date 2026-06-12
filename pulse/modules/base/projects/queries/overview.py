# -----------------------------------------------------------------------------
# sparQ — Projects: Overview projection queries (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from uuid import UUID


def _coerce_dt(value: object) -> datetime | None:
    """Return a datetime from *value*, handling SQLite's string storage."""
    if value is None or isinstance(value, datetime):
        return value  # type: ignore[return-value]
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None

from sqlalchemy import case, func, select, union_all
from sqlalchemy.orm import aliased

from system.db.database import db

# Fallback maps used when no status_config is provided.
_STATUS_COLORS = {
    "upcoming": "#6b7280",
    "current": "#2563eb",
    "on_hold": "#f59e0b",
    "archived": "#16a34a",
}

_STATUS_LABELS = {
    "current": "In Progress",
    "upcoming": "To Do",
    "on_hold": "On Hold",
    "archived": "Completed",
}


@dataclass(frozen=True)
class ProjectMemberAvatar:
    """Minimal member info for project avatar chips."""

    member_id: int
    first_name: str
    last_name: str | None
    avatar_color: str | None


@dataclass(frozen=True)
class ProjectOverviewRow:
    """Flat projection of a project with aggregated item counts and activity."""

    id: int
    name: str
    emoji: str | None
    is_private: bool
    status: str
    color: str | None
    owner_id: int | None
    owner_first_name: str | None
    created_by_id: int | None
    open_count: int
    in_progress_count: int
    overdue_count: int
    eta: date | None
    last_activity_at: datetime | None
    stale_days: int = 3
    members: list[ProjectMemberAvatar] = field(default_factory=list)
    involved_member_ids: list[int] = field(default_factory=list)
    # Workspace-specific status config: {code: {"label": ..., "color": ..., "is_archived": ...}}
    status_config: dict = field(default_factory=dict)

    @property
    def status_color(self) -> str:
        cfg = self.status_config.get(self.status)
        if cfg:
            return cfg.get("color", "#6b7280")
        return _STATUS_COLORS.get(self.status, "#6b7280")

    @property
    def status_label(self) -> str:
        cfg = self.status_config.get(self.status)
        if cfg:
            return cfg.get("label", self.status)
        return _STATUS_LABELS.get(self.status, self.status)

    @property
    def is_stale(self) -> bool:
        if self.last_activity_at is None:
            return False
        # Stale applies to non-archived statuses only
        cfg = self.status_config.get(self.status)
        if cfg and cfg.get("is_archived", False):
            return False
        if not cfg and self.status == "archived":
            return False
        return self.last_activity_at < datetime.utcnow() - timedelta(days=self.stale_days)

    def last_activity_label(self) -> str | None:
        if self.last_activity_at is None:
            return None
        delta = datetime.utcnow() - self.last_activity_at
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days < 7:
            return f"{days}d ago"
        if days < 30:
            weeks = days // 7
            return f"{weeks}w ago"
        return self.last_activity_at.strftime("%b %d")

    def eta_label(self) -> str | None:
        """Format the ETA date for display.

        Returns:
            Short date string like "May 28" or "May 28, 2027", or None.
        """
        if self.eta is None:
            return None
        if self.eta.year != date.today().year:
            return self.eta.strftime("%b %-d, %Y")
        return self.eta.strftime("%b %-d")


def get_project_overview(
    organization_id: UUID,
    workspace_id: UUID,
    current_member_id: int,
    stale_days: int = 3,
    status_config: dict | None = None,
) -> list[ProjectOverviewRow]:
    """Return projects with aggregated item counts, activity timestamps, and member avatars.

    Args:
        organization_id: Current org UUID.
        workspace_id: Current workspace UUID.
        current_member_id: WorkspaceUser.id of the viewer (for privacy filter).
        stale_days: Idle threshold for the stale indicator.
        status_config: Dict of {code: {"label": str, "color": str, "is_archived": bool}}.
            Built by the caller from ProjectStatus.get_for_workspace(). When None,
            the function falls back to module-level dicts.
    """
    if status_config is None:
        status_config = {
            code: {"label": label, "color": color, "is_archived": code == "archived"}
            for code, label, color in [
                ("upcoming", _STATUS_LABELS["upcoming"], _STATUS_COLORS["upcoming"]),
                ("current", _STATUS_LABELS["current"], _STATUS_COLORS["current"]),
                ("on_hold", _STATUS_LABELS["on_hold"], _STATUS_COLORS["on_hold"]),
                ("archived", _STATUS_LABELS["archived"], _STATUS_COLORS["archived"]),
            ]
        }
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.projects.models.project import Project
    from modules.base.updates.models.post import UpdatePost

    OwnerMember = aliased(WorkspaceUser)
    OwnerUser = aliased(User)
    today = date.today()

    ai_agg = (
        select(
            Task.project_id,
            func.count(case(
                (Task.workflow_status.in_(["todo", "in_progress"]), 1),
            )).label("open_count"),
            func.count(case(
                (Task.workflow_status == "in_progress", 1),
            )).label("in_progress_count"),
            func.count(case(
                (db.and_(
                    Task.status == "open",
                    Task.due_date.isnot(None),
                    Task.due_date < today,
                ), 1),
            )).label("overdue_count"),
            func.max(case(
                (Task.status == "open", Task.due_date),
            )).label("eta"),
            func.greatest(
                func.max(Task.created_at),
                func.max(Task.resolved_at),
            ).label("last_ai_activity"),
        )
        .where(
            Task.project_id.isnot(None),
            Task.organization_id == organization_id,
            Task.workspace_id == workspace_id,
        )
        .group_by(Task.project_id)
        .subquery()
    )

    post_agg = (
        select(
            UpdatePost.channel_id,
            func.max(UpdatePost.created_at).label("last_post_at"),
        )
        .where(
            UpdatePost.channel_id.isnot(None),
            UpdatePost.organization_id == organization_id,
            UpdatePost.workspace_id == workspace_id,
        )
        .group_by(UpdatePost.channel_id)
        .subquery()
    )

    activity_expr = func.greatest(
        Project.created_at,
        func.coalesce(ai_agg.c.last_ai_activity, Project.created_at),
        func.coalesce(post_agg.c.last_post_at, Project.created_at),
    )

    stmt = (
        select(
            Project.id,
            Project.name,
            Project.emoji,
            Project.is_private,
            Project.status,
            Project.color,
            Project.channel_id,
            Project.owner_id,
            Project.created_by_id,
            OwnerUser.first_name.label("owner_first_name"),
            func.coalesce(ai_agg.c.open_count, 0).label("open_count"),
            func.coalesce(ai_agg.c.in_progress_count, 0).label("in_progress_count"),
            func.coalesce(ai_agg.c.overdue_count, 0).label("overdue_count"),
            ai_agg.c.eta,
            activity_expr.label("last_activity_at"),
        )
        .outerjoin(OwnerMember, OwnerMember.id == Project.owner_id)
        .outerjoin(OwnerUser, OwnerUser.id == OwnerMember.user_id)
        .outerjoin(ai_agg, ai_agg.c.project_id == Project.id)
        .outerjoin(post_agg, post_agg.c.channel_id == Project.channel_id)
        .where(
            Project.organization_id == organization_id,
            Project.workspace_id == workspace_id,
            db.or_(
                Project.is_private == False,  # noqa: E712
                Project.created_by_id == current_member_id,
                Project.owner_id == current_member_id,
            ),
        )
        .order_by(activity_expr.desc())
    )

    raw_rows = db.session.execute(stmt).all()
    project_ids = [r.id for r in raw_rows]

    members_map = _get_project_members(project_ids, organization_id, workspace_id)
    involved_map = _get_project_involved_members(project_ids, organization_id, workspace_id)

    return [
        ProjectOverviewRow(
            id=r.id,
            name=r.name,
            emoji=r.emoji,
            is_private=r.is_private,
            status=r.status,
            color=r.color,
            owner_id=r.owner_id,
            owner_first_name=r.owner_first_name,
            created_by_id=r.created_by_id,
            open_count=r.open_count,
            in_progress_count=r.in_progress_count,
            overdue_count=r.overdue_count,
            eta=r.eta,
            last_activity_at=_coerce_dt(r.last_activity_at),
            stale_days=stale_days,
            members=members_map.get(r.id, []),
            involved_member_ids=involved_map.get(r.id, []),
            status_config=status_config,
        )
        for r in raw_rows
    ]


def _get_project_members(
    project_ids: list[int],
    organization_id: UUID,
    workspace_id: UUID,
) -> dict[int, list[ProjectMemberAvatar]]:
    """Batch-fetch up to 5 distinct member avatars per project."""
    if not project_ids:
        return {}

    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.projects.models.project import Project
    from modules.base.updates.models.post import UpdatePost

    assignees = select(
        Task.project_id.label("project_id"),
        Task.assignee_id.label("member_id"),
    ).where(
        Task.project_id.in_(project_ids),
        Task.assignee_id.isnot(None),
        Task.organization_id == organization_id,
        Task.workspace_id == workspace_id,
    )

    raisers = select(
        Task.project_id.label("project_id"),
        Task.raised_by_id.label("member_id"),
    ).where(
        Task.project_id.in_(project_ids),
        Task.raised_by_id.isnot(None),
        Task.organization_id == organization_id,
        Task.workspace_id == workspace_id,
    )

    post_authors = (
        select(
            Project.id.label("project_id"),
            UpdatePost.member_id.label("member_id"),
        )
        .join(UpdatePost, UpdatePost.channel_id == Project.channel_id)
        .where(
            Project.id.in_(project_ids),
            Project.channel_id.isnot(None),
            UpdatePost.member_id.isnot(None),
            UpdatePost.organization_id == organization_id,
            UpdatePost.workspace_id == workspace_id,
        )
    )

    all_members_sq = union_all(assignees, raisers, post_authors).subquery()

    stmt = (
        select(
            all_members_sq.c.project_id,
            WorkspaceUser.id.label("member_id"),
            User.first_name,
            User.last_name,
            User._avatar_color.label("avatar_color"),
        )
        .select_from(all_members_sq)
        .join(WorkspaceUser, WorkspaceUser.id == all_members_sq.c.member_id)
        .join(User, User.id == WorkspaceUser.user_id)
        .distinct()
    )

    result: dict[int, list[ProjectMemberAvatar]] = {}
    for row in db.session.execute(stmt).all():
        pid = row.project_id
        if pid not in result:
            result[pid] = []
        if len(result[pid]) < 5:
            result[pid].append(ProjectMemberAvatar(
                member_id=row.member_id,
                first_name=row.first_name,
                last_name=row.last_name,
                avatar_color=row.avatar_color,
            ))

    return result


def _get_project_involved_members(
    project_ids: list[int],
    organization_id: int,
    workspace_id: int,
) -> dict[int, list[int]]:
    """Batch-fetch involved member IDs per project.

    Includes: owner, creator, co-owners, followers, and task participants
    (assignees/raisers). This powers the filter pills so clicking a member
    shows every project they touch.
    """
    if not project_ids:
        return {}

    from modules.base.tasks.models.task import Task
    from modules.base.projects.models.project import Project
    from modules.base.projects.models.follower import project_follower
    from modules.base.projects.models.co_owner import project_co_owner

    owners = select(
        Project.id.label("project_id"),
        Project.owner_id.label("member_id"),
    ).where(
        Project.id.in_(project_ids),
        Project.owner_id.isnot(None),
    )

    creators = select(
        Project.id.label("project_id"),
        Project.created_by_id.label("member_id"),
    ).where(
        Project.id.in_(project_ids),
        Project.created_by_id.isnot(None),
    )

    co_owners = select(
        project_co_owner.c.project_id.label("project_id"),
        project_co_owner.c.member_id.label("member_id"),
    ).where(project_co_owner.c.project_id.in_(project_ids))

    followers = select(
        project_follower.c.project_id.label("project_id"),
        project_follower.c.member_id.label("member_id"),
    ).where(project_follower.c.project_id.in_(project_ids))

    assignees = select(
        Task.project_id.label("project_id"),
        Task.assignee_id.label("member_id"),
    ).where(
        Task.project_id.in_(project_ids),
        Task.assignee_id.isnot(None),
        Task.organization_id == organization_id,
        Task.workspace_id == workspace_id,
    )

    raisers = select(
        Task.project_id.label("project_id"),
        Task.raised_by_id.label("member_id"),
    ).where(
        Task.project_id.in_(project_ids),
        Task.raised_by_id.isnot(None),
        Task.organization_id == organization_id,
        Task.workspace_id == workspace_id,
    )

    all_sq = union_all(owners, creators, co_owners, followers, assignees, raisers).subquery()
    stmt = select(all_sq.c.project_id, all_sq.c.member_id).distinct()

    result: dict[int, list[int]] = {}
    for row in db.session.execute(stmt).all():
        result.setdefault(row.project_id, []).append(row.member_id)
    return result
