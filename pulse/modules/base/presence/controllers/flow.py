# -----------------------------------------------------------------------------
# sparQ - Presence Module: Flow/Free and Pulse Controller
#
# Routes for flow status and pulse check-ins.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime, timedelta

from flask import Blueprint, abort, jsonify, redirect, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.device.template import render_device_template

blueprint = Blueprint(
    "presence_flow_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.route("/overview/")
@login_required
def overview() -> ResponseReturnValue:
    """Presence overview — redirects to dashboard (Presence tab removed)."""
    return redirect(url_for("dashboard_bp.index"))


@blueprint.route("/overview-legacy/")
@login_required
def overview_legacy() -> ResponseReturnValue:
    """Legacy presence overview — kept for direct access if needed."""
    from collections import defaultdict

    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.core.models.user_setting import UserSetting

    now = datetime.utcnow()
    week_start = now - timedelta(days=7)

    # Active members
    active_members = (
        WorkspaceUser.scoped()
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )
    member_map = {m.id: m for m in active_members}

    # Flow statuses
    user_ids = [m.user_id for m in active_members if m.user_id]
    statuses = UserSetting.get_bulk(user_ids, "flow_status", default="free")
    flow_count = sum(1 for s in statuses.values() if s == "flow")
    open_door_members = [m for m in active_members if m.door_is_open]

    # Team health data (compact)
    energy_data = []
    on_track_pct = 0
    total_track = 0
    checkin_count_week = 0

    try:
        from modules.base.updates.models.post import UpdatePost
        from modules.base.updates.models.template import UpdateTemplate

        pulse_templates = UpdateTemplate.get_for_workspace(post_type="pulse")
        energy_template = None
        track_template = None
        for t in pulse_templates:
            name_lower = t.name.lower()
            if "energy" in name_lower:
                energy_template = t
            if "track" in name_lower:
                track_template = t

        # Energy averages
        if energy_template:
            energy_posts = UpdatePost.scoped().filter(
                UpdatePost.post_type == "pulse",
                UpdatePost.template_id == energy_template.id,
                UpdatePost.created_at >= week_start,
            ).all()
            member_scores = defaultdict(list)
            for post in energy_posts:
                for field in energy_template.fields or []:
                    val = (post.payload or {}).get(field.get("key", ""))
                    if val and field.get("type") == "scale":
                        try:
                            member_scores[post.member_id].append(int(val))
                        except (ValueError, TypeError):
                            pass
            for member_id, scores in member_scores.items():
                member = member_map.get(member_id)
                if member and scores:
                    energy_data.append({
                        "member": member,
                        "avg": round(sum(scores) / len(scores), 1),
                    })
            energy_data.sort(key=lambda x: x["avg"], reverse=True)

        # On track
        on_track_count = 0
        off_track_count = 0
        if track_template:
            track_posts = UpdatePost.scoped().filter(
                UpdatePost.post_type == "pulse",
                UpdatePost.template_id == track_template.id,
                UpdatePost.created_at >= week_start,
            ).all()
            for post in track_posts:
                for field in track_template.fields or []:
                    val = (post.payload or {}).get(field.get("key", ""))
                    if val and field.get("type") == "choice":
                        if val == "on_track":
                            on_track_count += 1
                        elif val == "off_track":
                            off_track_count += 1
        total_track = on_track_count + off_track_count
        on_track_pct = round(on_track_count / total_track * 100) if total_track > 0 else 0

        # Total check-ins this week
        checkin_count_week = UpdatePost.scoped().filter(
            UpdatePost.post_type == "pulse",
            UpdatePost.created_at >= week_start,
        ).count()
    except Exception:
        pass

    # Timesheet hours this week (pending approvals for admins)
    pending_approval_count = 0
    try:
        from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest
        if current_user.is_admin:
            pending_approval_count = PunchCorrectionRequest.pending_count()
    except Exception:
        pass

    return render_device_template(
        "presence/desktop/overview.html",
        team_count=len(active_members),
        flow_count=flow_count,
        open_door_members=open_door_members,
        energy_data=energy_data[:5],
        on_track_pct=on_track_pct,
        total_track=total_track,
        checkin_count_week=checkin_count_week,
        pending_approval_count=pending_approval_count,
        active_page="overview",
    )


@blueprint.route("/")
@login_required
def flow_index() -> ResponseReturnValue:
    """Show focus/available status page with team board."""
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser
    from modules.base.core.models.user_setting import UserSetting

    member = WorkspaceUser.get_by_user_id(current_user.id)

    flow_status = "available"
    if member:
        legacy = UserSetting.get(current_user.id, "flow_status", default="free")
        flow_status = "focus" if legacy == "flow" else "available"

    # Build team board
    from sqlalchemy.orm import joinedload

    active_members = (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )

    user_ids = [m.user_id for m in active_members if m.user_id]
    flow_bulk = UserSetting.get_bulk(user_ids, "flow_status", default="free") if user_ids else {}

    team_board = []
    for m in active_members:
        if m.user_id and m.user_id in flow_bulk:
            status = "focus" if flow_bulk[m.user_id] == "flow" else "available"
        else:
            status = "available"
        team_board.append({
            "member": m,
            "flow_status": status,
        })
    # Sort: focus first, then alphabetical
    team_board.sort(key=lambda x: (x["flow_status"] != "focus", x["member"].user.full_name if x["member"].user else "ZZZZ"))

    return render_device_template(
        "presence/desktop/flow.html",
        flow_status=flow_status,
        member=member,
        team_board=team_board,
        active_page="flow",
    )


@blueprint.route("/toggle", methods=["POST"])
@login_required
def flow_toggle() -> ResponseReturnValue:
    """Toggle focus status between 'focus' and 'available'."""
    from modules.base.core.models.user_setting import UserSetting

    current_status = UserSetting.get(current_user.id, "flow_status", default="free")
    # Map old values: flow->focus, free->available
    is_focusing = current_status in ("flow", "focus")
    new_status = "free" if is_focusing else "flow"
    new_signal_value = "available" if is_focusing else "focus"
    UserSetting.set(current_user.id, "flow_status", new_status)

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"flow_status": new_status})

    # HTMX partial response for top bar badge
    if request.headers.get("HX-Request"):
        return render_device_template(
            "core/desktop/partials/_header_focus_badge.html",
            header_focus_status=new_signal_value,
        )

    return redirect(url_for("presence_flow_bp.flow_index"))


@blueprint.route("/open-door/")
@login_required
def open_door() -> ResponseReturnValue:
    """Open Door page — set/clear availability."""
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser

    member = WorkspaceUser.get_by_user_id(current_user.id)

    # Get all active members with open doors (excluding self)
    active_members = (
        WorkspaceUser.scoped()
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )
    open_door_members = [
        m for m in active_members
        if m.door_is_open and m.user_id != current_user.id
    ]

    return render_device_template(
        "presence/desktop/open_door.html",
        member=member,
        open_door_members=open_door_members,
        active_page="open_door",
    )


@blueprint.route("/open-door/set", methods=["POST"])
@login_required
def open_door_set() -> ResponseReturnValue:
    """Open door for 30 minutes."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if member:
        member.open_door_until = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()

    return redirect(url_for("presence_flow_bp.flow_index"))


@blueprint.route("/open-door/clear", methods=["POST"])
@login_required
def open_door_clear() -> ResponseReturnValue:
    """Close door."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if member:
        member.open_door_until = None
        db.session.commit()

    return redirect(url_for("presence_flow_bp.flow_index"))


@blueprint.route("/pulse/")
@login_required
def pulse_index() -> ResponseReturnValue:
    """Pulse check-ins — redirects to sync updates (check-ins are now folded into updates)."""
    return redirect(url_for("updates_bp.updates_index"))


@blueprint.route("/pulse/new/<int:template_id>")
@login_required
def pulse_new(template_id: int) -> ResponseReturnValue:
    """Show pulse check-in form with optional pre-fill from AI nudge."""
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate.get_by_id(template_id)
    if not template or template.post_type != "pulse":
        abort(404)

    # Support pre-fill from AI nudge query parameters
    prefill_value = request.args.get("prefill_value")
    nudge_id = request.args.get("nudge_id", type=int)

    return render_device_template(
        "presence/desktop/pulse_form.html",
        template=template,
        prefill_value=prefill_value,
        nudge_id=nudge_id,
        active_page="pulse",
    )


@blueprint.route("/pulse/nudge/<int:nudge_id>/dismiss", methods=["POST"])
@login_required
def pulse_nudge_dismiss(nudge_id: int) -> ResponseReturnValue:
    """Dismiss a pulse nudge."""
    from modules.base.updates.models.nudge_log import UpdateNudgeLog

    nudge = UpdateNudgeLog.scoped().filter_by(id=nudge_id, user_id=current_user.id).first()
    if nudge:
        nudge.dismiss()
        from modules.base.core.models.notification import SystemNotification
        SystemNotification.dismiss_by_url(f"nudge_id={nudge_id}", user_id=current_user.id)

    if request.is_json or request.headers.get("Accept") == "application/json":
        return jsonify({"ok": True})

    return redirect(url_for("presence_flow_bp.pulse_index"))


@blueprint.route("/health/")
@login_required
def health_index() -> ResponseReturnValue:
    """Team health dashboard — redirects to dashboard (Presence tab removed)."""
    return redirect(url_for("dashboard_bp.index"))
