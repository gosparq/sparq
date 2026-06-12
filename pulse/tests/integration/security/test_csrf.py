# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - CSRF Protection Integration Tests
#
# Tests for the CSRF middleware (system/middleware/csrf.py).
# Uses separate fixtures with CSRF enabled (the root conftest disables it).
# -----------------------------------------------------------------------------

import os
import re
import sys

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_csrf_token(html: str) -> str:
    """Extract CSRF token from meta tag or hidden input in response HTML."""
    match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    if match:
        return match.group(1)
    raise ValueError("No CSRF token found in HTML")


# ---------------------------------------------------------------------------
# Fixtures — CSRF-enabled app (does NOT set WTF_CSRF_ENABLED=False)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def csrf_app():
    """Flask app with CSRF protection enabled."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-csrf"
    os.environ["FLASK_DEBUG"] = "False"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    # Explicitly ensure CSRF is enabled (default, but be explicit)
    app.config["WTF_CSRF_ENABLED"] = True
    return app


@pytest.fixture(scope="function")
def csrf_db(csrf_app):
    """Provide a clean database for each CSRF test."""
    from system.db.database import db
    from sqlalchemy import text

    with csrf_app.app_context():
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
def csrf_client(csrf_app):
    """Flask test client with CSRF enabled."""
    return csrf_app.test_client()


@pytest.fixture(scope="function")
def csrf_test_user(csrf_app, csrf_db):
    """Create a test user for CSRF tests."""
    from modules.base.core.models.user import User

    with csrf_app.app_context():
        user = User.create(
            email="csrf-test@example.com",
            password="testpass123",
            first_name="CSRF",
            last_name="Test",
            is_admin=False,
        )
        yield user


@pytest.fixture(scope="function")
def csrf_authenticated_client(csrf_app, csrf_client, csrf_test_user):
    """Test client authenticated with CSRF enabled."""
    with csrf_client.session_transaction() as sess:
        sess["_user_id"] = str(csrf_test_user.id)
        sess["_fresh"] = True
    return csrf_client


# ---------------------------------------------------------------------------
# 1. Middleware Core — Token Rejection / Acceptance
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFMiddlewareCore:
    """Test that the middleware correctly rejects and accepts requests."""

    def test_post_without_token_returns_403(self, csrf_client, csrf_app, csrf_db):
        """POST with no CSRF token should be rejected."""
        with csrf_app.app_context():
            response = csrf_client.post(
                "/login",
                data={"email": "x@x.com", "password": "x"},
            )
            assert response.status_code == 403

    def test_post_with_wrong_token_returns_403(self, csrf_client, csrf_app, csrf_db):
        """POST with an incorrect CSRF token should be rejected."""
        with csrf_app.app_context():
            # GET first to establish session
            csrf_client.get("/login")
            response = csrf_client.post(
                "/login",
                data={
                    "email": "x@x.com",
                    "password": "x",
                    "csrf_token": "totally-wrong-token",
                },
            )
            assert response.status_code == 403

    def test_post_with_valid_form_token_accepted(self, csrf_client, csrf_app, csrf_db):
        """POST with correct csrf_token form field should pass CSRF check."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            token = extract_csrf_token(resp.data.decode())

            response = csrf_client.post(
                "/login",
                data={
                    "email": "nobody@example.com",
                    "password": "wrong",
                    "csrf_token": token,
                },
                follow_redirects=True,
            )
            # Should NOT be 403 — CSRF passed (login may fail, that's fine)
            assert response.status_code != 403

    def test_post_with_valid_header_token_accepted(self, csrf_client, csrf_app, csrf_db):
        """POST with correct X-CSRF-Token header should pass CSRF check."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            token = extract_csrf_token(resp.data.decode())

            response = csrf_client.post(
                "/login",
                data={"email": "nobody@example.com", "password": "wrong"},
                headers={"X-CSRF-Token": token},
                follow_redirects=True,
            )
            assert response.status_code != 403

    def test_get_requests_pass_without_token(self, csrf_client, csrf_app, csrf_db):
        """GET requests should never require a CSRF token."""
        with csrf_app.app_context():
            response = csrf_client.get("/login")
            assert response.status_code == 200

    def test_head_requests_pass_without_token(self, csrf_client, csrf_app, csrf_db):
        """HEAD requests should never require a CSRF token."""
        with csrf_app.app_context():
            response = csrf_client.head("/login")
            assert response.status_code in (200, 302)

    def test_options_requests_pass_without_token(self, csrf_client, csrf_app, csrf_db):
        """OPTIONS requests should never require a CSRF token."""
        with csrf_app.app_context():
            response = csrf_client.options("/login")
            assert response.status_code in (200, 204, 405)

    def test_token_consistent_within_session(self, csrf_client, csrf_app, csrf_db):
        """Same session should return the same CSRF token across requests."""
        with csrf_app.app_context():
            resp1 = csrf_client.get("/login")
            token1 = extract_csrf_token(resp1.data.decode())

            resp2 = csrf_client.get("/login")
            token2 = extract_csrf_token(resp2.data.decode())

            assert token1 == token2


# ---------------------------------------------------------------------------
# 2. Exempt Paths
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFExemptPaths:
    """Test that exempt paths work without a CSRF token."""

    def test_health_endpoint_exempt(self, csrf_client, csrf_app, csrf_db):
        """POST to /health should work without CSRF token."""
        with csrf_app.app_context():
            response = csrf_client.post("/health")
            # /health is GET-only, so it may 405 — but NOT 403
            assert response.status_code != 403

    def test_webhook_api_exempt(self, csrf_client, csrf_app, csrf_db):
        """POST to /api/webhooks/* should work without CSRF token."""
        with csrf_app.app_context():
            response = csrf_client.post(
                "/api/webhooks/fake-token-12345",
                json={"content": "test message"},
            )
            # May 404 (no such webhook) but NOT 403
            assert response.status_code != 403

    def test_auth_callback_exempt(self, csrf_client, csrf_app, csrf_db):
        """POST to /auth/* should work without CSRF token (OAuth callbacks)."""
        with csrf_app.app_context():
            response = csrf_client.post("/auth/google/callback")
            # May 400/404 (no OAuth state) but NOT 403
            assert response.status_code != 403


# ---------------------------------------------------------------------------
# 3. Form Submissions
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFFormSubmissions:
    """Test CSRF with real form submissions."""

    def test_login_with_csrf_succeeds(self, csrf_client, csrf_app, csrf_db, csrf_test_user):
        """Login form with valid CSRF token should authenticate."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            token = extract_csrf_token(resp.data.decode())

            response = csrf_client.post(
                "/login",
                data={
                    "email": "csrf-test@example.com",
                    "password": "testpass123",
                    "csrf_token": token,
                },
                follow_redirects=False,
            )
            # Successful login redirects
            assert response.status_code == 302

    def test_login_without_csrf_rejected(self, csrf_client, csrf_app, csrf_db, csrf_test_user):
        """Login form without CSRF token should be rejected."""
        with csrf_app.app_context():
            response = csrf_client.post(
                "/login",
                data={
                    "email": "csrf-test@example.com",
                    "password": "testpass123",
                },
            )
            assert response.status_code == 403

    def test_authenticated_post_with_csrf(self, csrf_authenticated_client, csrf_app, csrf_db):
        """POST to a protected endpoint with CSRF token should work."""
        import secrets

        with csrf_app.app_context():
            # Set a CSRF token directly in the session
            token = secrets.token_urlsafe(32)
            with csrf_authenticated_client.session_transaction() as sess:
                sess["_csrf_token"] = token

            # POST with token — won't 403
            response = csrf_authenticated_client.post(
                "/login",
                data={"email": "x", "password": "x", "csrf_token": token},
                follow_redirects=True,
            )
            assert response.status_code != 403

    def test_authenticated_post_without_csrf(self, csrf_authenticated_client, csrf_app, csrf_db):
        """POST to a protected endpoint without CSRF token should be rejected."""
        with csrf_app.app_context():
            response = csrf_authenticated_client.post(
                "/login",
                data={"email": "x", "password": "x"},
            )
            assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. Header-Based Tokens (HTMX / fetch path)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFHeaderTokens:
    """Test X-CSRF-Token header acceptance (HTMX and fetch path)."""

    def test_header_token_accepted(self, csrf_client, csrf_app, csrf_db):
        """POST with X-CSRF-Token header (no form field) should be accepted."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            token = extract_csrf_token(resp.data.decode())

            response = csrf_client.post(
                "/login",
                data={"email": "x", "password": "x"},
                headers={"X-CSRF-Token": token},
                follow_redirects=True,
            )
            assert response.status_code != 403

    def test_header_token_wrong_value_rejected(self, csrf_client, csrf_app, csrf_db):
        """POST with wrong X-CSRF-Token header should be rejected."""
        with csrf_app.app_context():
            csrf_client.get("/login")  # establish session

            response = csrf_client.post(
                "/login",
                data={"email": "x", "password": "x"},
                headers={"X-CSRF-Token": "wrong-token-value"},
            )
            assert response.status_code == 403

    def test_header_works_without_form_field(self, csrf_client, csrf_app, csrf_db):
        """Header-only CSRF (no form field) should still pass validation."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            token = extract_csrf_token(resp.data.decode())

            # Send JSON-style request with header only, no csrf_token in form data
            response = csrf_client.post(
                "/login",
                headers={
                    "X-CSRF-Token": token,
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data="email=x&password=x",
                follow_redirects=True,
            )
            assert response.status_code != 403


# ---------------------------------------------------------------------------
# 5. Token Generation
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFTokenGeneration:
    """Test token generation and template integration."""

    def test_token_present_in_session_after_get(self, csrf_client, csrf_app, csrf_db):
        """GET request should generate and store a token in the session."""
        with csrf_app.app_context():
            csrf_client.get("/login")
            with csrf_client.session_transaction() as sess:
                assert "_csrf_token" in sess
                assert len(sess["_csrf_token"]) > 20

    def test_token_in_meta_tag(self, csrf_client, csrf_app, csrf_db):
        """Response HTML should include CSRF token in meta tag."""
        with csrf_app.app_context():
            resp = csrf_client.get("/login")
            html = resp.data.decode()
            assert 'name="csrf-token"' in html or 'name="csrf_token"' in html

    def test_token_format_url_safe(self, csrf_client, csrf_app, csrf_db):
        """Token should be a URL-safe base64 string of reasonable length."""
        with csrf_app.app_context():
            csrf_client.get("/login")
            with csrf_client.session_transaction() as sess:
                token = sess["_csrf_token"]
                # secrets.token_urlsafe(32) produces ~43 chars
                assert len(token) >= 40
                # URL-safe: only alphanumeric, hyphens, underscores
                assert re.match(r'^[A-Za-z0-9_-]+$', token)


# ---------------------------------------------------------------------------
# 6. Security Edge Cases
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestCSRFSecurityEdgeCases:
    """Test edge cases and security properties."""

    def test_empty_token_rejected(self, csrf_client, csrf_app, csrf_db):
        """POST with empty csrf_token should be rejected."""
        with csrf_app.app_context():
            csrf_client.get("/login")  # establish session

            response = csrf_client.post(
                "/login",
                data={"email": "x", "password": "x", "csrf_token": ""},
            )
            assert response.status_code == 403

    def test_no_session_token_rejected(self, csrf_app, csrf_db):
        """POST with a token but no session token should be rejected."""
        with csrf_app.app_context():
            # Fresh client — no GET first, so no session token
            client = csrf_app.test_client()
            response = client.post(
                "/login",
                data={
                    "email": "x",
                    "password": "x",
                    "csrf_token": "some-random-token",
                },
            )
            assert response.status_code == 403

    def test_delete_method_requires_csrf(self, csrf_authenticated_client, csrf_app, csrf_db, csrf_test_user):
        """DELETE requests should also require CSRF token."""
        with csrf_app.app_context():
            response = csrf_authenticated_client.delete("/some-nonexistent-endpoint")
            assert response.status_code in (302, 403)

    def test_put_method_requires_csrf(self, csrf_authenticated_client, csrf_app, csrf_db, csrf_test_user):
        """PUT requests should also require CSRF token."""
        with csrf_app.app_context():
            response = csrf_authenticated_client.put("/some-nonexistent-endpoint")
            assert response.status_code in (302, 403)

    def test_timing_safe_comparison_used(self):
        """Verify the middleware uses secrets.compare_digest (not ==)."""
        import inspect
        from system.middleware.csrf import validate_csrf_token

        source = inspect.getsource(validate_csrf_token)
        assert "compare_digest" in source
        # Should NOT use == for token comparison
        assert "==" not in source.split("compare_digest")[0].split("submitted")[1] if "submitted" in source else True
