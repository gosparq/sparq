# Copyright (c) 2025-2026 remarQable LLC

"""GitHubProvider — IntegrationProvider adapter for GitHub App.

Registered into IntegrationRegistry at import time. Import this module from
modules/integrations/github/__init__.py to ensure registration on startup.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from modules.integrations.base import IntegrationProvider
from modules.integrations.registry import register

if TYPE_CHECKING:
    from modules.integrations.models.integration_connection import IntegrationConnection

logger = logging.getLogger(__name__)

# GitHub events the auto-registered repo webhook subscribes to.
#   issues       → issue ↔ task sync
#   push         → commits surfaced as the pusher's "Current" status
#   pull_request → PR lifecycle surfaced as the actor's "Current" status
WEBHOOK_EVENTS = ["issues", "push", "pull_request"]


class GitHubProvider(IntegrationProvider):
    """IntegrationProvider adapter for GitHub App installations.

    One installation per workspace. Credentials dict expected by connect()
    carries installation_id and repo (owner/repo).

    Attributes:
        provider_name: Registry slug.
    """

    provider_name = "github"
    palette_shortcut = "gh"

    # ── Display ───────────────────────────────────────────────────────────────

    def get_display_info(self) -> dict:
        """Return display metadata for the Settings > Integrations card.

        Returns:
            Dict with name, icon_class, color, description, settings_url, connect_url.
        """
        from flask import url_for
        return {
            "name": "GitHub",
            "icon_class": "fa-brands fa-github",
            "color": "#24292f",
            "description": "Link GitHub issues to Tasks, Updates, and Blockers.",
            "settings_url": url_for("github_bp.github_settings"),
            "connect_url": url_for("github_bp.github_connect"),
        }

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def connect(self, workspace_id: int, credentials: dict) -> "IntegrationConnection":
        """Persist a GitHub connection (App or PAT) for a workspace.

        Dispatches on ``credentials['auth_type']``:
        - ``'pat'``: calls ``finalize_pat_connection()`` with the provided token and repo.
        - anything else (or absent): treats as App and calls ``finalize_connection()``.

        In practice the connect routes call the model methods directly; this
        method exists for interface completeness.

        Args:
            workspace_id: Target workspace ID.
            credentials: For App — ``{installation_id, repo}``; for PAT — ``{auth_type: 'pat', pat_token, repo}``.

        Returns:
            Created or updated IntegrationConnection.
        """
        from flask import g
        from modules.integrations.models.integration_connection import IntegrationConnection

        g.workspace_id = workspace_id
        conn = IntegrationConnection.get_or_create("github")

        if credentials.get("auth_type") == "pat":
            conn.finalize_pat_connection(
                pat_token=credentials["pat_token"],
                repo=credentials["repo"],
                member_id=credentials.get("member_id"),
            )
        else:
            conn.finalize_connection(
                installation_id=credentials["installation_id"],
                repo=credentials["repo"],
                member_id=credentials.get("member_id"),
            )
        return conn

    def disconnect(self, connection: "IntegrationConnection") -> None:
        """Revoke the connection and mark it disconnected.

        The GitHub App installation revoke via API is performed only for App
        connections — PAT connections have no server-side installation to revoke.
        Local cleanup (clearing credentials, setting status) applies to both.

        Args:
            connection: The active IntegrationConnection to disconnect.
        """
        from system.db.database import db

        # Remove any auto-registered repo webhook first, while credentials and
        # the repo are still present. No-op for App connections (webhook_id
        # unset — events arrive through the GitHub App, not a repo hook).
        self.deregister_webhook(connection)

        # App-only: revoke the GitHub App installation via the GitHub API.
        if connection.auth_type == "app" and connection.installation_id:
            try:
                import jwt
                import time
                import requests

                app_id = os.environ.get("GITHUB_APP_ID", "")
                from modules.integrations.github.client import _load_private_key
                private_key = _load_private_key()
                now = int(time.time())
                app_jwt = jwt.encode(
                    {"iat": now - 60, "exp": now + 600, "iss": app_id},
                    private_key,
                    algorithm="RS256",
                )
                requests.delete(
                    f"https://api.github.com/app/installations/{connection.installation_id}",
                    headers={
                        "Authorization": f"Bearer {app_jwt}",
                        "Accept": "application/vnd.github+json",
                    },
                    timeout=10,
                )
            except Exception as exc:
                logger.warning("GitHub disconnect revoke failed (ignored): %s", exc)

        connection.status = "disconnected"
        connection.installation_id = None
        connection.external_repo = None
        connection.cached_token = None
        connection.token_expires_at = None
        connection.error_message = None
        db.session.commit()
        logger.info("GitHub disconnected for ts=%s", connection.workspace_id)

    # ── Webhook registration (PAT) ─────────────────────────────────────────────

    def _webhook_callback_url(self) -> str:
        """Build the public URL GitHub should deliver webhook events to.

        Prefers the ``GITHUB_WEBHOOK_BASE_URL`` env var (set this behind a
        reverse proxy, or to an ngrok tunnel for local end-to-end testing);
        otherwise derives the URL from the current request host.

        Returns:
            Absolute URL to the github_webhook endpoint.
        """
        from flask import url_for

        base = os.environ.get("GITHUB_WEBHOOK_BASE_URL", "").strip()
        if base:
            return base.rstrip("/") + url_for("github_bp.github_webhook")
        return url_for("github_bp.github_webhook", _external=True)

    def register_webhook(self, connection: "IntegrationConnection") -> str:
        """Register (or reuse) a repo webhook so issue events sync automatically.

        Idempotent: if a hook already points at our callback URL it is reused
        rather than duplicated. Stores the webhook id on the connection via
        ``set_webhook_id``. Must be called within a request context (uses
        ``url_for``).

        Args:
            connection: A connected IntegrationConnection (typically PAT auth).

        Returns:
            Status string: ``"registered"`` (new hook), ``"reused"`` (existing
            hook adopted), ``"no_permission"`` (token lacks ``admin:repo_hook``
            or repo-admin rights), or ``"error"`` (other failure). The connection
            remains usable for manual sync in every non-success case.
        """
        from modules.integrations.github.client import GitHubClient, GitHubAPIError

        repo = connection.external_repo
        if not repo:
            return "error"

        callback_url = self._webhook_callback_url()
        secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

        try:
            client = GitHubClient(connection)
            for hook in client.list_repo_webhooks(repo):
                if (hook.get("config") or {}).get("url") == callback_url:
                    # Bring an existing hook onto the current event list (older
                    # hooks may be subscribed to "issues" only).
                    if set(hook.get("events") or []) != set(WEBHOOK_EVENTS):
                        client.update_repo_webhook(repo, int(hook["id"]), WEBHOOK_EVENTS)
                    connection.set_webhook_id(int(hook["id"]), WEBHOOK_EVENTS)
                    return "reused"
            created = client.create_repo_webhook(repo, callback_url, secret, WEBHOOK_EVENTS)
            connection.set_webhook_id(int(created["id"]), WEBHOOK_EVENTS)
            logger.info("Registered GitHub webhook for repo=%s ts=%s", repo, connection.workspace_id)
            return "registered"
        except GitHubAPIError as exc:
            # 403/404 → the token cannot manage hooks on this repo.
            if exc.status_code in (403, 404):
                logger.warning("Webhook registration denied for repo=%s: %s", repo, exc)
                return "no_permission"
            logger.error("Webhook registration failed for repo=%s: %s", repo, exc)
            return "error"
        except Exception as exc:
            logger.error("Webhook registration error for repo=%s: %s", repo, exc, exc_info=True)
            return "error"

    def deregister_webhook(self, connection: "IntegrationConnection") -> None:
        """Delete the auto-registered repo webhook, if any (best-effort).

        Reads the stored webhook id from the connection, deletes it on GitHub,
        and clears the stored id regardless of API outcome so a stale id is
        never left behind. No-op when no webhook id is stored.

        Args:
            connection: The IntegrationConnection whose webhook to remove.
        """
        from modules.integrations.github.client import GitHubClient

        hook_id = connection.get_webhook_id()
        repo = connection.external_repo
        if not hook_id or not repo:
            return
        try:
            client = GitHubClient(connection)
            client.delete_repo_webhook(repo, hook_id)
            logger.info("Deregistered GitHub webhook for repo=%s ts=%s", repo, connection.workspace_id)
        except Exception as exc:
            logger.warning("Webhook deregistration failed (ignored): %s", exc)
        finally:
            connection.set_webhook_id(None)

    # ── Webhook ───────────────────────────────────────────────────────────────

    def handle_webhook(
        self,
        connection: "IntegrationConnection",
        event_type: str,
        payload: dict,
    ) -> None:
        """Dispatch an inbound GitHub webhook event.

        Called from a background thread (via submit_task) — Flask app context
        is pushed by submit_task, and g.workspace_id / g.organization_id are
        restored from the captured request-time values.

        Handles:
          - issues.closed / issues.reopened  → UC-5 status sync
          - issues.assigned / issues.unassigned → UC-8 assignee sync
          - issues.labeled / issues.unlabeled   → UC-8 urgency label sync
          - all issues events → refresh cached_state on matching refs
          - push → commits posted as the pusher's "Current" status
          - pull_request → PR lifecycle posted as the actor's "Current" status

        Unknown events are silently ignored.

        Args:
            connection: The IntegrationConnection the event belongs to.
            event_type: GitHub event name (X-GitHub-Event header value).
            payload: Parsed JSON payload.
        """
        print(f"[webhook] handle_webhook: event={event_type!r} installation={connection.installation_id}")

        if event_type == "push":
            self._handle_push(connection, payload)
            return
        if event_type == "pull_request":
            self._handle_pull_request(connection, payload)
            return
        if event_type != "issues":
            print(f"[webhook] ignoring unhandled event={event_type!r}")
            return

        action = payload.get("action", "")
        issue = payload.get("issue", {})
        issue_number = str(issue.get("number", ""))
        print(f"[webhook] issues event action={action!r} issue=#{issue_number}")
        if not issue_number:
            return

        # Always refresh cached_state on any issues event.
        self._refresh_cached_state(connection, issue_number, issue)

        if action in ("closed", "reopened"):
            self._handle_status_change(connection, issue_number, action)
            # Prune the now-closed issue from the orphan cache (or re-add it on
            # reopen). Safe to re-query here — the issue isn't brand-new, so
            # GitHub's list API is consistent.
            self._refresh_orphans_async(connection.id)
        elif action == "opened":
            self._add_orphan_from_payload(connection.id, issue)
        elif action in ("assigned", "unassigned"):
            self._handle_assignee_change(connection, issue_number, payload)
        elif action in ("labeled", "unlabeled"):
            self._handle_label_change(connection, issue_number, issue)

    # ── Internal webhook helpers ──────────────────────────────────────────────

    def _refresh_cached_state(
        self,
        connection: "IntegrationConnection",
        issue_number: str,
        issue: dict,
    ) -> None:
        """Update cached_state on all matching IntegrationRef rows.

        Args:
            connection: Active IntegrationConnection.
            issue_number: Issue number as string.
            issue: Parsed issue object from the webhook payload.
        """

        from modules.integrations.models.integration_ref import IntegrationRef
        from system.db.database import db

        refs = IntegrationRef.get_by_external("github", issue_number, connection.workspace_id)
        if not refs:
            return

        labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        user = issue.get("user") or {}
        assignee = issue.get("assignee") or {}
        state = {
            "title": issue.get("title", ""),
            "state": issue.get("state", "open"),
            "html_url": issue.get("html_url", ""),
            "opened_by": user.get("login", ""),
            "opened_at": issue.get("created_at", ""),
            "labels": labels,
            "assignee_login": assignee.get("login", ""),
        }

        now = datetime.now(timezone.utc)
        for ref in refs:
            ref.cached_state = state
            ref.cached_at = now
        db.session.commit()

    def _handle_status_change(
        self,
        connection: "IntegrationConnection",
        issue_number: str,
        action: str,
    ) -> None:
        """Enqueue UC-5 sync for closed/reopened events.

        Args:
            connection: Active IntegrationConnection.
            issue_number: Issue number as string.
            action: "closed" or "reopened".
        """
        from modules.integrations.models.integration_ref import IntegrationRef
        from system.background import submit_task
        from modules.integrations.github.sync import sync_github_to_sparq

        refs = IntegrationRef.get_by_external("github", issue_number, connection.workspace_id)
        print(f"[webhook] _handle_status_change: issue=#{issue_number} action={action} refs={[r.id for r in refs]}")
        for ref in refs:
            task_id = ref.linked_task_id or (ref.object_id if ref.object_type == "task" else None)
            print(f"[webhook] ref={ref.id} linked_task_id={ref.linked_task_id} object_id={ref.object_id} → task_id={task_id}")
            if task_id:
                submit_task(sync_github_to_sparq, ref.id, action)
                print(f"[webhook] enqueued sync_github_to_sparq ref={ref.id} action={action} task={task_id}")
                logger.info(
                    "Enqueued sync_github_to_sparq ref=%s action=%s", ref.id, action
                )

    def _handle_assignee_change(
        self,
        connection: "IntegrationConnection",
        issue_number: str,
        payload: dict,
    ) -> None:
        """Enqueue UC-8 assignee sync for assigned/unassigned events.

        Maps the GitHub assignee's numeric id to a sparQ WorkspaceUser via
        OAuthConnection.provider_user_id. Silently skips if no mapping found.

        Args:
            connection: Active IntegrationConnection.
            issue_number: Issue number as string.
            payload: Full webhook payload (contains assignee object).
        """
        from modules.integrations.models.integration_ref import IntegrationRef
        from modules.base.core.models.oauth_connection import OAuthConnection
        from modules.base.core.models.workspace_user import WorkspaceUser
        from system.background import submit_task
        from modules.integrations.github.sync import sync_github_to_sparq

        assignee_payload = payload.get("assignee") or {}
        github_user_id = str(assignee_payload.get("id", ""))

        # Resolve GitHub numeric id → sparQ WorkspaceUser
        ts_member_id = None
        if github_user_id:
            oauth = OAuthConnection.query.filter_by(
                provider="github", provider_user_id=github_user_id
            ).first()
            if oauth:
                member = WorkspaceUser.query.filter_by(
                    workspace_id=connection.workspace_id, user_id=oauth.user_id
                ).first()
                if member:
                    ts_member_id = member.id

        action = payload.get("action", "assigned")
        # For unassigned with no mapping, skip
        if action == "unassigned" and ts_member_id is None:
            return

        refs = IntegrationRef.get_by_external("github", issue_number, connection.workspace_id)
        for ref in refs:
            if ref.linked_task_id:
                submit_task(
                    sync_github_to_sparq, ref.id, "assigned",
                    new_assignee_id=ts_member_id,
                )

    def _handle_label_change(
        self,
        connection: "IntegrationConnection",
        issue_number: str,
        issue: dict,
    ) -> None:
        """Enqueue UC-8 urgency sync for labeled/unlabeled events.

        Extracts the strictest sparq:* label from the issue's current label
        set and syncs to urgency_tier on linked Tasks.

        Args:
            connection: Active IntegrationConnection.
            issue_number: Issue number as string.
            issue: Current issue state from the webhook payload.
        """
        from modules.integrations.models.integration_ref import IntegrationRef
        from system.background import submit_task
        from modules.integrations.github.sync import sync_github_to_sparq

        _SPARQ_TIERS = {"sparq:now": 1, "sparq:later": 2, "sparq:whenever": 3}
        labels = [lbl.get("name", "").lower() for lbl in issue.get("labels", [])]
        sparq_labels = [lbl for lbl in labels if lbl in _SPARQ_TIERS]
        if not sparq_labels:
            return

        # Use the strictest (lowest number = most urgent) label.
        tier = min(_SPARQ_TIERS[lbl] for lbl in sparq_labels)

        refs = IntegrationRef.get_by_external("github", issue_number, connection.workspace_id)
        for ref in refs:
            if ref.linked_task_id:
                submit_task(sync_github_to_sparq, ref.id, "relabeled", new_tier=tier)

    def _post_current_activity(self, github_user: dict, text: str | None) -> None:
        """Post a repo-activity line as the mapped sparQ member's "Current" status.

        Resolves the GitHub actor to a sparQ member via the identity mapping and
        skips silently when the actor is unmapped (the feed is person-centric —
        an authorless post has no place in it).

        Args:
            github_user: The ``sender`` object from the webhook payload.
            text: Plain-text summary line, or None to skip.
        """
        if not text:
            return
        from modules.base.core.models.oauth_connection import OAuthConnection
        from modules.base.updates.models.post import UpdatePost

        github_id = (github_user or {}).get("id")
        if github_id is None:
            return
        member = OAuthConnection.get_member_for_github_id(github_id)
        if not member:
            print(f"[webhook] activity: GitHub user {(github_user or {}).get('login')!r} not mapped — skipping")
            return
        UpdatePost.create_current_activity(member.id, text)

    def _handle_push(self, connection: "IntegrationConnection", payload: dict) -> None:
        """Post a push as the pusher's "Current" status (skips if unmapped).

        Args:
            connection: Active IntegrationConnection.
            payload: The push webhook payload.
        """
        from modules.integrations.github.activity import summarize_push

        self._post_current_activity(payload.get("sender") or {}, summarize_push(payload))

    def _handle_pull_request(self, connection: "IntegrationConnection", payload: dict) -> None:
        """Post a meaningful PR action as the actor's "Current" status.

        Args:
            connection: Active IntegrationConnection.
            payload: The pull_request webhook payload.
        """
        from modules.integrations.github.activity import summarize_pull_request

        self._post_current_activity(payload.get("sender") or {}, summarize_pull_request(payload))

    def _add_orphan_from_payload(self, connection_id: int, issue: dict) -> None:
        """Add a newly-opened issue to the orphan cache using webhook payload data.

        Re-fetches the connection in the current (background) thread — the
        instance passed into handle_webhook is detached from this thread's
        session — then appends the issue from the payload. Avoids re-querying
        GitHub's eventually-consistent issue-list API, which races issue
        creation and can cache a stale/empty result.

        Args:
            connection_id: IntegrationConnection id to update.
            issue: The issue object from the webhook payload.
        """
        try:
            from modules.integrations.models.integration_connection import IntegrationConnection as IC

            conn = IC.query.get(connection_id)
            if conn:
                conn.add_orphan_from_issue(issue)
        except Exception as exc:
            logger.warning("_add_orphan_from_payload failed: %s", exc)

    def _refresh_orphans_async(self, connection_id: int) -> None:
        """Rebuild the orphan cache from GitHub in a background thread.

        Used on ``issues.closed``/``reopened`` and after a link — points where
        the issue is no longer brand-new, so GitHub's issue-list API is
        consistent (unlike ``issues.opened``, which races issue creation and
        uses ``_add_orphan_from_payload`` instead). The full re-query prunes
        issues that are now closed or linked and heals any cache drift.

        Args:
            connection_id: IntegrationConnection id to refresh.
        """
        try:
            from system.background import submit_task

            def _refresh(conn_id: int) -> None:
                from modules.integrations.models.integration_connection import IntegrationConnection as IC
                from modules.integrations.github.client import GitHubClient as GHC
                from flask import g
                conn = IC.query.get(conn_id)
                if not conn:
                    return
                g.workspace_id = conn.workspace_id
                g.organization_id = conn.organization_id
                client = GHC(conn)
                conn.refresh_orphans(client)

            submit_task(_refresh, connection_id)
        except Exception as exc:
            logger.warning("_refresh_orphans_async failed: %s", exc)

    def handle_deferred_action(self, task, action: dict) -> None:
        """Create or link a GitHub issue after the task has been saved.

        Reads action["action"] == "create" or "link":
          create: creates a new GitHub issue using the task's actual urgency_tier
                  as the sparq:now/later/whenever label.
          link:   pairs an existing issue (action["external_id"]) with the task.

        In both cases the IntegrationRef is created, the task title receives
        [GH-N], and a sparQ backlink is written into the GitHub issue body.

        Args:
            task: Newly created Task instance.
            action: Dict written by the palette panel:
                    create → {"action": "create", "title": str, "body": str}
                    link   → {"action": "link", "external_id": str}
        """
        from modules.integrations.models.integration_connection import IntegrationConnection
        from modules.integrations.models.integration_ref import IntegrationRef
        from modules.integrations.github.client import GitHubClient
        from system.db.database import db

        connection = IntegrationConnection.get_active(self.provider_name)
        if not connection:
            return

        client = GitHubClient(connection)
        repo = connection.external_repo
        action_type = action.get("action", "")
        _TIER_LABELS = {1: "sparq:now", 2: "sparq:later", 3: "sparq:whenever"}
        _LABEL_COLORS = {"sparq:now": "dc2626", "sparq:later": "d97706", "sparq:whenever": "16a34a"}

        try:
            if action_type == "create":
                title = str(action.get("title", "")).strip()
                body = str(action.get("body", "")).strip()
                if not title:
                    return
                label = _TIER_LABELS.get(task.urgency_tier, "sparq:later")
                for lname, lcolor in _LABEL_COLORS.items():
                    try:
                        client.ensure_label(repo, lname, lcolor)
                    except Exception:
                        pass
                raw = client.create_issue(repo=repo, title=title, body=body, labels=[label])
                issue_number = str(raw.get("number", ""))
                if not issue_number:
                    return

            elif action_type == "link":
                issue_number = str(action.get("external_id", "")).strip()
                if not issue_number:
                    return
                try:
                    raw = client.get_issue(repo, int(issue_number))
                except Exception:
                    raw = {}
            else:
                return

            ref = IntegrationRef.get_or_create(
                provider="github",
                external_id=issue_number,
                external_repo=repo,
                object_type="task",
                object_id=task.id,
            )
            ref.linked_task_id = task.id
            user = (raw or {}).get("user") or {}
            ref.update_cached_state({
                "title": (raw or {}).get("title", action.get("title", "")),
                "state": (raw or {}).get("state", "open"),
                "html_url": (raw or {}).get("html_url", ""),
                "opened_by": user.get("login", ""),
                "opened_at": (raw or {}).get("created_at", ""),
                "labels": [lbl.get("name", "") for lbl in (raw or {}).get("labels", [])],
                "assignee_login": "",
            })

            token = f"[GH-{issue_number}]"
            if token not in (task.title or ""):
                task.title = (task.title or "").rstrip() + " " + token
            db.session.commit()

            # The issue is now linked, so it's no longer an orphan — rebuild the
            # cache so it drops out of the link list.
            self._refresh_orphans_async(connection.id)

            # Write the sparQ backlink using the URL pre-computed in the request
            # context (url_for with _external=True doesn't work in background threads).
            task_url = action.get("_sparq_task_url", "")
            if task_url:
                try:
                    import re as _re
                    from modules.integrations.github.sync import inject_backlink
                    clean_title = _re.sub(r"\s*\[GH-\d+\]\s*", " ", task.title or "").strip()
                    current_body = (raw or {}).get("body") or ""
                    new_body = inject_backlink(current_body, clean_title, task_url)
                    if new_body != current_body:
                        client.update_issue_body(repo, int(issue_number), new_body)
                except Exception as exc:
                    logger.warning("handle_deferred_action: backlink write failed: %s", exc)

        except Exception as exc:
            logger.error("GitHubProvider.handle_deferred_action failed: %s", exc, exc_info=True)

    def get_palette_commands(self, task_id: int) -> list[dict]:
        """Return GitHub slash-palette commands.

        Returns empty list if the task already has a linked GitHub issue,
        otherwise returns create-issue and link-issue commands.

        Args:
            task_id: Current task PK; 0 for new-task context.

        Returns:
            List of command dicts with action_url pointing to panel routes.
        """
        from flask import url_for
        from modules.integrations.models.integration_ref import IntegrationRef

        if task_id:
            already_linked = (
                IntegrationRef.scoped()
                .filter_by(provider="github", linked_task_id=task_id)
                .first()
            )
            if already_linked:
                return []

        s = self.palette_shortcut
        return [
            {
                "id": "github-create",
                "label": "Create Issue",
                "shortcut": s,
                "icon": "fa-brands fa-github",
                "action_url": url_for("github_bp.palette_create_panel", task_id=task_id),
            },
            {
                "id": "github-link",
                "label": "Link Issue",
                "shortcut": s,
                "icon": "fa-brands fa-github",
                "action_url": url_for("github_bp.palette_link_panel", task_id=task_id),
            },
        ]

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self, connection: "IntegrationConnection") -> dict:
        """Return a summary of the current connection state.

        Args:
            connection: The IntegrationConnection to inspect.

        Returns:
            Dict with connected (bool), repo (str|None), last_synced_at (datetime|None).
        """
        return {
            "connected": connection.status == "connected",
            "repo": connection.external_repo,
            "last_synced_at": connection.last_synced_at,
        }


# Register into the global registry at import time.
register(GitHubProvider)
