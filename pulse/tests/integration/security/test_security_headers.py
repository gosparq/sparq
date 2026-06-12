# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Security Headers Integration Tests
#
# Tests for security headers (P0 Stage 3) and nonce-based CSP (P0 Stage 7).
# (system/startup/request_hooks.py → add_security_headers, generate_csp_nonce).
# -----------------------------------------------------------------------------

import os

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def prod_app():
    """Flask app configured as production (DEBUG_MODE=False) for header tests."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-headers"
    os.environ["FLASK_DEBUG"] = "False"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture(scope="function")
def prod_db(prod_app):
    """Provide a clean database for each test."""
    from system.db.database import db
    from sqlalchemy import text

    with prod_app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        with db.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys = OFF"))
            for table in reversed(db.metadata.sorted_tables):
                conn.execute(table.delete())
            conn.execute(text("PRAGMA foreign_keys = ON"))
            conn.commit()


@pytest.fixture(scope="function")
def client(prod_app):
    """Flask test client."""
    return prod_app.test_client()


# ---------------------------------------------------------------------------
# 1. Security Headers Present
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSecurityHeadersPresent:
    """Verify all security headers are present on responses."""

    def test_x_frame_options(self, client, prod_app, prod_db):
        """X-Frame-Options should be SAMEORIGIN."""
        with prod_app.app_context():
            resp = client.get("/login")
            assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"

    def test_x_content_type_options(self, client, prod_app, prod_db):
        """X-Content-Type-Options should be nosniff."""
        with prod_app.app_context():
            resp = client.get("/login")
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self, client, prod_app, prod_db):
        """Referrer-Policy should be strict-origin-when-cross-origin."""
        with prod_app.app_context():
            resp = client.get("/login")
            assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client, prod_app, prod_db):
        """Permissions-Policy should disable camera, allow microphone/geolocation for self."""
        with prod_app.app_context():
            resp = client.get("/login")
            policy = resp.headers.get("Permissions-Policy")
            assert "camera=()" in policy
            assert "microphone=(self)" in policy
            assert "geolocation=(self)" in policy

    def test_content_security_policy(self, client, prod_app, prod_db):
        """Content-Security-Policy header should be present."""
        with prod_app.app_context():
            resp = client.get("/login")
            assert resp.headers.get("Content-Security-Policy") is not None

    def test_hsts_in_production(self, client, prod_app, prod_db):
        """HSTS should be present when _DEBUG_MODE is False."""
        with prod_app.app_context():
            resp = client.get("/login")
            hsts = resp.headers.get("Strict-Transport-Security")
            assert hsts is not None
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts


# ---------------------------------------------------------------------------
# 2. HSTS Production-Only Behavior
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHSTSProductionOnly:
    """HSTS should only appear in production mode."""

    def test_hsts_absent_in_debug_mode(self, prod_app):
        """HSTS header should not be set when _DEBUG_MODE is True."""
        original = prod_app.config.get("_DEBUG_MODE")
        try:
            prod_app.config["_DEBUG_MODE"] = True
            with prod_app.app_context():
                client = prod_app.test_client()
                resp = client.get("/login")
                assert resp.headers.get("Strict-Transport-Security") is None
        finally:
            prod_app.config["_DEBUG_MODE"] = original

    def test_hsts_present_in_production_mode(self, client, prod_app, prod_db):
        """HSTS header should be set when _DEBUG_MODE is False."""
        with prod_app.app_context():
            assert prod_app.config.get("_DEBUG_MODE") is False
            resp = client.get("/login")
            assert resp.headers.get("Strict-Transport-Security") is not None


# ---------------------------------------------------------------------------
# 3. CSP Directives
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSPDirectives:
    """Verify Content-Security-Policy includes expected directives."""

    def _get_csp(self, client, prod_app, prod_db):
        with prod_app.app_context():
            resp = client.get("/login")
            return resp.headers.get("Content-Security-Policy", "")

    def test_default_src_self(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "default-src 'self'" in csp

    def test_script_src_includes_cdns(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "script-src" in csp
        assert "https://unpkg.com" in csp
        assert "https://cdn.jsdelivr.net" in csp

    def test_script_src_has_unsafe_inline(self, client, prod_app, prod_db):
        """script-src should contain unsafe-inline (nonce removed for Alpine.js compatibility)."""
        csp = self._get_csp(client, prod_app, prod_db)
        script_src = csp.split("script-src")[1].split(";")[0]
        assert "'unsafe-inline'" in script_src

    def test_script_src_no_nonce(self, client, prod_app, prod_db):
        """script-src should NOT contain a nonce (removed for Alpine.js event handler compat)."""
        csp = self._get_csp(client, prod_app, prod_db)
        script_src = csp.split("script-src")[1].split(";")[0]
        assert "'nonce-" not in script_src

    def test_script_src_has_unsafe_eval(self, client, prod_app, prod_db):
        """script-src should still allow unsafe-eval for Alpine.js compatibility."""
        csp = self._get_csp(client, prod_app, prod_db)
        script_src = csp.split("script-src")[1].split(";")[0]
        assert "'unsafe-eval'" in script_src

    def test_style_src_includes_cdns(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "style-src" in csp
        assert "https://cdn.jsdelivr.net" in csp
        assert "https://cdnjs.cloudflare.com" in csp

    def test_font_src(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "font-src 'self' https://cdnjs.cloudflare.com" in csp

    def test_img_src_allows_data_and_https(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "img-src 'self' data: https:" in csp

    def test_connect_src_allows_websockets(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "connect-src 'self' wss: ws: https://cdn.jsdelivr.net" in csp

    def test_frame_ancestors_self(self, client, prod_app, prod_db):
        csp = self._get_csp(client, prod_app, prod_db)
        assert "frame-ancestors 'self'" in csp


# ---------------------------------------------------------------------------
# 4. Headers on All Response Types
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHeadersOnAllResponses:
    """Security headers should appear on all response types, not just 200s."""

    def test_headers_on_404(self, client, prod_app, prod_db):
        """Security headers should be present on 404 responses."""
        with prod_app.app_context():
            resp = client.get("/nonexistent-page-12345")
            assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("Content-Security-Policy") is not None

    def test_headers_on_redirect(self, client, prod_app, prod_db):
        """Security headers should be present on redirect responses."""
        with prod_app.app_context():
            resp = client.get("/dashboard")  # Should redirect to login
            assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ---------------------------------------------------------------------------
# 5. CSP Inline Policy (nonces removed for Alpine.js compatibility)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSPInlinePolicy:
    """Verify CSP inline policy (nonces removed in favor of unsafe-inline for Alpine.js)."""

    def test_csp_does_not_contain_nonce(self, client, prod_app, prod_db):
        """CSP header should NOT contain a nonce (removed for Alpine.js compat)."""
        with prod_app.app_context():
            resp = client.get("/login")
            csp = resp.headers.get("Content-Security-Policy", "")
            assert "'nonce-" not in csp

    def test_csp_consistent_across_requests(self, client, prod_app, prod_db):
        """CSP policy should be consistent across requests (no per-request nonce)."""
        with prod_app.app_context():
            resp1 = client.get("/login")
            resp2 = client.get("/login")
            csp1 = resp1.headers.get("Content-Security-Policy", "")
            csp2 = resp2.headers.get("Content-Security-Policy", "")
            assert csp1 == csp2

    def test_csp_on_404(self, client, prod_app, prod_db):
        """CSP should be present even on error responses."""
        with prod_app.app_context():
            resp = client.get("/nonexistent-page-12345")
            csp = resp.headers.get("Content-Security-Policy", "")
            assert "script-src" in csp
            assert "'unsafe-inline'" in csp

    def test_style_src_still_allows_inline(self, client, prod_app, prod_db):
        """style-src should still allow unsafe-inline (inline styles are low risk)."""
        with prod_app.app_context():
            resp = client.get("/login")
            csp = resp.headers.get("Content-Security-Policy", "")
            style_src = csp.split("style-src")[1].split(";")[0]
            assert "'unsafe-inline'" in style_src
