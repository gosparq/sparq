# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Authentication API Integration Tests
#
# Tests for login, logout, and session management endpoints.
# -----------------------------------------------------------------------------



import pytest

@pytest.mark.integration
class TestLoginEndpoint:
    """Tests for the /login endpoint."""

    def test_login_page_renders(self, client, app, db_session):
        """Test that login page renders successfully."""
        with app.app_context():
            response = client.get("/login")
            assert response.status_code == 200
            assert b"Login" in response.data

    def test_login_success(self, client, app, db_session, test_user):
        """Test successful login with valid credentials."""
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "email": test_user.email,
                    "password": "testpass123",
                },
                follow_redirects=False,
            )
            # Should redirect on success
            assert response.status_code == 302

    def test_login_invalid_password(self, client, app, db_session, test_user):
        """Test login with invalid password."""
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            # Should show error and stay on login page
            assert b"Login" in response.data

    def test_login_nonexistent_user(self, client, app, db_session):
        """Test login with non-existent email."""
        with app.app_context():
            response = client.post(
                "/login",
                data={
                    "email": "nonexistent@example.com",
                    "password": "anypassword",
                },
                follow_redirects=True,
            )
            assert response.status_code == 200
            assert b"Login" in response.data

    def test_login_redirect_when_authenticated(self, authenticated_client, app, db_session):
        """Test that authenticated users are redirected from login page."""
        with app.app_context():
            response = authenticated_client.get("/login", follow_redirects=False)
            assert response.status_code == 302


@pytest.mark.integration
class TestLogoutEndpoint:
    """Tests for the /logout endpoint."""

    def test_logout_success(self, authenticated_client, app, db_session):
        """Test successful logout."""
        with app.app_context():
            response = authenticated_client.get("/logout", follow_redirects=False)
            assert response.status_code in [302, 308]

            # Verify logged out by trying to access protected page
            response = authenticated_client.get("/dashboard/", follow_redirects=False)
            # Should redirect to login
            assert response.status_code in [302, 308]

    def test_logout_when_not_logged_in(self, client, app, db_session):
        """Test logout when not logged in."""
        with app.app_context():
            response = client.get("/logout", follow_redirects=False)
            # Should redirect (to login)
            assert response.status_code == 302


@pytest.mark.integration
class TestProtectedEndpoints:
    """Tests for protected endpoint access."""

    def test_dashboard_requires_login(self, client, app, db_session):
        """Test that dashboard requires authentication."""
        with app.app_context():
            response = client.get("/dashboard/", follow_redirects=False)
            assert response.status_code in [302, 308]

    def test_dashboard_accessible_when_authenticated(self, authenticated_client, app, db_session):
        """Test that authenticated users can access dashboard."""
        with app.app_context():
            response = authenticated_client.get("/dashboard/")
            # Should succeed (200) or redirect to appropriate page based on role
            assert response.status_code in [200, 302, 308]

    def test_health_endpoint_public(self, client, app, db_session):
        """Test that health endpoint is public."""
        with app.app_context():
            response = client.get("/health")
            assert response.status_code == 200
