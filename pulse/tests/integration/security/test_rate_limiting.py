# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Rate Limiting Integration Tests
#
# Tests for the rate limiting middleware (system/middleware/ratelimit.py).
# Verifies decorator behavior, auth endpoint limits, and IP handling.
# -----------------------------------------------------------------------------

import os
import sys
from unittest.mock import patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rl_app():
    """Flask app for rate limiting tests."""
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SECRET_KEY"] = "test-secret-key-ratelimit"
    os.environ["FLASK_DEBUG"] = "False"

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture(scope="function")
def rl_db(rl_app):
    """Provide a clean database for each rate limit test."""
    from system.db.database import db
    from sqlalchemy import text

    with rl_app.app_context():
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
def client(rl_app):
    """Flask test client."""
    return rl_app.test_client()


# ---------------------------------------------------------------------------
# 1. Rate Limit Middleware Core
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRateLimitMiddleware:
    """Test core rate limiting decorator behavior."""

    def test_requests_under_limit_succeed(self, client, rl_app, rl_db):
        """Requests within the limit should not be blocked."""
        with rl_app.app_context():
            for _ in range(10):
                resp = client.post("/login", data={"email": "x", "password": "x"})
                assert resp.status_code != 429

    def test_requests_over_limit_return_429(self, client, rl_app, rl_db):
        """Requests exceeding the limit should get 429."""
        with rl_app.app_context():
            # Exhaust the login limit (10/min)
            for _ in range(10):
                client.post("/login", data={"email": "x", "password": "x"})

            # 11th request should be rate limited
            resp = client.post("/login", data={"email": "x", "password": "x"})
            assert resp.status_code == 429

    def test_window_expiry_allows_new_requests(self, client, rl_app, rl_db):
        """After the window expires, requests should be allowed again."""
        with rl_app.app_context():
            base_time = 1000000.0

            # Fill the bucket at time T
            with patch("system.middleware.ratelimit.time") as mock_time:
                mock_time.time.return_value = base_time
                for _ in range(10):
                    client.post("/login", data={"email": "x", "password": "x"})

                # Should be blocked at time T
                resp = client.post("/login", data={"email": "x", "password": "x"})
                assert resp.status_code == 429

            # Advance past the 60s window
            with patch("system.middleware.ratelimit.time") as mock_time:
                mock_time.time.return_value = base_time + 61
                resp = client.post("/login", data={"email": "x", "password": "x"})
                assert resp.status_code != 429

    def test_different_ips_have_independent_buckets(self, client, rl_app, rl_db):
        """Different IPs should have separate rate limit counters."""
        with rl_app.app_context():
            # Exhaust limit from IP-A
            for _ in range(10):
                client.post(
                    "/login",
                    data={"email": "x", "password": "x"},
                    headers={"X-Forwarded-For": "1.2.3.4"},
                )

            # IP-A should be blocked
            resp = client.post(
                "/login",
                data={"email": "x", "password": "x"},
                headers={"X-Forwarded-For": "1.2.3.4"},
            )
            assert resp.status_code == 429

            # IP-B should still be allowed
            resp = client.post(
                "/login",
                data={"email": "x", "password": "x"},
                headers={"X-Forwarded-For": "5.6.7.8"},
            )
            assert resp.status_code != 429

    def test_json_request_gets_json_429(self, client, rl_app, rl_db):
        """JSON requests should receive a JSON 429 response."""
        with rl_app.app_context():
            # Exhaust login limit
            for _ in range(10):
                client.post("/login", data={"email": "x", "password": "x"})

            # JSON request should get JSON response
            resp = client.post(
                "/login",
                json={"email": "x", "password": "x"},
                content_type="application/json",
            )
            assert resp.status_code == 429
            data = resp.get_json()
            assert data is not None
            assert "error" in data

    def test_non_json_request_gets_429(self, client, rl_app, rl_db):
        """Non-JSON requests should receive a 429 response via abort()."""
        with rl_app.app_context():
            # Exhaust login limit
            for _ in range(10):
                client.post("/login", data={"email": "x", "password": "x"})

            resp = client.post("/login", data={"email": "x", "password": "x"})
            assert resp.status_code == 429

    def test_get_requests_are_not_counted(self, client, rl_app, rl_db):
        """GET requests should not consume from the rate limit bucket."""
        with rl_app.app_context():
            # Make many GETs — should not affect the budget
            for _ in range(20):
                client.get("/login")

            # POST should still succeed (bucket is empty)
            resp = client.post("/login", data={"email": "x", "password": "x"})
            assert resp.status_code != 429


# ---------------------------------------------------------------------------
# 2. Auth Endpoint Limits
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestAuthEndpointLimits:
    """Verify each auth endpoint has the correct rate limit."""

    def test_login_allows_10_per_minute(self, client, rl_app, rl_db):
        """/login should allow 10 requests before blocking."""
        with rl_app.app_context():
            for i in range(10):
                resp = client.post("/login", data={"email": "x", "password": "x"})
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post("/login", data={"email": "x", "password": "x"})
            assert resp.status_code == 429

    def test_signup_allows_5_per_minute(self, client, rl_app, rl_db):
        """/signup should allow 5 requests before blocking."""
        with rl_app.app_context():
            for i in range(5):
                resp = client.post(
                    "/signup",
                    data={
                        "email": f"user{i}@test.com",
                        "password": "test123",
                        "first_name": "Test",
                        "last_name": "User",
                    },
                )
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post(
                "/signup",
                data={
                    "email": "extra@test.com",
                    "password": "test123",
                    "first_name": "Test",
                    "last_name": "User",
                },
            )
            assert resp.status_code == 429

    def test_forgot_password_allows_5_per_5_minutes(self, client, rl_app, rl_db):
        """/auth/forgot-password should allow 5 requests before blocking."""
        with rl_app.app_context():
            for i in range(5):
                resp = client.post(
                    "/auth/forgot-password",
                    data={"email": "x@test.com"},
                )
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post(
                "/auth/forgot-password",
                data={"email": "x@test.com"},
            )
            assert resp.status_code == 429

    def test_sms_request_allows_3_per_5_minutes(self, client, rl_app, rl_db):
        """/auth/sms should allow 3 requests before blocking (tightest limit)."""
        with rl_app.app_context():
            for i in range(3):
                resp = client.post(
                    "/auth/sms",
                    data={"phone": "5551234567"},
                )
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post(
                "/auth/sms",
                data={"phone": "5551234567"},
            )
            assert resp.status_code == 429

    def test_sms_verify_allows_5_per_5_minutes(self, client, rl_app, rl_db):
        """/auth/sms/verify should allow 5 requests before blocking."""
        with rl_app.app_context():
            # Set phone in session so the route doesn't redirect
            with client.session_transaction() as sess:
                sess["sms_login_phone"] = "5551234567"

            for i in range(5):
                resp = client.post(
                    "/auth/sms/verify",
                    data={"otp": "123456"},
                )
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post(
                "/auth/sms/verify",
                data={"otp": "123456"},
            )
            assert resp.status_code == 429

    def test_magic_link_allows_5_per_5_minutes(self, client, rl_app, rl_db):
        """/auth/magic-link should allow 5 requests before blocking."""
        with rl_app.app_context():
            for i in range(5):
                resp = client.post(
                    "/auth/magic-link",
                    data={"email": "x@test.com"},
                )
                assert resp.status_code != 429, f"Blocked on request {i + 1}"

            resp = client.post(
                "/auth/magic-link",
                data={"email": "x@test.com"},
            )
            assert resp.status_code == 429


# ---------------------------------------------------------------------------
# 3. IP Handling
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestRateLimitIPHandling:
    """Test IP extraction for rate limit keys."""

    def test_uses_x_forwarded_for_first_entry(self, client, rl_app, rl_db):
        """Should use the first IP from X-Forwarded-For header."""
        with rl_app.app_context():
            from system.middleware.ratelimit import _buckets

            client.post(
                "/login",
                data={"email": "x", "password": "x"},
                headers={"X-Forwarded-For": "10.0.0.1, 192.168.1.1"},
            )

            # Bucket key should contain the first IP (10.0.0.1)
            keys = list(_buckets.keys())
            assert any("10.0.0.1" in k for k in keys)
            assert not any("192.168.1.1" in k for k in keys)

    def test_falls_back_to_remote_addr(self, client, rl_app, rl_db):
        """Without X-Forwarded-For, should use REMOTE_ADDR."""
        with rl_app.app_context():
            from system.middleware.ratelimit import _buckets

            # No X-Forwarded-For header — uses REMOTE_ADDR (127.0.0.1 in tests)
            client.post(
                "/login",
                data={"email": "x", "password": "x"},
            )

            keys = list(_buckets.keys())
            assert any("127.0.0.1" in k for k in keys)
