# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     API routes for Web Push notifications. Handles subscription management
#     and provides the VAPID public key for client subscription.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

import logging
from typing import Any

from flask import jsonify, request
from flask_login import current_user, login_required

from .routes import blueprint

logger = logging.getLogger(__name__)


@blueprint.route("/api/push/vapid-public-key", methods=["GET"])
@login_required
def get_vapid_public_key() -> tuple[Any, int]:
    """Return the VAPID public key for push subscription.

    If push notifications are not configured, returns 404.
    """
    from modules.base.core.services.push_notification import (
        get_vapid_public_key,
        is_push_configured,
    )

    if not is_push_configured():
        return jsonify({"error": "Push notifications not configured"}), 404

    public_key = get_vapid_public_key()
    return jsonify({"publicKey": public_key}), 200


@blueprint.route("/api/push/subscribe", methods=["POST"])
@login_required
def subscribe_push() -> tuple[Any, int]:
    """Register a new push subscription for the current user.

    Expected JSON payload:
    {
        "endpoint": "https://...",
        "keys": {
            "auth": "...",
            "p256dh": "..."
        }
    }
    """
    from modules.base.core.models.push_subscription import PushSubscription
    from modules.base.core.services.push_notification import is_push_configured

    if not is_push_configured():
        return jsonify({"error": "Push notifications not configured"}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        endpoint = data.get("endpoint")
        keys = data.get("keys", {})
        auth_key = keys.get("auth")
        p256dh_key = keys.get("p256dh")

        if not all([endpoint, auth_key, p256dh_key]):
            return jsonify({"error": "Missing required fields: endpoint, keys.auth, keys.p256dh"}), 400

        subscription = PushSubscription.create(
            user_id=current_user.id,
            endpoint=endpoint,
            auth_key=auth_key,
            p256dh_key=p256dh_key,
        )

        logger.info(f"Push subscription created/updated for user {current_user.id}")
        return jsonify({"status": "success", "id": subscription.id}), 201

    except Exception as e:
        logger.exception(f"Error creating push subscription: {e}")
        return jsonify({"error": "Failed to create subscription"}), 500


@blueprint.route("/api/push/unsubscribe", methods=["DELETE"])
@login_required
def unsubscribe_push() -> tuple[Any, int]:
    """Remove a push subscription.

    Expected JSON payload:
    {
        "endpoint": "https://..."
    }
    """
    from modules.base.core.models.push_subscription import PushSubscription

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        endpoint = data.get("endpoint")
        if not endpoint:
            return jsonify({"error": "Missing required field: endpoint"}), 400

        deleted = PushSubscription.delete_by_endpoint(endpoint)
        if deleted:
            logger.info(f"Push subscription deleted for user {current_user.id}")
            return jsonify({"status": "success"}), 200
        else:
            return jsonify({"error": "Subscription not found"}), 404

    except Exception as e:
        logger.exception(f"Error deleting push subscription: {e}")
        return jsonify({"error": "Failed to delete subscription"}), 500


@blueprint.route("/api/push/test", methods=["GET", "POST"])
@login_required
def test_push() -> tuple[Any, int]:
    """Send a test push notification to the current user.

    Visit this URL in your browser while logged in to test push notifications.
    """
    from modules.base.core.services.push_notification import is_push_configured, send_push

    if not is_push_configured():
        return jsonify({"error": "Push notifications not configured"}), 404

    try:
        count = send_push(
            user_id=current_user.id,
            title="Test Notification",
            body="This is a test push notification from sparQ",
            url="/",
        )

        if count > 0:
            logger.info(f"Test push sent to user {current_user.id}, {count} notification(s)")
            return jsonify({
                "status": "success",
                "message": f"Sent {count} test notification(s)",
            }), 200
        else:
            return jsonify({
                "status": "warning",
                "message": "No active push subscriptions found for your account",
            }), 200

    except Exception as e:
        logger.exception(f"Error sending test push: {e}")
        return jsonify({"error": "Failed to send test notification"}), 500


@blueprint.route("/api/push/badge-test", methods=["GET"])
@login_required
def badge_test_page() -> str:
    """Test page for Badge API debugging on mobile devices."""
    return """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Badge API Test</title>
    <style>
        body { font-family: -apple-system, sans-serif; padding: 20px; background: #1e1e2e; color: white; }
        .nav { display: flex; gap: 10px; margin-bottom: 20px; }
        .nav a, .nav button { flex: 1; padding: 12px; font-size: 14px; text-align: center;
                 background: #374151; color: white; border: none; border-radius: 8px; text-decoration: none; }
        button { display: block; width: 100%; padding: 15px; margin: 10px 0; font-size: 16px;
                 background: #7c3aed; color: white; border: none; border-radius: 8px; }
        #log { background: #2d2d3d; padding: 15px; border-radius: 8px; margin-top: 20px;
               font-family: monospace; font-size: 12px; white-space: pre-wrap; min-height: 200px; }
    </style>
</head>
<body>
    <div class="nav">
        <a href="/settings">← Settings</a>
        <button onclick="location.reload()">Refresh</button>
        <a href="/">Home</a>
    </div>
    <h2>Badge API Test</h2>
    <button onclick="checkSupport()">1. Check Badge API Support</button>
    <button onclick="setBadge()">2. Set Badge (dot)</button>
    <button onclick="setBadgeNumber(5)">3. Set Badge (5)</button>
    <button onclick="clearBadge()">4. Clear Badge</button>
    <button onclick="sendPush()">5. Send Push + Badge</button>
    <button onclick="updateSW()">6. Update Service Worker</button>
    <div id="log">Tap buttons to test...\n</div>
    <script>
        function log(msg) {
            document.getElementById('log').textContent += msg + '\\n';
        }

        function checkSupport() {
            log('--- Checking Support ---');
            log('setAppBadge: ' + (typeof navigator.setAppBadge));
            log('clearAppBadge: ' + (typeof navigator.clearAppBadge));
            log('Standalone: ' + window.matchMedia('(display-mode: standalone)').matches);
            log('User Agent: ' + navigator.userAgent.slice(0, 50) + '...');
        }

        async function setBadge() {
            log('--- Setting Badge (dot) ---');
            try {
                if (!navigator.setAppBadge) { log('ERROR: API not available'); return; }
                await navigator.setAppBadge();
                log('SUCCESS: Badge set');
            } catch (e) { log('ERROR: ' + e.name + ': ' + e.message); }
        }

        async function setBadgeNumber(n) {
            log('--- Setting Badge (' + n + ') ---');
            try {
                if (!navigator.setAppBadge) { log('ERROR: API not available'); return; }
                await navigator.setAppBadge(n);
                log('SUCCESS: Badge set to ' + n);
            } catch (e) { log('ERROR: ' + e.name + ': ' + e.message); }
        }

        async function clearBadge() {
            log('--- Clearing Badge ---');
            try {
                if (!navigator.clearAppBadge) { log('ERROR: API not available'); return; }
                await navigator.clearAppBadge();
                log('SUCCESS: Badge cleared');
            } catch (e) { log('ERROR: ' + e.name + ': ' + e.message); }
        }

        async function sendPush() {
            log('--- Sending Push ---');
            try {
                const resp = await fetch('/api/push/test');
                const data = await resp.json();
                log('Push result: ' + JSON.stringify(data));
            } catch (e) { log('ERROR: ' + e.message); }
        }

        async function updateSW() {
            log('--- Updating Service Worker ---');
            try {
                const reg = await navigator.serviceWorker.getRegistration();
                if (reg) {
                    await reg.update();
                    log('SUCCESS: SW update triggered');
                    log('Refresh page after a moment...');
                } else {
                    log('ERROR: No SW registration found');
                }
            } catch (e) { log('ERROR: ' + e.message); }
        }

        // Check SW version on load
        fetch('/service-worker.js').then(r => r.text()).then(t => {
            const match = t.match(/CACHE_VERSION = '(v\\d+)'/);
            if (match) log('SW Version: ' + match[1]);
        });

        // Listen for messages from service worker (for badge setting)
        if (navigator.serviceWorker) {
            navigator.serviceWorker.addEventListener('message', function(event) {
                log('--- SW Message Received ---');
                log('Message: ' + JSON.stringify(event.data));
                if (event.data && event.data.type === 'SET_BADGE') {
                    if (navigator.setAppBadge) {
                        navigator.setAppBadge(event.data.count)
                            .then(() => log('SUCCESS: Badge set from SW message'))
                            .catch(e => log('ERROR setting badge: ' + e.message));
                    } else {
                        log('ERROR: setAppBadge not available');
                    }
                }
            });
            log('Listening for SW messages...');
        }
    </script>
</body>
</html>"""
