# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Push Notification API Route Tests
#
# Tests for device registration and unregistration.
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestRegisterDevice:
    """Tests for POST /api/v1/devices/register."""

    def test_register_success(self, app, client, api_user, auth_headers):
        """Register a new device token."""
        with app.app_context():
            resp = client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "abc123token",
                "platform": "ios",
                "device_id": "device-001",
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["platform"] == "ios"
            assert data["device_id"] == "device-001"

    def test_register_upsert(self, app, client, api_user, auth_headers):
        """Re-registering same device_id updates the token."""
        with app.app_context():
            client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "old-token",
                "platform": "ios",
                "device_id": "device-002",
            })
            resp = client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "new-token",
                "platform": "ios",
                "device_id": "device-002",
            })
            assert resp.status_code == 200
            assert resp.get_json()["device_token"] == "new-token"

    def test_register_invalid_platform(self, app, client, api_user, auth_headers):
        """Returns 400 for invalid platform."""
        with app.app_context():
            resp = client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "abc123",
                "platform": "windows",
                "device_id": "device-003",
            })
            assert resp.status_code == 400

    def test_register_missing_fields(self, app, client, api_user, auth_headers):
        """Returns 400 when required fields missing."""
        with app.app_context():
            resp = client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "abc123",
            })
            assert resp.status_code == 400

    def test_register_no_auth(self, app, client, db_session):
        """Returns 401 without auth."""
        with app.app_context():
            resp = client.post("/api/v1/devices/register", json={
                "device_token": "abc", "platform": "ios", "device_id": "d1",
            })
            assert resp.status_code == 401


@pytest.mark.integration
class TestUnregisterDevice:
    """Tests for DELETE /api/v1/devices/<device_id>."""

    def test_unregister_success(self, app, client, api_user, auth_headers):
        """Unregister a previously registered device."""
        with app.app_context():
            client.post("/api/v1/devices/register", headers=auth_headers, json={
                "device_token": "abc123",
                "platform": "android",
                "device_id": "device-del-001",
            })
            resp = client.delete("/api/v1/devices/device-del-001", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_unregister_not_found(self, app, client, api_user, auth_headers):
        """Returns 404 for nonexistent device."""
        with app.app_context():
            resp = client.delete("/api/v1/devices/nonexistent", headers=auth_headers)
            assert resp.status_code == 404
