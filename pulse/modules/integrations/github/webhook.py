# Copyright (c) 2025-2026 remarQable LLC

"""GitHub App webhook ingestion endpoint.

Receives POST /integrations/webhooks/github from GitHub. Verifies the
HMAC-SHA256 signature, looks up the IntegrationConnection by installation_id,
sets workspace context, and dispatches to GitHubProvider.handle_webhook()
in a background thread.

CSRF is exempt for this path — the signature is the authentication mechanism.
"""

import hashlib
import hmac
import logging
import os

from flask import g, request

from system.background import submit_task

from .routes import github_bp

logger = logging.getLogger(__name__)


def _verify_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    """Verify the HMAC-SHA256 signature from GitHub.

    When GITHUB_WEBHOOK_SECRET is set, the signature is verified and the
    request is rejected on mismatch. When the secret is not configured, the
    webhook is rejected in production (fail closed) and accepted with a
    warning in development.

    Args:
        payload_bytes: Raw request body bytes.
        signature_header: Value of the X-Hub-Signature-256 header.

    Returns:
        True if the signature is valid (or no secret is configured in dev).
    """
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        from system.version import is_production

        if is_production():
            logger.error(
                "GITHUB_WEBHOOK_SECRET not set — rejecting webhook in production. "
                "Set this variable so inbound GitHub events can be verified."
            )
            return False
        logger.warning(
            "GITHUB_WEBHOOK_SECRET not set — accepting webhook without signature verification "
            "(development only). Set this variable to harden against spoofed events."
        )
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@github_bp.route("/webhooks/github", methods=["POST"])
def github_webhook():
    """Ingest a GitHub App webhook event.

    Verifies HMAC-SHA256 signature, resolves the IntegrationConnection from
    the installation_id in the payload, then dispatches the event to
    GitHubProvider.handle_webhook() in a background thread.

    Returns:
        200 OK immediately. GitHub retries on non-2xx.
    """
    from modules.integrations.models.integration_connection import IntegrationConnection
    from modules.integrations.github.provider import GitHubProvider

    payload_bytes = request.get_data()
    signature = request.headers.get("X-Hub-Signature-256")
    event_type = request.headers.get("X-GitHub-Event", "")
    print(f"[webhook] GitHub event={event_type!r} sig={'present' if signature else 'MISSING'} bytes={len(payload_bytes)}")

    if not _verify_signature(payload_bytes, signature):
        print("[webhook] signature verification FAILED — check GITHUB_WEBHOOK_SECRET matches the GitHub App setting")
        logger.warning("GitHub webhook signature verification failed")
        return "", 401

    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        logger.warning("GitHub webhook: failed to parse JSON body")
        return "", 200

    action = payload.get("action", "")
    issue_number = payload.get("issue", {}).get("number", "")
    print(f"[webhook] action={action!r} issue=#{issue_number}")

    installation_id = str(
        payload.get("installation", {}).get("id", "")
        or request.headers.get("X-GitHub-Hook-Installation-Target-Id", "")
    )
    print(f"[webhook] installation_id={installation_id!r}")

    if not installation_id:
        print(f"[webhook] no installation_id — ignoring event={event_type}")
        return "", 200

    connection = IntegrationConnection.get_by_installation_id(installation_id)
    if not connection:
        # Fallback: PAT connections carry no installation_id; look up by repo.
        repo_full_name = payload.get("repository", {}).get("full_name", "")
        if repo_full_name:
            logger.debug(
                "webhook: no installation_id match — trying repo fallback for %s",
                repo_full_name,
            )
            connection = IntegrationConnection.get_by_repo(repo_full_name)
    if not connection:
        print(f"[webhook] no IntegrationConnection for installation_id={installation_id} — is the GitHub App installed and connected?")
        return "", 200

    print(f"[webhook] matched connection workspace={connection.workspace_id} repo={connection.external_repo}")

    g.workspace_id = connection.workspace_id
    g.organization_id = connection.organization_id

    provider = GitHubProvider()
    submit_task(provider.handle_webhook, connection, event_type, payload)
    print(f"[webhook] dispatched handle_webhook for event={event_type}")

    return "", 200
