# -----------------------------------------------------------------------------
# sparQ — Updates: Feed projection queries (DB Access Standards §5.2)
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from system.db.database import db


# ---------------------------------------------------------------------------
# Member Filter Projection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MemberRow:
    """Flat projection of a team member for filter dropdowns and modals."""

    id: int
    first_name: str
    last_name: str
    avatar_color: str | None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


def get_active_members(
    organization_id: UUID,
    workspace_id: UUID,
) -> list[MemberRow]:
    """Return active team members as flat projections (no ORM lazy-load risk)."""
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.core.models.user import User

    stmt = (
        select(
            WorkspaceUser.id,
            User.first_name,
            User.last_name,
            User._avatar_color.label("avatar_color"),
        )
        .join(User, User.id == WorkspaceUser.user_id)
        .where(
            WorkspaceUser.organization_id == organization_id,
            WorkspaceUser.workspace_id == workspace_id,
            WorkspaceUser.status == EmployeeStatus.ACTIVE,
            WorkspaceUser.deleted_at.is_(None),
        )
        .order_by(WorkspaceUser.id)
    )

    rows = db.session.execute(stmt).all()
    return [
        MemberRow(id=r.id, first_name=r.first_name, last_name=r.last_name, avatar_color=r.avatar_color)
        for r in rows
    ]


def build_ack_member_info(members: list[MemberRow]) -> list[tuple[int, str, str]]:
    """Convert MemberRow list to (id, initials, display_name) tuples for ack grids."""
    return [
        (m.id,
         ((m.first_name or "")[:1] + (m.last_name or "")[:1]).upper(),
         f"{m.first_name or ''} {m.last_name or ''}".strip())
        for m in members
    ]


@dataclass(frozen=True)
class FeedPostRow:
    """Flat projection of an update post for feed rendering."""

    id: int
    post_type: str
    is_anonymous: bool
    created_at: datetime
    payload: dict
    member_id: int | None
    member_user_id: int | None
    member_first_name: str | None
    member_last_name: str | None
    member_avatar_color: str | None
    template_id: int
    template_name: str
    template_fields: list
    template_post_type: str
    template_schedule_type: str | None
    area_name: str | None
    area_emoji: str | None
    area_color: str | None

    @property
    def member_full_name(self) -> str | None:
        if not self.member_first_name:
            return None
        parts = [self.member_first_name]
        if self.member_last_name:
            parts.append(self.member_last_name)
        return " ".join(parts)

    def time_ago(self) -> str:
        now = datetime.utcnow()
        diff = now - self.created_at
        if diff.days > 0:
            return f"{diff.days}d ago" if diff.days > 1 else "1d ago"
        elif diff.seconds >= 3600:
            hours = diff.seconds // 3600
            return f"{hours}h ago" if hours > 1 else "1h ago"
        elif diff.seconds >= 60:
            minutes = diff.seconds // 60
            return f"{minutes}m ago" if minutes > 1 else "1m ago"
        return "just now"

    def preview_text(self) -> str:
        return " · ".join(
            text for _, _, items in self._preview_parts() for text in items
        )

    def _preview_parts(self) -> list[tuple[str, str, list[str]]]:
        if not self.payload:
            return []
        if self.post_type == "board":
            title = str(self.payload.get("title") or "")
            return [("", "title", [title])] if title else []
        fields = self.template_fields or []
        if fields:
            parts: list[tuple[str, str, list[str]]] = []
            for field in fields:
                key = field.get("key")
                ftype = field.get("type")
                label = field.get("label", "")
                if not key:
                    continue
                val = self.payload.get(key)
                if not val:
                    continue
                if ftype == "structured_list" and isinstance(val, list):
                    texts = []
                    for item in val:
                        if isinstance(item, dict):
                            text = (item.get("text") or "").strip()
                            if text:
                                texts.append(text)
                        elif isinstance(item, str) and item.strip():
                            texts.append(item.strip())
                    if texts:
                        parts.append((label, ftype, texts))
                elif ftype == "bullets" and isinstance(val, list):
                    texts = [str(b).strip() for b in val if str(b).strip()]
                    if texts:
                        parts.append((label, ftype, texts))
                elif ftype in ("title", "text", "text_audio", None):
                    if isinstance(val, str) and val.strip():
                        parts.append((label, ftype or "text", [val.strip()]))
            return parts
        texts = [v.strip() for v in self.payload.values()
                 if isinstance(v, str) and v.strip()]
        return [("", "text", texts)] if texts else []


def _coerce_fields(raw: object) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return raw if isinstance(raw, list) else []


def get_feed_posts(
    organization_id: UUID,
    workspace_id: UUID,
    post_type: list[str] | str | None = None,
    template_id: int | None = None,
    member_id: int | None = None,
    area_id: int | None = None,
    today_only: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[FeedPostRow], bool]:
    """Return feed posts with member and template info, plus a has_more flag."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from modules.base.updates.models.area import UpdateArea
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.template import UpdateTemplate

    MemberTS = aliased(WorkspaceUser)
    MemberUser = aliased(User)
    now = datetime.utcnow()

    stmt = (
        select(
            UpdatePost.id,
            UpdatePost.post_type,
            UpdatePost.is_anonymous,
            UpdatePost.created_at,
            UpdatePost.payload,
            UpdatePost.member_id,
            MemberUser.id.label("member_user_id"),
            MemberUser.first_name.label("member_first_name"),
            MemberUser.last_name.label("member_last_name"),
            MemberUser._avatar_color.label("member_avatar_color"),
            UpdateTemplate.id.label("template_id"),
            UpdateTemplate.name.label("template_name"),
            UpdateTemplate._fields.label("template_fields"),
            UpdateTemplate.post_type.label("template_post_type"),
            UpdateTemplate.schedule_type.label("template_schedule_type"),
            UpdateArea.name.label("area_name"),
            UpdateArea.emoji.label("area_emoji"),
            UpdateArea.color.label("area_color"),
        )
        .join(UpdateTemplate, UpdateTemplate.id == UpdatePost.template_id)
        .outerjoin(MemberTS, MemberTS.id == UpdatePost.member_id)
        .outerjoin(MemberUser, MemberUser.id == MemberTS.user_id)
        .outerjoin(UpdateArea, UpdateArea.id == UpdatePost.area_id)
        .where(
            UpdatePost.organization_id == organization_id,
            UpdatePost.workspace_id == workspace_id,
            db.or_(UpdatePost.expires_at.is_(None), UpdatePost.expires_at > now),
            UpdatePost.channel_id.is_(None),
            UpdatePost.parent_id.is_(None),
        )
    )

    if post_type:
        if isinstance(post_type, (list, tuple)):
            stmt = stmt.where(UpdatePost.post_type.in_(post_type))
        else:
            stmt = stmt.where(UpdatePost.post_type == post_type)

    if template_id:
        stmt = stmt.where(UpdatePost.template_id == template_id)
    if member_id:
        stmt = stmt.where(UpdatePost.member_id == member_id)
    if area_id:
        stmt = stmt.where(UpdatePost.area_id == area_id)
    if today_only:
        from datetime import date
        stmt = stmt.where(func.date(UpdatePost.created_at) == date.today())

    stmt = stmt.order_by(UpdatePost.created_at.desc())

    if limit:
        stmt = stmt.offset(offset).limit(limit + 1)
        rows = db.session.execute(stmt).all()
        has_more = len(rows) > limit
        if has_more:
            rows = rows[:limit]
    else:
        rows = db.session.execute(stmt).all()
        has_more = False

    return [
        FeedPostRow(
            id=r.id,
            post_type=r.post_type,
            is_anonymous=r.is_anonymous,
            created_at=r.created_at,
            payload=r.payload or {},
            member_id=r.member_id,
            member_user_id=r.member_user_id,
            member_first_name=r.member_first_name,
            member_last_name=r.member_last_name,
            member_avatar_color=r.member_avatar_color,
            template_id=r.template_id,
            template_name=r.template_name,
            template_fields=_coerce_fields(r.template_fields),
            template_post_type=r.template_post_type,
            template_schedule_type=r.template_schedule_type,
            area_name=r.area_name,
            area_emoji=r.area_emoji,
            area_color=r.area_color,
        )
        for r in rows
    ], has_more
