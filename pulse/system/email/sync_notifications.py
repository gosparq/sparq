# -----------------------------------------------------------------------------
# sparQ - Sync Email Notifications
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Email notifications for Sync follow system.

Provides 60-second batching for follow notifications and immediate
delivery for @mention notifications.
"""

import logging
import sys
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


def _format_time(dt_utc: datetime) -> str:
    """Format a UTC datetime as local time using company timezone and time_format.

    Must be called within Flask request context (needs WorkspaceSettings access).
    Falls back to UTC 12-hour format on any error.
    """
    try:
        import pytz
        from modules.base.core.models.workspace_settings import WorkspaceSettings

        settings = WorkspaceSettings.get_instance()
        tz_name = settings.timezone or "America/Chicago"
        local_tz = pytz.timezone(tz_name)

        if dt_utc.tzinfo is None:
            dt_utc = pytz.UTC.localize(dt_utc)
        local_dt = dt_utc.astimezone(local_tz)

        if settings.time_format == "24-hour":
            return local_dt.strftime("%H:%M")
        return local_dt.strftime("%I:%M %p")
    except Exception:
        return dt_utc.strftime("%I:%M %p")


def _log(msg: str) -> None:
    """Log to both logger and stderr (flush immediately for gunicorn)."""
    logger.info(msg)
    print(msg, file=sys.stderr, flush=True)

# Batching state — keyed by (entity_type, entity_id)
_pending_batches: dict[tuple[str, int], list[dict]] = {}
_batch_timers: dict[tuple[str, int], threading.Timer] = {}
_batch_lock = threading.Lock()

# Track which (member_id, content_key) pairs have pending follow emails
# to avoid duplicate mention emails
_pending_follow_recipients: dict[tuple[str, int], set[int]] = {}


def notify_followers(entity_type: str, entity_id: int, content, author_member):
    """Queue a follow notification with 60-second batching.

    Args:
        entity_type: 'channel', 'status_template', or 'board_template'
        entity_id: ID of the entity
        content: UpdatePost object
        author_member: WorkspaceUser who created the content
    """
    from flask import current_app

    # Collect item info synchronously while we have app context
    item = _extract_item_info(entity_type, entity_id, content, author_member)
    if not item:
        return

    # Capture Flask app and workspace context — timer thread won't have either
    app = current_app._get_current_object()
    from flask import g
    workspace_id = getattr(g, "workspace_id", None)
    batch_key = (entity_type, entity_id)
    _log(f"[FOLLOW] notify_followers called: {entity_type}:{entity_id} by member {author_member.id} (ts={workspace_id})")

    with _batch_lock:
        if batch_key not in _pending_batches:
            _pending_batches[batch_key] = []
            _pending_follow_recipients[batch_key] = set()

        _pending_batches[batch_key].append(item)

        # Track follower member IDs for dedup with mentions
        from modules.base.updates.models.follow import UpdateFollow
        followers = UpdateFollow.get_followers(entity_type, entity_id)
        for f in followers:
            if f.id != author_member.id:
                _pending_follow_recipients[batch_key].add(f.id)

        # Start timer on first message, let subsequent ones accumulate
        if batch_key not in _batch_timers or not _batch_timers[batch_key].is_alive():
            timer = threading.Timer(60.0, _flush_batch, args=[batch_key, app, workspace_id])
            timer.daemon = True
            timer.start()
            _batch_timers[batch_key] = timer


def _flush_batch(batch_key: tuple[str, int], app, workspace_id):
    """Fire when the 60-second window expires. Dispatches batched email.

    Args:
        batch_key: (entity_type, entity_id) tuple
        app: Flask app instance captured when the timer was created
        workspace_id: Workspace ID for scoped queries
    """
    from system.background import executor

    with _batch_lock:
        items = _pending_batches.pop(batch_key, [])
        _batch_timers.pop(batch_key, None)
        _pending_follow_recipients.pop(batch_key, None)

    if not items:
        return

    entity_type, entity_id = batch_key
    author_member_id = items[0].get("author_member_id")

    _log(f"[FOLLOW] Flushing batch {entity_type}:{entity_id} with {len(items)} items")

    # Use executor directly with captured app + scope context
    def run_with_context():
        try:
            with app.app_context():
                from flask import g
                from modules.base.core.models.workspace import Workspace
                g.workspace_id = workspace_id
                ts = Workspace.query.get(workspace_id) if workspace_id else None
                if ts is not None:
                    g.organization_id = ts.organization_id
                _dispatch_notifications(entity_type, entity_id, items, author_member_id)
        except Exception as e:
            _log(f"[FOLLOW] ERROR in dispatch: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()

    executor.submit(run_with_context)


def _dispatch_notifications(entity_type: str, entity_id: int, items: list[dict], author_member_id: int | None):
    """Background task: send batched email and in-app notifications to all followers."""
    from modules.base.updates.models.follow import UpdateFollow
    from system.email.service import send_email_async

    followers = UpdateFollow.get_followers(entity_type, entity_id)
    _log(f"[FOLLOW] Dispatching to {len(followers)} followers for {entity_type}:{entity_id}")
    if not followers:
        return

    entity_name = items[0].get("entity_name", "")
    author_name = items[0].get("author_name", "Unknown")
    subject = _format_subject(entity_type, entity_name, author_name, items)
    html_body = _build_notification_email(entity_type, entity_name, items)
    view_url = items[0].get("view_url", "/sync/")

    # Build in-app notification content
    preview = items[0].get("preview", "")
    if len(items) > 1:
        inapp_message = f"{len(items)} new messages"
    else:
        inapp_message = f"{author_name}: {preview[:80]}" if preview else f"{author_name} posted"
    if entity_type == "channel":
        inapp_title = f"#{entity_name}" if entity_name else "Channel"
    else:
        inapp_title = entity_name

    for member in followers:
        if member.user and member.user.email:
            send_email_async(to=member.user.email, subject=subject, html_body=html_body)
            _log(f"[FOLLOW] Queued notification email to {member.user.email} for {entity_type}:{entity_id}")

        # In-app bell notification — skip the author
        if member.id == author_member_id:
            continue
        if not member.user_id:
            continue
        try:
            from modules.base.core.models.notification import SystemNotification
            SystemNotification.create(
                title=inapp_title,
                message=inapp_message,
                type="info",
                target_role="user",
                user_id=member.user_id,
                icon="fa-comment",
                action_url=view_url,
                category="system",
            )
        except Exception as e:
            _log(f"[FOLLOW] Error creating in-app notification for member {member.id}: {e}")


def notify_mention(member_id: int, content, author_member):
    """Send immediate email for @mention. Skips if member is already getting a follow email.

    Args:
        member_id: ID of the mentioned WorkspaceUser
        content: UpdatePost object
        author_member: WorkspaceUser who created the content
    """
    if member_id == author_member.id:
        return  # Don't notify self-mentions

    # Check if this member is already getting a follow notification for this content
    with _batch_lock:
        for batch_key, recipients in _pending_follow_recipients.items():
            if member_id in recipients:
                logger.info(f"[MENTION] Skipping mention email for member {member_id} — already in follow batch")
                return

    # Extract info while we have request context
    from flask import request

    author_name = author_member.user.full_name if author_member and author_member.user else "Unknown"

    if hasattr(content, "preview_text") and getattr(content, "template_id", None):
        preview = content.preview_text()
    elif hasattr(content, "plain_text_content"):
        preview = content.plain_text_content or ""
    elif hasattr(content, "content"):
        preview = content.content or ""
    else:
        preview = ""

    base_url = request.host_url.rstrip("/")
    view_url = f"{base_url}/sync/"

    from system.background import submit_task
    submit_task(_dispatch_mention, member_id, author_name, preview, view_url)


def _dispatch_mention(member_id: int, author_name: str, preview: str, view_url: str):
    """Background task: send mention email."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.email.service import send_email_async

    member = WorkspaceUser.query.get(member_id)
    if not member or not member.user or not member.user.email:
        return

    preview_short = preview[:80] + "..." if len(preview) > 80 else preview

    subject = f"{author_name} mentioned you: {preview_short[:40]}"
    html_body = _build_mention_email(author_name, preview, view_url)

    send_email_async(to=member.user.email, subject=subject, html_body=html_body)
    logger.info(f"[MENTION] Queued mention email to {member.user.email}")


def _extract_item_info(entity_type: str, entity_id: int, content, author_member) -> dict | None:
    """Extract serializable info from content for batching."""
    from flask import request

    author_name = "Unknown"
    if author_member and author_member.user:
        author_name = author_member.user.full_name

    entity_name = ""
    if entity_type == "channel":
        from modules.base.updates.models.channel import UpdateChannel
        channel = UpdateChannel.query.get(entity_id)
        entity_name = channel.name if channel else ""
    elif entity_type in ("status_template", "board_template"):
        from modules.base.updates.models.template import UpdateTemplate
        tmpl = UpdateTemplate.query.get(entity_id)
        entity_name = tmpl.name if tmpl else ""

    if hasattr(content, "preview_parts") and getattr(content, "template_id", None):
        parts = content.preview_parts()
        preview = " · ".join(t for _, _, texts in parts for t in texts)
        preview_html = _render_preview_html(parts)
    elif hasattr(content, "plain_text_content"):
        preview = content.plain_text_content or ""
        preview_html = ""
    elif hasattr(content, "content"):
        preview = content.content or ""
        preview_html = ""
    else:
        preview = ""
        preview_html = ""

    # Build view URL
    base_url = request.host_url.rstrip("/")
    if entity_type == "channel":
        view_url = f"{base_url}/sync/chat/channels/{entity_name}"
    elif entity_type == "status_template":
        view_url = f"{base_url}/sync/updates/"
    elif entity_type == "board_template":
        view_url = f"{base_url}/sync/board/"
    else:
        view_url = base_url

    return {
        "author_name": author_name,
        "author_member_id": author_member.id if author_member else None,
        "entity_name": entity_name,
        "preview": preview,
        "preview_html": preview_html,
        "created_at": _format_time(datetime.utcnow()),
        "view_url": view_url,
    }


def _render_preview_html(parts: list[tuple[str, str, list[str]]]) -> str:
    """Render preview parts as email-safe HTML with field labels and bullets.

    Args:
        parts: Output of UpdatePost.preview_parts() — list of
               (label, field_type, texts) tuples.

    Returns:
        HTML string with inline styles suitable for email clients.
        Empty string if parts is empty.
    """
    from html import escape

    if not parts:
        return ""

    sections: list[str] = []
    for label, ftype, texts in parts:
        heading = (
            f'<div style="font-size:12px;color:#6b7280;margin-bottom:2px;">'
            f'{escape(label)}</div>'
        ) if label else ""

        if ftype in ("structured_list", "bullets"):
            items = "".join(
                f'<li style="margin:2px 0;color:#4b5563;">{escape(t)}</li>'
                for t in texts
            )
            sections.append(
                f'{heading}<ul style="margin:0 0 8px;padding-left:20px;">{items}</ul>'
            )
        else:
            for t in texts:
                sections.append(
                    f'{heading}<div style="color:#4b5563;margin-bottom:8px;">{escape(t)}</div>'
                )

    return "".join(sections)


def _format_subject(entity_type: str, entity_name: str, author_name: str, items: list[dict]) -> str:
    """Format email subject line, truncated to ~70 chars."""
    if entity_type == "channel":
        prefix = f"[#{entity_name}]"
    else:
        prefix = f"[{entity_name}]"

    if len(items) == 1:
        preview = items[0].get("preview", "")
        preview_short = preview[:50] + "..." if len(preview) > 50 else preview
        subject = f"{prefix} {author_name}: {preview_short}"
    else:
        subject = f"{prefix} {len(items)} new messages"

    # Truncate to ~80 chars
    if len(subject) > 80:
        subject = subject[:77] + "..."
    return subject


def _build_notification_email(entity_type: str, entity_name: str, items: list[dict]) -> str:
    """Build HTML body for follow notification email."""
    if entity_type == "channel":
        header = f"New messages in #{entity_name}"
    else:
        header = f"New posts in {entity_name}"

    view_url = items[0].get("view_url", "#") if items else "#"

    messages_html = ""
    for item in items:
        # Prefer structured HTML preview (already escaped); fall back to plain text
        preview_html = item.get("preview_html", "")
        if preview_html:
            content_html = f'<div style="font-size:14px;margin-top:4px;">{preview_html}</div>'
        else:
            preview = item.get("preview", "").replace("<", "&lt;").replace(">", "&gt;")
            if len(preview) > 300:
                preview = preview[:300] + "..."
            content_html = f'<span style="color:#4b5563;font-size:14px;">{preview}</span>'
        messages_html += f"""
        <tr>
            <td style="padding:8px 0;border-bottom:1px solid #f0f0f0;">
                <strong style="color:#374151;">{item.get('author_name', 'Unknown')}</strong>
                <span style="color:#9ca3af;font-size:12px;margin-left:8px;">{item.get('created_at', '')}</span>
                <br>
                {content_html}
            </td>
        </tr>"""

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#f9fafb;border-radius:8px;padding:24px;margin:16px 0;">
            <h2 style="margin:0 0 16px;font-size:18px;color:#111827;">{header}</h2>
            <table style="width:100%;border-collapse:collapse;">
                {messages_html}
            </table>
            <div style="margin-top:20px;">
                <a href="{view_url}" style="display:inline-block;background:#4f46e5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px;">View in sparQ</a>
                <p style="margin:8px 0 0;font-size:12px;color:#9ca3af;"><a href="{view_url}" style="color:#6b7280;">{view_url}</a></p>
            </div>
        </div>
        <p style="color:#9ca3af;font-size:12px;text-align:center;">
            You're receiving this because you follow this {entity_type.replace('_', ' ')}.
        </p>
    </div>"""


def _build_mention_email(author_name: str, preview: str, view_url: str) -> str:
    """Build HTML body for @mention notification email."""
    preview_safe = preview.replace("<", "&lt;").replace(">", "&gt;")
    if len(preview_safe) > 300:
        preview_safe = preview_safe[:300] + "..."

    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:600px;margin:0 auto;">
        <div style="background:#f9fafb;border-radius:8px;padding:24px;margin:16px 0;">
            <h2 style="margin:0 0 16px;font-size:18px;color:#111827;">{author_name} mentioned you</h2>
            <div style="padding:12px;background:#fff;border:1px solid #e5e7eb;border-radius:6px;">
                <span style="color:#4b5563;font-size:14px;">{preview_safe}</span>
            </div>
            <div style="margin-top:20px;">
                <a href="{view_url}" style="display:inline-block;background:#4f46e5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-size:14px;">View in sparQ</a>
                <p style="margin:8px 0 0;font-size:12px;color:#9ca3af;"><a href="{view_url}" style="color:#6b7280;">{view_url}</a></p>
            </div>
        </div>
        <p style="color:#9ca3af;font-size:12px;text-align:center;">
            You were @mentioned in sparQ Sync.
        </p>
    </div>"""
