# -----------------------------------------------------------------------------
# sparQ — People: Team Directory projection queries (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import aliased

from system.db.database import db


@dataclass(frozen=True)
class DirectoryMemberRow:
    """Flat projection of a team member for the directory listing."""

    user_id: int
    first_name: str
    last_name: str
    email: str
    member_id: int
    position: str | None
    department: str | None
    bio: str | None
    working_style: str | None
    status: str
    clock_pin: str | None
    phone: str | None
    flow_status: str


@dataclass(frozen=True)
class DirectoryStats:
    """Aggregate status counts for the directory filter badges."""

    total_count: int
    active_count: int
    on_leave_count: int
    terminated_count: int
    contractor_count: int


def get_directory_members(
    organization_id: UUID,
    workspace_id: UUID,
    search: str = "",
    status_filter: str = "",
) -> list[DirectoryMemberRow]:
    """Return team directory members with optional search and status filtering."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.core.models.user_setting import UserSetting

    FlowSetting = aliased(UserSetting)

    stmt = (
        select(
            User.id.label("user_id"),
            User.first_name,
            User.last_name,
            User.email,
            WorkspaceUser.id.label("member_id"),
            WorkspaceUser.position,
            WorkspaceUser.department,
            WorkspaceUser.bio,
            WorkspaceUser.working_style,
            WorkspaceUser.status,
            WorkspaceUser.clock_pin,
            WorkspaceUser.phone,
            func.coalesce(FlowSetting.value, "free").label("flow_status"),
        )
        .join(WorkspaceUser, WorkspaceUser.user_id == User.id)
        .outerjoin(
            FlowSetting,
            db.and_(
                FlowSetting.user_id == User.id,
                FlowSetting.key == "flow_status",
                FlowSetting.workspace_id == workspace_id,
            ),
        )
        .where(
            WorkspaceUser.workspace_id == workspace_id,
            WorkspaceUser.organization_id == organization_id,
            WorkspaceUser.deleted_at.is_(None),
        )
    )

    if search:
        search_term = f"%{search}%"
        stmt = stmt.where(
            db.or_(
                User.first_name.ilike(search_term),
                User.last_name.ilike(search_term),
                User.email.ilike(search_term),
            )
        )

    if status_filter:
        stmt = stmt.where(WorkspaceUser.status == status_filter)

    stmt = stmt.order_by(User.first_name)

    return [DirectoryMemberRow(*row) for row in db.session.execute(stmt).all()]


def get_directory_stats(organization_id: UUID, workspace_id: UUID) -> DirectoryStats:
    """Return aggregate status counts for directory filter badges."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    row = db.session.execute(
        select(
            func.count(
                case((WorkspaceUser.status != "INACTIVE", 1))
            ).label("total_count"),
            func.count(
                case((WorkspaceUser.status == "ACTIVE", 1))
            ).label("active_count"),
            func.count(
                case((WorkspaceUser.status == "ON_LEAVE", 1))
            ).label("on_leave_count"),
            func.count(
                case((WorkspaceUser.status == "TERMINATED", 1))
            ).label("terminated_count"),
            func.count(
                case((WorkspaceUser.type == "CONTRACTOR", 1))
            ).label("contractor_count"),
        )
        .where(
            WorkspaceUser.workspace_id == workspace_id,
            WorkspaceUser.organization_id == organization_id,
            WorkspaceUser.deleted_at.is_(None),
        )
    ).one()

    return DirectoryStats(*row)
