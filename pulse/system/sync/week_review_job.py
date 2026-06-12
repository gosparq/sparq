# -----------------------------------------------------------------------------
# sparQ - Week in Review Job
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Background job that generates the Week in Review summary.

Collects data from the current Mon-Fri period:
- Win posts
- Blockers opened and resolved
- Pulse on-track / off-track summary
- Active member count, messages sent, updates posted

Generates a structured markdown summary (template-based, no AI dependency).
Notifies admins when the review is ready.

Usage:
    from system.background import submit_task
    from system.sync.week_review_job import generate_week_review
    submit_task(generate_week_review)
"""

import logging
from datetime import date, datetime, timedelta

from system.db.database import db

logger = logging.getLogger(__name__)


def generate_week_review():
    """Generate the Week in Review summary for the current week.

    Creates or updates an UpdateWeekReview draft with a structured markdown
    summary. Notifies admins via SystemNotification when complete.
    """
    from modules.base.core.models.notification import SystemNotification
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.week_review import UpdateWeekReview

    # Determine the current week boundaries (Mon 00:00 - Fri 23:59)
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)
    week_start_dt = datetime.combine(monday, datetime.min.time())
    week_end_dt = datetime.combine(friday, datetime.max.time())

    # Get or create the review draft
    review = UpdateWeekReview.get_or_create_for_week(monday)

    # ── Collect data ──

    # Wins
    win_posts = (
        UpdatePost.scoped()
        .filter(
            UpdatePost.post_type == "win",
            UpdatePost.created_at >= week_start_dt,
            UpdatePost.created_at <= week_end_dt,
        )
        .order_by(UpdatePost.created_at.asc())
        .all()
    )

    win_lines = []
    for post in win_posts:
        # Try to extract a meaningful text from the payload
        text = _extract_post_text(post)
        author_name = _get_author_name(post)
        if text:
            win_lines.append(f"- {text} ({author_name})")

    # Pulse summary
    pulse_posts = (
        UpdatePost.scoped()
        .filter(
            UpdatePost.post_type == "pulse",
            UpdatePost.created_at >= week_start_dt,
            UpdatePost.created_at <= week_end_dt,
        )
        .all()
    )

    on_track_count = 0
    off_track_count = 0
    energy_values = []
    for post in pulse_posts:
        payload = post.payload or {}
        status = payload.get("status", "")
        if status == "on_track":
            on_track_count += 1
        elif status == "off_track":
            off_track_count += 1
        energy = payload.get("energy")
        if energy is not None:
            try:
                energy_values.append(float(energy))
            except (ValueError, TypeError):
                pass

    total_pulse = on_track_count + off_track_count
    on_track_pct = round((on_track_count / total_pulse) * 100) if total_pulse > 0 else 0
    off_track_pct = 100 - on_track_pct if total_pulse > 0 else 0
    avg_energy = round(sum(energy_values) / len(energy_values), 1) if energy_values else 0

    # Team activity
    active_members = (
        WorkspaceUser.scoped()
        .filter_by(status=EmployeeStatus.ACTIVE)
        .count()
    )

    messages_sent = (
        UpdatePost.scoped()
        .filter(
            UpdatePost.channel_id.isnot(None),
            UpdatePost.created_at >= week_start_dt,
            UpdatePost.created_at <= week_end_dt,
        )
        .count()
    )

    updates_posted = (
        UpdatePost.scoped()
        .filter(
            UpdatePost.post_type.in_(["update", "win"]),
            UpdatePost.created_at >= week_start_dt,
            UpdatePost.created_at <= week_end_dt,
        )
        .count()
    )

    # ── Build markdown ──
    mon_label = monday.strftime("%b %d")
    fri_label = friday.strftime("%b %d, %Y")

    sections = [f"# Week in Review: {mon_label} - {fri_label}"]

    # Wins section
    sections.append("\n## Wins")
    if win_lines:
        sections.append("\n".join(win_lines))
    else:
        sections.append("- No wins posted this week")

    # Pulse section
    sections.append("\n## Pulse Summary")
    if total_pulse > 0:
        sections.append(f"- On track: {on_track_pct}% | Off track: {off_track_pct}%")
        if energy_values:
            sections.append(f"- Average energy: {avg_energy}/5")
        else:
            sections.append("- Average energy: N/A")
    else:
        sections.append("- No pulse data this week")

    # Team activity section
    sections.append("\n## Team Activity")
    sections.append(f"- Active members: {active_members}")
    sections.append(f"- Messages sent: {messages_sent}")
    sections.append(f"- Updates posted: {updates_posted}")

    content = "\n".join(sections)

    # Save the content
    review.content = content
    db.session.commit()

    # Notify admins
    SystemNotification.create(
        title="Week in Review is ready",
        message=f"The summary for {mon_label} - {fri_label} has been generated and is ready for review.",
        type="info",
        target_role="admin",
        icon="fa-newspaper",
        color="info",
        action_url=f"/sync/week-review/{review.id}/",
        category="system",
    )

    logger.info(f"[WEEK REVIEW] Generated review for {mon_label} - {fri_label}")


def _extract_post_text(post):
    """Extract the first non-empty text value from a post payload."""
    payload = post.payload or {}
    for value in payload.values():
        if isinstance(value, str) and value.strip():
            return value.strip()[:120]
        if isinstance(value, list):
            items = [v for v in value if isinstance(v, str) and v.strip()]
            if items:
                return items[0].strip()[:120]
    return None


def _get_author_name(post):
    """Get the display name of a post's author."""
    if post.member and post.member.user:
        return post.member.user.full_name
    return "Anonymous"
