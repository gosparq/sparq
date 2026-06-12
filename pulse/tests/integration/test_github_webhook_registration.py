# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
"""Tests for GitHub PAT webhook auto-registration lifecycle.

Covers GitHubProvider.register_webhook / deregister_webhook (idempotency,
permission failure, cleanup) and the fail-closed _verify_signature hardening.
The GitHub API is faked — no network calls.
"""

import hashlib
import hmac

import pytest
from flask import g

CALLBACK_URL = "https://example.test/integrations/webhooks/github"


def _set_ctx(seeded_workspace):
    """Restore workspace context inside a fresh app_context block."""
    g.organization_id = seeded_workspace["organization"].id
    g.workspace_id = seeded_workspace["workspace"].id


def _make_pat_connection():
    """Create a connected PAT IntegrationConnection for the current workspace."""
    from modules.integrations.models.integration_connection import IntegrationConnection
    from system.db.database import db

    conn = IntegrationConnection.get_or_create("github")
    conn.auth_type = "pat"
    conn.external_repo = "acme/repo"
    conn.status = "connected"
    db.session.commit()
    return conn


class _FakeClient:
    """Stand-in for GitHubClient capturing webhook API calls."""

    list_return: list = []
    list_exc: Exception | None = None
    create_id: int = 0
    last_created: tuple | None = None
    last_deleted: tuple | None = None
    last_updated: tuple | None = None

    def __init__(self, connection):
        self.connection = connection

    def list_repo_webhooks(self, repo):
        if _FakeClient.list_exc is not None:
            raise _FakeClient.list_exc
        return _FakeClient.list_return

    def create_repo_webhook(self, repo, callback_url, secret, events):
        _FakeClient.last_created = (repo, callback_url, secret, tuple(events))
        return {"id": _FakeClient.create_id}

    def delete_repo_webhook(self, repo, hook_id):
        _FakeClient.last_deleted = (repo, hook_id)

    def update_repo_webhook(self, repo, hook_id, events):
        _FakeClient.last_updated = (repo, hook_id, tuple(events))
        return {"id": hook_id}


@pytest.fixture
def patched_provider(monkeypatch):
    """Patch GitHubClient with the fake and pin the callback URL."""
    monkeypatch.setattr(
        "modules.integrations.github.client.GitHubClient", _FakeClient
    )
    monkeypatch.setenv("GITHUB_WEBHOOK_BASE_URL", "https://example.test")
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cr3t")
    # Reset shared fake state between tests.
    _FakeClient.list_return = []
    _FakeClient.list_exc = None
    _FakeClient.create_id = 0
    _FakeClient.last_created = None
    _FakeClient.last_deleted = None
    _FakeClient.last_updated = None
    from modules.integrations.github.provider import GitHubProvider

    return GitHubProvider()


@pytest.mark.integration
class TestRegisterWebhook:
    """GitHubProvider.register_webhook."""

    def test_creates_and_stores_id(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            _FakeClient.create_id = 123

            status = patched_provider.register_webhook(conn)

            assert status == "registered"
            assert conn.get_webhook_id() == 123
            # Created against the right repo, URL, and event set.
            repo, url, secret, events = _FakeClient.last_created
            assert repo == "acme/repo"
            assert url == CALLBACK_URL
            assert events == ("issues", "push", "pull_request")

    def test_reuses_existing_hook(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            _FakeClient.list_return = [{
                "id": 999, "config": {"url": CALLBACK_URL},
                "events": ["issues", "push", "pull_request"],
            }]

            status = patched_provider.register_webhook(conn)

            assert status == "reused"
            assert conn.get_webhook_id() == 999
            assert _FakeClient.last_created is None   # no duplicate created
            assert _FakeClient.last_updated is None   # events already current

    def test_reuse_updates_drifted_events(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            # An older hook subscribed to issues only.
            _FakeClient.list_return = [{
                "id": 777, "config": {"url": CALLBACK_URL}, "events": ["issues"],
            }]

            status = patched_provider.register_webhook(conn)

            assert status == "reused"
            assert _FakeClient.last_updated == (
                "acme/repo", 777, ("issues", "push", "pull_request"),
            )

    def test_no_permission_keeps_connection(self, app_with_sample_data, seeded_workspace, patched_provider):
        from modules.integrations.github.client import GitHubAPIError

        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            _FakeClient.list_exc = GitHubAPIError("not found", 404)

            status = patched_provider.register_webhook(conn)

            assert status == "no_permission"
            assert conn.get_webhook_id() is None
            assert conn.status == "connected"  # still usable for manual sync

    def test_generic_error(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            _FakeClient.list_exc = RuntimeError("boom")

            assert patched_provider.register_webhook(conn) == "error"
            assert conn.get_webhook_id() is None

    def test_no_repo_errors(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            conn.external_repo = None

            assert patched_provider.register_webhook(conn) == "error"


@pytest.mark.integration
class TestDeregisterWebhook:
    """GitHubProvider.deregister_webhook."""

    def test_deletes_and_clears(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            conn.set_webhook_id(555)

            patched_provider.deregister_webhook(conn)

            assert _FakeClient.last_deleted == ("acme/repo", 555)
            assert conn.get_webhook_id() is None

    def test_noop_without_id(self, app_with_sample_data, seeded_workspace, patched_provider):
        with app_with_sample_data.test_request_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()

            patched_provider.deregister_webhook(conn)

            assert _FakeClient.last_deleted is None


@pytest.mark.integration
class TestVerifySignature:
    """webhook._verify_signature fail-closed behaviour."""

    def test_rejects_unsigned_in_production(self, monkeypatch):
        from modules.integrations.github import webhook

        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr("system.version.is_production", lambda: True)

        assert webhook._verify_signature(b"{}", None) is False

    def test_accepts_unsigned_in_dev(self, monkeypatch):
        from modules.integrations.github import webhook

        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr("system.version.is_production", lambda: False)

        assert webhook._verify_signature(b"{}", None) is True

    def test_valid_signature_passes(self, monkeypatch):
        from modules.integrations.github import webhook

        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cr3t")
        body = b'{"action":"closed"}'
        sig = "sha256=" + hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()

        assert webhook._verify_signature(body, sig) is True

    def test_bad_signature_fails(self, monkeypatch):
        from modules.integrations.github import webhook

        monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "s3cr3t")

        assert webhook._verify_signature(b"{}", "sha256=deadbeef") is False


@pytest.mark.integration
class TestOrphanCache:
    """IntegrationConnection.add_orphan_from_issue — payload-based orphan cache."""

    def _issue(self, number=3, title="test 3"):
        return {"number": number, "title": title, "html_url": "https://x/3",
                "labels": [{"name": "bug"}], "assignee": {"login": "octocat"},
                "created_at": "2026-06-11T00:00:00Z"}

    def test_append_from_payload(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            conn.add_orphan_from_issue(self._issue())
            orphans = conn.cached_orphan_ids or []
            assert [o["number"] for o in orphans] == [3]
            assert orphans[0]["title"] == "test 3"
            assert orphans[0]["assignee_login"] == "octocat"

    def test_dedup(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            conn.add_orphan_from_issue(self._issue())
            conn.add_orphan_from_issue(self._issue())
            nums = [o["number"] for o in (conn.cached_orphan_ids or [])]
            assert nums.count(3) == 1

    def test_skip_when_already_linked(self, app_with_sample_data, seeded_workspace):
        from modules.integrations.models.integration_ref import IntegrationRef
        from system.db.database import db

        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _make_pat_connection()
            ref = IntegrationRef(
                provider="github", external_id="3", external_repo="acme/repo",
                object_type="task", object_id=999,
                workspace_id=seeded_workspace["workspace"].id,
                organization_id=seeded_workspace["organization"].id,
            )
            db.session.add(ref)
            db.session.commit()

            conn.add_orphan_from_issue(self._issue())

            assert (conn.cached_orphan_ids or []) == []


@pytest.mark.integration
class TestWebhookOrphanDispatch:
    """handle_webhook routes opened → append (payload), closed → async refresh."""

    def _run(self, seeded_workspace, monkeypatch, action):
        from modules.integrations.github.provider import GitHubProvider

        conn = _make_pat_connection()
        provider = GitHubProvider()
        calls = []
        monkeypatch.setattr(provider, "_add_orphan_from_payload",
                            lambda cid, issue: calls.append(("append", cid)))
        monkeypatch.setattr(provider, "_refresh_orphans_async",
                            lambda cid: calls.append(("refresh", cid)))
        provider.handle_webhook(
            conn, "issues",
            {"action": action, "issue": {"number": 5, "title": "t", "labels": []}},
        )
        return conn, calls

    def test_opened_appends_from_payload(self, app_with_sample_data, seeded_workspace, monkeypatch):
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn, calls = self._run(seeded_workspace, monkeypatch, "opened")
            assert ("append", conn.id) in calls
            assert not any(c[0] == "refresh" for c in calls)

    def test_closed_triggers_refresh(self, app_with_sample_data, seeded_workspace, monkeypatch):
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn, calls = self._run(seeded_workspace, monkeypatch, "closed")
            assert ("refresh", conn.id) in calls
            assert not any(c[0] == "append" for c in calls)
