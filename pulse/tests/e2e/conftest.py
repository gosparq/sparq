# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - E2E Test Configuration
#
# Playwright fixtures for end-to-end browser testing.
# Requires: pip install pytest-playwright && playwright install
#
# IMPORTANT: E2E tests require a running server.
# Start the server before running: make run (or flask run)
# -----------------------------------------------------------------------------

import os
import pytest
from typing import Generator
from playwright.sync_api import Playwright, Browser, Page, sync_playwright


# Base URL for the running application
BASE_URL = os.environ.get("TEST_BASE_URL", "http://localhost:8000")

# Screenshot directory
SCREENSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".scratch",
    "screenshots"
)


@pytest.fixture(scope="session")
def playwright_instance() -> Generator[Playwright, None, None]:
    """Provide a Playwright instance for the test session."""
    with sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Generator[Browser, None, None]:
    """Provide a browser instance for the test session."""
    browser = playwright_instance.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture(scope="function")
def page(browser: Browser) -> Generator[Page, None, None]:
    """Provide a fresh page for each test."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="function")
def authenticated_page(browser: Browser, e2e_user_credentials) -> Generator[Page, None, None]:
    """Provide a page with an authenticated session.

    Logs in before yielding the page.
    """
    context = browser.new_context()
    page = context.new_page()

    # Navigate to login and authenticate
    page.goto(f"{BASE_URL}/login")
    page.fill('input[name="email"]', e2e_user_credentials["email"])
    page.fill('input[name="password"]', e2e_user_credentials["password"])
    page.click('button[type="submit"]')

    # Wait for redirect after login
    page.wait_for_load_state("networkidle")

    yield page
    context.close()


@pytest.fixture
def e2e_user_credentials() -> dict:
    """Default credentials for E2E testing.

    These should match a user in your test/demo database.
    Override via environment variables if needed.
    """
    return {
        "email": os.environ.get("E2E_USER_EMAIL", "maria@example.com"),
        "password": os.environ.get("E2E_USER_PASSWORD", "password"),
    }


@pytest.fixture
def base_url() -> str:
    """Base URL for the application under test."""
    return BASE_URL


def take_screenshot(page: Page, name: str) -> str:
    """Take a screenshot and save to .scratch/screenshots/.

    Args:
        page: Playwright page object
        name: Screenshot filename (without extension)

    Returns:
        Path to the saved screenshot
    """
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    path = os.path.join(SCREENSHOTS_DIR, f"{name}.png")
    page.screenshot(path=path)
    return path
