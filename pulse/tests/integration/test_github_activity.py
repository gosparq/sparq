# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
"""Tests for GitHub commit/PR activity → "Current" status feed.

Covers the token-less identity mapping (admin/self-serve), the plain-text
event summarizers, and webhook dispatch (push/pull_request → mapped member's
Current status; unmapped → skipped). No network — GitHub data comes from
synthetic webhook payloads.
"""

import uuid

import pytest
from flask import g


def _set_ctx(sw):
    g.organization_id = sw["organization"].id
    g.workspace_id = sw["workspace"].id


def _pat_connection():
    from modules.integrations.models.integration_connection import IntegrationConnection
    from system.db.database import db

    conn = IntegrationConnection.get_or_create("github")
    conn.auth_type = "pat"
    conn.external_repo = "acme/repo"
    conn.status = "connected"
    db.session.commit()
    return conn


def _second_user():
    from modules.base.core.models.user import User

    return User.create(
        email=f"second-{uuid.uuid4().hex[:8]}@test.com",
        password="testpass123", first_name="Second", last_name="User", is_admin=False,
    )


@pytest.mark.integration
class TestGithubIdentityMapping:
    """OAuthConnection token-less GitHub mapping."""

    def test_set_creates_tokenless_row(self, app_with_sample_data, seeded_workspace):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            row = OAuthConnection.set_github_mapping("12345", seeded_workspace["user"].id)
            assert row.provider == "github"
            assert row.provider_user_id == "12345"
            assert row.user_id == seeded_workspace["user"].id
            assert row.access_token is None

    def test_self_override_reassigns(self, app_with_sample_data, seeded_workspace):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            user_a = seeded_workspace["user"].id
            user_b = _second_user().id
            OAuthConnection.set_github_mapping("12345", user_a)
            OAuthConnection.set_github_mapping("12345", user_b)   # B claims it

            rows = OAuthConnection.query.filter_by(provider="github", provider_user_id="12345").all()
            assert len(rows) == 1
            assert rows[0].user_id == user_b
            assert OAuthConnection.query.filter_by(provider="github", user_id=user_a).first() is None

    def test_resolver_returns_member(self, app_with_sample_data, seeded_workspace):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            OAuthConnection.set_github_mapping("12345", seeded_workspace["user"].id)
            member = OAuthConnection.get_member_for_github_id("12345")
            assert member is not None
            assert member.id == seeded_workspace["membership"].id

    def test_unmapped_resolves_none(self, app_with_sample_data, seeded_workspace):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            assert OAuthConnection.get_member_for_github_id("99999") is None

    def test_clear_removes(self, app_with_sample_data, seeded_workspace):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            OAuthConnection.set_github_mapping("12345", seeded_workspace["user"].id)
            OAuthConnection.clear_github_mapping("12345")
            assert OAuthConnection.get_member_for_github_id("12345") is None


@pytest.mark.integration
class TestActivitySummarizers:
    """Plain-text one-liners for the Current feed."""

    def test_push_summary(self):
        from modules.integrations.github.activity import summarize_push
        payload = {
            "ref": "refs/heads/main",
            "commits": [{"message": "a"}, {"message": "fix login bug\n\ndetails"}],
            "head_commit": {"message": "fix login bug\n\ndetails"},
        }
        assert summarize_push(payload) == "Pushed 2 commits to main: fix login bug"

    def test_push_empty_returns_none(self):
        from modules.integrations.github.activity import summarize_push
        assert summarize_push({"ref": "refs/heads/main", "commits": []}) is None

    def test_push_pr_merge_commit_skipped(self):
        from modules.integrations.github.activity import summarize_push
        # A PR merge fires both pull_request (merged) and this push of the merge
        # commit — the push must be suppressed to avoid double-posting.
        payload = {
            "ref": "refs/heads/main",
            "commits": [{"message": "Add feed"}, {"message": "Merge pull request #6 from acme/test-pr"}],
            "head_commit": {"message": "Merge pull request #6 from acme/test-pr\n\nAdd feed"},
        }
        assert summarize_push(payload) is None

    def test_pr_opened(self):
        from modules.integrations.github.activity import summarize_pull_request
        assert summarize_pull_request(
            {"action": "opened", "pull_request": {"number": 7, "title": "Add feed"}}
        ) == "Opened PR #7: Add feed"

    def test_pr_merged(self):
        from modules.integrations.github.activity import summarize_pull_request
        assert summarize_pull_request(
            {"action": "closed", "pull_request": {"number": 7, "title": "Add feed", "merged": True}}
        ) == "Merged PR #7: Add feed"

    def test_pr_synchronize_skipped(self):
        from modules.integrations.github.activity import summarize_pull_request
        assert summarize_pull_request(
            {"action": "synchronize", "pull_request": {"number": 7, "title": "x"}}
        ) is None


@pytest.mark.integration
class TestActivityDispatch:
    """handle_webhook(push/pull_request) → mapped member's Current status."""

    def _capture(self, monkeypatch):
        from modules.integrations.github.provider import GitHubProvider
        from modules.base.updates.models.post import UpdatePost

        calls: list = []
        monkeypatch.setattr(
            UpdatePost, "create_current_activity",
            classmethod(lambda cls, member_id, text: calls.append((member_id, text))),
        )
        return GitHubProvider(), calls

    def test_push_posts_for_mapped_member(self, app_with_sample_data, seeded_workspace, monkeypatch):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _pat_connection()
            OAuthConnection.set_github_mapping("4242", seeded_workspace["user"].id)
            provider, calls = self._capture(monkeypatch)

            provider.handle_webhook(conn, "push", {
                "ref": "refs/heads/main",
                "commits": [{"message": "do thing"}],
                "head_commit": {"message": "do thing"},
                "sender": {"id": 4242, "login": "octocat"},
            })

            assert len(calls) == 1
            assert calls[0][0] == seeded_workspace["membership"].id
            assert "Pushed 1 commit to main" in calls[0][1]

    def test_push_unmapped_skipped(self, app_with_sample_data, seeded_workspace, monkeypatch):
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _pat_connection()
            provider, calls = self._capture(monkeypatch)

            provider.handle_webhook(conn, "push", {
                "ref": "refs/heads/main", "commits": [{"message": "x"}],
                "head_commit": {"message": "x"}, "sender": {"id": 9999, "login": "ghost"},
            })

            assert calls == []

    def test_pull_request_opened_posts(self, app_with_sample_data, seeded_workspace, monkeypatch):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _pat_connection()
            OAuthConnection.set_github_mapping("4242", seeded_workspace["user"].id)
            provider, calls = self._capture(monkeypatch)

            provider.handle_webhook(conn, "pull_request", {
                "action": "opened",
                "pull_request": {"number": 5, "title": "Feed"},
                "sender": {"id": 4242, "login": "octocat"},
            })

            assert len(calls) == 1
            assert "Opened PR #5" in calls[0][1]

    def test_pull_request_synchronize_skipped(self, app_with_sample_data, seeded_workspace, monkeypatch):
        from modules.base.core.models.oauth_connection import OAuthConnection
        with app_with_sample_data.app_context():
            _set_ctx(seeded_workspace)
            conn = _pat_connection()
            OAuthConnection.set_github_mapping("4242", seeded_workspace["user"].id)
            provider, calls = self._capture(monkeypatch)

            provider.handle_webhook(conn, "pull_request", {
                "action": "synchronize",
                "pull_request": {"number": 5, "title": "Feed"},
                "sender": {"id": 4242, "login": "octocat"},
            })

            assert calls == []
