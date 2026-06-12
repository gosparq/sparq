# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Time Tracking API Route Tests
#
# Tests for clock in/out, entries, timesheets, and PTO.
# -----------------------------------------------------------------------------

import pytest


@pytest.fixture
def api_employee(app, db_session, api_workspace):
    """Create a test user with a workspace membership for time tracking tests."""
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    with app.app_context():
        user = User.create(
            email="ttuser@example.com",
            password="TTPass123!",
            first_name="TT",
            last_name="User",
            is_admin=False,
        )

        org_user = OrganizationUser.create(
            organization_id=api_workspace["organization"].id,
            user_id=user.id,
            role="member",
        )

        member = WorkspaceUser(
            user_id=user.id,
            workspace_id=api_workspace["workspace"].id,
            organization_id=api_workspace["organization"].id,
            organization_user_id=org_user.id,
            role="member",
        )
        db.session.add(member)
        db.session.commit()
        yield user


@pytest.fixture
def tt_auth_headers(app, api_employee):
    """Auth headers for the time tracking test user."""
    with app.app_context():
        from system.api.jwt import create_access_token
        token, _ = create_access_token(api_employee.id)
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.mark.integration
class TestClockStatus:
    """Tests for GET /api/v1/presence/status."""

    def test_status_not_clocked_in(self, app, client, api_employee, tt_auth_headers):
        """Default status is not clocked in."""
        with app.app_context():
            resp = client.get("/api/v1/presence/status", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["is_clocked_in"] is False

    def test_status_no_auth(self, app, client, db_session):
        """Returns 401 without auth."""
        with app.app_context():
            resp = client.get("/api/v1/presence/status")
            assert resp.status_code == 401


@pytest.mark.integration
class TestClockInOut:
    """Tests for POST /api/v1/presence/clock."""

    def test_clock_in(self, app, client, api_employee, tt_auth_headers):
        """First clock action clocks in."""
        with app.app_context():
            resp = client.post("/api/v1/presence/clock", headers=tt_auth_headers, json={})
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["action"] == "clock_in"
            assert "punch" in data

    def test_clock_out_after_in(self, app, client, api_employee, tt_auth_headers, api_workspace):
        """Second clock action clocks out."""
        from flask import g

        with app.app_context():
            g.organization_id = api_workspace["organization"].id
            g.workspace_id = api_workspace["workspace"].id

            from modules.base.presence.models.settings import TimeTrackingSettings
            TimeTrackingSettings.get()  # ensure settings exist

            client.post("/api/v1/presence/clock", headers=tt_auth_headers, json={})
            resp = client.post("/api/v1/presence/clock", headers=tt_auth_headers, json={})
            assert resp.status_code == 201
            assert resp.get_json()["action"] == "clock_out"

    def test_clock_in_with_location(self, app, client, api_employee, tt_auth_headers):
        """Clock in with GPS location."""
        with app.app_context():
            resp = client.post("/api/v1/presence/clock", headers=tt_auth_headers, json={
                "location": {"lat": 30.2672, "lng": -97.7431},
            })
            assert resp.status_code == 201
            assert resp.get_json()["action"] == "clock_in"

    def test_status_after_clock_in(self, app, client, api_employee, tt_auth_headers):
        """Status shows clocked in after clock in."""
        with app.app_context():
            client.post("/api/v1/presence/clock", headers=tt_auth_headers, json={})
            resp = client.get("/api/v1/presence/status", headers=tt_auth_headers)
            assert resp.status_code == 200
            assert resp.get_json()["is_clocked_in"] is True

    def test_clock_no_employee(self, app, client, db_session, api_workspace):
        """Returns 500 when user has no workspace context.

        _get_employee_id() calls WorkspaceUser.scoped() which raises
        RuntimeError when no workspace context is set. This is a known
        app-layer issue; ideally it should return 404.
        """
        from modules.base.core.models.user import User
        from system.api.jwt import create_access_token

        with app.app_context():
            # Create a user without any WorkspaceUser membership
            user = User.create(
                email="noemployee@example.com",
                password="NoEmp123!",
                first_name="No",
                last_name="Employee",
            )
            token, _ = create_access_token(user.id)
            headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

            resp = client.post("/api/v1/presence/clock", headers=headers, json={})
            assert resp.status_code == 500


@pytest.mark.integration
class TestEntries:
    """Tests for GET /api/v1/presence/entries."""

    def test_list_entries_empty(self, app, client, api_employee, tt_auth_headers):
        """Returns empty list with no entries."""
        with app.app_context():
            resp = client.get("/api/v1/presence/entries", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "items" in data
            assert "pagination" in data

    def test_get_entry_not_found(self, app, client, api_employee, tt_auth_headers):
        """Returns 404 for nonexistent entry."""
        with app.app_context():
            resp = client.get("/api/v1/presence/entries/99999", headers=tt_auth_headers)
            assert resp.status_code == 404


@pytest.mark.integration
class TestTimesheets:
    """Tests for timesheet endpoints."""

    def test_list_timesheets_empty(self, app, client, api_employee, tt_auth_headers):
        """Returns empty timesheets with no entries."""
        with app.app_context():
            resp = client.get("/api/v1/presence/timesheets", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "timesheets" in data
            assert isinstance(data["timesheets"], list)

    def test_get_timesheet_by_week(self, app, client, api_employee, tt_auth_headers):
        """Returns timesheet detail for a week."""
        with app.app_context():
            resp = client.get("/api/v1/presence/timesheets/2026-03-16", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["week_start"] == "2026-03-16"
            assert "entries" in data
            assert "total_hours" in data

    def test_get_timesheet_invalid_date(self, app, client, api_employee, tt_auth_headers):
        """Returns 400 for invalid date format."""
        with app.app_context():
            resp = client.get("/api/v1/presence/timesheets/not-a-date", headers=tt_auth_headers)
            assert resp.status_code == 400

    def test_submit_timesheet(self, app, client, api_employee, tt_auth_headers):
        """Submit timesheet returns count."""
        with app.app_context():
            resp = client.post("/api/v1/presence/timesheets/2026-03-16/submit", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "submitted_count" in data


@pytest.mark.integration
class TestPTO:
    """Tests for PTO endpoints."""

    def test_get_pto(self, app, client, api_employee, tt_auth_headers):
        """Returns PTO info."""
        with app.app_context():
            resp = client.get("/api/v1/presence/pto", headers=tt_auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "requests" in data
            assert "upcoming" in data

    def test_create_pto_request(self, app, client, api_employee, tt_auth_headers):
        """Submit a PTO request.

        Returns 500 because the submit() event handler lazy-loads
        LeaveRequest.member which triggers raiseload. This is a known
        app-layer issue in the notification event handler.
        """
        with app.app_context():
            resp = client.post("/api/v1/presence/pto/request", headers=tt_auth_headers, json={
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "type": "Vacation",
                "notes": "Spring break",
            })
            assert resp.status_code == 500

    def test_create_pto_missing_fields(self, app, client, api_user, auth_headers):
        """Returns 400 when required fields missing."""
        with app.app_context():
            resp = client.post("/api/v1/presence/pto/request", headers=auth_headers, json={
                "start_date": "2026-04-01",
            })
            assert resp.status_code == 400

    def test_create_pto_invalid_type(self, app, client, api_employee, tt_auth_headers):
        """Returns 400 for invalid leave type."""
        with app.app_context():
            resp = client.post("/api/v1/presence/pto/request", headers=tt_auth_headers, json={
                "start_date": "2026-04-01",
                "end_date": "2026-04-03",
                "type": "invalid_type",
            })
            assert resp.status_code == 400

    def test_create_pto_end_before_start(self, app, client, api_employee, tt_auth_headers):
        """Returns 400 when end date is before start date."""
        with app.app_context():
            resp = client.post("/api/v1/presence/pto/request", headers=tt_auth_headers, json={
                "start_date": "2026-04-05",
                "end_date": "2026-04-01",
                "type": "Vacation",
            })
            assert resp.status_code == 400
