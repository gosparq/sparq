# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""IntegrationConnection model — workspace-scoped external app connection.

One row per (workspace, provider). Stores the GitHub App installation ID,
cached access token, and connection metadata. All tokens are encrypted via
TokenManager before storage.

Classes:
    IntegrationConnection: Represents one active or inactive integration link.
"""

from datetime import datetime
from typing import Optional


from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.workspace import WorkspaceMixin
from system.db.raise_on_lazy import LAZY


@ModelRegistry.register
class IntegrationConnection(db.Model, WorkspaceMixin):
    """Workspace-scoped connection to an external provider (e.g. GitHub App).

    Attributes:
        provider: Provider slug, e.g. "github".
        installation_id: GitHub App installation ID (provider-specific).
        external_repo: Connected resource slug, e.g. "owner/repo".
        cached_token: Short-lived access token, encrypted via TokenManager.
        token_expires_at: Expiry time for cached_token.
        status: "connected", "disconnected", or "error".
        error_message: Last error detail when status is "error".
        connected_by_id: WorkspaceUser who initiated the connection.
        connected_at: When the connection was established.
        last_synced_at: Last successful sync timestamp.
        extra_data: Provider-specific non-secret metadata (JSON).
        auth_type: Authentication strategy — ``'app'`` for GitHub App, ``'pat'`` for Personal Access Token.
    cached_orphan_ids: Cached list of orphaned external issue dicts (JSON).
    """

    __tablename__ = "integration_connection"

    id = db.Column(db.Integer, primary_key=True)

    provider = db.Column(db.String(50), nullable=False)
    # 'app' = GitHub App installation; 'pat' = Personal Access Token.
    auth_type = db.Column(db.String(20), nullable=False, default="app")
    installation_id = db.Column(db.String(100), nullable=True)
    external_repo = db.Column(db.String(255), nullable=True)

    # Short-lived access token (encrypted); refresh before use.
    # For PAT auth this stores the encrypted PAT itself (no expiry).
    cached_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)

    status = db.Column(db.String(20), nullable=False, default="disconnected")
    error_message = db.Column(db.String(255), nullable=True)

    connected_by_id = db.Column(
        db.Integer,
        db.ForeignKey("workspace_user.id", ondelete="SET NULL"),
        nullable=True,
    )
    connected_at = db.Column(db.DateTime, nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=True)

    # Non-secret provider metadata (app_id, app_slug, etc.)
    extra_data = db.Column(db.JSON, nullable=True)

    # Cached orphan issue list for UC-7; refreshed by background task.
    cached_orphan_ids = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    connected_by = db.relationship(
        "WorkspaceUser",
        foreign_keys=[connected_by_id],
        lazy=LAZY,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "workspace_id", "provider", name="uq_integration_connection_ts_provider"
        ),
        db.Index("ix_integration_connection_provider", "provider", "status"),
    )

    # ── Class methods ─────────────────────────────────────────────────────────

    @classmethod
    def get_active(cls, provider: str) -> Optional["IntegrationConnection"]:
        """Return the connected row for the current workspace, or None.

        Args:
            provider: Provider slug (e.g. "github").

        Returns:
            IntegrationConnection with status "connected", or None.
        """
        from sqlalchemy.orm import joinedload
        from modules.base.core.models.workspace_user import WorkspaceUser

        return (
            cls.scoped()
            .options(joinedload(cls.connected_by).joinedload(WorkspaceUser.user))
            .filter_by(provider=provider, status="connected")
            .first()
        )

    @classmethod
    def get_or_create(cls, provider: str) -> "IntegrationConnection":
        """Fetch the connection row for the current workspace, creating if absent.

        Args:
            provider: Provider slug.

        Returns:
            Existing or freshly-created IntegrationConnection.
        """
        conn = cls.scoped().filter_by(provider=provider).first()
        if conn:
            return conn
        conn = cls(provider=provider, status="disconnected")
        db.session.add(conn)
        db.session.commit()
        return conn

    @classmethod
    def get_by_installation_id(cls, installation_id: str) -> Optional["IntegrationConnection"]:
        """Look up a connection by GitHub App installation ID (no workspace filter).

        Used by the global webhook endpoint before workspace context is known.

        Args:
            installation_id: GitHub App installation ID string.

        Returns:
            IntegrationConnection or None.
        """
        return cls.query.filter_by(
            installation_id=str(installation_id), status="connected"
        ).first()

    @classmethod
    def get_by_repo(cls, repo: str) -> Optional["IntegrationConnection"]:
        """Look up a connected row by external_repo (no workspace filter).

        Used as a webhook fallback for PAT connections that carry no
        installation_id.  When two workspaces share the same repo via PAT,
        only the first connected row is returned — this is a known limitation.

        Args:
            repo: Full repository name, e.g. ``"owner/repo"``.

        Returns:
            IntegrationConnection with status ``'connected'``, or None.
        """
        return cls.query.filter_by(
            external_repo=repo, provider="github", status="connected"
        ).first()

    def is_token_expired(self, buffer_minutes: int = 5) -> bool:
        """Check whether the cached token is expired or will expire soon.

        Args:
            buffer_minutes: Treat as expired if within this many minutes.

        Returns:
            True if token needs refresh.
        """
        if not self.token_expires_at:
            return True
        from datetime import timezone, timedelta
        now = datetime.now(timezone.utc)
        expires = self.token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return now + timedelta(minutes=buffer_minutes) >= expires

    def refresh_orphans(self, client: "object") -> None:
        """Fetch open issues from GitHub and cache those without an IntegrationRef.

        Called on GET /settings/github page load (background) and on
        issues.opened webhook events to keep the orphan list current.
        Caches up to 200 issues; fetches two pages of 100.

        Args:
            client: Authenticated GitHubClient instance.
        """
        from datetime import timezone

        from modules.integrations.models.integration_ref import IntegrationRef

        if not self.external_repo:
            return

        try:
            all_issues: list[dict] = []
            for page in (1, 2):
                batch = client._request(
                    "GET",
                    f"/repos/{self.external_repo}/issues",
                    params={"state": "open", "per_page": 100, "page": page},
                )
                if not isinstance(batch, list):
                    break
                all_issues.extend(batch)
                if len(batch) < 100:
                    break
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("refresh_orphans: GitHub fetch failed: %s", exc)
            return

        linked_ids = IntegrationRef.query.filter_by(
            workspace_id=self.workspace_id, provider="github"
        ).with_entities(IntegrationRef.external_id).all()
        linked_set = {r.external_id for r in linked_ids}

        orphans = []
        for issue in all_issues:
            if str(issue.get("number", "")) not in linked_set:
                assignee = issue.get("assignee") or {}
                labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
                orphans.append({
                    "number": issue.get("number"),
                    "title": issue.get("title", ""),
                    "created_at": issue.get("created_at", ""),
                    "assignee_login": assignee.get("login", ""),
                    "labels": labels,
                    "html_url": issue.get("html_url", ""),
                })

        self.cached_orphan_ids = orphans
        self.last_synced_at = datetime.now(timezone.utc)
        db.session.commit()

    def add_orphan_from_issue(self, issue: dict) -> None:
        """Prepend a newly-opened issue to the orphan cache from webhook data.

        Called on ``issues.opened`` so the orphan list reflects the new issue
        immediately, using the issue object delivered in the webhook payload.
        This avoids re-querying GitHub's eventually-consistent issue-list API,
        which can omit the just-created issue and overwrite the cache with a
        stale or empty result.

        No-op when the issue is already linked to a sparQ object in this
        workspace, or already present in the cache.

        Args:
            issue: The ``issue`` object from the ``issues.opened`` payload.
        """
        from modules.integrations.models.integration_ref import IntegrationRef

        number = issue.get("number")
        if number is None:
            return
        number_str = str(number)

        # Skip if this issue is already linked to a sparQ object.
        if IntegrationRef.query.filter_by(
            workspace_id=self.workspace_id, provider="github", external_id=number_str
        ).first():
            return

        orphans = list(self.cached_orphan_ids or [])
        if any(str(o.get("number", "")) == number_str for o in orphans):
            return

        assignee = issue.get("assignee") or {}
        labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        orphans.insert(0, {
            "number": number,
            "title": issue.get("title", ""),
            "created_at": issue.get("created_at", ""),
            "assignee_login": assignee.get("login", ""),
            "labels": labels,
            "html_url": issue.get("html_url", ""),
        })
        self.cached_orphan_ids = orphans
        db.session.commit()

    def finalize_connection(
        self,
        installation_id: str,
        repo: str,
        member_id: Optional[int],
    ) -> None:
        """Activate a GitHub App connection after the user selects a repo.

        Explicitly sets ``auth_type='app'`` so that a re-connect after a prior
        PAT connection does not silently inherit the wrong auth strategy.

        Args:
            installation_id: GitHub App installation ID.
            repo: Owner/repo string (e.g. "acme/my-repo").
            member_id: WorkspaceUser.id who completed the connection.
        """
        from datetime import timezone

        self.auth_type = "app"
        self.installation_id = installation_id
        self.external_repo = repo
        self.status = "connected"
        self.connected_by_id = member_id
        self.connected_at = datetime.now(timezone.utc)
        self.cached_token = None
        self.token_expires_at = None
        self.error_message = None
        db.session.commit()

    def finalize_pat_connection(
        self,
        pat_token: str,
        repo: str,
        member_id: Optional[int],
    ) -> None:
        """Activate a Personal Access Token connection.

        The PAT is encrypted via TokenManager before storage — never stored in
        plain text.  ``token_expires_at`` is left ``None`` because PATs do not
        have a server-controlled expiry; ``_resolve_token()`` dispatches on
        ``auth_type`` before checking expiry so the null value is never reached
        for PAT connections.

        Args:
            pat_token: Plain-text GitHub classic PAT (``ghp_...``).
            repo: Owner/repo string validated before calling this method.
            member_id: WorkspaceUser.id who initiated the connection.
        """
        from datetime import timezone
        from system.oauth.token_manager import TokenManager

        self.auth_type = "pat"
        self.installation_id = None
        self.external_repo = repo
        self.cached_token = TokenManager.encrypt(pat_token)
        self.token_expires_at = None
        self.status = "connected"
        self.connected_by_id = member_id
        self.connected_at = datetime.now(timezone.utc)
        self.error_message = None
        db.session.commit()

    def get_webhook_id(self) -> Optional[int]:
        """Return the registered repo webhook id, or None.

        Stored in ``extra_data`` (non-secret provider metadata) so no schema
        migration is required. Only set for PAT connections, which register
        their own repo webhook; App connections receive events through the
        GitHub App and leave this unset.

        Returns:
            The numeric webhook id, or None if no webhook is registered.
        """
        data = self.extra_data or {}
        val = data.get("webhook_id")
        return int(val) if val is not None else None

    def set_webhook_id(
        self,
        hook_id: Optional[int],
        events: Optional[list[str]] = None,
    ) -> None:
        """Persist (or clear) the registered repo webhook id in ``extra_data``.

        Passing ``hook_id=None`` removes both the id and the cached event list.
        The JSON column is reassigned (not mutated in place) so SQLAlchemy
        detects the change.

        Args:
            hook_id: Numeric webhook id, or None to clear.
            events: Subscribed event names to cache alongside the id.
        """
        data = dict(self.extra_data or {})
        if hook_id is None:
            data.pop("webhook_id", None)
            data.pop("webhook_events", None)
        else:
            data["webhook_id"] = int(hook_id)
            if events is not None:
                data["webhook_events"] = list(events)
        self.extra_data = data
        db.session.commit()

    def mark_error(self, message: str) -> None:
        """Set status to error with a message and commit.

        Args:
            message: Human-readable error description.
        """
        self.status = "error"
        self.error_message = message[:255]
        db.session.commit()

    def update_repo(self, repo: str) -> None:
        """Switch the connected repository without touching auth credentials.

        Args:
            repo: New owner/repo string (e.g. "acme/new-repo"). Caller must
                  validate access before calling this method.
        """
        self.external_repo = repo
        db.session.commit()

    def __repr__(self) -> str:
        return f"<IntegrationConnection {self.provider} ts={self.workspace_id} {self.status}>"
