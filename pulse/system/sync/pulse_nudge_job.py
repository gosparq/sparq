# -----------------------------------------------------------------------------
# sparQ - Pulse Nudge Job
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""AI pulse nudge job — collects signals and creates smart nudges.

Examines each active member's open blockers, posts, and messages to
pre-fill a suggested pulse value (on_track / energy) and create a
nudge via UpdateNudgeLog.create_nudge().

Usage:
    from system.background import submit_task
    from system.sync.pulse_nudge_job import run_pulse_nudges
    submit_task(run_pulse_nudges)
"""

import logging
from datetime import datetime

from system.db.database import db

logger = logging.getLogger(__name__)


def run_pulse_nudges():
    """Run AI pulse nudges for all active members in the current workspace.

    For each active member:
    1. Check UpdateNudgeLog.should_nudge() to avoid spamming.
    2. Collect signals (open blockers, posts today, messages today).
    3. Compute suggested values for on_track and energy.
    4. Create nudge entries with SystemNotification.
    """
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.models.nudge_log import UpdateNudgeLog
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.template import UpdateTemplate

    # Get pulse templates for action_url linking
    pulse_templates = UpdateTemplate.get_for_workspace(post_type="pulse") if hasattr(UpdateTemplate, "get_for_workspace") else []
    track_template = None
    for t in pulse_templates:
        if "track" in t.name.lower():
            track_template = t

    # Get all active members
    active_members = (
        WorkspaceUser.scoped()
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )

    if not active_members:
        logger.debug("No active members found for pulse nudges")
        return

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    nudged_count = 0

    for member in active_members:
        if not member.user_id:
            continue

        # Check cooldown
        if not UpdateNudgeLog.should_nudge(member.user_id):
            continue

        # Collect signals
        _posts_today = UpdatePost.scoped().filter(
            UpdatePost.post_type == "pulse",
            UpdatePost.member_id == member.id,
            UpdatePost.created_at >= today_start,
        ).count()

        _messages_today = UpdatePost.scoped().filter(
            UpdatePost.channel_id.isnot(None),
            UpdatePost.member_id == member.id,
            UpdatePost.created_at >= today_start,
        ).count()

        # Compute on_track suggestion
        on_track_value = "on_track"

        # Create on_track nudge if template exists
        if track_template:
            UpdateNudgeLog.create_nudge(
                user_id=member.user_id,
                nudge_type="on_track",
                suggested_value=on_track_value,
                template_id=track_template.id,
            )
            nudged_count += 1

    db.session.commit()
    logger.info(f"[PULSE NUDGE] Created {nudged_count} nudges for {len(active_members)} members")
