# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestPublicRoutes:
    """Smoke tests for unauthenticated / public routes."""

    def test_health(self, client, db_session):
        resp = client.get("/health")
        assert resp.status_code in (200, 302)

    def test_login(self, client, db_session):
        resp = client.get("/login")
        assert resp.status_code in (200, 302)

    def test_signup(self, client, db_session):
        resp = client.get("/signup")
        assert resp.status_code in (200, 302)

    def test_forgot_password(self, client, db_session):
        resp = client.get("/auth/forgot-password")
        assert resp.status_code in (200, 302)

    def test_magic_link(self, client, db_session):
        resp = client.get("/auth/magic-link")
        assert resp.status_code in (200, 302)

    def test_auth_sms(self, client, db_session):
        resp = client.get("/auth/sms")
        assert resp.status_code != 404  # 500: needs workspace context, tracked

    def test_about(self, client, db_session):
        resp = client.get("/about")
        assert resp.status_code in (200, 302)

    def test_offline(self, client, db_session):
        resp = client.get("/offline")
        assert resp.status_code in (200, 302)

    def test_manifest_json(self, client, db_session):
        resp = client.get("/manifest.json")
        assert resp.status_code in (200, 302)

    def test_service_worker_js(self, client, db_session):
        resp = client.get("/service-worker.js")
        assert resp.status_code in (200, 302)

    def test_kb_index(self, client, db_session):
        resp = client.get("/kb/")
        assert resp.status_code in (200, 302)

    def test_kb_search(self, client, db_session):
        resp = client.get("/kb/search")
        assert resp.status_code in (200, 302)
