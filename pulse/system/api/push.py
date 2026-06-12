# -----------------------------------------------------------------------------
# sparQ — Push Notification Device Registration
#
# DeviceToken model and endpoints for registering/unregistering mobile
# devices for push notifications (iOS APNs, Android FCM).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request

from system.api.decorators import jwt_required
from system.api.errors import api_error_response, validate_required
from system.api.serialization import SerializableMixin
from system.db.database import db
from system.middleware.ratelimit import rate_limit

push_bp = Blueprint("api_push", __name__, url_prefix="/devices")


class DeviceToken(db.Model, SerializableMixin):
    """Push notification device token for mobile apps."""

    __tablename__ = "device_token"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    device_token = db.Column(db.String(512), nullable=False)
    platform = db.Column(db.String(20), nullable=False)  # "ios" or "android"
    device_id = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


@push_bp.route("/register", methods=["POST"])
@jwt_required
@rate_limit(limit=60, window=60)
def register_device():
    """Register or update a device token for push notifications.

    Upserts by device_id: if the device already exists, update the token.
    """
    data = request.get_json(silent=True)
    errors = validate_required(data, ["device_token", "platform", "device_id"])
    if errors:
        return api_error_response("VALIDATION_ERROR", "Missing required fields", 400, errors)

    platform = data["platform"].lower()
    if platform not in ("ios", "android"):
        return api_error_response("VALIDATION_ERROR", "Platform must be 'ios' or 'android'", 400)

    # Upsert by device_id
    device = DeviceToken.query.filter_by(device_id=data["device_id"]).first()
    if device:
        device.device_token = data["device_token"]
        device.platform = platform
        device.user_id = g.current_user.id
    else:
        device = DeviceToken(
            user_id=g.current_user.id,
            device_token=data["device_token"],
            platform=platform,
            device_id=data["device_id"],
        )
        db.session.add(device)

    db.session.commit()
    return jsonify(device.to_dict()), 200


@push_bp.route("/<device_id>", methods=["DELETE"])
@jwt_required
@rate_limit(limit=60, window=60)
def unregister_device(device_id):
    """Unregister a device (e.g. on logout)."""
    device = DeviceToken.query.filter_by(
        device_id=device_id,
        user_id=g.current_user.id,
    ).first()
    if not device:
        return api_error_response("NOT_FOUND", "Device not found", 404)

    db.session.delete(device)
    db.session.commit()
    return jsonify({"status": "ok"}), 200
