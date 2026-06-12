# -----------------------------------------------------------------------------
# sparQ - Tasks System Triggers
#
# Description:
#     Periodically checks for conditions that should auto-generate Tasks:
#       - Overdue timesheets (no clock entry submitted for a workday)
#       - Overdue onboarding steps (pending > 48hrs)
#       - Pending PTO approval > 24hrs
#       - Missed daily check-in (no Sync post by end of day)
#
#     Runs as part of the Tasks nudge scheduler (piggybacks on the
#     1-minute check cycle but only runs system trigger checks every 30 min).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_last_trigger_check = None


def check_system_triggers(app) -> None:
    """Run system trigger checks (called from nudge scheduler).

    Throttled to run at most every 30 minutes.

    Args:
        app: Flask application instance for app_context.
    """
    global _last_trigger_check

    now = datetime.utcnow()
    if _last_trigger_check and (now - _last_trigger_check) < timedelta(minutes=30):
        return

    _last_trigger_check = now

    with app.app_context():
        try:
            _run_triggers()
        except Exception as e:
            logger.error(f"System trigger check failed: {e}")


def _run_triggers() -> None:
    """Execute all system trigger checks across workspaces."""
    from flask import g

    from modules.base.core.models.workspace import Workspace

    workspaces = Workspace.query.filter_by(is_active=True).all()

    for ts in workspaces:
        g.workspace_id = ts.id
        g.organization_id = ts.organization_id
        _check_stale_items(ts)
        _check_overdue_timesheets(ts)
        _check_overdue_onboarding(ts)
        _check_pending_pto(ts)
        _check_missed_checkins(ts)
        _check_missed_periodic_checkins(ts)


def _check_stale_items(ts) -> None:
    """Move stale projects and tasks to On Hold based on workspace threshold."""
    try:
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        from modules.base.projects.models.project import Project
        from modules.base.tasks.models.task import Task

        settings = WorkspaceSettings.get_instance()
        stale_days = settings.stale_days or 3
        cutoff = datetime.utcnow() - timedelta(days=stale_days)

        stale_projects = Project.get_stale_upcoming(cutoff)
        for project in stale_projects:
            project.set_status(Project.STATUS_ON_HOLD)
            logger.debug(f"Stale project {project.id} ({project.name}) moved to On Hold")

        stale_count = Task.mark_stale_tasks(stale_days)
        if stale_count:
            logger.debug(f"Moved {stale_count} stale tasks to On Hold")
    except Exception as e:
        logger.debug(f"Stale check skipped: {e}")


def _has_open_item(source_type, source_id) -> bool:
    """Check if an open Task already exists for this source (dedup)."""
    from modules.base.tasks.models.task import Task

    return Task.scoped().filter(
        Task.source_type == source_type,
        Task.source_id == source_id,
        Task.status == "open",
    ).first() is not None


def _create_system_item(title, assignee_id, urgency_tier, context_note, source_type, source_id):
    """Create a system-generated Task (raised_by_id=None)."""
    from modules.base.tasks.models.task import Task

    if _has_open_item(source_type, source_id):
        return None

    return Task.create(
        title=title[:200],
        urgency_tier=urgency_tier,
        assignee_id=assignee_id,
        raised_by_id=None,  # System
        context_note=context_note[:500] if context_note else None,
        source_type=source_type,
        source_id=source_id,
    )


def _check_overdue_timesheets(ts) -> None:
    """Create Tasks for members with no timesheet entry for yesterday."""
    try:
        from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
        from modules.base.presence.models.timesheet import Timesheet

        yesterday = datetime.utcnow().date() - timedelta(days=1)
        # Skip weekends
        if yesterday.weekday() > 4:
            return

        members = WorkspaceUser.scoped().filter_by(status=EmployeeStatus.ACTIVE).all()
        for member in members:
            has_entry = Timesheet.scoped().filter(
                Timesheet.member_id == member.id,
                Timesheet.date == yesterday,
            ).first()
            if not has_entry:
                _create_system_item(
                    title="Timesheet",
                    assignee_id=member.id,
                    urgency_tier=2,
                    context_note=f"No timesheet entry found for {yesterday.strftime('%b %d, %Y')}.",
                    source_type="timesheet_overdue",
                    source_id=member.id * 10000 + yesterday.toordinal() % 10000,
                )
    except ImportError:
        pass  # Presence module not loaded
    except Exception as e:
        logger.debug(f"Timesheet trigger skipped: {e}")


def _check_overdue_onboarding(ts) -> None:
    """Create Tasks for onboarding steps pending > 48 hours."""
    try:
        from modules.base.people.models.onboarding import OnboardingStep

        cutoff = datetime.utcnow() - timedelta(hours=48)
        pending_steps = OnboardingStep.scoped().filter(
            OnboardingStep.completed_at.is_(None),
            OnboardingStep.created_at <= cutoff,
        ).all()

        for step in pending_steps:
            if not step.assigned_to_id:
                continue
            _create_system_item(
                title=f"Onboarding: {step.title[:150]}",
                assignee_id=step.assigned_to_id,
                urgency_tier=2,
                context_note="Onboarding step has been pending for over 48 hours.",
                source_type="onboarding_step",
                source_id=step.id,
            )
    except ImportError:
        pass  # People module not loaded
    except Exception as e:
        logger.debug(f"Onboarding trigger skipped: {e}")


def _check_pending_pto(ts) -> None:
    """Create Tasks for PTO requests pending approval > 24hrs."""
    try:
        from modules.base.presence.models.pto import PTORequest

        cutoff = datetime.utcnow() - timedelta(hours=24)
        pending = PTORequest.scoped().filter(
            PTORequest.status == "pending",
            PTORequest.created_at <= cutoff,
        ).all()

        for req in pending:
            # Assign to the approver (admin) — find the first admin
            from modules.base.core.models.workspace_user import WorkspaceUser
            admin = WorkspaceUser.scoped().filter_by(role="admin").first()
            if not admin:
                continue

            member_name = ""
            if req.member and req.member.user:
                member_name = req.member.user.first_name

            _create_system_item(
                title=f"PTO request from {member_name}",
                assignee_id=admin.id,
                urgency_tier=2,
                context_note="PTO request has been pending approval for over 24 hours.",
                source_type="pto_approval",
                source_id=req.id,
            )
    except ImportError:
        pass  # PTO module not loaded
    except Exception as e:
        logger.debug(f"PTO trigger skipped: {e}")


def _check_missed_checkins(ts) -> None:
    """Disabled — missed check-ins are now tracked via UpdateNudgeLog status."""
    return


def _check_missed_periodic_checkins(ts) -> None:
    """Disabled — missed periodic nudges are now tracked via UpdateNudgeLog status."""
    return
