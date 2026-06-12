# -----------------------------------------------------------------------------
# sparQ - Webhook Admin Routes
#
# Admin routes for managing webhooks on channels and DM threads.
# Mounted on the sync_bp blueprint.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import current_app, jsonify, render_template, request
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from ..models import UpdateChannel, DMThread, UpdateWebhook
from . import blueprint


@blueprint.route("/chat/webhooks/<int:webhook_id>/ten-four", methods=["POST"])
@login_required
def toggle_webhook_ten_four(webhook_id: int) -> ResponseReturnValue:
    """Toggle 10-4 acknowledgment on a webhook (admin only)."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    webhook = UpdateWebhook.scoped().filter_by(id=webhook_id).first()
    if not webhook:
        return "Webhook not found", 404

    new_value = webhook.toggle_ten_four()
    return jsonify({"enable_ten_four": new_value})


@blueprint.route("/chat/channels/<channel_name>/webhooks")
@login_required
def list_channel_webhooks(channel_name: str) -> ResponseReturnValue:
    """List webhooks for a channel (HTMX partial)."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    channel = UpdateChannel.get_by_name(channel_name)
    if not channel:
        return "Channel not found", 404

    webhooks = UpdateWebhook.get_for_channel(channel.id)
    return render_template(
        "updates/desktop/settings/_webhook_list.html",
        webhooks=webhooks,
        target_type="channel",
        target_name=channel_name,
    )


@blueprint.route("/chat/channels/<channel_name>/webhooks", methods=["POST"])
@login_required
def create_channel_webhook(channel_name: str) -> ResponseReturnValue:
    """Create a webhook for a channel."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    channel = UpdateChannel.get_by_name(channel_name)
    if not channel:
        return "Channel not found", 404

    github_secret = request.form.get("github_secret", "").strip() or None

    try:
        UpdateWebhook.create(
            created_by_id=current_user.id,
            channel_id=channel.id,
            github_secret=github_secret,
        )
        webhooks = UpdateWebhook.get_for_channel(channel.id)
        return render_template(
            "updates/desktop/settings/_webhook_list.html",
            webhooks=webhooks,
            target_type="channel",
            target_name=channel_name,
        )
    except Exception as e:
        current_app.logger.error(f"Error creating webhook: {e}")
        return "Failed to create webhook", 500


@blueprint.route("/chat/dms/<int:thread_id>/webhooks")
@login_required
def list_dm_webhooks(thread_id: int) -> ResponseReturnValue:
    """List webhooks for a DM thread (HTMX partial)."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    thread = DMThread.get_by_id(thread_id)
    if not thread:
        return "Thread not found", 404

    webhooks = UpdateWebhook.get_for_dm_thread(thread.id)
    return render_template(
        "updates/desktop/settings/_webhook_list.html",
        webhooks=webhooks,
        target_type="dm",
        target_name=str(thread_id),
    )


@blueprint.route("/chat/dms/<int:thread_id>/webhooks", methods=["POST"])
@login_required
def create_dm_webhook(thread_id: int) -> ResponseReturnValue:
    """Create a webhook for a DM thread."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    thread = DMThread.get_by_id(thread_id)
    if not thread:
        return "Thread not found", 404

    github_secret = request.form.get("github_secret", "").strip() or None

    try:
        UpdateWebhook.create(
            created_by_id=current_user.id,
            dm_thread_id=thread.id,
            github_secret=github_secret,
        )
        webhooks = UpdateWebhook.get_for_dm_thread(thread.id)
        return render_template(
            "updates/desktop/settings/_webhook_list.html",
            webhooks=webhooks,
            target_type="dm",
            target_name=str(thread_id),
        )
    except Exception as e:
        current_app.logger.error(f"Error creating DM webhook: {e}")
        return "Failed to create webhook", 500


@blueprint.route("/chat/webhooks/<int:webhook_id>", methods=["DELETE"])
@login_required
def delete_webhook(webhook_id: int) -> ResponseReturnValue:
    """Delete a webhook."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    if UpdateWebhook.delete_webhook(webhook_id):
        return "", 204
    return "Webhook not found", 404


@blueprint.route("/chat/webhooks/<int:webhook_id>/regenerate", methods=["POST"])
@login_required
def regenerate_webhook_token(webhook_id: int) -> ResponseReturnValue:
    """Regenerate a webhook token."""
    if not current_user.is_admin:
        return "Unauthorized", 403

    webhook = UpdateWebhook.scoped().filter_by(id=webhook_id).first()
    if not webhook:
        return "Webhook not found", 404

    new_token = webhook.regenerate_token()
    return jsonify({"token": new_token})
