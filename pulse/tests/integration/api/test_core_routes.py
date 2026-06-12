# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Core API Route Tests
#
# Tests for GET/PUT /profile and GET /settings.
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestGetProfile:
    """Tests for GET /api/v1/core/profile."""

    def test_get_profile_success(self, app, client, api_user, auth_headers):
        """Returns current user profile."""
        with app.app_context():
            resp = client.get("/api/v1/core/profile", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["email"] == "apiuser@example.com"
            assert data["first_name"] == "API"
            assert data["last_name"] == "User"

    def test_get_profile_no_auth(self, app, client, db_session):
        """Returns 401 without auth token."""
        with app.app_context():
            resp = client.get("/api/v1/core/profile")
            assert resp.status_code == 401

    def test_get_profile_excludes_sensitive_fields(self, app, client, api_user, auth_headers):
        """Profile response does not include password_hash."""
        with app.app_context():
            resp = client.get("/api/v1/core/profile", headers=auth_headers)
            data = resp.get_json()
            assert "password_hash" not in data
            assert "otp_secret" not in data


@pytest.mark.integration
class TestUpdateProfile:
    """Tests for PUT /api/v1/core/profile."""

    def test_update_name(self, app, client, api_user, auth_headers):
        """Can update first_name and last_name."""
        with app.app_context():
            resp = client.put("/api/v1/core/profile", headers=auth_headers, json={
                "first_name": "Updated",
                "last_name": "Name",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["first_name"] == "Updated"
            assert data["last_name"] == "Name"

    def test_update_phone(self, app, client, api_user, auth_headers):
        """Can update phone_number."""
        with app.app_context():
            resp = client.put("/api/v1/core/profile", headers=auth_headers, json={
                "phone_number": "555-1234",
            })
            assert resp.status_code == 200
            assert resp.get_json()["phone_number"] == "555-1234"

    def test_update_rejects_email(self, app, client, api_user, auth_headers):
        """Cannot change email through profile update."""
        with app.app_context():
            resp = client.put("/api/v1/core/profile", headers=auth_headers, json={
                "email": "hacked@example.com",
            })
            assert resp.status_code == 400

    def test_update_empty_body(self, app, client, api_user, auth_headers):
        """Empty body returns 400."""
        with app.app_context():
            resp = client.put("/api/v1/core/profile", headers=auth_headers)
            assert resp.status_code == 400

    def test_update_no_auth(self, app, client, db_session):
        """Returns 401 without auth token."""
        with app.app_context():
            resp = client.put("/api/v1/core/profile", json={"first_name": "Nope"})
            assert resp.status_code == 401


@pytest.mark.integration
class TestGetSettings:
    """Tests for GET /api/v1/core/settings."""

    def test_get_settings_success(self, app, client, api_user, auth_headers):
        """Returns company settings."""
        with app.app_context():
            resp = client.get("/api/v1/core/settings", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "timezone" in data
            assert "currency" in data

    def test_get_settings_excludes_secrets(self, app, client, api_user, auth_headers):
        """Settings response excludes sensitive fields."""
        with app.app_context():
            resp = client.get("/api/v1/core/settings", headers=auth_headers)
            data = resp.get_json()
            assert "email_password" not in data

    def test_get_settings_no_auth(self, app, client, db_session):
        """Returns 401 without auth token."""
        with app.app_context():
            resp = client.get("/api/v1/core/settings")
            assert resp.status_code == 401
