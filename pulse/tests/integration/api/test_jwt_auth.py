# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - JWT Auth Integration Tests
#
# Tests for login, refresh, logout, magic-link, and decorator enforcement.
# -----------------------------------------------------------------------------


import pytest


@pytest.mark.integration
class TestLogin:
    """Tests for POST /api/v1/auth/login."""

    def test_login_success(self, app, client, api_user):
        """Valid email/password returns JWT pair and user data."""
        with app.app_context():
            resp = client.post("/api/v1/auth/login", json={
                "email": "apiuser@example.com",
                "password": "ApiPass123!",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert "expires_in" in data
            assert data["user"]["email"] == "apiuser@example.com"
            assert "password_hash" not in data["user"]

    def test_login_wrong_password(self, app, client, api_user):
        """Wrong password returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/login", json={
                "email": "apiuser@example.com",
                "password": "wrongpassword",
            })
            assert resp.status_code == 401
            data = resp.get_json()
            assert data["error"]["code"] == "INVALID_CREDENTIALS"

    def test_login_unknown_email(self, app, client, db_session):
        """Unknown email returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/login", json={
                "email": "unknown@example.com",
                "password": "whatever",
            })
            assert resp.status_code == 401

    def test_login_missing_fields(self, app, client, db_session):
        """Missing email or password returns 400."""
        with app.app_context():
            resp = client.post("/api/v1/auth/login", json={"email": "test@example.com"})
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "VALIDATION_ERROR"

    def test_login_inactive_user(self, app, client, api_user):
        """Inactive user returns 401."""
        with app.app_context():
            from system.db.database import db
            from modules.base.core.models.user import User
            user = db.session.get(User, api_user.id)
            user.is_active = False
            db.session.commit()

            resp = client.post("/api/v1/auth/login", json={
                "email": "apiuser@example.com",
                "password": "ApiPass123!",
            })
            assert resp.status_code == 401
            assert resp.get_json()["error"]["code"] == "ACCOUNT_INACTIVE"

    def test_login_lockout(self, app, client, api_user):
        """Account locks after too many failed attempts."""
        with app.app_context():
            for _ in range(5):
                client.post("/api/v1/auth/login", json={
                    "email": "apiuser@example.com",
                    "password": "wrong",
                })

            resp = client.post("/api/v1/auth/login", json={
                "email": "apiuser@example.com",
                "password": "ApiPass123!",
            })
            assert resp.status_code == 401
            assert resp.get_json()["error"]["code"] == "ACCOUNT_LOCKED"


@pytest.mark.integration
class TestRefresh:
    """Tests for POST /api/v1/auth/refresh."""

    def test_refresh_success(self, app, client, api_user, refresh_token):
        """Valid refresh token returns new JWT pair."""
        with app.app_context():
            resp = client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["refresh_token"] != refresh_token  # rotated

    def test_refresh_rotation_revokes_old(self, app, client, api_user, refresh_token):
        """Refresh token rotation revokes the old token."""
        with app.app_context():
            # Use the refresh token
            resp = client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token,
            })
            assert resp.status_code == 200

            # Old token should be revoked
            resp2 = client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token,
            })
            assert resp2.status_code == 401

    def test_refresh_invalid_token(self, app, client, db_session):
        """Invalid refresh token returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/refresh", json={
                "refresh_token": "invalid-token-value",
            })
            assert resp.status_code == 401

    def test_refresh_missing_token(self, app, client, db_session):
        """Missing refresh_token field returns 400."""
        with app.app_context():
            resp = client.post("/api/v1/auth/refresh", json={})
            assert resp.status_code == 400


@pytest.mark.integration
class TestLogout:
    """Tests for POST /api/v1/auth/logout."""

    def test_logout_success(self, app, client, auth_headers, refresh_token):
        """Logout revokes the specified refresh token."""
        with app.app_context():
            resp = client.post("/api/v1/auth/logout", headers=auth_headers, json={
                "refresh_token": refresh_token,
            })
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

            # Refresh token should be revoked
            resp2 = client.post("/api/v1/auth/refresh", json={
                "refresh_token": refresh_token,
            })
            assert resp2.status_code == 401

    def test_logout_requires_auth(self, app, client, db_session):
        """Logout without token returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/logout", json={})
            assert resp.status_code == 401

    def test_logout_all(self, app, client, api_user, admin_auth_headers):
        """Logout all revokes all refresh tokens for the user."""
        with app.app_context():
            # Create multiple refresh tokens for admin user
            from system.api.jwt import create_refresh_token
            from modules.base.core.models.user import User

            admin = User.get_by_email("apiadmin@example.com")
            create_refresh_token(admin.id, device_info="device1")
            create_refresh_token(admin.id, device_info="device2")

            resp = client.post("/api/v1/auth/logout/all", headers=admin_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"
            assert data["revoked"] >= 2


@pytest.mark.integration
class TestMagicLink:
    """Tests for POST /api/v1/auth/magic-link and /magic-link/verify."""

    def test_magic_link_request(self, app, client, api_user):
        """Magic link request always returns ok (prevents enumeration)."""
        with app.app_context():
            resp = client.post("/api/v1/auth/magic-link", json={
                "email": "apiuser@example.com",
            })
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_magic_link_request_unknown_email(self, app, client, db_session):
        """Magic link request for unknown email still returns ok."""
        with app.app_context():
            resp = client.post("/api/v1/auth/magic-link", json={
                "email": "unknown@example.com",
            })
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_magic_link_verify(self, app, client, api_user):
        """Valid magic link token returns JWT pair."""
        with app.app_context():
            from system.db.database import db
            from modules.base.core.models.user import User
            user = db.session.get(User, api_user.id)
            token = user.generate_magic_link_token()

            resp = client.post("/api/v1/auth/magic-link/verify", json={
                "token": token,
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["user"]["email"] == "apiuser@example.com"

    def test_magic_link_verify_invalid(self, app, client, db_session):
        """Invalid magic link token returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/magic-link/verify", json={
                "token": "invalid-magic-token",
            })
            assert resp.status_code == 401

    def test_magic_link_consumed_after_use(self, app, client, api_user):
        """Magic link token can only be used once."""
        with app.app_context():
            from system.db.database import db
            from modules.base.core.models.user import User
            user = db.session.get(User, api_user.id)
            token = user.generate_magic_link_token()

            # First use succeeds
            resp = client.post("/api/v1/auth/magic-link/verify", json={"token": token})
            assert resp.status_code == 200

            # Second use fails
            resp2 = client.post("/api/v1/auth/magic-link/verify", json={"token": token})
            assert resp2.status_code == 401


@pytest.mark.integration
class TestDecorators:
    """Tests for JWT decorator enforcement."""

    def test_missing_token_returns_401(self, app, client, db_session):
        """Request without Authorization header returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/logout", json={})
            assert resp.status_code == 401
            assert resp.get_json()["error"]["code"] == "UNAUTHORIZED"

    def test_invalid_token_returns_401(self, app, client, db_session):
        """Request with invalid token returns 401."""
        with app.app_context():
            resp = client.post("/api/v1/auth/logout",
                headers={"Authorization": "Bearer invalid.token.value"},
                json={},
            )
            assert resp.status_code == 401
            assert resp.get_json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_expired_token_returns_401(self, app, client, api_user):
        """Request with expired token returns 401."""
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone

        with app.app_context():
            payload = {
                "user_id": api_user.id,
                "type": "access",
                "iat": datetime.now(timezone.utc) - timedelta(hours=2),
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            }
            expired_token = pyjwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")

            resp = client.post("/api/v1/auth/logout",
                headers={"Authorization": f"Bearer {expired_token}"},
                json={},
            )
            assert resp.status_code == 401
