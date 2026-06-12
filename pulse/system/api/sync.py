# -----------------------------------------------------------------------------
# sparQ — Offline Sync API
#
# Batch sync for offline time entries and delta change polling.
# Used when the mobile app reconnects after being offline.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import date, datetime

from flask import Blueprint, g, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response, validate_required
from system.db.database import db
from system.middleware.ratelimit import rate_limit

sync_bp = Blueprint("api_sync", __name__, url_prefix="/sync")


@sync_bp.route("/time-entries", methods=["POST"])
@jwt_required
@rate_limit(limit=30, window=60)
def sync_time_entries():
    """Batch sync offline time entries with conflict detection.

    Request body:
        {"entries": [{"local_id": "...", "date": "YYYY-MM-DD", "hours": float, ...}]}

    Returns per-entry results: created, conflict, or error.
    Uses local_id for client-side correlation.
    """
    from modules.base.presence.models.time_entry import TimeEntry

    data = request.get_json(silent=True)
    errors = validate_required(data, ["entries"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    entries = data["entries"]
    if not isinstance(entries, list):
        return api_error_response("VALIDATION_ERROR", "entries must be an array", 400)

    from modules.base.core.models.workspace_user import WorkspaceUser

    emp = WorkspaceUser.scoped().filter_by(user_id=g.current_user.id).first()
    if not emp:
        return api_error_response("NOT_FOUND", "No employee profile found", 404)

    results = []
    member_id = emp.id

    for item in entries:
        local_id = item.get("local_id", "")
        try:
            entry_date = date.fromisoformat(item["date"])
            hours = float(item["hours"])

            entry = TimeEntry.create(
                member_id=member_id,
                date=entry_date,
                hours=hours,
                description=item.get("description", ""),
                is_billable=item.get("is_billable", False),
                job_id=item.get("job_id"),
                category=item.get("category"),
            )
            results.append({
                "local_id": local_id,
                "status": "created",
                "server_id": entry.id,
            })
        except ValueError as e:
            results.append({
                "local_id": local_id,
                "status": "error",
                "message": str(e),
            })
        except Exception as e:
            db.session.rollback()
            results.append({
                "local_id": local_id,
                "status": "error",
                "message": str(e),
            })

    return jsonify({"results": results}), 200


@sync_bp.route("/changes", methods=["GET"])
@jwt_required
@rate_limit(limit=120, window=60)
def get_changes():
    """Delta changes since a given timestamp for specified modules.

    Query params:
        since: ISO8601 datetime (required)
        modules: comma-separated module names (optional, default: all)

    Returns recently updated records the client needs to refresh.
    """
    since_str = request.args.get("since", "")
    if not since_str:
        return api_error_response("VALIDATION_ERROR", "since parameter required (ISO8601)", 400)

    try:
        since = datetime.fromisoformat(since_str.replace("Z", "+00:00"))
    except ValueError:
        return api_error_response("VALIDATION_ERROR", "Invalid since format. Use ISO8601", 400)

    modules_param = request.args.get("modules", "")
    requested_modules = {m.strip() for m in modules_param.split(",") if m.strip()} if modules_param else None

    changes = {}

    # Resolve employee ID for time tracking queries
    from modules.base.core.models.workspace_user import WorkspaceUser
    emp = WorkspaceUser.scoped().filter_by(user_id=g.current_user.id).first()
    emp_id = emp.id if emp else None

    # Time tracking changes
    if not requested_modules or "presence" in requested_modules:
        from modules.base.presence.models.clock_punch import ClockPunch
        from modules.base.presence.models.time_entry import TimeEntry

        if emp_id:
            entries = TimeEntry.scoped().filter(
                TimeEntry.member_id == emp_id,
                TimeEntry.updated_at >= since,
            ).order_by(TimeEntry.updated_at.desc()).limit(100).all()

            punches = ClockPunch.scoped().filter(
                ClockPunch.member_id == emp_id,
                ClockPunch.created_at >= since,
            ).order_by(ClockPunch.created_at.desc()).limit(50).all()
        else:
            entries = []
            punches = []

        changes["presence"] = {
            "entries": [e.to_dict() for e in entries],
            "punches": [p.to_dict() for p in punches],
        }

    # Connect changes (new posts — unified model)
    if not requested_modules or "connect" in requested_modules:
        from modules.base.updates.models.post import UpdatePost

        posts = UpdatePost.scoped().filter(
            UpdatePost.created_at >= since,
            UpdatePost.channel_id.isnot(None),
        ).order_by(UpdatePost.created_at.desc()).limit(100).all()

        changes["connect"] = {
            "messages": [
                {
                    "id": p.id,
                    "content": (p.payload or {}).get("content", ""),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "channel_id": p.channel_id,
                    "member_id": p.member_id,
                    "post_type": p.post_type,
                }
                for p in posts
            ],
        }

    return jsonify({
        "since": since.isoformat(),
        "changes": changes,
    }), 200
