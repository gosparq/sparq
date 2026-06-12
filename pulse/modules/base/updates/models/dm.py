# -----------------------------------------------------------------------------
# sparQ - Sync Module Direct Message Models
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Direct message models — DM threads and messages between members.

DM threads are scoped to the ORGANIZATION (§12.4), not the workspace. Any two
organization members can DM each other regardless of shared workspace
membership. member1_id / member2_id still reference workspace_user.id per
Q3 (resolved 2026-04-21) — a follow-up goal will switch these to
organization_user.id once org-only-member DMs become a real use case.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from flask import g
from markupsafe import Markup

from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import OrganizationMixin
from system.db.raise_on_lazy import LAZY

if TYPE_CHECKING:
    from modules.base.core.models.workspace_user import WorkspaceUser


@ModelRegistry.register
class DMThread(db.Model, OrganizationMixin, SerializableMixin):
    """DM conversation between two members within a single organization."""

    __tablename__ = "dm_thread"

    id = db.Column(db.Integer, primary_key=True)
    member1_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    member2_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    updated_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    # Relationships
    member1 = db.relationship("WorkspaceUser", foreign_keys=[member1_id], lazy=LAZY)
    member2 = db.relationship("WorkspaceUser", foreign_keys=[member2_id], lazy=LAZY)
    messages = db.relationship(
        "DM",
        backref=db.backref("thread", lazy=LAZY),
        lazy="dynamic",
    )

    __table_args__ = (
        db.UniqueConstraint("member1_id", "member2_id", name="unique_dm_thread"),
        db.CheckConstraint("member1_id < member2_id", name="member_order_constraint"),
    )

    @classmethod
    def get_or_create(cls, member_id_1: int, member_id_2: int) -> "DMThread":
        """Get existing thread or create one between two members.

        Both members must belong to the current organization (g.organization_id).
        The resulting thread is organization-scoped — the participants can live
        in different workspaces within the same org per §12.4.

        Limited members cannot initiate DM threads; the guard is dormant
        until the external_project_invites spec introduces 'limited' members.
        """
        from modules.base.core.models.workspace_user import WorkspaceUser

        # Dormant limited-member guard — ships inactive, activates in Phase 4.
        initiator = WorkspaceUser.query.get(member_id_1) or WorkspaceUser.query.get(member_id_2)
        if initiator is not None and getattr(initiator, "member_type", "full") == "limited":
            raise PermissionError("Limited members cannot initiate DM threads.")

        if member_id_1 > member_id_2:
            member_id_1, member_id_2 = member_id_2, member_id_1

        thread = cls.scoped().filter_by(member1_id=member_id_1, member2_id=member_id_2).first()
        if not thread:
            thread = cls(member1_id=member_id_1, member2_id=member_id_2)
            db.session.add(thread)
            db.session.commit()
        return thread

    @classmethod
    def get_threads_for_member(cls, member_id: int) -> list["DMThread"]:
        """Get all DM threads for a member, ordered by most recent activity."""
        cache_key = ("dm_threads", member_id)
        try:
            cache = getattr(g, "_dm_thread_cache", None)
            if cache is None:
                cache = {}
                g._dm_thread_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        from sqlalchemy.orm import joinedload

        from modules.base.core.models.workspace_user import WorkspaceUser

        result = (
            cls.scoped()
            .options(
                joinedload(cls.member1).joinedload(WorkspaceUser.user),
                joinedload(cls.member2).joinedload(WorkspaceUser.user),
            )
            .filter(db.or_(cls.member1_id == member_id, cls.member2_id == member_id))
            .order_by(cls.updated_at.desc())
            .all()
        )
        if cache is not None:
            cache[cache_key] = result
        return result

    @classmethod
    def get_thread_map_for_member(cls, member_id: int) -> dict[int, tuple["DMThread", int]]:
        """Map other-member-id to (thread, unread_count) for all threads."""
        threads = cls.get_threads_for_member(member_id)
        result: dict[int, tuple[DMThread, int]] = {}
        for thread in threads:
            other = thread.get_other_member(member_id)
            if other:
                result[other.id] = (thread, thread.get_unread_count(member_id))
        return result

    # Backwards-compatible alias
    @classmethod
    def get_threads_for_user(cls, user_id: int) -> list["DMThread"]:
        """Deprecated: Use get_threads_for_member. Converts user_id to member_id."""
        from modules.base.core.models.workspace_user import WorkspaceUser
        member = WorkspaceUser.get_by_user_id(user_id)
        if member:
            return cls.get_threads_for_member(member.id)
        return []

    @classmethod
    def get_total_unread_count(cls, member_id: int) -> int:
        """Get total unread DM count across all threads for a member."""
        threads = cls.get_threads_for_member(member_id)
        if not threads:
            return 0

        try:
            cache = getattr(g, "_dm_unread_cache", None)
            if cache is None:
                cache = {}
                g._dm_unread_cache = cache
        except Exception:
            cache = None

        uncached_ids = []
        total = 0
        for t in threads:
            if cache is not None and (t.id, member_id) in cache:
                total += cache[(t.id, member_id)]
            else:
                uncached_ids.append(t.id)

        if uncached_ids:
            batch = cls._batch_unread_counts(uncached_ids, member_id)
            for tid in uncached_ids:
                cnt = batch.get(tid, 0)
                if cache is not None:
                    cache[(tid, member_id)] = cnt
                total += cnt

        return total

    @classmethod
    def batch_unread_counts(cls, thread_ids: list[int], member_id: int) -> dict[int, int]:
        """Batch fetch unread counts for multiple threads in a single query.

        Also warms g._dm_unread_cache so subsequent get_unread_count()
        calls on the same threads are free.
        """
        if not thread_ids:
            return {}
        rows = (
            db.session.query(DM.thread_id, db.func.count(DM.id))
            .filter(
                DM.organization_id == g.organization_id,
                DM.thread_id.in_(thread_ids),
                DM.member_id != member_id,
                DM.read_at.is_(None),
            )
            .group_by(DM.thread_id)
            .all()
        )
        result = {tid: cnt for tid, cnt in rows}

        try:
            cache = getattr(g, "_dm_unread_cache", None)
            if cache is None:
                cache = {}
                g._dm_unread_cache = cache
            for tid in thread_ids:
                cache[(tid, member_id)] = result.get(tid, 0)
        except Exception:
            pass

        return result

    _batch_unread_counts = batch_unread_counts

    @classmethod
    def get_by_id(cls, thread_id: int) -> "DMThread | None":
        """Get thread by ID."""
        return cls.scoped().filter_by(id=thread_id).first()

    def get_other_member(self, current_member_id: int) -> "WorkspaceUser | None":
        """Get the other participant in the thread.

        DM threads are organization-scoped (§12.4), so the other member can
        live in a different workspace. Uses the pre-loaded member1/member2
        relationships (eager-loaded by get_threads_for_member). Falls back
        to lazy load for single-thread contexts.
        """
        if self.member1_id == current_member_id:
            return self.member2
        return self.member1

    def get_other_user(self, current_user_id: int):
        """Deprecated: Get the other user in the thread (compatibility)."""

        # Find which member belongs to this user
        if self.member1 and self.member1.user_id == current_user_id:
            other_member = self.member2
        else:
            other_member = self.member1
        return other_member.user if other_member else None

    def get_unread_count(self, member_id: int) -> int:
        """Get unread message count for a member."""
        cache_key = (self.id, member_id)
        try:
            cache = getattr(g, "_dm_unread_cache", None)
            if cache is None:
                cache = {}
                g._dm_unread_cache = cache
            if cache_key in cache:
                return cache[cache_key]
        except Exception:
            cache = None

        result = DM.scoped().filter(
            DM.thread_id == self.id,
            DM.member_id != member_id,
            DM.read_at.is_(None),
        ).count()
        if cache is not None:
            cache[cache_key] = result
        return result

    def has_member(self, member_id: int) -> bool:
        """Check if member is part of this thread."""
        return member_id in (self.member1_id, self.member2_id)

    def has_user(self, user_id: int) -> bool:
        """Compatibility: Check if user is part of this thread."""
        return (
            (self.member1 and self.member1.user_id == user_id)
            or (self.member2 and self.member2.user_id == user_id)
        )


@ModelRegistry.register
class DM(db.Model, OrganizationMixin, SerializableMixin):
    """Individual direct message — organization-scoped (§12.4).

    Uses member_id (workspace_user.id) for the author. The organization_id
    is auto-set via the before_flush listener from g.organization_id, matching
    the thread's scope.
    """

    __tablename__ = "dm"

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey("dm_thread.id", ondelete="CASCADE"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id"), nullable=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    read_at = db.Column(db.DateTime, nullable=True)
    mentioned_member_ids = db.Column(db.JSON, default=list)

    # Webhook fields
    webhook_id = db.Column(db.Integer, db.ForeignKey("update_webhook.id", ondelete="SET NULL"), nullable=True)
    webhook_username = db.Column(db.String(80), nullable=True)

    # Relationships
    webhook = db.relationship("UpdateWebhook", foreign_keys=[webhook_id], lazy="joined")
    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy="joined")

    @property
    def author(self):
        """Compatibility: return User via member."""
        return self.member.user if self.member else None

    @property
    def author_id(self):
        """Compatibility: return user_id via member."""
        return self.member.user_id if self.member else None

    @property
    def plain_text_content(self) -> str:
        """Resolve mentions to plain text — for push notifications and previews."""
        import re

        from modules.base.core.models.workspace_user import WorkspaceUser

        content = self.content or ""

        # Resolve @[member_id] → @FirstName
        def replace_mention(match: re.Match[str]) -> str:
            mid = int(match.group(1))
            # Unscoped: mentioned members in a DM may belong to a different
            # workspace within the same organization (§12.4).
            m = WorkspaceUser.query.get(mid)
            if m and m.user:
                return f"@{m.user.first_name}"
            return match.group(0)

        return re.sub(r"@\[(\d+)\]", replace_mention, content)

    @property
    def formatted_content(self) -> Markup:
        """Format message content with markdown, emoji, and mentions."""
        import html
        import re

        from modules.base.core.models.workspace_user import WorkspaceUser

        from ..utils.emoji import convert_shortcodes

        content = html.escape(self.content)
        content = convert_shortcodes(content)

        # Parse @[member_id] mentions
        def replace_mention(match: re.Match[str]) -> str:
            mid = int(match.group(1))
            # Unscoped: mentioned members in a DM may belong to a different
            # workspace within the same organization (§12.4).
            m = WorkspaceUser.query.get(mid)
            if m and m.user:
                return f'<span class="mention" data-member-id="{mid}">@{m.user.first_name}</span>'
            return match.group(0)

        content = re.sub(r"@\[(\d+)\]", replace_mention, content)

        # Markdown formatting
        def replace_code_block(match: re.Match[str]) -> str:
            return f"<pre><code>{match.group(1)}</code></pre>"

        content = re.sub(r"```\n?([\s\S]*?)```", replace_code_block, content)
        content = re.sub(r"`([^`]+)`", r"<code>\1</code>", content)
        content = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", content)
        content = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", content)
        content = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", content)
        content = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", content)
        content = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", content)

        # URLs
        url_pattern = r'(https?://[^\s<>"]+|www\.[^\s<>"]+)'

        def replace_url(match: re.Match[str]) -> str:
            url = match.group(0)
            full_url = url if url.startswith(("http://", "https://")) else f"https://{url}"
            return (
                f'<span class="chat-link-wrapper">'
                f'<a href="{full_url}" target="_blank" rel="noopener noreferrer" class="chat-link">{url}</a>'
                f'<button class="chat-link-copy" data-action="copy-url" data-url="{full_url}" title="Copy URL">'
                f'<i class="fas fa-copy"></i></button>'
                f'</span>'
            )

        content = re.sub(url_pattern, replace_url, content)

        parts = re.split(r"(<pre><code>[\s\S]*?</code></pre>)", content)
        for i, part in enumerate(parts):
            if not part.startswith("<pre>"):
                parts[i] = part.replace("\n", "<br>")
        content = "".join(parts)

        return Markup(content)

    @classmethod
    def create(cls, thread_id: int, member_id: int, content: str) -> "DM":
        """Create a new direct message."""
        msg = cls(thread_id=thread_id, member_id=member_id, content=content.strip())
        db.session.add(msg)

        thread = DMThread.scoped().filter_by(id=thread_id).first()
        if thread:
            thread.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        return msg

    @classmethod
    def create_from_webhook(
        cls,
        content: str,
        thread_id: int,
        webhook_id: int,
        username: str | None = None,
    ) -> "DM":
        """Create a DM from a webhook."""
        msg = cls(
            thread_id=thread_id,
            member_id=None,
            content=content.strip()[:4000],
            webhook_id=webhook_id,
            webhook_username=username,
        )
        db.session.add(msg)

        thread = DMThread.scoped().filter_by(id=thread_id).first()
        if thread:
            thread.updated_at = datetime.now(timezone.utc)

        db.session.commit()
        return msg

    @classmethod
    def get_by_id(cls, message_id: int) -> "DM | None":
        """Get message by ID."""
        return cls.scoped().filter_by(id=message_id).first()

    @classmethod
    def mark_read(cls, message_id: int) -> bool:
        """Mark a message as read."""
        msg = cls.scoped().filter_by(id=message_id).first()
        if msg and not msg.read_at:
            msg.read_at = datetime.now(timezone.utc)
            db.session.commit()
            return True
        return False

    @classmethod
    def mark_thread_read(cls, thread_id: int, member_id: int) -> int:
        """Mark all unread messages in a thread as read for a member."""
        unread = cls.scoped().filter(
            cls.thread_id == thread_id,
            cls.member_id != member_id,
            cls.read_at.is_(None),
        ).all()

        now = datetime.now(timezone.utc)
        for msg in unread:
            msg.read_at = now

        db.session.commit()
        return len(unread)

    @classmethod
    def delete_message(cls, message_id: int) -> bool:
        """Delete a DM message."""
        message = cls.scoped().filter_by(id=message_id).first()
        if not message:
            return False
        db.session.delete(message)
        db.session.commit()
        return True


@ModelRegistry.register
class DMReaction(db.Model, OrganizationMixin):
    """Emoji reactions on direct messages — organization-scoped alongside the message."""

    __tablename__ = "dm_reaction"

    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey("dm.id", ondelete="CASCADE"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("workspace_user.id", ondelete="CASCADE"), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("message_id", "member_id", "emoji", name="unique_dm_member_message_emoji"),
    )

    member = db.relationship("WorkspaceUser", backref=db.backref("dm_reactions", lazy="dynamic"), lazy=LAZY)
    message = db.relationship("DM", backref=db.backref("reactions", lazy="dynamic"), lazy=LAZY)

    @classmethod
    def toggle(cls, message_id: int, member_id: int, emoji: str) -> tuple[bool, int]:
        """Toggle a reaction. Returns (added: bool, new_count: int)."""
        existing = cls.scoped().filter_by(
            message_id=message_id, member_id=member_id, emoji=emoji
        ).first()

        if existing:
            db.session.delete(existing)
            db.session.commit()
            count = cls.scoped().filter_by(message_id=message_id, emoji=emoji).count()
            return (False, count)
        else:
            reaction = cls(message_id=message_id, member_id=member_id, emoji=emoji)
            db.session.add(reaction)
            db.session.commit()
            count = cls.scoped().filter_by(message_id=message_id, emoji=emoji).count()
            return (True, count)

    @classmethod
    def get_for_message(cls, message_id: int) -> dict:
        """Get reactions for a message grouped by emoji."""
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        reactions = (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
            .filter_by(message_id=message_id)
            .all()
        )
        result = {}
        for r in reactions:
            if r.emoji not in result:
                result[r.emoji] = {"count": 0, "users": [], "member_ids": [], "user_ids": []}
            result[r.emoji]["count"] += 1
            name = r.member.user.first_name if r.member and r.member.user else "Unknown"
            result[r.emoji]["users"].append(name)
            result[r.emoji]["member_ids"].append(r.member_id)
            if r.member and r.member.user:
                result[r.emoji]["user_ids"].append(r.member.user_id)
        return result

    @classmethod
    def member_reacted(cls, message_id: int, member_id: int, emoji: str) -> bool:
        """Check if member has reacted with a specific emoji."""
        return cls.scoped().filter_by(
            message_id=message_id, member_id=member_id, emoji=emoji
        ).first() is not None
