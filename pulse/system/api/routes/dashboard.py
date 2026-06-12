# -----------------------------------------------------------------------------
# sparQ — Dashboard API Routes
#
# Read-only dashboard data for the mobile app: metrics summary, activity feed,
# notifications. Single write: mark notification read.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import Blueprint, g, jsonify

from system.api.decorators import jwt_required
from system.api.errors import api_error_response
from system.api.pagination import paginated_response
from system.middleware.ratelimit import rate_limit

dashboard_bp = Blueprint("api_dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_summary():
    """Return dashboard metrics summary for the current user."""
    from modules.base.dashboard.models.activity_log import ActivityLog
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.presence.models.clock_punch import ClockPunch

    emp = WorkspaceUser.scoped().filter_by(user_id=g.current_user.id).first()
    activities = ActivityLog.get_recent(limit=5)
    clock_status = ClockPunch.get_current_status(emp.id) if emp else {"is_clocked_in": False}

    return jsonify({
        "clock_status": {
            "is_clocked_in": clock_status["is_clocked_in"],
            "clock_in_time": clock_status["clock_in_time"].isoformat() if clock_status.get("clock_in_time") else None,
            "elapsed_str": clock_status.get("elapsed_str", ""),
        },
        "recent_activity": [a.to_dict() for a in activities],
    }), 200


@dashboard_bp.route("/activity", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_activity():
    """Paginated activity feed."""
    from modules.base.dashboard.models.activity_log import ActivityLog

    query = ActivityLog.scoped().order_by(ActivityLog.created_at.desc())
    return paginated_response(query)


@dashboard_bp.route("/notifications", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_notifications():
    """User notifications (activity log entries for this user)."""
    from modules.base.dashboard.models.activity_log import ActivityLog

    query = ActivityLog.scoped().filter_by(
        user_id=g.current_user.id,
    ).order_by(ActivityLog.created_at.desc())
    return paginated_response(query)


@dashboard_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def mark_notification_read(notification_id):
    """Mark a notification as read.

    ActivityLog doesn't have a read flag, so this is a no-op acknowledgment
    that returns success. The mobile app tracks read state locally.
    """
    # TODO(human): If a dedicated Notification model is added later, update this
    # to actually mark the notification as read in the database.
    from modules.base.dashboard.models.activity_log import ActivityLog

    activity = ActivityLog.scoped().filter_by(id=notification_id).first()
    if not activity:
        return api_error_response("NOT_FOUND", "Notification not found", 404)

    return jsonify({"status": "ok"}), 200
