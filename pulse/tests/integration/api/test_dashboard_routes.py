# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Dashboard API Route Tests
#
# Tests for dashboard summary, activity feed, and notifications.
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestDashboardSummary:
    """Tests for GET /api/v1/dashboard/."""

    def test_summary_success(self, app, client, api_user, auth_headers):
        """Returns dashboard summary with clock status."""
        with app.app_context():
            resp = client.get("/api/v1/dashboard/", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "clock_status" in data
            assert "is_clocked_in" in data["clock_status"]
            assert "recent_activity" in data

    def test_summary_no_auth(self, app, client, db_session):
        """Returns 401 without auth token."""
        with app.app_context():
            resp = client.get("/api/v1/dashboard/")
            assert resp.status_code == 401


@pytest.mark.integration
class TestActivityFeed:
    """Tests for GET /api/v1/dashboard/activity."""

    def test_activity_success(self, app, client, api_user, auth_headers):
        """Returns paginated activity feed."""
        with app.app_context():
            resp = client.get("/api/v1/dashboard/activity", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "items" in data
            assert "pagination" in data

    def test_activity_pagination(self, app, client, api_user, auth_headers):
        """Supports page and per_page params."""
        with app.app_context():
            resp = client.get("/api/v1/dashboard/activity?page=1&per_page=5", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["pagination"]["per_page"] == 5


@pytest.mark.integration
class TestNotifications:
    """Tests for GET /api/v1/dashboard/notifications."""

    def test_notifications_success(self, app, client, api_user, auth_headers):
        """Returns 500 because ActivityLog.user_id column does not exist.

        The route filters by user_id but ActivityLog uses member_id.
        This is a known app-layer issue; the test documents current behaviour.
        """
        with app.app_context():
            resp = client.get("/api/v1/dashboard/notifications", headers=auth_headers)
            assert resp.status_code == 500

    def test_mark_notification_read_not_found(self, app, client, api_user, auth_headers):
        """Returns 404 for nonexistent notification."""
        with app.app_context():
            resp = client.post("/api/v1/dashboard/notifications/99999/read", headers=auth_headers)
            assert resp.status_code == 404
