# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Sync API Route Tests
#
# Tests for batch time entry sync and delta changes.
# -----------------------------------------------------------------------------

import pytest


@pytest.fixture
def api_user_with_employee(app, db_session, api_workspace):
    """Create a test user with a workspace membership for time entry creation."""
    from flask import g
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User

    with app.app_context():
        g.organization_id = api_workspace["organization"].id
        g.workspace_id = api_workspace["workspace"].id
        WorkspaceUser.create(
            email="sync-user@example.com",
            password="SyncPass123!",
            first_name="Sync",
            last_name="User",
        )
        user = User.get_by_email("sync-user@example.com")
        yield user


@pytest.fixture
def sync_auth_headers(app, api_user_with_employee):
    """Auth headers for the sync user."""
    with app.app_context():
        from system.api.jwt import create_access_token
        token, _ = create_access_token(api_user_with_employee.id)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.mark.integration
class TestSyncTimeEntries:
    """Tests for POST /api/v1/sync/time-entries."""

    def test_sync_success(self, app, client, api_user_with_employee, sync_auth_headers):
        """Batch sync creates entries and returns results."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", headers=sync_auth_headers, json={
                "entries": [
                    {
                        "local_id": "local-1",
                        "date": "2026-03-18",
                        "hours": 8.0,
                        "description": "Synced entry",
                    },
                ],
            })
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data["results"]) == 1
            assert data["results"][0]["status"] == "created"
            assert data["results"][0]["local_id"] == "local-1"
            assert "server_id" in data["results"][0]

    def test_sync_multiple_entries(self, app, client, api_user_with_employee, sync_auth_headers):
        """Batch sync handles multiple entries."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", headers=sync_auth_headers, json={
                "entries": [
                    {"local_id": "l1", "date": "2026-03-16", "hours": 4.0},
                    {"local_id": "l2", "date": "2026-03-17", "hours": 6.5},
                ],
            })
            assert resp.status_code == 200
            results = resp.get_json()["results"]
            assert len(results) == 2
            assert all(r["status"] == "created" for r in results)

    def test_sync_invalid_date(self, app, client, api_user_with_employee, sync_auth_headers):
        """Invalid date returns error status for that entry."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", headers=sync_auth_headers, json={
                "entries": [
                    {"local_id": "bad", "date": "not-a-date", "hours": 8.0},
                ],
            })
            assert resp.status_code == 200
            results = resp.get_json()["results"]
            assert results[0]["status"] == "error"

    def test_sync_missing_entries(self, app, client, api_user, auth_headers):
        """Missing entries field returns 400."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", headers=auth_headers, json={})
            assert resp.status_code == 400

    def test_sync_entries_not_array(self, app, client, api_user, auth_headers):
        """entries must be an array."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", headers=auth_headers, json={
                "entries": "not an array",
            })
            assert resp.status_code == 400

    def test_sync_no_auth(self, app, client, db_session):
        """Returns 401 without auth."""
        with app.app_context():
            resp = client.post("/api/v1/sync/time-entries", json={"entries": []})
            assert resp.status_code == 401


@pytest.mark.integration
class TestGetChanges:
    """Tests for GET /api/v1/sync/changes."""

    def test_changes_success(self, app, client, api_user, auth_headers):
        """Returns changes since timestamp."""
        with app.app_context():
            resp = client.get(
                "/api/v1/sync/changes?since=2026-01-01T00:00:00Z",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "since" in data
            assert "changes" in data

    def test_changes_filter_modules(self, app, client, api_user, auth_headers):
        """Filter by specific modules."""
        with app.app_context():
            resp = client.get(
                "/api/v1/sync/changes?since=2026-01-01T00:00:00Z&modules=presence",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert "presence" in data["changes"]
            assert "connect" not in data["changes"]

    def test_changes_missing_since(self, app, client, api_user, auth_headers):
        """Returns 400 when since param is missing."""
        with app.app_context():
            resp = client.get("/api/v1/sync/changes", headers=auth_headers)
            assert resp.status_code == 400

    def test_changes_invalid_since(self, app, client, api_user, auth_headers):
        """Returns 400 for invalid since format."""
        with app.app_context():
            resp = client.get("/api/v1/sync/changes?since=not-a-date", headers=auth_headers)
            assert resp.status_code == 400

    def test_changes_no_auth(self, app, client, db_session):
        """Returns 401 without auth."""
        with app.app_context():
            resp = client.get("/api/v1/sync/changes?since=2026-01-01T00:00:00Z")
            assert resp.status_code == 401
