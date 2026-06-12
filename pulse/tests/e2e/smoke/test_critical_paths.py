# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Smoke Tests
#
# Quick sanity checks that verify the application is running and
# critical paths are functional. These should complete in under 30 seconds.
#
# Run with: make smoke (requires running server)
# -----------------------------------------------------------------------------

from playwright.sync_api import Page, expect


class TestAppLoads:
    """Verify the application loads and renders."""

    def test_login_page_loads(self, page: Page, base_url: str):
        """Test that the login page loads successfully."""
        page.goto(f"{base_url}/login")

        # Check page title
        expect(page).to_have_title("Login - sparQOne")

        # Check login form elements exist
        expect(page.locator('input[name="email"]')).to_be_visible()
        expect(page.locator('input[name="password"]')).to_be_visible()
        expect(page.get_by_role("button", name="Login")).to_be_visible()

    def test_health_endpoint(self, page: Page, base_url: str):
        """Test that health check endpoint responds."""
        response = page.goto(f"{base_url}/health")
        assert response is not None
        assert response.status == 200


class TestAuthentication:
    """Verify authentication flows work."""

    def test_login_with_valid_credentials(
        self, page: Page, base_url: str, e2e_user_credentials: dict
    ):
        """Test successful login redirects to dashboard."""
        page.goto(f"{base_url}/login")

        # Fill login form
        page.fill('input[name="email"]', e2e_user_credentials["email"])
        page.fill('input[name="password"]', e2e_user_credentials["password"])
        page.click('button[type="submit"]')

        # Wait for navigation
        page.wait_for_load_state("networkidle")

        # Should redirect away from login page
        assert "/login" not in page.url

    def test_login_with_invalid_credentials(self, page: Page, base_url: str):
        """Test login with wrong password stays on login page."""
        page.goto(f"{base_url}/login")

        page.fill('input[name="email"]', "wrong@example.com")
        page.fill('input[name="password"]', "wrongpassword")
        page.click('button[type="submit"]')

        page.wait_for_load_state("networkidle")

        # Should stay on login page
        assert "/login" in page.url

    def test_logout(self, authenticated_page: Page, base_url: str):
        """Test logout redirects to login page."""
        # Navigate to logout
        authenticated_page.goto(f"{base_url}/logout")
        authenticated_page.wait_for_load_state("networkidle")

        # Should end up at login page
        assert "/login" in authenticated_page.url


class TestCriticalPages:
    """Verify critical pages are accessible when authenticated."""

    def test_dashboard_loads(self, authenticated_page: Page, base_url: str):
        """Test dashboard page loads for authenticated user."""
        authenticated_page.goto(f"{base_url}/dashboard/")
        authenticated_page.wait_for_load_state("networkidle")

        # Should not redirect to login
        assert "/login" not in authenticated_page.url

