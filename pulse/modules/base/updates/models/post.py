# -----------------------------------------------------------------------------
# sparQ - UpdatePost Model
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""UpdatePost model — unified content model for all update data.

Stores template-driven posts (updates, board) AND chat messages.
Chat messages use template_id=NULL with content stored in payload["content"].
The payload JSON stores actual content keyed by template field keys.

Classes:
    UpdatePost: Unified post/message content model.
"""

import logging
import re
from datetime import datetime, timedelta

from flask_login import current_user
from markupsafe import Markup

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY

logger = logging.getLogger(__name__)

BOARD_EXPIRY_DAYS = 30


@ModelRegistry.register
class UpdatePost(db.Model, WorkspaceMixin):
    """Unified post/message model (update, board, channel, webhook).

    Attributes:
        template_id: FK to UpdateTemplate (NULL for chat messages).
        post_type: 'update', 'board', 'channel', 'webhook'.
        member_id: Author (NULL for anonymous or webhook posts).
        payload: JSON content keyed by template field keys.
        visibility: 'team', 'leads', or 'private'.
        is_anonymous: Denormalised from template.anonymous.
        expires_at: Optional expiration date (used by board posts).
        pinned: Whether this post is pinned (chat messages).
        mentioned_member_ids: JSON list of @mentioned member IDs.
        target_user_id: For AI messages — which user the AI is responding to.
    """

    __tablename__ = "update_post"
    __table_args__ = (
        db.Index("ix_update_post_type_date", "workspace_id", "post_type", db.text("created_at DESC")),
        db.Index("ix_update_post_template_date", "workspace_id", "template_id", db.text("created_at DESC")),
        db.Index("ix_update_post_member_date", "workspace_id", "member_id", db.text("created_at DESC")),
        db.Index("ix_update_post_channel_org", "channel_id", "organization_id", "workspace_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("update_template.id"), nullable=True)
    post_type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    migrated_from = db.Column(db.String(50), nullable=True)

    member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    payload = db.Column(db.JSON, nullable=False, default=dict)
    visibility = db.Column(db.String(20), nullable=False, default="team")
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)

    area_id = db.Column(
        db.Integer, db.ForeignKey("update_area.id", ondelete="SET NULL"), nullable=True
    )
    channel_id = db.Column(
        db.Integer, db.ForeignKey("update_channel.id", ondelete="SET NULL"), nullable=True
    )
    is_win = db.Column(db.Boolean, nullable=False, default=False)

    parent_id = db.Column(
        db.Integer, db.ForeignKey("update_post.id", ondelete="CASCADE"), nullable=True
    )
    subject = db.Column(db.String(300), nullable=True)

    # Chat-specific columns
    pinned = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    promoted_to_dashboard = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    mentioned_member_ids = db.Column(db.JSON, default=list)
    target_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # Denormalized threading metadata
    reply_count_col = db.Column("reply_count", db.Integer, nullable=False, default=0, server_default="0")
    last_reply_at = db.Column(db.DateTime, nullable=True)
    last_reply_member_id = db.Column(
        db.Integer, db.ForeignKey("workspace_user.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    member = db.relationship("WorkspaceUser", foreign_keys=[member_id], lazy=LAZY)
    last_reply_member = db.relationship("WorkspaceUser", foreign_keys=[last_reply_member_id], lazy=LAZY)
    area = db.relationship("UpdateArea", foreign_keys=[area_id], lazy=LAZY)
    channel = db.relationship("UpdateChannel", foreign_keys=[channel_id], back_populates="posts", lazy=LAZY)
    reactions = db.relationship("UpdatePostReaction", backref=db.backref("post", lazy=LAZY), lazy="dynamic", cascade="all, delete-orphan")
    acknowledgments = db.relationship("UpdatePostAck", backref=db.backref("post", lazy=LAZY), lazy="dynamic", cascade="all, delete-orphan")
    parent = db.relationship("UpdatePost", remote_side="UpdatePost.id", foreign_keys=[parent_id], backref=db.backref("replies", lazy="dynamic", order_by="UpdatePost.created_at"), lazy=LAZY)
    # ── Threading properties ──────────────────────────────────────────

    @property
    def reply_count(self):
        """Number of replies to this post (denormalized column)."""
        return self.reply_count_col

    @property
    def last_activity_at(self):
        """Timestamp of the most recent reply, or created_at if no replies."""
        return self.last_reply_at or self.created_at

    @property
    def is_reply(self):
        """Whether this post is a reply to another post."""
        return bool(self.parent_id)

    @property
    def is_migrated(self):
        """Whether this post was migrated from a legacy table."""
        return bool(self.migrated_from)

    # ── Chat-compat properties ────────────────────────────────────────

    @property
    def content(self) -> str:
        """Raw text content (from payload for chat/webhook posts)."""
        return (self.payload or {}).get("content", "")

    @property
    def author(self):
        """The User object via member relationship."""
        return self.member.user if self.member else None

    @property
    def author_id(self):
        """The user_id via member."""
        return self.member.user_id if self.member else None

    @property
    def is_author(self) -> bool:
        """Check if current user is the author."""
        if not current_user.is_authenticated or not self.member:
            return False
        return self.member.user_id == current_user.id

    @property
    def webhook_id(self):
        """Webhook ID from payload (for webhook posts)."""
        return (self.payload or {}).get("webhook_id")

    @property
    def webhook_username(self):
        """Webhook display name from payload."""
        return (self.payload or {}).get("webhook_username")

    @property
    def message_type(self) -> str:
        """Message type (compat alias for post_type)."""
        return self.post_type

    def _get_webhook(self):
        """Lazy-load the UpdateWebhook object if this is a webhook post."""
        wh_id = self.webhook_id
        if not wh_id:
            return None
        from .webhook import UpdateWebhook
        return UpdateWebhook.query.get(wh_id)

    @property
    def created_at_formatted(self) -> str:
        """Format the creation date for display."""
        from system.i18n.translation import format_datetime
        return format_datetime(self.created_at, "%B %d, %Y %I:%M %p")

    @property
    def plain_text_content(self) -> str:
        """Resolve mentions to plain text — for push notifications and previews."""
        from modules.base.core.models.workspace_user import WorkspaceUser

        text = self.content or ""
        text = text.replace("@[channel]", "@channel")

        def replace_mention(match: re.Match[str]) -> str:
            mid = int(match.group(1))
            member = WorkspaceUser.scoped().filter_by(id=mid).first()
            if member and member.user:
                return f"@{member.user.first_name}"
            return match.group(0)

        return re.sub(r"@\[(\d+)\]", replace_mention, text)

    @property
    def formatted_content(self) -> Markup:
        """Format message content with markdown, emoji shortcodes, mentions, and links."""
        import html as html_mod

        from modules.base.core.models.workspace_user import WorkspaceUser
        from ..utils.emoji import convert_shortcodes

        raw = html_mod.escape(self.content or "")
        raw = convert_shortcodes(raw)

        # @[channel] mention
        raw = raw.replace(
            "@[channel]", '<span class="mention mention-channel">@channel</span>'
        )

        # @[member_id] mentions
        def replace_mention(match: re.Match[str]) -> str:
            mid = int(match.group(1))
            member = WorkspaceUser.scoped().filter_by(id=mid).first()
            if member and member.user:
                return f'<span class="mention" data-member-id="{mid}">@{member.user.first_name}</span>'
            return match.group(0)

        raw = re.sub(r"@\[(\d+)\]", replace_mention, raw)

        # Markdown formatting
        def replace_code_block(match: re.Match[str]) -> str:
            code = match.group(1)
            return f"<pre><code>{code}</code></pre>"

        raw = re.sub(r"```\n?([\s\S]*?)```", replace_code_block, raw)
        raw = re.sub(r"`([^`]+)`", r"<code>\1</code>", raw)
        raw = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", raw)
        raw = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", raw)
        raw = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", raw)
        raw = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", raw)
        raw = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", raw)

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

        raw = re.sub(url_pattern, replace_url, raw)

        # Newlines to breaks (but not inside <pre> blocks)
        parts = re.split(r"(<pre><code>[\s\S]*?</code></pre>)", raw)
        for i, part in enumerate(parts):
            if not part.startswith("<pre>"):
                parts[i] = part.replace("\n", "<br>")
        raw = "".join(parts)

        return Markup(raw)

    def get_replies(self, limit=100):
        """Get direct replies to this post, oldest first."""
        return self.replies.order_by(UpdatePost.created_at.asc()).limit(limit).all()

    def get_root_post(self):
        """Walk up parent chain to find the thread root post."""
        post = self
        while post.parent_id:
            post = UpdatePost.scoped().filter_by(id=post.parent_id).first()
            if not post:
                break
        return post

    def get_threaded_replies(self, limit=200):
        """Get all descendants as a flat list with depth, ordered for display.

        Returns a list of (reply, depth) tuples. Top-level replies have depth=0,
        replies to replies have depth=1, etc. Depth is capped at 1 for display
        (deeper replies render at depth 1 but show a "replying to" reference).

        Ordering: top-level replies chronologically, with each reply's children
        inserted directly after their parent, also chronologically.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        # Fetch all posts in this thread (any descendant)
        all_posts = (
            UpdatePost.scoped()
            .options(joinedload(UpdatePost.member).joinedload(WorkspaceUser.user))
            .filter(UpdatePost.parent_id.isnot(None))
            .filter(
                db.or_(
                    UpdatePost.parent_id == self.id,
                    UpdatePost.id.in_(
                        db.session.query(UpdatePost.id)
                        .filter(UpdatePost.parent_id.in_(
                            db.session.query(UpdatePost.id)
                            .filter(UpdatePost.parent_id == self.id)
                        ))
                    ),
                )
            )
            .order_by(UpdatePost.created_at.asc())
            .limit(limit)
            .all()
        )

        # Build parent->children map
        children_map = {}
        for p in all_posts:
            children_map.setdefault(p.parent_id, []).append(p)

        # Walk tree: top-level replies (parent_id == self.id), then their children
        result = []
        for reply in children_map.get(self.id, []):
            result.append((reply, 0))
            for child in children_map.get(reply.id, []):
                result.append((child, 1))

        return result

    @classmethod
    def _parse_mentioned_ids(cls, text: str) -> list[int]:
        """Extract WorkspaceUser IDs from @[member_id] mention tokens.

        Args:
            text: Raw post body that may contain @[member_id] tokens.

        Returns:
            List of integer WorkspaceUser IDs (de-duped, in order of appearance).
        """
        return [int(m) for m in re.findall(r"@\[(\d+)\]", text or "")]

    @classmethod
    def create_channel_post(cls, member_id, channel_id, body, subject=None):
        """Create a forum-style channel post using the first update template.

        Args:
            member_id: Author's workspace_user.id.
            channel_id: Channel to post into.
            body: Post body text.
            subject: Optional thread subject (for top-level posts).

        Returns:
            Created UpdatePost instance.
        """
        from .template import UpdateTemplate

        update_templates = UpdateTemplate.get_for_workspace(post_type="update")
        if not update_templates:
            raise ValueError("No update templates available")
        template = update_templates[0]

        first_text_key = next(
            (f["key"] for f in (template.fields or []) if f.get("type") in ("text", "textarea")),
            "body",
        )
        post = cls.create(
            template=template,
            member_id=member_id,
            payload={first_text_key: body},
            channel_id=channel_id,
            subject=subject,
        )
        mentioned_ids = list(dict.fromkeys(
            cls._parse_mentioned_ids(subject or "") + cls._parse_mentioned_ids(body)
        ))
        if mentioned_ids:
            post.mentioned_member_ids = mentioned_ids
            db.session.commit()
        cls._notify_mentioned_members(post, mentioned_ids)
        return post

    @classmethod
    def create_channel_reply(cls, member_id, channel_id, parent_id, body):
        """Create a reply to a post (channel thread or status update thread).

        Replies are always plain text — no template. Content stored as
        ``{"content": body}`` regardless of the parent's template.
        ``parent_id`` can point to any post in the thread (root or reply).
        Denormalized threading metadata is always updated on the root post.

        Args:
            member_id: Author's workspace_user.id.
            channel_id: Channel the thread belongs to (None for status updates).
            parent_id: Post ID to reply to (root post or another reply).
            body: Reply body text.

        Returns:
            Created UpdatePost instance.
        """
        parent = cls.scoped().filter_by(id=parent_id).first()
        if not parent:
            raise ValueError(f"Parent post {parent_id} not found")

        # Find the root post for denormalized counts
        root = parent.get_root_post() if parent.parent_id else parent

        payload = {"content": body}
        reply = cls.create(
            template=None,
            member_id=member_id,
            payload=payload,
            channel_id=channel_id,
            parent_id=parent_id,
            post_type=root.post_type,
        )

        mentioned_ids = cls._parse_mentioned_ids(body)
        if mentioned_ids:
            reply.mentioned_member_ids = mentioned_ids

        # Update root post's denormalized threading metadata
        root.reply_count_col = (root.reply_count_col or 0) + 1
        root.last_reply_at = reply.created_at
        root.last_reply_member_id = member_id
        db.session.commit()

        cls._notify_mentioned_members(reply, mentioned_ids)
        return reply

    @classmethod
    def create(cls, template, member_id, payload, channel_id=None, is_win=False,
               parent_id=None, subject=None, post_type=None):
        """Create a new post from a template.

        Applies visibility rules:
        - off_track → visibility='leads'
        - anonymous template → member_id=None, is_anonymous=True

        Raises:
            PermissionError: If the channel is linked to a closed project.
              Closed projects lock their channel to all writes (top-level
              posts and replies).

        Args:
            template: UpdateTemplate instance (or None for template-free posts).
            member_id: Author's workspace_user.id.
            payload: Dict of field values.
            channel_id: Optional channel to post into.
            is_win: Whether to flag this post as a win.
            post_type: Explicit post type (required when template is None).

        Returns:
            Created UpdatePost instance.
        """
        if channel_id is not None:
            from .channel import UpdateChannel
            from modules.base.projects.models.project import Project

            channel = UpdateChannel.get_by_id(channel_id)
            if Project.is_channel_locked(channel):
                raise PermissionError(
                    "Channel is locked because its project is closed."
                )

        visibility = "team"
        is_anonymous = template.anonymous if template else False
        actual_member_id = member_id

        # Anonymous templates hide the author
        if is_anonymous:
            actual_member_id = None

        resolved_post_type = post_type or (template.post_type if template else "channel")

        # Off-track pulse → leads only
        if template and template.post_type == "update" and payload.get("status") == "off_track":
            visibility = "leads"

        expires_at = None
        if template and template.post_type == "board":
            expires_at = datetime.utcnow() + timedelta(days=BOARD_EXPIRY_DAYS)

        post = cls(
            template_id=template.id if template else None,
            post_type=resolved_post_type,
            member_id=actual_member_id,
            payload=payload,
            visibility=visibility,
            is_anonymous=is_anonymous,
            expires_at=expires_at,
            channel_id=channel_id,
            is_win=bool(is_win),
            parent_id=parent_id,
            subject=subject[:300] if subject else None,
        )
        db.session.add(post)
        db.session.commit()
        return post

    @classmethod
    def create_current_activity(cls, member_id, text):
        """Post a one-line repo-activity item to a member's "Current" status.

        Used by the GitHub integration to surface commits/PRs as the actor's
        current status. The "Current" template's body is a structured_list, so
        the line is stored as a single ``{text: ...}`` item.

        Args:
            member_id: Author's workspace_user.id (the mapped sparQ member).
            text: Plain-text summary line (e.g. "Pushed 2 commits to main: …").

        Returns:
            The created UpdatePost, or None if the Current template is missing.
        """
        from .template import UpdateTemplate

        template = UpdateTemplate.get_by_name("Current", post_type="update")
        if not template:
            return None
        payload = {
            "body": [
                {
                    "text": (text or "")[:500],
                    "project_id": None,
                    "action_item_id": None,
                    "assignee_id": None,
                }
            ]
        }
        return cls.create(template=template, member_id=member_id, payload=payload)

    @classmethod
    def is_recent_duplicate(cls, member_id: int, template_id: int | None = None,
                            channel_id: int | None = None,
                            window_seconds: int = 30,
                            org_wide: bool = False) -> bool:
        """Check if this member posted recently with matching criteria.

        Args:
            member_id: Author's workspace_user.id.
            template_id: Template to match (omit to match any).
            channel_id: Channel to match (omit to match any).
            window_seconds: Lookback window in seconds.
            org_wide: Use org-wide scope (for org-level channels).

        Returns:
            True if a matching post exists within the window.
        """
        cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
        base = cls.org_wide() if org_wide else cls.scoped()
        q = base.filter(
            cls.member_id == member_id,
            cls.created_at >= cutoff,
        )
        if template_id is not None:
            q = q.filter(cls.template_id == template_id)
        if channel_id is not None:
            q = q.filter(cls.channel_id == channel_id)
        return q.first() is not None

    # ── Chat message class methods ────────────────────────────────────

    @classmethod
    def create_channel_message(
        cls,
        content: str,
        member_id: int,
        channel_id: int,
        target_user_id: int | None = None,
        message_type: str = "channel",
    ) -> "UpdatePost":
        """Create a channel message.

        Raises:
            PermissionError: If the channel is linked to a closed project.
        """
        from .channel import UpdateChannel
        from modules.base.projects.models.project import Project

        channel = UpdateChannel.get_by_id(channel_id)
        if Project.is_channel_locked(channel):
            raise PermissionError(
                "Channel is locked because its project is closed."
            )

        post = cls(
            template_id=None,
            post_type=message_type,
            member_id=member_id,
            payload={"content": content.strip()},
            channel_id=channel_id,
            target_user_id=target_user_id,
        )
        db.session.add(post)
        db.session.commit()
        return post

    @classmethod
    def create_with_mentions(
        cls,
        content: str,
        member_id: int,
        channel_id: int,
    ) -> "UpdatePost":
        """Create a channel message with @mention extraction."""
        post = cls.create_channel_message(
            content=content, member_id=member_id, channel_id=channel_id
        )

        # Extract @[member_id] mentions
        mentioned_ids = [int(m) for m in re.findall(r"@\[(\d+)\]", content or "")]

        # Handle @[channel] broadcast — resolve to all active members except sender
        if "@[channel]" in (content or ""):
            from modules.base.core.models.workspace_user import WorkspaceUser
            all_member_ids = [
                tu.id
                for tu in WorkspaceUser.scoped().filter(WorkspaceUser.id != member_id).all()
            ]
            mentioned_ids = list(set(mentioned_ids + all_member_ids))

        if mentioned_ids:
            post.mentioned_member_ids = mentioned_ids
            payload = dict(post.payload or {})
            payload["mentioned_member_ids"] = mentioned_ids
            post.payload = payload
            db.session.commit()

        cls._notify_mentioned_members(post, mentioned_ids)
        return post

    @classmethod
    def _notify_mentioned_members(cls, post: "UpdatePost", mentioned_ids: list[int]) -> None:
        """Send inbox notifications for @mentioned members."""
        if not mentioned_ids:
            return
        try:
            from sqlalchemy.orm import joinedload
            from modules.base.core.models.notification import NotificationCategory, SystemNotification
            from modules.base.core.models.workspace_user import WorkspaceUser
            from modules.base.core.services.push_notification import send_push

            author = (
                WorkspaceUser.scoped()
                .options(joinedload(WorkspaceUser.user))
                .filter_by(id=post.member_id)
                .first()
            ) if post.member_id else None
            author_name = author.user.first_name if author and author.user else "Someone"

            channel_name = ""
            if post.channel_id:
                from .channel import UpdateChannel
                ch = UpdateChannel.scoped().filter_by(id=post.channel_id).first()
                if ch:
                    channel_name = f" in {ch.name}"

            action_url = f"/sync/chat/{post.channel_id}" if post.channel_id else "/updates/"

            unique_ids = {mid for mid in mentioned_ids if mid != post.member_id}
            if not unique_ids:
                return
            members = (
                WorkspaceUser.scoped()
                .options(joinedload(WorkspaceUser.user))
                .filter(WorkspaceUser.id.in_(unique_ids))
                .all()
            )
            for member in members:
                if not member.user:
                    continue
                SystemNotification.create(
                    title="You were mentioned",
                    message=f"{author_name} mentioned you{channel_name}",
                    type="info",
                    target_role="user",
                    user_id=member.user_id,
                    icon="fa-at",
                    action_url=action_url,
                    category=NotificationCategory.MENTION,
                )
                send_push(
                    user_id=member.user_id,
                    title="You were mentioned",
                    body=f"{author_name} mentioned you{channel_name}",
                    url=action_url,
                )
        except Exception:
            logger.exception("Failed to send mention notifications for post %s", post.id)

    @classmethod
    def get_by_id(cls, post_id: int) -> "UpdatePost | None":
        """Get a post by ID."""
        return cls.scoped().filter_by(id=post_id).first()

    @classmethod
    def get_mentions_for_member(cls, member_id: int, limit: int = 5) -> list["UpdatePost"]:
        """Recent posts that @mention the given member. Filters in Python so it
        works across JSON/JSONB backends; scans the most recent ~200 posts."""
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        recent = (
            cls.scoped()
            .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
            .filter(cls.mentioned_member_ids.isnot(None))
            .order_by(cls.created_at.desc())
            .limit(200)
            .all()
        )
        out = []
        for p in recent:
            ids = p.mentioned_member_ids or []
            if member_id in ids:
                out.append(p)
                if len(out) >= limit:
                    break
        return out

    @classmethod
    def toggle_pin(cls, post_id: int) -> bool | None:
        """Toggle pinned status. Returns new pin status or None if not found."""
        post = cls.scoped().filter_by(id=post_id).first()
        if not post:
            return None
        post.pinned = not post.pinned
        db.session.commit()
        return post.pinned

    @classmethod
    def delete_message(cls, post_id: int) -> bool:
        """Delete a chat message."""
        post = cls.scoped().filter_by(id=post_id).first()
        if not post:
            return False
        db.session.delete(post)
        db.session.commit()
        return True

    @classmethod
    def bump(cls, original_post: "UpdatePost", member_id: int) -> "UpdatePost":
        """Create a bump (repost) of an existing post for the current interval.

        Copies the original's template, payload, and metadata into a new post.
        The bump is marked by a ``_bumped_from`` key in the payload JSON.

        Args:
            original_post: UpdatePost instance to bump.
            member_id: Author's workspace_user.id (must match original).

        Returns:
            Created UpdatePost instance.

        Raises:
            ValueError: If the post type is not bumpable or member doesn't own it.
        """
        if original_post.post_type not in ("update",):
            raise ValueError("Only update posts can be bumped.")
        if not original_post.template or original_post.template.schedule_type != "periodic":
            raise ValueError("Only periodic check-in posts can be bumped.")
        if original_post.member_id != member_id:
            raise ValueError("Only the author can bump their own post.")

        payload = {**original_post.payload, "_bumped_from": original_post.id}

        post = cls(
            template_id=original_post.template_id,
            post_type=original_post.post_type,
            member_id=member_id,
            payload=payload,
            visibility=original_post.visibility,
            is_anonymous=original_post.is_anonymous,
            area_id=original_post.area_id,
        )
        db.session.add(post)
        db.session.commit()
        return post

    @property
    def is_bump(self) -> bool:
        """Whether this post is a bump of a previous post."""
        return bool(self.payload.get("_bumped_from"))

    @classmethod
    def get_feed(cls, post_type, template_id=None, today_only=False, limit=None, offset=0, member_id=None, area_id=None):
        """Get posts for a feed view.

        Args:
            post_type: Filter by post_type (string or list of strings).
            template_id: Optional filter by template.
            today_only: Only include today's posts.
            limit: Max results (returns (posts, has_more) tuple when set).
            offset: Number of rows to skip (used with limit).
            member_id: Optional filter by author's workspace_user.id.
            area_id: Optional filter by area.
        """
        from datetime import date

        from sqlalchemy.orm import joinedload

        from modules.base.core.models.workspace_user import WorkspaceUser

        now = datetime.utcnow()

        if isinstance(post_type, (list, tuple)):
            query = cls.scoped().filter(cls.post_type.in_(post_type))
        else:
            query = cls.scoped().filter(cls.post_type == post_type)

        # Eager-load relationships the feed templates touch on every post,
        # otherwise each row triggers a fresh SELECT (classic N+1).
        query = query.options(
            joinedload(cls.template),
            joinedload(cls.member).joinedload(WorkspaceUser.user),
            joinedload(cls.area),
        )

        # Exclude soft-deleted (expired) posts
        query = query.filter(db.or_(cls.expires_at.is_(None), cls.expires_at > now))

        # Exclude channel discussion posts and replies — those belong in
        # channel feeds, not the status/update feed.
        query = query.filter(
            cls.channel_id.is_(None),
            cls.parent_id.is_(None),
        )

        if template_id:
            query = query.filter(cls.template_id == template_id)

        if member_id:
            query = query.filter(cls.member_id == member_id)

        if area_id:
            query = query.filter(cls.area_id == area_id)

        if today_only:
            query = query.filter(db.func.date(cls.created_at) == date.today())

        query = query.order_by(cls.created_at.desc())

        if limit:
            query = query.offset(offset).limit(limit + 1)
            results = query.all()
            has_more = len(results) > limit
            return results[:limit], has_more

        return query.all(), False

    @classmethod
    def get_recent_for_member_template(
        cls, member_id: int, template_id: int, limit: int = 3
    ) -> list["UpdatePost"]:
        """Return the most recent unique posts by a member for a given template.

        Used to populate the bump picker on the post creation form. Applies two
        dedup passes so the picker shows only distinct, non-superseded options:

        1. Superseded filter — if post A was bumped to create post B, post A is
           excluded; only the most recent version in a bump chain is shown.
        2. Content dedup — if two posts have identical payload content, only the
           newest is kept (comparison ignores the internal ``_bumped_from`` key).

        Fetches ``limit * 5`` candidates to have enough after filtering.

        Args:
            member_id: Author's workspace_user.id.
            template_id: Template to filter by.
            limit: Maximum number of unique posts to return.

        Returns:
            List of UpdatePost instances ordered newest-first, length <= limit.
        """
        now = datetime.utcnow()
        candidates = (
            cls.scoped()
            .filter(
                cls.member_id == member_id,
                cls.template_id == template_id,
                cls.channel_id.is_(None),
                cls.parent_id.is_(None),
                db.or_(cls.expires_at.is_(None), cls.expires_at > now),
            )
            .order_by(cls.created_at.desc())
            .limit(limit * 5)
            .all()
        )

        # ids that have been superseded by a newer bump
        bumped_from_ids = {
            p.payload.get("_bumped_from")
            for p in candidates
            if p.payload.get("_bumped_from")
        }

        # Dedup by visible text — if two posts render identically in the picker,
        # only the newest (first encountered, since candidates are newest-first)
        # should be shown.
        results: list["UpdatePost"] = []
        seen_text: set[str] = set()
        for p in candidates:
            if p.id in bumped_from_ids:
                continue
            text = p.preview_text()
            if text in seen_text:
                continue
            seen_text.add(text)
            results.append(p)
            if len(results) >= limit:
                break

        return results

    @classmethod
    def get_promoted_to_dashboard(cls, limit: int = 5) -> list["UpdatePost"]:
        """Get active board posts promoted to the workspace dashboard.

        Args:
            limit: Max number of results.

        Returns:
            Non-expired board posts with promoted_to_dashboard=True, newest first.
        """
        now = datetime.utcnow()
        return (
            cls.scoped()
            .filter(
                cls.post_type == "board",
                cls.promoted_to_dashboard.is_(True),
                db.or_(cls.expires_at.is_(None), cls.expires_at > now),
            )
            .order_by(cls.created_at.desc())
            .limit(limit)
            .all()
        )

    @classmethod
    def get_latest_status_per_member(cls, member_ids: list[int]) -> dict[int, dict[str, str | bool]]:
        """Get the most recent status post per member (working-on or blocker).

        Checks "Current", "Async - Standup", and "I'm blocked"
        posts. If a member's most recent status post is a blocker, returns
        that instead.

        Args:
            member_ids: List of WorkspaceUser IDs to look up.

        Returns:
            Dict mapping member_id to ``{"text": str, "is_blocked": bool}``.
        """
        if not member_ids:
            return {}

        from datetime import datetime as dt, timedelta

        from .template import UpdateTemplate

        cutoff = dt.utcnow() - timedelta(days=14)
        posts = (
            cls.scoped()
            .join(UpdateTemplate, cls.template_id == UpdateTemplate.id)
            .filter(
                cls.member_id.in_(member_ids),
                cls.post_type == "update",
                cls.created_at >= cutoff,
                UpdateTemplate.name.in_(["Current", "Async - Standup", "I'm blocked"]),
            )
            .order_by(cls.created_at.desc())
            .all()
        )

        # Batch-check which blocker action items are resolved
        blocker_ai_ids = set()
        for post in posts:
            if post.template and post.template.name == "I'm blocked":
                ai_id = (post.payload or {}).get("action_item_id")
                if ai_id:
                    blocker_ai_ids.add(int(ai_id))

        resolved_ai_ids: set[int] = set()
        if blocker_ai_ids:
            from modules.base.tasks.models.task import Task
            resolved = Task.scoped().filter(
                Task.id.in_(blocker_ai_ids),
                Task.status == "resolved",
            ).all()
            resolved_ai_ids = {a.id for a in resolved}

        result: dict[int, dict[str, str | bool]] = {}
        for post in posts:
            if post.member_id in result:
                continue
            payload = post.payload or {}
            body = payload.get("body") or payload.get("working_on")
            is_blocked = post.template and post.template.name == "I'm blocked"

            if is_blocked:
                ai_id = payload.get("action_item_id")
                if ai_id and int(ai_id) in resolved_ai_ids:
                    continue
                text = body if isinstance(body, str) else ""
                if text:
                    result[post.member_id] = {"text": text, "is_blocked": True}
            elif isinstance(body, list) and body:
                text = " · ".join(
                    item.get("text", "") for item in body if item.get("text")
                )
                if text:
                    result[post.member_id] = {"text": text, "is_blocked": False}
        return result

    @classmethod
    def get_for_date_range(cls, start_date, end_date, post_types=None):
        """Get posts within a date range.

        Args:
            start_date: Start date (inclusive).
            end_date: End date (inclusive).
            post_types: Optional list of post_type strings to filter by.

        Returns:
            List of UpdatePost instances, newest first.
        """
        from datetime import datetime as dt

        start_dt = dt.combine(start_date, dt.min.time())
        end_dt = dt.combine(end_date, dt.max.time())

        query = cls.scoped().filter(
            cls.created_at >= start_dt,
            cls.created_at <= end_dt,
        )
        if post_types:
            query = query.filter(cls.post_type.in_(post_types))
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def count_by_type_in_range(cls, post_type, start_date, end_date):
        """Count posts of a given type within a date range.

        Args:
            post_type: The post_type string (e.g. 'update').
            start_date: Start date (inclusive).
            end_date: End date (inclusive).

        Returns:
            Integer count.
        """
        from datetime import datetime as dt

        start_dt = dt.combine(start_date, dt.min.time())
        end_dt = dt.combine(end_date, dt.max.time())

        return cls.scoped().filter(
            cls.post_type == post_type,
            cls.created_at >= start_dt,
            cls.created_at <= end_dt,
        ).count()

    @classmethod
    def get_board_feed(cls, template_id=None):
        """Get active (non-expired) board posts.

        Args:
            template_id: Optional filter by template/category.
        """
        from sqlalchemy.orm import joinedload

        from modules.base.core.models.workspace_user import WorkspaceUser

        now = datetime.utcnow()
        query = cls.scoped().options(
            joinedload(cls.template),
            joinedload(cls.member).joinedload(WorkspaceUser.user),
            joinedload(cls.area),
        ).filter(
            cls.post_type == "board",
            db.or_(cls.expires_at.is_(None), cls.expires_at > now),
        )
        if template_id:
            query = query.filter(cls.template_id == template_id)
        return query.order_by(cls.created_at.desc()).all()

    def tag_area(self, area_id):
        """Tag this post with an area.

        Args:
            area_id: Area ID to associate, or None to clear.
        """
        self.area_id = area_id
        db.session.commit()

    def update_payload(self, payload: dict) -> None:
        """Update this post's payload content.

        Args:
            payload: New payload dict keyed by template field keys.
        """
        self.payload = payload
        db.session.commit()

    def soft_delete(self) -> None:
        """Soft-delete this post by setting expires_at to now."""
        # Decrement root post's reply count if this is a reply
        if self.parent_id:
            root = self.get_root_post()
            if root and root.reply_count_col and root.reply_count_col > 0:
                root.reply_count_col -= 1
        self.expires_at = datetime.utcnow()
        db.session.commit()

    def refresh_expiry(self):
        """Extend this post's expiry by 30 days from now."""
        self.expires_at = datetime.utcnow() + timedelta(days=BOARD_EXPIRY_DAYS)
        db.session.commit()

    def set_promoted(self, value: bool) -> None:
        self.promoted_to_dashboard = value
        db.session.commit()

    @property
    def is_expired(self):
        """Check if this post has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def days_until_expiry(self):
        """Days remaining until expiry, or None if no expiry."""
        if self.expires_at is None:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)

    def time_ago(self):
        """Return human-readable time since post was created."""
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

    def preview_parts(self) -> list[tuple[str, str, list[str]]]:
        """Return structured preview data from the post's payload.

        Walks the post's template fields and extracts plain text from the
        structured payload. This is the single source of field-walking
        logic — consumers format the output for their context (flat text
        for dashboards, HTML for emails, etc.).

        Returns:
            List of (label, field_type, texts) tuples. Each tuple has the
            field's human-readable label, its type identifier, and the list
            of text values extracted from the payload. Empty list if payload
            has no renderable text.
        """
        if not self.payload:
            return []

        # Board posts: title lives at payload["title"]
        if self.post_type == "board":
            title = str(self.payload.get("title") or "")
            return [("", "title", [title])] if title else []

        # Walk template fields when available — preferred path
        template = self.template if self.template_id else None
        fields = (template.fields or []) if template else []

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
                # scale and unknown types intentionally skipped
            return parts

        # Legacy / no-template fallback: pull string-ish leaves
        texts = [v.strip() for v in self.payload.values()
                 if isinstance(v, str) and v.strip()]
        return [("", "text", texts)] if texts else []

    def preview_text(self) -> str:
        """Return a flat human-readable preview of the post's payload.

        One-line summary used by dashboard cards and any surface that needs
        a compact text representation. Joins all text values with " · ".

        Returns:
            Plain-text preview, never None. Empty string if payload has no
            renderable text. Caller is responsible for truncation/escaping.
        """
        return " · ".join(
            text for _, _, items in self.preview_parts() for text in items
        )

    @classmethod
    def get_my_pulse_today(cls, member_id, template_id=None):
        """Get current member's pulse posts for today.

        Args:
            member_id: The member's ID.
            template_id: Optional template ID to filter by.
        """
        from datetime import date

        query = cls.scoped().filter(
            cls.post_type == "update",
            cls.member_id == member_id,
            db.func.date(cls.created_at) == date.today(),
        )
        if template_id is not None:
            query = query.filter(cls.template_id == template_id)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_github_thread_root(cls, channel_id: int, webhook_id: int) -> "UpdatePost | None":
        """Find the root post for a GitHub webhook thread in this channel.

        Returns the OLDEST top-level (parent_id IS NULL) webhook post whose
        payload.webhook_id matches AND whose content is a GitHub-rendered
        block (starts with GITHUB_HTML::). All subsequent GitHub events for
        the same webhook are appended as replies to this root.
        """
        candidates = (
            cls.scoped()
            .filter(
                cls.channel_id == channel_id,
                cls.post_type == "webhook",
                cls.parent_id.is_(None),
            )
            .order_by(cls.created_at.asc())
            .all()
        )
        for p in candidates:
            payload = p.payload or {}
            if payload.get("webhook_id") != webhook_id:
                continue
            content = payload.get("content") or ""
            if content.startswith("GITHUB_HTML::"):
                return p
        return None

    @classmethod
    def trim_github_thread_replies(cls, root_id: int, keep: int = 10) -> int:
        """Delete github-thread replies older than the Nth most recent.

        Keeps the root untouched and the `keep` newest direct replies.
        Returns the number of posts deleted.
        """
        replies = (
            cls.scoped()
            .filter(cls.parent_id == root_id)
            .order_by(cls.created_at.desc())
            .all()
        )
        if len(replies) <= keep:
            return 0
        to_delete = replies[keep:]
        for r in to_delete:
            db.session.delete(r)
        db.session.commit()
        return len(to_delete)

    @classmethod
    def create_from_webhook(cls, content, channel_id, webhook_id, username=None, parent_id=None):
        """Create a post from an incoming webhook payload.

        Stores webhook metadata in the payload JSON. Uses a system-level
        webhook template (workspace_id=NULL, post_type='webhook').

        Args:
            content: Webhook message content (may include HTML).
            channel_id: Channel to post into.
            webhook_id: UpdateWebhook.id that received the payload.
            username: Display name of the webhook source.

        Returns:
            Created UpdatePost instance.
        """
        from .template import UpdateTemplate

        template = UpdateTemplate.query.filter_by(
            post_type="webhook", workspace_id=None
        ).first()
        if not template:
            template = UpdateTemplate(
                post_type="webhook",
                name="Webhook",
                description="Auto-created posts from webhook integrations",
                fields=[{"key": "content", "type": "text", "label": "Content"}],
                is_active=False,  # Not shown in composer menus
                workspace_id=None,
            )
            db.session.add(template)
            db.session.flush()

        post = cls(
            template_id=template.id,
            post_type="webhook",
            member_id=None,
            payload={
                "content": content,
                "webhook_id": webhook_id,
                "webhook_username": username or "Webhook",
            },
            visibility="team",
            is_anonymous=False,
            channel_id=channel_id,
            parent_id=parent_id,
        )
        db.session.add(post)
        db.session.commit()
        return post

    def mark_as_win(self):
        """Flag this post as a win."""
        self.is_win = True
        db.session.commit()

    def unmark_as_win(self):
        """Remove the win flag from this post."""
        self.is_win = False
        db.session.commit()

    @classmethod
    def wins_feed_for_scope(cls, limit: int | None = None, offset: int = 0):
        """Return the wins feed for the current scope.

          - workspace scope: wins posted in g.workspace_id.
          - organization scope: wins in org-wide posts (workspace_id IS NULL).

        Visibility derives purely from workspace_id now — org-wide wins are
        wins created when g.scope was 'organization' (no workspace stamped).

        Args:
            limit: Max results.
            offset: Rows to skip.

        Returns:
            (posts, has_more)
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        query = (
            cls.scoped()
            .options(
                joinedload(cls.member).joinedload(WorkspaceUser.user),
                joinedload(cls.template),
                joinedload(cls.channel),
            )
            .filter(cls.is_win.is_(True))
            .order_by(cls.created_at.desc())
        )

        if limit:
            results = query.offset(offset).limit(limit + 1).all()
            has_more = len(results) > limit
            return results[:limit], has_more
        return query.all(), False

    @classmethod
    def get_wins_feed(cls, limit=None, offset=0):
        """Get posts flagged as wins (workspace-scoped legacy entry point).

        Args:
            limit: Max results.
            offset: Number of rows to skip.

        Returns:
            Tuple of (posts, has_more).
        """
        query = cls.scoped().filter(cls.is_win.is_(True)).order_by(cls.created_at.desc())
        if limit:
            query = query.offset(offset).limit(limit + 1)
            results = query.all()
            has_more = len(results) > limit
            return results[:limit], has_more
        return query.all(), False

    @classmethod
    def get_channel_feed(cls, channel_id, limit=None, offset=0):
        """Get posts for a specific channel.

        Args:
            channel_id: The channel's ID.
            limit: Max results.
            offset: Number of rows to skip.

        Returns:
            Tuple of (posts, has_more).
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        query = (
            cls.scoped()
            .options(
                joinedload(cls.member).joinedload(WorkspaceUser.user),
                joinedload(cls.template),
            )
            .filter(cls.channel_id == channel_id, cls.parent_id.is_(None))
            .order_by(db.func.coalesce(cls.last_reply_at, cls.created_at).desc())
        )
        if limit:
            query = query.offset(offset).limit(limit + 1)
            results = query.all()
            has_more = len(results) > limit
            return results[:limit], has_more
        return query.all(), False

    @classmethod
    def get_activity_feed(cls, limit=None, offset=0):
        """Get webhook-originated posts for the activity feed.

        Args:
            limit: Max results.
            offset: Number of rows to skip.

        Returns:
            Tuple of (posts, has_more).
        """
        from sqlalchemy.orm import joinedload

        query = (
            cls.scoped()
            .options(joinedload(cls.channel))
            .filter(cls.post_type == "webhook")
            .order_by(cls.created_at.desc())
        )
        if limit:
            query = query.offset(offset).limit(limit + 1)
            results = query.all()
            has_more = len(results) > limit
            return results[:limit], has_more
        return query.all(), False

    @classmethod
    def get_ackable_by_ids(cls, post_ids: list[int]) -> dict[int, "UpdatePost"]:
        """Get non-anonymous posts with authors for a set of IDs.

        Filters out anonymous posts and posts without an author,
        returning only those eligible for 10-4 acknowledgment.

        Args:
            post_ids: List of update_post IDs to look up.

        Returns:
            Dict mapping post ID to UpdatePost for eligible posts.
        """
        posts = cls.scoped().filter(cls.id.in_(post_ids)).all()
        return {
            p.id: p for p in posts
            if not p.is_anonymous and p.member_id
        }
