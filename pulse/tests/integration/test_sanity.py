# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Sanity Test
#
# Quick verification that the application bootstraps correctly:
# - App starts
# - Core modules loaded
# - Demo data loads
# - Login works
#
# Run with: make sanity (no server required, ~5 seconds)
# -----------------------------------------------------------------------------



import pytest

@pytest.mark.integration
class TestSanity:
    """Quick sanity checks - run these first to verify system health."""

    def test_app_starts(self, app):
        """Verify Flask app initializes."""
        assert app is not None
        assert app.config["TESTING"] is True

    def test_core_modules_loaded(self, app):
        """Verify all core modules are loaded."""
        with app.app_context():
            installed = app.config.get("INSTALLED_MODULES", {})

            # Required core modules
            required = ["Core", "Home", "People", "Updates"]
            for module in required:
                assert module in installed, f"Required module '{module}' not loaded"

    def test_module_count(self, app):
        """Verify expected number of modules loaded."""
        with app.app_context():
            installed = app.config.get("INSTALLED_MODULES", {})
            # Should have at least the core modules
            assert len(installed) >= 4, f"Expected at least 4 modules, got {len(installed)}"

    def test_database_connection(self, app, db_session):
        """Verify database is accessible."""
        from modules.base.core.models.user import User

        # Should be able to query without error
        count = db_session.query(User).count()
        assert count >= 0

    def test_demo_data_loads(self, app_with_sample_data):
        """Verify sample data seeds correctly."""
        from modules.base.core.models.user import User

        with app_with_sample_data.app_context():
            # Should have demo users
            users = User.query.all()
            assert len(users) > 0, "No demo users found"

    def test_login_works(self, app, seeded_workspace):
        """Verify login with seeded credentials works."""
        client = seeded_workspace["client"]
        user = seeded_workspace["user"]

        # Login as the seeded user
        response = client.post(
            "/login",
            data={"email": user.email, "password": "testpass123"},
            follow_redirects=False,
        )

        # Should redirect on successful login
        assert response.status_code in [302, 308], "Login failed"

    def test_dashboard_accessible_after_login(self, app, seeded_workspace):
        """Verify dashboard shows data after login."""
        client = seeded_workspace["client"]

        # Session is already authenticated via seeded_workspace fixture
        response = client.get("/dashboard/", follow_redirects=True)
        assert response.status_code == 200

    def test_health_endpoint(self, app, db_session):
        """Verify health check endpoint works."""
        client = app.test_client()
        response = client.get("/health")
        assert response.status_code == 200
