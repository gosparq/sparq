# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""TaskComment model — discussion on Tasks and Blockers.

Flat comments attached to a Task. Supports soft delete and
audit tracking. Any workspace member can comment.

Example:
    Creating a comment::

        comment = TaskComment.create(
            task_id=42,
            content="Can you clarify the scope?",
            author_id=member.id,
            user_id=current_user.id,
        )

    Fetching comments for an item::

        comments = TaskComment.get_for_item(task_id=42)
"""

import logging
import re
from datetime import datetime, timezone

from sqlalchemy.orm import joinedload

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin, SoftDeleteMixin
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

logger = logging.getLogger(__name__)


@ModelRegistry.register
class TaskComment(db.Model, WorkspaceMixin, AuditMixin, SoftDeleteMixin):
    """Comment on a Task or Blocker.

    Attributes:
        id: Primary key.
        task_id: FK to the parent task.
        author_id: FK to workspace_user who wrote the comment.
        content: Plain-text comment content (max 2000 chars enforced at model).
        created_at: When the comment was posted.
        updated_at: When the comment was last edited.
    """

    __tablename__ = "task_comment"
    __table_args__ = (
        db.Index(
            "ix_task_comment_item",
            "task_id",
            "created_at",
        ),
        db.Index(
            "ix_task_comment_org_item",
            "organization_id",
            "task_id",
            "created_at",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("task.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id"),
        nullable=False,
        index=True,
    )
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime,
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    task = db.relationship(
        "Task",
        backref=db.backref("comments", lazy="dynamic"),
        lazy=LAZY,
    )
    author = db.relationship(
        "WorkspaceUser",
        foreign_keys=[author_id],
        lazy=LAZY,
    )

    @classmethod
    def create(cls, task_id: int, content: str, author_id: int, user_id: int) -> "TaskComment":
        """Create a new comment on a task.

        Args:
            task_id: ID of the parent action item.
            content: Plain-text comment content.
            author_id: WorkspaceUser.id of the comment author.
            user_id: User.id for AuditMixin tracking.

        Returns:
            The newly created TaskComment instance.
        """
        comment = cls(
            task_id=task_id,
            content=content[:2000],
            author_id=author_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        db.session.add(comment)
        db.session.commit()

        cls._send_comment_notifications(comment)
        return comment

    @classmethod
    def _send_comment_notifications(cls, comment: "TaskComment") -> None:
        """Notify task participants and @mentioned members about a new comment."""
        try:
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            from modules.base.core.models.workspace_user import WorkspaceUser
            from modules.base.core.services.push_notification import send_push
            from modules.base.tasks.models.task import Task

            task = (
                Task.scoped()
                .options(
                    joinedload(Task.assignee).joinedload(WorkspaceUser.user),
                    joinedload(Task.raised_by).joinedload(WorkspaceUser.user),
                )
                .filter_by(id=comment.task_id)
                .first()
            )
            if not task:
                return

            author = (
                WorkspaceUser.scoped()
                .options(joinedload(WorkspaceUser.user))
                .filter_by(id=comment.author_id)
                .first()
            )
            author_name = author.user.first_name if author and author.user else "Someone"
            notified_user_ids: set[int] = set()

            # Notify assignee
            if (
                task.assignee
                and task.assignee.user
                and task.assignee.id != comment.author_id
            ):
                uid = task.assignee.user_id
                notified_user_ids.add(uid)
                SystemNotification.create(
                    title=task.title[:100],
                    message=f'{author_name} commented: "{comment.content[:80]}"',
                    type="info",
                    target_role="user",
                    user_id=uid,
                    icon="fa-comment",
                    action_url=f"/tasks/{task.id}",
                    category=NotificationCategory.COMMENT,
                )
                send_push(
                    user_id=uid,
                    title=task.title[:80],
                    body=f'{author_name}: "{comment.content[:80]}"',
                    url=f"/tasks/{task.id}",
                )

            # Notify raiser
            if (
                task.raised_by
                and task.raised_by.user
                and task.raised_by.id != comment.author_id
                and task.raised_by.user_id not in notified_user_ids
            ):
                uid = task.raised_by.user_id
                notified_user_ids.add(uid)
                SystemNotification.create(
                    title=task.title[:100],
                    message=f'{author_name} commented: "{comment.content[:80]}"',
                    type="info",
                    target_role="user",
                    user_id=uid,
                    icon="fa-comment",
                    action_url=f"/tasks/{task.id}",
                    category=NotificationCategory.COMMENT,
                )
                send_push(
                    user_id=uid,
                    title=task.title[:80],
                    body=f'{author_name}: "{comment.content[:80]}"',
                    url=f"/tasks/{task.id}",
                )

            # @mention notifications — batch query to avoid N+1
            mentioned_ids = {int(m) for m in re.findall(r"@\[(\d+)\]", comment.content or "")}
            mentioned_ids.discard(comment.author_id)
            if mentioned_ids:
                members = (
                    WorkspaceUser.scoped()
                    .options(joinedload(WorkspaceUser.user))
                    .filter(WorkspaceUser.id.in_(mentioned_ids))
                    .all()
                )
                for member in members:
                    if not member.user or member.user_id in notified_user_ids:
                        continue
                    notified_user_ids.add(member.user_id)
                    SystemNotification.create(
                        title=task.title[:100],
                        message=f"{author_name} mentioned you in a comment",
                        type="info",
                        target_role="user",
                        user_id=member.user_id,
                        icon="fa-at",
                        action_url=f"/tasks/{task.id}",
                        category=NotificationCategory.MENTION,
                    )
                    send_push(
                        user_id=member.user_id,
                        title=task.title[:80],
                        body=f"{author_name} mentioned you in a comment",
                        url=f"/tasks/{task.id}",
                    )
        except Exception:
            logger.exception("Failed to send comment notifications for comment %s", comment.id)

    @classmethod
    def get_for_item(cls, task_id: int) -> list["TaskComment"]:
        """Get all active comments for a task, oldest first.

        Eager-loads the author and their User record to avoid N+1.

        Args:
            task_id: ID of the action item.

        Returns:
            List of active TaskComment instances, oldest first.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            cls.active()
            .options(
                joinedload(cls.author).joinedload(WorkspaceUser.user),
            )
            .filter_by(task_id=task_id)
            .order_by(cls.created_at.asc())
            .all()
        )

    def update_content(self, content: str, user_id: int) -> None:
        """Update the comment content.

        Args:
            content: New plain-text content (max 2000 chars).
            user_id: User.id of the user making the edit.
        """
        self.content = content[:2000]
        self.updated_by_id = user_id
        db.session.commit()

    def __repr__(self) -> str:
        return f"<TaskComment {self.id} item={self.task_id}>"
