# Copyright (c) 2025-2026 remarQable LLC

"""GitHubClient — authenticates via GitHub App installation tokens and wraps the Issues API.

Two-layer auth:
1. JWT signed with the App private key (RS256) → proves we are the GitHub App.
2. Installation access token (POST .../app/installations/{id}/access_tokens) →
   short-lived bearer token used for all API calls. Cached on IntegrationConnection.

Environment variables required:
    GITHUB_APP_ID          Numeric GitHub App ID.
    GITHUB_APP_PRIVATE_KEY PEM private key (raw or base64-encoded).
"""

from __future__ import annotations

import base64
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Optional

import jwt
import requests

from system.oauth.token_manager import TokenManager

if TYPE_CHECKING:
    from modules.integrations.models.integration_connection import IntegrationConnection

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Raised on non-2xx responses from the GitHub API."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


def _load_private_key() -> str:
    """Return the GitHub App RSA private key as a PEM string.

    Accepts either a raw PEM string or a base64-encoded PEM stored in
    GITHUB_APP_PRIVATE_KEY. The base64 path handles Docker/prod environments
    where multi-line env vars are awkward.
    """
    raw = os.environ.get("GITHUB_APP_PRIVATE_KEY", "")
    if not raw:
        raise RuntimeError("GITHUB_APP_PRIVATE_KEY environment variable not set")

    # If it looks like base64 (no PEM header present), decode it first.
    if "-----BEGIN" not in raw:
        try:
            raw = base64.b64decode(raw).decode()
        except Exception as exc:
            raise RuntimeError(
                "GITHUB_APP_PRIVATE_KEY is neither valid PEM nor valid base64"
            ) from exc

    # Normalise escaped newlines written by some env var tools.
    return raw.replace("\\n", "\n")


def _generate_app_jwt() -> str:
    """Build a 10-minute JWT signed with the GitHub App private key.

    Returns:
        Encoded JWT string.
    """
    app_id = os.environ.get("GITHUB_APP_ID", "")
    if not app_id:
        raise RuntimeError("GITHUB_APP_ID environment variable not set")

    private_key = _load_private_key()
    now = int(time.time())
    payload = {
        "iat": now - 60,   # issued-at backdated 60 s for clock skew
        "exp": now + 600,  # expires in 10 minutes (GitHub max)
        "iss": app_id,
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def _exchange_installation_token(installation_id: str) -> tuple[str, datetime]:
    """Call GitHub to get a short-lived installation access token.

    Args:
        installation_id: The GitHub App installation ID.

    Returns:
        Tuple of (plain-text token, UTC expiry datetime).

    Raises:
        GitHubAPIError: On non-2xx response.
    """
    app_jwt = _generate_app_jwt()
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, headers=headers, timeout=15)
    if not resp.ok:
        raise GitHubAPIError(
            f"Failed to get installation token: {resp.text}", resp.status_code
        )
    data = resp.json()
    token = data["token"]
    # GitHub returns ISO 8601 string like "2024-01-01T12:00:00Z"
    expires_at_str = data.get("expires_at", "")
    try:
        expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    return token, expires_at


class GitHubClient:
    """Authenticated GitHub Issues API client for a specific App installation.

    Args:
        connection: An IntegrationConnection with status "connected".
    """

    def __init__(self, connection: "IntegrationConnection") -> None:
        self._connection = connection
        self.token = self._resolve_token()
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    # ── Auth helpers ──────────────────────────────────────────────────────────

    def _resolve_token(self) -> str:
        """Return a valid bearer token for the connection's auth strategy.

        For PAT connections the stored token is decrypted and returned directly
        — there is no expiry or refresh cycle.  For App connections the cached
        installation access token is returned if still valid, otherwise a new
        one is exchanged via the GitHub App JWT flow.

        Returns:
            Plain-text bearer token ready for use in an Authorization header.

        Raises:
            GitHubAPIError: If the PAT is missing or the App token exchange fails.
        """
        from system.db.database import db

        conn = self._connection

        # PAT path: decrypt and return directly; no expiry check needed.
        if conn.auth_type == "pat":
            if not conn.cached_token:
                raise GitHubAPIError("GitHub PAT not found in connection", 401)
            return TokenManager.decrypt(conn.cached_token)

        # App path: return cached token if still valid, otherwise refresh.
        if conn.cached_token and not conn.is_token_expired():
            return TokenManager.decrypt(conn.cached_token)

        logger.info("Refreshing GitHub installation token for ts=%s", conn.workspace_id)
        plain_token, expires_at = _exchange_installation_token(conn.installation_id)
        conn.cached_token = TokenManager.encrypt(plain_token)
        conn.token_expires_at = expires_at
        db.session.commit()
        return plain_token

    # ── Internal request helper ───────────────────────────────────────────────

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict] = None,
        json_data: Optional[dict] = None,
    ) -> dict | list:
        """Make an authenticated request to the GitHub API.

        Args:
            method: HTTP verb ("GET", "POST", etc.)
            path: API path, e.g. "/repos/owner/repo/issues".
            params: Query parameters.
            json_data: JSON body.

        Returns:
            Parsed JSON response (dict or list).

        Raises:
            GitHubAPIError: On non-2xx response.
        """
        url = f"{GITHUB_API_BASE}{path}"
        try:
            resp = requests.request(
                method,
                url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=15,
            )
        except requests.RequestException as exc:
            raise GitHubAPIError(f"GitHub API request failed: {exc}") from exc

        if not resp.ok:
            logger.error(
                "GitHub API %s %s → %s: %s",
                method,
                path,
                resp.status_code,
                resp.text[:200],
            )
            raise GitHubAPIError(
                f"GitHub API error {resp.status_code}: {resp.text[:200]}",
                resp.status_code,
            )
        if resp.status_code == 204:
            return {}
        return resp.json()

    # ── Installation repos ────────────────────────────────────────────────────

    def get_installation_repos(self) -> list[dict]:
        """List all repos accessible to this installation.

        Returns:
            List of repository dicts with at least {full_name, private, html_url}.
        """
        result = self._request("GET", "/installation/repositories", params={"per_page": 100})
        return result.get("repositories", []) if isinstance(result, dict) else []

    # ── Issues API ────────────────────────────────────────────────────────────

    def search_issues(self, repo: str, query: str, limit: int = 20) -> list[dict]:
        """Search issues in a repository.

        Args:
            repo: Owner/repo string, e.g. "acme/backend".
            query: Free-text search string.
            limit: Maximum results to return.

        Returns:
            List of issue dicts with {number, title, state, html_url}.
        """
        q = f"repo:{repo} is:issue is:open {query}" if query else f"repo:{repo} is:issue is:open"
        data = self._request(
            "GET",
            "/search/issues",
            params={"q": q, "per_page": min(limit, 30)},
        )
        items = data.get("items", []) if isinstance(data, dict) else []
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "state": i["state"],
                "html_url": i["html_url"],
            }
            for i in items
        ]

    def get_issue(self, repo: str, number: int) -> dict:
        """Fetch a single issue.

        Args:
            repo: Owner/repo string.
            number: Issue number.

        Returns:
            Full issue dict from GitHub API.
        """
        return self._request("GET", f"/repos/{repo}/issues/{number}")

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str,
        assignee_login: Optional[str] = None,
        labels: Optional[list[str]] = None,
    ) -> dict:
        """Create a new GitHub issue.

        Args:
            repo: Owner/repo string.
            title: Issue title.
            body: Issue body (Markdown).
            assignee_login: GitHub login to assign.
            labels: List of label names.

        Returns:
            Created issue dict.
        """
        payload: dict = {"title": title, "body": body}
        if assignee_login:
            payload["assignees"] = [assignee_login]
        if labels:
            payload["labels"] = labels
        return self._request("POST", f"/repos/{repo}/issues", json_data=payload)

    def close_issue(self, repo: str, number: int) -> dict:
        """Close a GitHub issue.

        Args:
            repo: Owner/repo string.
            number: Issue number.

        Returns:
            Updated issue dict.
        """
        return self._request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            json_data={"state": "closed"},
        )

    def reopen_issue(self, repo: str, number: int) -> dict:
        """Reopen a closed GitHub issue.

        Args:
            repo: Owner/repo string.
            number: Issue number.

        Returns:
            Updated issue dict.
        """
        return self._request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            json_data={"state": "open"},
        )

    def set_issue_assignee(self, repo: str, number: int, login: str) -> dict:
        """Replace all assignees on an issue with a single login.

        Args:
            repo: Owner/repo string.
            number: Issue number.
            login: GitHub login to assign.

        Returns:
            Updated issue dict.
        """
        return self._request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            json_data={"assignees": [login]},
        )

    def update_issue_body(self, repo: str, number: int, body: str) -> dict:
        """Replace the body of a GitHub issue.

        Args:
            repo: Owner/repo string.
            number: Issue number.
            body: New body text (Markdown).

        Returns:
            Updated issue dict.
        """
        return self._request(
            "PATCH",
            f"/repos/{repo}/issues/{number}",
            json_data={"body": body},
        )

    def set_issue_labels(self, repo: str, number: int, labels: list[str]) -> dict:
        """Replace all labels on an issue.

        Args:
            repo: Owner/repo string.
            number: Issue number.
            labels: Complete list of label names to set.

        Returns:
            Response dict from GitHub.
        """
        return self._request(
            "PUT",
            f"/repos/{repo}/issues/{number}/labels",
            json_data={"labels": labels},
        )

    def list_collaborators(self, repo: str) -> list[dict]:
        """List collaborators with push access.

        Args:
            repo: Owner/repo string.

        Returns:
            List of collaborator dicts with {login, avatar_url}.
        """
        data = self._request(
            "GET",
            f"/repos/{repo}/collaborators",
            params={"per_page": 100},
        )
        return data if isinstance(data, list) else []

    def list_contributors(self, repo: str) -> list[dict]:
        """List repository contributors sorted by commit count descending.

        Filters out bot accounts (login ending with [bot]).

        Args:
            repo: Owner/repo string.

        Returns:
            List of contributor dicts with {login, avatar_url, contributions}.
        """
        data = self._request(
            "GET",
            f"/repos/{repo}/contributors",
            params={"per_page": 100, "anon": "false"},
        )
        if not isinstance(data, list):
            return []
        return [c for c in data if not c.get("login", "").endswith("[bot]")]

    # ── Repo webhooks ─────────────────────────────────────────────────────────

    def list_repo_webhooks(self, repo: str) -> list[dict]:
        """List repository webhooks.

        Requires the token to have ``admin:repo_hook`` scope and the user to
        hold admin rights on the repo; otherwise GitHub returns 403/404.

        Args:
            repo: Owner/repo string.

        Returns:
            List of webhook dicts with at least {id, config: {url}}.
        """
        data = self._request("GET", f"/repos/{repo}/hooks", params={"per_page": 100})
        return data if isinstance(data, list) else []

    def create_repo_webhook(
        self,
        repo: str,
        callback_url: str,
        secret: str,
        events: list[str],
    ) -> dict:
        """Create a repository webhook delivering JSON payloads.

        Args:
            repo: Owner/repo string.
            callback_url: Public URL GitHub will POST events to.
            secret: HMAC secret GitHub signs payloads with. Omitted from the
                config when empty.
            events: GitHub event names to subscribe to (e.g. ``["issues"]``).

        Returns:
            Created webhook dict, including its numeric ``id``.
        """
        config: dict = {"url": callback_url, "content_type": "json"}
        if secret:
            config["secret"] = secret
        return self._request(
            "POST",
            f"/repos/{repo}/hooks",
            json_data={"name": "web", "active": True, "events": events, "config": config},
        )

    def delete_repo_webhook(self, repo: str, hook_id: int) -> None:
        """Delete a repository webhook by id.

        Args:
            repo: Owner/repo string.
            hook_id: Numeric webhook id returned by create_repo_webhook.
        """
        self._request("DELETE", f"/repos/{repo}/hooks/{hook_id}")

    def update_repo_webhook(self, repo: str, hook_id: int, events: list[str]) -> dict:
        """Update the subscribed events on an existing repository webhook.

        Used to bring older hooks (registered before push/pull_request support)
        onto the current event list without recreating them.

        Args:
            repo: Owner/repo string.
            hook_id: Numeric webhook id.
            events: Complete list of GitHub event names to subscribe to.

        Returns:
            Updated webhook dict.
        """
        return self._request(
            "PATCH",
            f"/repos/{repo}/hooks/{hook_id}",
            json_data={"events": events, "active": True},
        )

    def ensure_label(self, repo: str, name: str, color: str) -> bool:
        """Create a label if it does not exist.

        Args:
            repo: Owner/repo string.
            name: Label name.
            color: Six-digit hex color without leading #.

        Returns:
            True if label was created, False if it already existed.
        """
        try:
            self._request("GET", f"/repos/{repo}/labels/{name}")
            return False  # already exists
        except GitHubAPIError as exc:
            if exc.status_code != 404:
                raise
        self._request(
            "POST",
            f"/repos/{repo}/labels",
            json_data={"name": name, "color": color},
        )
        return True
