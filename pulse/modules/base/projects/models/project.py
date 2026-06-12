# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Project model — lightweight container grouping action items and sync posts.

A Project is a named, status-bearing bucket that holds action items and
captures related team activity. Projects accumulate organically from real
work — team members tag existing items and posts as they go.

Classes:
    Project: Core project entity.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Self
from system.db.raise_on_lazy import LAZY

if TYPE_CHECKING:
    from sqlalchemy.sql.elements import ColumnElement

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from .follower import project_follower
from .co_owner import project_co_owner


@ModelRegistry.register
class Project(db.Model, WorkspaceMixin):
    """Lightweight project container.

    Attributes:
        name: Project name (max 200 chars).
        description: Optional description (max 500 chars).
        status: 'current', 'upcoming', 'on_hold', or 'archived'.
        color: Optional hex color.
        emoji: Optional emoji.
        owner_id: FK to workspace_user — project owner.
        channel_id: FK to sync_channel — auto-created dedicated chat channel.
        archived_at: Timestamp when archived (NULL = visible).
        created_by_id: FK to workspace_user who created it.
    """

    __tablename__ = "project"

    __table_args__ = (
        db.Index("ix_project_org_ws_status", "organization_id", "workspace_id", "status"),
        db.Index("ix_project_owner", "owner_id", "status"),
        db.Index("ix_project_channel", "channel_id"),
    )

    STATUS_CURRENT = "current"
    STATUS_UPCOMING = "upcoming"
    STATUS_ON_HOLD = "on_hold"
    STATUS_ARCHIVED = "archived"

    VALID_STATUSES = [STATUS_CURRENT, STATUS_UPCOMING, STATUS_ON_HOLD, STATUS_ARCHIVED]

    # Fallback label/color maps used when project_status table is empty (dev/test).
    STATUS_LABELS = {
        STATUS_CURRENT: "In Progress",
        STATUS_UPCOMING: "To Do",
        STATUS_ON_HOLD: "On Hold",
        STATUS_ARCHIVED: "Completed",
    }

    STATUS_COLORS = {
        STATUS_UPCOMING: "#6b7280",
        STATUS_CURRENT: "#2563eb",
        STATUS_ON_HOLD: "#f59e0b",
        STATUS_ARCHIVED: "#16a34a",
    }

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), nullable=False, default=STATUS_CURRENT)
    color = db.Column(db.String(10), nullable=True)
    emoji = db.Column(db.String(10), nullable=True)

    owner_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id", ondelete="SET NULL"), nullable=True
    )
    channel_id = db.Column(
        db.Integer, db.ForeignKey("update_channel.id", ondelete="SET NULL"), nullable=True
    )

    is_private = db.Column(db.Boolean, nullable=False, default=False)

    archived_at = db.Column(db.DateTime, nullable=True)

    created_by_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    owner = db.relationship("WorkspaceUser", foreign_keys=[owner_id], lazy=LAZY)
    created_by = db.relationship("WorkspaceUser", foreign_keys=[created_by_id], lazy=LAZY)
    channel = db.relationship(
        "UpdateChannel",
        foreign_keys=[channel_id],
        lazy=LAZY,
    )
    followers = db.relationship(
        "WorkspaceUser",
        secondary=project_follower,
        backref=db.backref("followed_projects", lazy=LAZY),
        lazy=LAZY,
    )
    co_owners = db.relationship(
        "WorkspaceUser",
        secondary=project_co_owner,
        backref=db.backref("co_owned_projects", lazy=LAZY),
        lazy=LAZY,
    )

    # ── Follower Methods ───────────────────────────────────────────────────

    def get_followers(self) -> list:
        """Return followers with their user records eagerly loaded.

        Returns:
            List of WorkspaceUser instances following this project.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            WorkspaceUser.scoped()
            .join(project_follower, WorkspaceUser.id == project_follower.c.member_id)
            .filter(project_follower.c.project_id == self.id)
            .options(joinedload(WorkspaceUser.user))
            .all()
        )

    def can_follow(self, member_id: int) -> bool:
        """Return True if the member is allowed to follow this project.

        Private projects can only be followed by the owner, co-owners, or
        creator; public projects can be followed by any workspace member.
        """
        if not self.is_private:
            return True
        return member_id in (self.owner_id, self.created_by_id) or self.is_co_owner(member_id)

    # ── Co-Owner Methods ───────────────────────────────────────────────────

    def get_co_owners(self) -> list:
        """Return co-owners with their user records eagerly loaded.

        Returns:
            List of WorkspaceUser instances who are co-owners of this project.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            WorkspaceUser.scoped()
            .join(project_co_owner, WorkspaceUser.id == project_co_owner.c.member_id)
            .filter(project_co_owner.c.project_id == self.id)
            .options(joinedload(WorkspaceUser.user))
            .all()
        )

    def is_co_owner(self, member_id: int) -> bool:
        """Check whether a member is a co-owner of this project.

        Args:
            member_id: WorkspaceUser.id to check.

        Returns:
            True if the member is a co-owner.
        """
        result = db.session.execute(
            db.select(project_co_owner).where(
                project_co_owner.c.project_id == self.id,
                project_co_owner.c.member_id == member_id,
            )
        ).first()
        return result is not None

    def is_owner_or_co_owner(self, member_id: int) -> bool:
        """Check whether a member has owner-level access to this project.

        Returns True for the primary owner or any co-owner. Use this
        everywhere a permission check previously compared member_id to
        project.owner_id.

        Args:
            member_id: WorkspaceUser.id to check.

        Returns:
            True if the member is the primary owner or a co-owner.
        """
        return member_id == self.owner_id or self.is_co_owner(member_id)

    def add_co_owner(self, member_id: int) -> bool:
        """Add a member as a co-owner of this project.

        Args:
            member_id: WorkspaceUser.id to add.

        Returns:
            True if added, False if already a co-owner.
        """
        if self.is_co_owner(member_id):
            return False

        db.session.execute(
            project_co_owner.insert().values(
                project_id=self.id, member_id=member_id
            )
        )
        db.session.commit()

        try:
            from modules.base.core.models.workspace_user import WorkspaceUser
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            member = WorkspaceUser.scoped().filter_by(id=member_id).first()
            if member and member.user_id:
                SystemNotification.create(
                    title=self.name,
                    message=f"You've been added as a co-owner of {self.name}.",
                    type="info",
                    target_role="user",
                    user_id=member.user_id,
                    icon="fa-crown",
                    action_url=f"/projects/{self.id}/",
                    category=NotificationCategory.PROJECT_UPDATE,
                )
        except Exception:
            pass

        return True

    def remove_co_owner(self, member_id: int) -> bool:
        """Remove a member as a co-owner of this project.

        Does not affect the member's follower status.

        Args:
            member_id: WorkspaceUser.id to remove.

        Returns:
            True if removed, False if they were not a co-owner.
        """
        result = db.session.execute(
            project_co_owner.delete().where(
                project_co_owner.c.project_id == self.id,
                project_co_owner.c.member_id == member_id,
            )
        )
        db.session.commit()
        return result.rowcount > 0

    def is_follower(self, member_id: int) -> bool:
        """Check whether a member is following this project.

        Args:
            member_id: WorkspaceUser.id to check.

        Returns:
            True if the member follows this project.
        """
        result = db.session.execute(
            db.select(project_follower).where(
                project_follower.c.project_id == self.id,
                project_follower.c.member_id == member_id,
            )
        ).first()
        return result is not None

    def add_follower(self, member_id: int) -> bool:
        """Add a member as an interested party on this project.

        Also auto-follows the project's channel so the member receives
        email and push notifications via the existing UpdateFollow pipeline.

        Args:
            member_id: WorkspaceUser.id to add.

        Returns:
            True if added, False if already following.
        """
        if self.is_follower(member_id):
            return False

        db.session.execute(
            project_follower.insert().values(
                project_id=self.id, member_id=member_id
            )
        )
        db.session.commit()

        # Auto-follow the channel so notifications fire immediately
        if self.channel_id:
            try:
                from modules.base.updates.models.follow import UpdateFollow
                if not UpdateFollow.is_following("channel", self.channel_id, member_id):
                    UpdateFollow.toggle("channel", self.channel_id, member_id)
            except Exception:
                pass

        return True

    def remove_follower(self, member_id: int) -> bool:
        """Remove a member as an interested party on this project.

        Does not remove the channel follow — the member may have followed
        the channel independently, and the UI can handle that separately.

        Args:
            member_id: WorkspaceUser.id to remove.

        Returns:
            True if removed, False if they were not following.
        """
        result = db.session.execute(
            project_follower.delete().where(
                project_follower.c.project_id == self.id,
                project_follower.c.member_id == member_id,
            )
        )
        db.session.commit()
        return result.rowcount > 0

    # ── Properties ─────────────────────────────────────────────────────────

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def is_closed(self) -> bool:
        """True when the project's status is the workspace archive status."""
        try:
            from .project_status import ProjectStatus
            archived = ProjectStatus.get_archived_status()
            if archived:
                return self.status == archived.code
        except Exception:
            pass
        return self.status == self.STATUS_ARCHIVED

    @property
    def status_label(self) -> str:
        try:
            from .project_status import ProjectStatus
            for s in ProjectStatus.get_for_workspace():
                if s.code == self.status:
                    return s.label
        except Exception:
            pass
        return self.STATUS_LABELS.get(self.status, self.status)

    @property
    def status_color(self) -> str:
        try:
            from .project_status import ProjectStatus
            for s in ProjectStatus.get_for_workspace():
                if s.code == self.status:
                    return s.color
        except Exception:
            pass
        return self.STATUS_COLORS.get(self.status, "#6b7280")

    # ── State Transitions ──────────────────────────────────────────────────

    def archive(self) -> None:
        """Archive this project using the workspace's designated archive status."""
        try:
            from .project_status import ProjectStatus
            archived = ProjectStatus.get_archived_status()
            if archived:
                self.set_status(archived.code)
                return
        except Exception:
            pass
        self.set_status(self.STATUS_ARCHIVED)

    def unarchive(self) -> None:
        """Restore this project to the workspace's default status."""
        try:
            from .project_status import ProjectStatus
            default = ProjectStatus.get_default()
            if default:
                self.set_status(default.code)
                return
        except Exception:
            pass
        self.set_status(self.STATUS_CURRENT)

    def set_status(self, new_status: str) -> None:
        """Set project status and notify followers of the change.

        Moving to the archive status sets archived_at and locks the channel;
        moving away clears archived_at.

        Args:
            new_status: A code present in the workspace's project_status table.

        Raises:
            ValueError: If new_status is not a valid status code.
        """
        # Validate against DB statuses, fallback to hardcoded list
        try:
            from .project_status import ProjectStatus
            valid_codes = ProjectStatus.get_codes()
            if valid_codes and new_status not in valid_codes:
                raise ValueError(f"Invalid status: {new_status}")
            if not valid_codes and new_status not in self.VALID_STATUSES:
                raise ValueError(f"Invalid status: {new_status}")
            # Determine archive code from DB
            archived_status = ProjectStatus.get_archived_status()
            archive_code = archived_status.code if archived_status else self.STATUS_ARCHIVED
        except ValueError:
            raise
        except Exception:
            if new_status not in self.VALID_STATUSES:
                raise ValueError(f"Invalid status: {new_status}")
            archive_code = self.STATUS_ARCHIVED

        old_status = self.status
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if new_status == archive_code and not self.archived_at:
            self.archived_at = datetime.utcnow()
            if self.channel and hasattr(self.channel, 'is_private'):
                self.channel.is_private = True
        elif new_status != archive_code and self.archived_at:
            self.archived_at = None

        db.session.commit()

        if old_status != new_status:
            if new_status == self.STATUS_ON_HOLD and old_status != self.STATUS_ON_HOLD:
                self.cascade_tasks_to_on_hold()
            elif new_status == self.STATUS_UPCOMING and old_status == self.STATUS_ON_HOLD:
                self.cascade_tasks_to_todo()
            self._notify_followers_status_change(old_status, new_status)

    def cascade_tasks_to_on_hold(self) -> int:
        """Move open todo tasks (except Now priority) to on_hold when project enters On Hold.

        Returns:
            Number of tasks updated.
        """
        from modules.base.tasks.models.task import Task

        count = (
            Task.scoped()
            .filter(
                Task.project_id == self.id,
                Task.status == "open",
                Task.workflow_status == "todo",
                Task.urgency_tier != 1,
            )
            .update({"workflow_status": "on_hold"}, synchronize_session="fetch")
        )
        if count:
            db.session.commit()
        return count

    def cascade_tasks_to_todo(self) -> int:
        """Move open on_hold tasks back to todo when project returns to To Do.

        Returns:
            Number of tasks updated.
        """
        from modules.base.tasks.models.task import Task

        count = (
            Task.scoped()
            .filter(
                Task.project_id == self.id,
                Task.status == "open",
                Task.workflow_status == "on_hold",
            )
            .update({"workflow_status": "todo"}, synchronize_session="fetch")
        )
        if count:
            db.session.commit()
        return count

    def notify_followers_new_post(self, post, author_member) -> None:
        """Create in-app notifications for project followers when a channel post is made."""
        import logging
        log = logging.getLogger(__name__)

        followers = self.get_followers()
        log.info("[PROJECT] notify_followers_new_post: project=%s followers=%d", self.id, len(followers))
        if not followers:
            return

        author_name = (
            author_member.user.first_name
            if author_member and author_member.user
            else "Someone"
        )
        raw = getattr(post, "plain_text_content", None) or getattr(post, "content", None) or ""
        preview = raw[:80] + "…" if len(raw) > 80 else raw
        msg = f"{author_name}: {preview}" if preview else f"{author_name} posted in {self.name}"

        from modules.base.core.models.notification import NotificationCategory, SystemNotification
        for follower in followers:
            if not follower.user:
                continue
            if author_member and follower.id == author_member.id:
                continue
            SystemNotification.create(
                title=self.name,
                message=msg,
                type="info",
                target_role="user",
                user_id=follower.user_id,
                icon="fa-comment",
                action_url=f"/projects/{self.id}/?tab=log",
                category=NotificationCategory.PROJECT_UPDATE,
            )

    def _notify_followers_status_change(self, old_status: str, new_status: str) -> None:
        """Send push and in-app notifications to followers when project status changes.

        Args:
            old_status: Previous status value.
            new_status: New status value.
        """
        followers = self.get_followers()
        if not followers:
            return

        try:
            from .project_status import ProjectStatus
            label_map = {s.code: s.label for s in ProjectStatus.get_for_workspace()}
        except Exception:
            label_map = self.STATUS_LABELS
        old_label = label_map.get(old_status, old_status)
        new_label = label_map.get(new_status, new_status)

        for follower in followers:
            if not follower.user:
                continue
            try:
                from modules.base.core.models.notification import NotificationCategory, SystemNotification
                from modules.base.core.services.push_notification import send_push

                SystemNotification.create(
                    title=self.name,
                    message=f"Status changed from {old_label} to {new_label}",
                    type="info",
                    target_role="user",
                    user_id=follower.user_id,
                    icon="fa-circle-dot",
                    action_url=f"/projects/{self.id}/",
                    category=NotificationCategory.PROJECT_UPDATE,
                )
                send_push(
                    user_id=follower.user_id,
                    title=self.name,
                    body=f"Status changed from {old_label} to {new_label}",
                    url=f"/projects/{self.id}/",
                )
            except Exception:
                pass

    @staticmethod
    def is_channel_locked(channel) -> bool:
        """True iff the channel's linked project is closed.

        Used to gate channel-write operations (post creation, replies,
        reactions, follows, acknowledgments) when a project has been
        closed. Channels not linked to a project are never locked.
        """
        if channel is None or not channel.project_id:
            return False
        project = Project.scoped().filter_by(id=channel.project_id).first()
        if project is None:
            return False
        return project.is_closed

    # ── Queries ────────────────────────────────────────────────────────────

    @classmethod
    def _archive_code(cls) -> str:
        """Return the current workspace's archive status code.

        Falls back to STATUS_ARCHIVED if project_status table is unavailable.
        """
        try:
            from .project_status import ProjectStatus
            archived = ProjectStatus.get_archived_status()
            if archived:
                return archived.code
        except Exception:
            pass
        return cls.STATUS_ARCHIVED

    @classmethod
    def _visible_filter(cls):
        """Filter that excludes private projects not owned/co-owned by current user."""
        try:
            from flask_login import current_user
            from modules.base.core.models.workspace_user import WorkspaceUser

            member = WorkspaceUser.get_by_user_id(current_user.id) if current_user.is_authenticated else None
            member_id = member.id if member else -1
            return db.or_(
                cls.is_private == False,  # noqa: E712
                cls.created_by_id == member_id,
                cls.owner_id == member_id,
                cls.id.in_(
                    db.select(project_co_owner.c.project_id).where(
                        project_co_owner.c.member_id == member_id
                    )
                ),
            )
        except Exception:
            db.session.rollback()
            return cls.is_private == False  # noqa: E712

    @classmethod
    def search(cls, query_text: str, limit: int = 5) -> list[Self]:
        """Search non-archived, visible projects by name and description."""
        search_term = f"%{query_text}%"
        return (
            cls.scoped()
            .filter(
                cls.status != cls._archive_code(),
                cls._visible_filter(),
                db.or_(
                    cls.name.ilike(search_term),
                    cls.description.ilike(search_term),
                ),
            )
            .order_by(cls.name)
            .limit(limit)
            .all()
        )

    @classmethod
    def get_active_for_member(cls, member_id: int) -> list[Self]:
        """Returns active projects where member is owner, co-owner, follower, or has action items."""
        from modules.base.tasks.models.task import Task

        return (
            cls.scoped()
            .filter(
                cls.status != cls._archive_code(),
                db.or_(
                    cls.owner_id == member_id,
                    cls.id.in_(
                        db.select(project_co_owner.c.project_id).where(
                            project_co_owner.c.member_id == member_id
                        )
                    ),
                    cls.id.in_(
                        db.select(project_follower.c.project_id).where(
                            project_follower.c.member_id == member_id
                        )
                    ),
                    cls.id.in_(
                        db.select(Task.project_id).where(
                            Task.project_id.isnot(None),
                            db.or_(
                                Task.assignee_id == member_id,
                                Task.raised_by_id == member_id,
                            ),
                            Task.status == "open",
                        )
                    ),
                ),
            )
            .order_by(cls.status, cls.name)
            .all()
        )

    @classmethod
    def get_active_for_workspace(cls):
        """Returns non-archived, visible projects ordered by status then name."""
        return (
            cls.scoped()
            .filter(cls.status != cls._archive_code(), cls._visible_filter())
            .order_by(cls.status, cls.name)
            .all()
        )

    @classmethod
    def _activity_order(cls) -> ColumnElement:
        """Build a last-activity ordering expression for project queries."""
        from sqlalchemy import func, select
        from modules.base.tasks.models.task import Task
        from modules.base.updates.models.post import UpdatePost

        ai_max = (
            select(
                func.greatest(
                    func.max(Task.created_at),
                    func.max(Task.resolved_at),
                )
            )
            .where(Task.project_id == cls.id)
            .correlate(cls)
            .scalar_subquery()
        )

        post_max = (
            select(func.max(UpdatePost.created_at))
            .where(UpdatePost.channel_id == cls.channel_id)
            .correlate(cls)
            .scalar_subquery()
        )

        return func.greatest(
            cls.created_at,
            func.coalesce(ai_max, cls.created_at),
            func.coalesce(post_max, cls.created_at),
        )

    @classmethod
    def get_active_for_workspace_by_activity(cls) -> list[Self]:
        """Returns non-archived, visible projects ordered by most recent activity."""
        return (
            cls.scoped()
            .filter(cls.status != cls._archive_code(), cls._visible_filter())
            .order_by(cls._activity_order().desc())
            .all()
        )

    @classmethod
    def get_stale_upcoming(cls, cutoff: datetime) -> list[Self]:
        """Return non-archived projects whose last activity is before cutoff."""
        return (
            cls.scoped()
            .filter(
                cls.status != cls._archive_code(),
                cls._activity_order() < cutoff,
            )
            .all()
        )

    @classmethod
    def get_all_for_workspace_by_activity(cls) -> list[Self]:
        """Returns all visible projects (including archived) ordered by activity."""
        return (
            cls.scoped()
            .filter(cls._visible_filter())
            .order_by(cls._activity_order().desc())
            .all()
        )

    @classmethod
    def get_archived_for_workspace(cls):
        """Returns archived, visible projects ordered by archive date descending."""
        return (
            cls.scoped()
            .filter(cls.status == cls._archive_code(), cls._visible_filter())
            .order_by(cls.archived_at.desc())
            .all()
        )

    @classmethod
    def archived_count_for_workspace(cls) -> int:
        """Count archived, visible projects without hydrating rows."""
        return (
            cls.scoped()
            .filter(cls.status == cls._archive_code(), cls._visible_filter())
            .count()
        )

    @classmethod
    def get_by_id(cls, project_id):
        """Get a project by ID within the current workspace."""
        from sqlalchemy.orm import joinedload

        return (
            cls.scoped()
            .options(joinedload(cls.channel))
            .filter_by(id=project_id)
            .first()
        )

    @classmethod
    def get_all_channel_ids(cls) -> list[int]:
        """Return channel ids for every project, including archived ones.

        Used by the chat secondary nav to exclude project channels from the
        general CHANNELS section regardless of archive state — otherwise
        archived-project channels leak into CHANNELS when their parent project
        drops out of the active list.
        """
        return [
            p.channel_id
            for p in cls.scoped().filter(cls.channel_id.isnot(None)).all()
        ]

    def get_open_tasks(self):
        """Get open action items for this project."""
        from sqlalchemy.orm import joinedload

        from modules.base.tasks.models.task import Task
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            Task.scoped()
            .options(joinedload(Task.assignee).joinedload(WorkspaceUser.user))
            .filter_by(project_id=self.id, status="open")
            .order_by(Task.urgency_tier.asc(), Task.created_at.asc())
            .all()
        )

    def get_closed_tasks(self):
        """Get resolved/dismissed action items for this project."""
        from sqlalchemy.orm import joinedload

        from modules.base.tasks.models.task import Task
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            Task.scoped()
            .options(joinedload(Task.assignee).joinedload(WorkspaceUser.user))
            .filter(
                Task.project_id == self.id,
                Task.status != "open",
            )
            .order_by(Task.resolved_at.desc())
            .all()
        )

    def get_recent_posts(self, limit: int = 10) -> list["UpdatePost"]:  # noqa: F821
        """Get recent sync posts that reference this project.

        Projects are linked at the structured-list item level inside each
        post's ``payload`` JSON (see migration 033, which dropped the direct
        ``sync_post.project_id`` FK). We scan the serialized payload for the
        exact ``project_id`` scalar, anchored on both sides so an id of 1
        does not false-match 10, 100, etc.

        Args:
            limit: Max number of posts to return. Defaults to 10.

        Returns:
            List of :class:`UpdatePost` instances, newest first.
        """
        from sqlalchemy.orm import joinedload

        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.updates.models.post import UpdatePost

        # Postgres json::text serialises integer scalars with either `,`
        # (middle of object) or `}` (last key) immediately after the digits —
        # never another digit. Anchoring on both characters makes the match
        # exact. Depends on json.dumps' default ": " separator, which is
        # what SQLAlchemy's db.JSON uses.
        payload_text = UpdatePost.payload.cast(db.Text)
        mid = f'"project_id": {self.id},'
        end = f'"project_id": {self.id}}}'

        return (
            UpdatePost.scoped()
            .options(joinedload(UpdatePost.member).joinedload(WorkspaceUser.user))
            .filter(db.or_(payload_text.contains(mid), payload_text.contains(end)))
            .order_by(UpdatePost.created_at.desc())
            .limit(limit)
            .all()
        )

    # ── Update ─────────────────────────────────────────────────────────────

    def update(self, name=None, description=None, owner_id=None, color=None, emoji=None):
        """Update editable project fields."""
        if name is not None:
            self.name = name[:200]
        if description is not None:
            self.description = description[:500] if description else None
        if owner_id is not None:
            self.owner_id = owner_id or None
        if color is not None:
            self.color = color or None
        if emoji is not None:
            self.emoji = emoji or None
        self.updated_at = datetime.utcnow()
        db.session.commit()

    # ── Creation ───────────────────────────────────────────────────────────

    @classmethod
    def create(cls, name, created_by_id, description=None, owner_id=None,
               color=None, emoji=None, create_channel=True, channel_name=None,
               is_private=False):
        """Create a new project, optionally with a dedicated chat channel.

        Args:
            name: Project name.
            created_by_id: WorkspaceUser.id of the creator.
            description: Optional description.
            owner_id: Optional WorkspaceUser.id of the owner.
            color: Optional hex color.
            emoji: Optional emoji.
            create_channel: Whether to create a chat channel.
            channel_name: Custom channel name (auto-generated if None).
            is_private: Whether the project is private (visible only to owner/creator).

        Returns:
            Created Project instance.
        """
        default_status = cls.STATUS_CURRENT
        try:
            from .project_status import ProjectStatus
            default_ps = ProjectStatus.get_default()
            if default_ps:
                default_status = default_ps.code
        except Exception:
            pass

        project = cls(
            name=name[:200],
            description=description[:500] if description else None,
            status=default_status,
            color=color,
            emoji=emoji,
            owner_id=owner_id,
            created_by_id=created_by_id,
            is_private=is_private,
        )
        db.session.add(project)
        db.session.flush()  # Get project.id before creating channel

        if create_channel:
            from modules.base.updates.models.channel import UpdateChannel

            slug = channel_name or cls._slugify_name(name)
            # Ensure unique channel name
            existing = UpdateChannel.get_by_name(slug)
            if existing:
                slug = slug[:47] + "-2"
                # If that also exists, try -3, etc.
                counter = 2
                while UpdateChannel.get_by_name(slug):
                    counter += 1
                    slug = cls._slugify_name(name)[:46] + f"-{counter}"

            channel = UpdateChannel.create(
                name=slug,
                description=f"Project log for {name[:50]}",
                created_by_id=created_by_id,
                is_private=is_private,
            )
            project.channel_id = channel.id
            channel.project_id = project.id

        db.session.commit()
        return project

    @classmethod
    def create_with_channel(cls, name, created_by_id, **kwargs):
        """Create a project with a guaranteed channel atomically.

        Wraps create() with create_channel=True. If channel creation
        fails, the entire transaction rolls back.

        Args:
            name: Project name.
            created_by_id: WorkspaceUser.id of the creator.
            **kwargs: Passed to create().

        Returns:
            Created Project instance with channel.

        Raises:
            Exception: Rolls back on any failure.
        """
        try:
            return cls.create(
                name=name,
                created_by_id=created_by_id,
                create_channel=True,
                **kwargs,
            )
        except Exception:
            db.session.rollback()
            raise

    def get_channel_posts(self, limit=20, offset=0):
        """Get posts from this project's linked channel.

        Args:
            limit: Max results.
            offset: Number of rows to skip.

        Returns:
            Tuple of (posts, has_more), or ([], False) if no channel.
        """
        if not self.channel:
            return [], False
        return self.channel.get_posts_feed(limit=limit, offset=offset)

    @staticmethod
    def _slugify_name(name):
        """Convert a project name to a channel-safe slug."""
        import re

        slug = name.lower()
        slug = re.sub(r"[^a-z0-9\s]", "", slug)
        slug = slug.strip()
        parts = slug.split()[:2]
        slug = "-".join(parts)
        if not slug:
            slug = "project"
        return slug[:20]
