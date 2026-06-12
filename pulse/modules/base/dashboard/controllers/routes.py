# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Dashboard module routes.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

from flask import g, jsonify, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.device.template import render_device_template
from system.i18n.translation import translate
from system.module.registry import module_enabled
from system.utils.calendar_utils import get_week_start
from system.widgets import (
    get_admin_widgets,
    get_available_admin_widgets,
    get_available_widgets,
    get_user_widgets,
    save_admin_widgets,
    save_user_widgets,
)
from . import blueprint



def _flatten_my_items(items: list[dict]) -> None:
    """Pre-resolve ORM traversals into flat display fields on My Items dicts."""
    for entry in items:
        obj = entry["item"]
        if entry["type"] == "blocker":
            raiser = obj.raised_by.user if obj.raised_by and obj.raised_by.user else None
            entry["item_id"] = obj.id
            entry["title"] = obj.title
            entry["context_note"] = obj.context_note
            entry["urgency_tier"] = obj.urgency_tier
            entry["time_ago_str"] = obj.time_ago()
            entry["person_first_name"] = raiser.first_name if raiser else None
            entry["person_last_name"] = raiser.last_name if raiser else None
            entry["person_avatar_color"] = raiser.avatar_color if raiser else None
        elif entry["type"] == "mention":
            poster = obj.member.user if obj.member and obj.member.user else None
            channel = None
            project = None
            if obj.channel_id:
                from modules.base.updates.models.channel import UpdateChannel
                from modules.base.projects.models.project import Project as _MentionProject
                channel = UpdateChannel.scoped().filter_by(id=obj.channel_id).first()
                if channel and channel.project_id:
                    project = _MentionProject.scoped().filter_by(id=channel.project_id).first()
            if project:
                post_url = url_for("projects_bp.channel_thread", project_id=project.id, post_id=obj.id)
            elif channel:
                post_url = url_for("updates_bp.channel_thread", slug=channel.name, post_id=obj.id)
            else:
                post_url = url_for("sync_bp.post_permalink", post_id=obj.id)
            entry["post_id"] = obj.id
            entry["post_url"] = post_url
            entry["title"] = translate("Mentioned you")
            entry["subtitle"] = obj.subject if obj.subject else None
            entry["project_name"] = project.name if project else (f"#{channel.name}" if channel else None)
            entry["time_ago_str"] = obj.time_ago()
            entry["person_first_name"] = poster.first_name if poster else None
            entry["person_last_name"] = poster.last_name if poster else None
            entry["person_avatar_color"] = poster.avatar_color if poster else None
        elif entry["type"] == "project_post":
            project = entry.get("project")
            poster = obj.member.user if obj.member and obj.member.user else None
            entry["post_id"] = obj.id
            entry["title"] = obj.subject or obj.preview_text()
            entry["subtitle"] = obj.preview_text() if obj.subject else None
            entry["time_ago_str"] = obj.time_ago()
            entry["person_first_name"] = poster.first_name if poster else None
            entry["project_id"] = project.id if project else None
            entry["project_name"] = project.name if project else None
            entry["project_emoji"] = project.emoji if project else None
            entry["project_color"] = project.color if project else None
        elif entry["type"] == "review":
            assignee = obj.assignee.user if obj.assignee and obj.assignee.user else None
            project = obj.project
            entry["item_id"] = obj.id
            entry["title"] = obj.title
            entry["project_name"] = project.name if project else None
            entry["project_emoji"] = project.emoji if project else None
            entry["time_ago_str"] = obj.time_ago()
            entry["person_first_name"] = assignee.first_name if assignee else None
            entry["person_last_name"] = assignee.last_name if assignee else None
            entry["person_avatar_color"] = assignee.avatar_color if assignee else None
        elif entry["type"] == "nudge":
            entry["nudge_time"] = obj.nudged_at
            entry["template_id"] = obj.template_id
            _label = obj.template.name if obj.template else "check-in"
            if _label.startswith("Async - "):
                _label = _label[8:]
            if _label.endswith(" (EOD)"):
                _label = _label[:-6]
            entry["template_name"] = _label


@blueprint.route("/search")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def search() -> ResponseReturnValue:
    """Workspace-wide keyword search (HTMX endpoint)."""
    query = request.args.get("q", "").strip()

    if not query or len(query) < 2:
        return ""

    projects = []
    tasks = []

    if module_enabled("Projects"):
        from modules.base.projects.models.project import Project
        projects = Project.search(query, limit=5)

    if module_enabled("Tasks"):
        from modules.base.tasks.models.task import Task
        tasks = Task.search(query, limit=5)

    return render_template(
        "dashboard/desktop/partials/_search_results.html",
        projects=projects,
        tasks=tasks,
        query=query,
        no_results=not projects and not tasks,
    )


@blueprint.route("/")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def index() -> str:
    """Dashboard main page"""
    if getattr(g, "organization_id", None) is None:
        return redirect(url_for("core_bp.login"))

    from modules.base.updates.queries.feed import get_feed_posts
    from ..queries.widgets import (
        get_bluf_metrics,
        get_completed_this_week,
        get_overdue_items,
        get_recent_activities,
        get_team_status,
    )

    today = date.today()
    start_of_week = get_week_start(today)
    end_of_week = start_of_week + timedelta(days=6)

    _hour = datetime.now().hour
    if _hour < 12:
        greeting = translate("Good morning")
    elif _hour < 17:
        greeting = translate("Good afternoon")
    else:
        greeting = translate("Good evening")

    # Activities — projection query
    activities = get_recent_activities(g.organization_id, g.workspace_id, limit=50)

    # Current member
    current_member_id = None
    member = getattr(current_user, "workspace_membership", None)
    if member:
        current_member_id = member.id

    # BLUF tab: open blockers, overdue items, completed this week
    bluf_open_blockers: list = []
    bluf_overdue_items: list = []
    bluf_completed_items: list = []
    if module_enabled("Tasks"):
        from modules.base.tasks.models.task import Task as _AI_bluf
        bluf_open_blockers = _AI_bluf.get_open_blockers()
        bluf_overdue_items = get_overdue_items(g.organization_id, g.workspace_id, today)
        bluf_completed_items = get_completed_this_week(g.organization_id, g.workspace_id, start_of_week, today)

    # My Items: blockers + mentions + nudge + project posts
    my_items: list[dict] = []
    _expired_nudges: list[dict] = []
    my_blocker_count = 0
    if module_enabled("Tasks") and current_member_id:
        from modules.base.tasks.models.task import Task

        _my_blockers = Task.get_my_active_blockers(current_member_id)
        my_blocker_count = len(_my_blockers)

        _my_mentions = []
        _pending_nudge = None
        if module_enabled("Updates"):
            from modules.base.updates.models.post import UpdatePost
            from modules.base.updates.models.nudge_log import UpdateNudgeLog
            _my_mentions = UpdatePost.get_mentions_for_member(current_member_id, limit=5)
            _pending_nudge = UpdateNudgeLog.get_pending(current_user.id)
            for _en in UpdateNudgeLog.get_expired_today(current_user.id):
                _label = _en.template.name if _en.template else "check-in"
                if _label.startswith("Async - "):
                    _label = _label[8:]
                if _label.endswith(" (EOD)"):
                    _label = _label[:-6]
                _expired_nudges.append({
                    "template_name": _label,
                    "template_id": _en.template_id,
                    "nudge_time": _en.nudged_at,
                    "status": _en.status,
                })
        my_items = Task.build_dashboard_items(
            _my_blockers, mentions=_my_mentions, nudge=_pending_nudge
        )

        if module_enabled("Projects"):
            _pending_reviews = Task.get_pending_reviews(current_member_id)
            my_items += [
                {"type": "review", "item": r, "_ts": r.updated_at or r.created_at}
                for r in _pending_reviews
            ]

        if module_enabled("Projects") and module_enabled("Updates"):
            from sqlalchemy.orm import joinedload as _jl_pp

            from modules.base.core.models.workspace_user import WorkspaceUser as _TSU_pp
            from modules.base.projects.models.project import Project
            from modules.base.updates.models.post import UpdatePost
            _my_projects = Project.get_active_for_member(current_member_id)
            _channel_ids = [p.channel_id for p in _my_projects if p.channel_id]
            if _channel_ids:
                _channel_map = {p.channel_id: p for p in _my_projects if p.channel_id}
                _mentioned_ids = {m.id for m in _my_mentions}
                _project_posts = (
                    UpdatePost.scoped()
                    .options(
                        _jl_pp(UpdatePost.member).joinedload(_TSU_pp.user),
                        _jl_pp(UpdatePost.template),
                    )
                    .filter(
                        UpdatePost.channel_id.in_(_channel_ids),
                        UpdatePost.parent_id.is_(None),
                    )
                    .order_by(UpdatePost.created_at.desc())
                    .limit(5)
                    .all()
                )
                my_items += [
                    {"type": "project_post", "item": p, "project": _channel_map[p.channel_id], "_ts": p.created_at}
                    for p in _project_posts
                    if p.id not in _mentioned_ids
                ]

        my_items.sort(key=Task.dashboard_sort_key, reverse=True)

    _flatten_my_items(my_items)

    # BLUF metrics — projection query (2 SQL: scalar counts + blocker IDs)
    bluf = get_bluf_metrics(g.organization_id, g.workspace_id, start_of_week, today)
    bluf_slipped = bluf.slipped
    bluf_shipped = bluf.shipped
    bluf_decisions = bluf.decisions_for(current_member_id)
    blocked_member_ids = bluf.blocked_member_ids
    open_blockers_count = bluf.open_blockers_count

    # Feed data — projection query
    recent_posts = []
    recent_updates_count = 0
    recent_wins_count = 0
    upcoming_events = []
    if module_enabled("Updates"):
        from modules.base.updates.models.event import Event as SyncEvent

        all_feed, _ = get_feed_posts(g.organization_id, g.workspace_id, post_type=["update", "win", "board"], limit=100)
        recent_updates_count = sum(1 for p in all_feed if p.post_type == "update")
        recent_wins_count = sum(1 for p in all_feed if p.post_type == "win")
        upcoming_events = SyncEvent.get_upcoming(limit=4)

        recent_posts = sorted(all_feed, key=lambda p: p.created_at, reverse=True)[:25]

    # Time clock — reuse page_context (no extra query)
    is_fsm_mode = g._page_context.time_clock_enabled

    # Team Status — projection query (only when time clock is active)
    team_status: list = []
    if is_fsm_mode:
        team_status = get_team_status(
            g.organization_id, g.workspace_id, {}, bluf,
        )

    # Current weekly plan
    _current_plan = None
    if module_enabled("Updates"):
        try:
            from modules.base.updates.models.weekly_plan import WeeklyPlan
            _current_plan = WeeklyPlan.get_or_create_current_week()
        except Exception:
            _current_plan = None

    # Employee-specific data for non-admin dashboard
    _employee_clock_status = None
    _employee_hours_this_week = 0.0
    _employee_pto_balance = 0
    _employee_assigned_jobs = []
    _employee_next_time_off = None
    _employee_upcoming_events_count = 0

    if not current_user.is_admin and hasattr(current_user, "workspace_membership") and current_user.workspace_membership:
        employee = current_user.workspace_membership

        if module_enabled("Presence"):
            from modules.base.presence.models.clock_punch import ClockPunch
            from modules.base.presence.models.time_entry import TimeEntry

            is_clocked_in = ClockPunch.is_clocked_in(employee.id)
            _employee_clock_status = {"is_clocked_in": is_clocked_in}

            week_entries = TimeEntry.scoped().filter(
                TimeEntry.member_id == employee.id,
                TimeEntry.date >= start_of_week,
                TimeEntry.date <= end_of_week,
            ).all()
            _employee_hours_this_week = sum(float(e.hours or 0) for e in week_entries)

            from modules.base.presence.models.leave_request import LeaveRequest, LeaveRequestStatus
            year_start = date(today.year, 1, 1)
            used_pto = LeaveRequest.scoped().filter(
                LeaveRequest.member_id == employee.id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date >= year_start,
            ).count()
            _employee_pto_balance = max(0, 15 - used_pto)

            next_leave = LeaveRequest.scoped().filter(
                LeaveRequest.member_id == employee.id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                LeaveRequest.start_date >= today,
            ).order_by(LeaveRequest.start_date.asc()).first()
            if next_leave:
                _employee_next_time_off = next_leave.start_date

        if module_enabled("Updates"):
            from modules.base.updates.models.event import Event as EmployeeEvent
            _employee_upcoming_events_count = EmployeeEvent.scoped().filter(
                EmployeeEvent.scheduled_date >= today,
                EmployeeEvent.scheduled_date <= today + timedelta(days=30),
            ).count()

        if module_enabled("Service"):
            from modules.base.service.models.job import Job, JobStatus
            from modules.base.service.models.scheduled_visit import VisitAssignment

            from sqlalchemy import select
            assigned_visit_ids = (
                select(VisitAssignment.visit_id)
                .where(VisitAssignment.employee_id == employee.id)
                .scalar_subquery()
            )
            from modules.base.service.models.scheduled_visit import ScheduledVisit
            job_ids_with_assignments = (
                select(ScheduledVisit.job_id)
                .where(ScheduledVisit.id.in_(assigned_visit_ids))
                .distinct()
                .scalar_subquery()
            )
            _employee_assigned_jobs = (
                Job.query
                .filter(
                    Job.id.in_(job_ids_with_assignments),
                    Job.status.in_([JobStatus.DRAFT, JobStatus.SCHEDULED, JobStatus.IN_PROGRESS])
                )
                .order_by(Job.created_at.desc())
                .limit(10)
                .all()
            )

        if module_enabled("Service") and not current_user.is_admin:
            from modules.base.service.models.scheduled_visit import ScheduledVisit, VisitAssignment, VisitStatus
            _visits_this_week = (
                ScheduledVisit.query
                .join(VisitAssignment, ScheduledVisit.id == VisitAssignment.visit_id)
                .filter(
                    VisitAssignment.employee_id == employee.id,
                    ScheduledVisit.scheduled_date >= start_of_week,
                    ScheduledVisit.scheduled_date <= end_of_week,
                    ScheduledVisit.status.in_([VisitStatus.SCHEDULED, VisitStatus.IN_PROGRESS]),
                )
                .order_by(ScheduledVisit.scheduled_date, ScheduledVisit.scheduled_start_time)
                .limit(5)
                .all()
            )

    _show_schedule_tab = module_enabled("Service")

    user_widgets = []
    admin_widgets = []
    # Pulse — weekly team momentum
    pulse_pct: int | None = None
    pulse_rag = "r"
    pulse_label = translate("No Data")
    pulse_enabled = False
    people: list = []
    template_groups: list = []
    team_overall_pct: int | None = None
    team_templates: dict = {}
    period = request.args.get("period", "weekly")
    if period not in ("daily", "weekly", "monthly", "quarterly"):
        period = "weekly"
    if module_enabled("Updates"):
        pulse_enabled = True
        try:
            from sqlalchemy.orm import selectinload

            from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
            from modules.base.updates.controllers.pulse import _date_range, _get_templates
            from modules.base.updates.models.nudge_log import UpdateNudgeLog

            _pulse_start, _pulse_end, _ = _date_range(period)
            _nudge_templates, template_groups = _get_templates()
            if _nudge_templates:
                _pulse_members = (
                    WorkspaceUser.scoped()
                    .filter_by(status=EmployeeStatus.ACTIVE)
                    .options(selectinload(WorkspaceUser.user))
                    .all()
                )
                _pulse_summary = UpdateNudgeLog.get_pulse_summary(
                    user_ids=[m.user_id for m in _pulse_members],
                    template_ids=[t.id for t in _nudge_templates],
                    template_groups=template_groups,
                    start_date=_pulse_start,
                    end_date=_pulse_end,
                )
                team_overall_pct = _pulse_summary["team_overall_pct"]
                team_templates = _pulse_summary["team_templates"]
                people = [
                    {"member": m, **_pulse_summary["people"].get(m.user_id, {})}
                    for m in _pulse_members
                ]
                pulse_pct = team_overall_pct
                if pulse_pct is not None:
                    if pulse_pct > 80:
                        pulse_rag = "g"
                        pulse_label = translate("On Track")
                    elif pulse_pct >= 51:
                        pulse_rag = "a"
                        pulse_label = translate("At Risk")
                    else:
                        pulse_rag = "r"
                        pulse_label = translate("Off Track")
        except Exception:
            logging.getLogger(__name__).exception("pulse dashboard error")

    if current_user.is_admin:
        admin_widgets = get_admin_widgets(current_user.id)
    else:
        user_widgets = get_user_widgets(current_user.id, is_fsm_mode)

    ts = getattr(g, "workspace", None)
    _workspace_name = ts.name if ts else ""

    # What's Happening: posts + activities merged chronologically
    _happening_all = sorted(
        [{"type": "post", "item": p, "created_at": p.created_at} for p in recent_posts]
        + [{"type": "activity", "item": a, "created_at": a.created_at} for a in activities],
        key=lambda x: x["created_at"],
        reverse=True,
    )
    whats_happening_items = _happening_all[:100]


    blocked_count = len(blocked_member_ids)
    weekly_stats = {
        "updates": recent_updates_count if module_enabled("Updates") else 0,
        "wins": recent_wins_count,
        "actions_raised": my_blocker_count,
        "blockers_open": open_blockers_count,
    }

    today_display = today.strftime("%A, %B %d")
    yesterday = today - timedelta(days=1)

    # GitHub orphan count — shown as dismissable panel when > 0.
    github_orphan_count = 0
    github_connection = None
    activity_gh_refs: dict[int, list] = {}
    try:
        from modules.integrations.models.integration_connection import IntegrationConnection
        from modules.integrations.models.integration_ref import IntegrationRef
        from sqlalchemy.orm import joinedload as _jl_gh

        github_connection = IntegrationConnection.get_active("github")
        if github_connection and github_connection.cached_orphan_ids:
            github_orphan_count = len(github_connection.cached_orphan_ids)

        # Bulk-load IntegrationRefs for Task activities in the feed.
        task_activity_ids = [
            e["item"].record_id
            for e in whats_happening_items
            if e["type"] == "activity"
            and getattr(e["item"], "model_type", None) == "Task"
            and e["item"].record_id
        ]
        if task_activity_ids and github_connection:
            refs = (
                IntegrationRef.query
                .options(_jl_gh(IntegrationRef.linked_task))
                .filter(
                    IntegrationRef.workspace_id == g.workspace_id,
                    IntegrationRef.provider == "github",
                    IntegrationRef.object_type == "task",
                    IntegrationRef.object_id.in_(task_activity_ids),
                )
                .all()
            )
            for ref in refs:
                activity_gh_refs.setdefault(ref.object_id, []).append(ref)
    except Exception:
        pass

    return render_device_template(
        "dashboard/desktop/index.html",
        active_page="dashboard",
        module_home="dashboard_bp.index",
        github_orphan_count=github_orphan_count,
        activity_gh_refs=activity_gh_refs,
        whats_happening_items=whats_happening_items,
        upcoming_events=upcoming_events,
        weekly_stats=weekly_stats,
        bluf_slipped=bluf_slipped,
        bluf_shipped=bluf_shipped,
        bluf_decisions=bluf_decisions,
        blocked_count=blocked_count,
        team_status=team_status,
        my_items=my_items,
        expired_nudges=_expired_nudges,
        my_blocker_count=my_blocker_count,
        current_member_id=current_member_id,
        greeting=greeting,
        today_display=today_display,
        today_date=today,
        yesterday_date=yesterday,
        start_of_week=start_of_week,
        admin_widgets=admin_widgets,
        user_widgets=user_widgets,
        pulse_rag=pulse_rag,
        pulse_label=pulse_label,
        pulse_pct=pulse_pct,
        pulse_enabled=pulse_enabled,
        people=people,
        template_groups=template_groups,
        team_overall_pct=team_overall_pct,
        team_templates=team_templates,
        period=period,
        bluf_open_blockers=bluf_open_blockers,
        bluf_overdue_items=bluf_overdue_items,
        bluf_completed_items=bluf_completed_items,
    )


@blueprint.route("/pulse-tab")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def pulse_tab() -> str:
    """Return the pulse partial for HTMX period toggle swaps."""
    from sqlalchemy.orm import selectinload

    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.updates.controllers.pulse import _date_range, _get_templates
    from modules.base.updates.models.nudge_log import UpdateNudgeLog

    period = request.args.get("period", "weekly")
    if period not in ("daily", "weekly", "monthly", "quarterly"):
        period = "weekly"

    people: list = []
    template_groups: list = []
    team_overall_pct: int | None = None
    team_templates: dict = {}

    try:
        _pulse_start, _pulse_end, _ = _date_range(period)
        _nudge_templates, template_groups = _get_templates()
        if _nudge_templates:
            _pulse_members = (
                WorkspaceUser.scoped()
                .filter_by(status=EmployeeStatus.ACTIVE)
                .options(selectinload(WorkspaceUser.user))
                .all()
            )
            _pulse_summary = UpdateNudgeLog.get_pulse_summary(
                user_ids=[m.user_id for m in _pulse_members],
                template_ids=[t.id for t in _nudge_templates],
                template_groups=template_groups,
                start_date=_pulse_start,
                end_date=_pulse_end,
            )
            team_overall_pct = _pulse_summary["team_overall_pct"]
            team_templates = _pulse_summary["team_templates"]
            people = [
                {"member": m, **_pulse_summary["people"].get(m.user_id, {})}
                for m in _pulse_members
            ]
    except Exception:
        logging.getLogger(__name__).exception("pulse_tab error")

    return render_template(
        "dashboard/desktop/partials/_pulse_tab.html",
        period=period,
        people=people,
        template_groups=template_groups,
        team_overall_pct=team_overall_pct,
        team_templates=team_templates,
        pulse_period_url=url_for("dashboard_bp.pulse_tab"),
    )


@blueprint.route("/happening-feed")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def happening_feed() -> str:
    """Return one page of What's Happening rows for infinite scroll."""
    from modules.base.updates.queries.feed import get_feed_posts
    from ..queries.widgets import get_recent_activities

    offset = request.args.get("offset", 0, type=int)
    limit = 20

    activities = get_recent_activities(g.organization_id, g.workspace_id, limit=200)
    posts = []
    if module_enabled("Updates"):
        all_feed, _ = get_feed_posts(
            g.organization_id, g.workspace_id,
            post_type=["update", "win", "board"],
            limit=200,
        )
        posts = sorted(all_feed, key=lambda p: p.created_at, reverse=True)

    combined = sorted(
        [{"type": "post", "item": p, "created_at": p.created_at} for p in posts]
        + [{"type": "activity", "item": a, "created_at": a.created_at} for a in activities],
        key=lambda x: x["created_at"],
        reverse=True,
    )

    batch_items = combined[offset : offset + limit]
    has_more = len(combined) > offset + limit
    next_offset = offset + limit

    return render_template(
        "dashboard/desktop/partials/_happening_feed_rows.html",
        batch_items=batch_items,
        offset=offset,
        has_more=has_more,
        next_offset=next_offset,
    )


@blueprint.route("/card-order", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def save_card_order() -> ResponseReturnValue:
    """Save the user's dashboard card order."""
    from modules.base.core.models.user_setting import UserSetting

    data = request.get_json()
    if not data or "order" not in data:
        return jsonify({"error": "Invalid request"}), 400

    order = data["order"]
    valid_ids = {"tasks", "team_status", "comm", "attention"}
    if not isinstance(order, list) or set(order) != valid_ids or len(order) != 4:
        return jsonify({"error": "Invalid card order"}), 400

    UserSetting.set(current_user.id, "dashboard_card_order", json.dumps(order))
    return jsonify({"success": True})


@blueprint.route("/widgets")  # type: ignore[misc]
@login_required  # type: ignore[misc]
def get_widgets() -> str:
    """Get the user's widget configuration."""
    # Detect FSM vs Office mode
    is_fsm_mode = False
    if module_enabled("Presence"):
        from modules.base.presence.models.settings import TimeTrackingSettings

        is_fsm_mode = TimeTrackingSettings.is_time_clock_enabled()

    # Return appropriate widgets based on user role
    if current_user.is_admin:
        widgets = get_admin_widgets(current_user.id)
        available = get_available_admin_widgets()
    else:
        widgets = get_user_widgets(current_user.id, is_fsm_mode)
        available = get_available_widgets()

    return jsonify({"widgets": widgets, "available": available})


@blueprint.route("/widgets", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def save_widgets() -> str:
    """Save the user's widget configuration."""
    data = request.get_json()

    if not data or "widgets" not in data:
        return jsonify({"error": "Invalid request"}), 400

    widgets = data["widgets"]

    # Validate that we have at most 6 widgets
    if len(widgets) > 6:
        return jsonify({"error": "Maximum 6 widgets allowed"}), 400

    # Validate widget structure
    required_fields = {"id", "route", "label", "icon", "color"}
    for widget in widgets:
        if not all(field in widget for field in required_fields):
            return jsonify({"error": "Invalid widget structure"}), 400

    # Save to appropriate setting based on user role
    if current_user.is_admin:
        save_admin_widgets(current_user.id, widgets)
    else:
        save_user_widgets(current_user.id, widgets)

    return jsonify({"success": True})


@blueprint.route("/widgets/reset", methods=["POST"])  # type: ignore[misc]
@login_required  # type: ignore[misc]
def reset_widgets() -> str:
    """Reset the user's widget configuration to defaults."""
    from system.widgets import get_default_admin_widgets, get_default_widgets

    # Get defaults based on user role
    if current_user.is_admin:
        widgets = get_default_admin_widgets()
        save_admin_widgets(current_user.id, widgets)
    else:
        # Check FSM mode
        is_fsm_mode = current_user.workspace_membership and current_user.workspace_membership.is_field_worker if hasattr(current_user, 'workspace_membership') else False
        widgets = get_default_widgets(is_fsm_mode)
        save_user_widgets(current_user.id, widgets)

    return jsonify({"success": True, "widgets": widgets})
