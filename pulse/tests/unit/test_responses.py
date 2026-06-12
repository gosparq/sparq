# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Response Utils Unit Tests
#
# Tests for system/utils/responses.py. Verifies HTMX redirect/refresh
# and API JSON response helpers.
# -----------------------------------------------------------------------------


import pytest

from system.utils.responses import (
    api_error,
    api_response,
    htmx_redirect,
    htmx_refresh,
)


# ---------------------------------------------------------------------------
# 1. htmx_redirect — HTMX redirect response
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHtmxRedirect:
    """Test HTMX redirect response creation."""

    def test_has_hx_redirect_header(self, app):
        """Response should contain HX-Redirect header."""
        with app.test_request_context():
            # Register a simple endpoint for url_for to resolve
            response = htmx_redirect("static", filename="test.css")
            assert "HX-Redirect" in response.headers

    def test_header_contains_url(self, app):
        """HX-Redirect header should contain the resolved URL."""
        with app.test_request_context():
            response = htmx_redirect("static", filename="test.css")
            header = response.headers["HX-Redirect"]
            # The URL should end with the filename regardless of static path prefix
            assert "test.css" in header


# ---------------------------------------------------------------------------
# 2. htmx_refresh — HTMX refresh response
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHtmxRefresh:
    """Test HTMX refresh response creation."""

    def test_has_hx_refresh_header(self, app):
        """Response should contain HX-Refresh header."""
        with app.test_request_context():
            response = htmx_refresh()
            assert "HX-Refresh" in response.headers

    def test_hx_refresh_is_true(self, app):
        """HX-Refresh header should be 'true'."""
        with app.test_request_context():
            response = htmx_refresh()
            assert response.headers["HX-Refresh"] == "true"


# ---------------------------------------------------------------------------
# 3. api_response — standardized JSON response
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApiResponse:
    """Test standardized API JSON response."""

    def test_default_success(self, app):
        """Default response should indicate success."""
        with app.test_request_context():
            resp, status = api_response()
            data = resp.get_json()
            assert data["success"] is True
            assert status == 200

    def test_with_data(self, app):
        """Response should include provided data."""
        with app.test_request_context():
            resp, status = api_response(data={"name": "test"})
            data = resp.get_json()
            assert data["data"]["name"] == "test"

    def test_with_error_message(self, app):
        """Response should include error message when provided."""
        with app.test_request_context():
            resp, status = api_response(success=False, error="Bad request", status=400)
            data = resp.get_json()
            assert data["success"] is False
            assert data["error"] == "Bad request"
            assert status == 400

    def test_custom_status_code(self, app):
        """Custom status codes should be returned."""
        with app.test_request_context():
            _, status = api_response(status=201)
            assert status == 201

    def test_data_not_included_when_none(self, app):
        """Data key should not appear when data is None."""
        with app.test_request_context():
            resp, _ = api_response()
            data = resp.get_json()
            assert "data" not in data

    def test_error_not_included_when_none(self, app):
        """Error key should not appear when error is None."""
        with app.test_request_context():
            resp, _ = api_response()
            data = resp.get_json()
            assert "error" not in data

    def test_list_data(self, app):
        """Response should handle list data."""
        with app.test_request_context():
            resp, _ = api_response(data=[1, 2, 3])
            data = resp.get_json()
            assert data["data"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# 4. api_error — error response shortcut
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApiError:
    """Test API error response shortcut."""

    def test_default_400_status(self, app):
        """Default status should be 400."""
        with app.test_request_context():
            _, status = api_error("Something failed")
            assert status == 400

    def test_success_is_false(self, app):
        """Success flag should be False."""
        with app.test_request_context():
            resp, _ = api_error("Something failed")
            data = resp.get_json()
            assert data["success"] is False

    def test_error_message_included(self, app):
        """Error message should be included in response."""
        with app.test_request_context():
            resp, _ = api_error("Not found")
            data = resp.get_json()
            assert data["error"] == "Not found"

    def test_custom_status(self, app):
        """Custom status codes should be respected."""
        with app.test_request_context():
            _, status = api_error("Not found", status=404)
            assert status == 404

    def test_server_error_status(self, app):
        """Should work with 500 status."""
        with app.test_request_context():
            _, status = api_error("Internal error", status=500)
            assert status == 500
