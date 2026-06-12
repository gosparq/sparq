# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Pagination Integration Tests
#
# Tests for paginated_response: shape, defaults, per_page cap, edge cases.
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestPagination:
    """Tests for paginated_response()."""

    def _create_users(self, app, count):
        """Helper to create multiple test users."""
        from modules.base.core.models.user import User

        users = []
        with app.app_context():
            for i in range(count):
                user = User.create(
                    email=f"page{i}@example.com",
                    password="testpass123",
                    first_name=f"Page{i}",
                    last_name="User",
                )
                users.append(user)
        return users

    def test_response_shape(self, app, client, db_session):
        """Response has correct top-level structure."""
        self._create_users(app, 3)

        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test?page=1&per_page=10"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert "items" in data
                assert "pagination" in data
                p = data["pagination"]
                assert "page" in p
                assert "per_page" in p
                assert "total" in p
                assert "pages" in p
                assert "has_next" in p
                assert "has_prev" in p

    def test_default_pagination(self, app, client, db_session):
        """Defaults to page=1, per_page=20."""
        self._create_users(app, 5)

        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert data["pagination"]["page"] == 1
                assert data["pagination"]["per_page"] == 20
                assert data["pagination"]["total"] == 5
                assert len(data["items"]) == 5

    def test_custom_page_and_per_page(self, app, client, db_session):
        """Respects custom page and per_page parameters."""
        self._create_users(app, 5)

        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test?page=2&per_page=2"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert data["pagination"]["page"] == 2
                assert data["pagination"]["per_page"] == 2
                assert len(data["items"]) == 2
                assert data["pagination"]["has_prev"] is True
                assert data["pagination"]["has_next"] is True

    def test_per_page_cap_at_100(self, app, client, db_session):
        """per_page is capped at 100."""
        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test?per_page=500"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert data["pagination"]["per_page"] == 100

    def test_empty_results(self, app, client, db_session):
        """Empty query returns empty items with correct pagination."""
        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test"):
                resp = paginated_response(User.query.filter(User.email == "nonexistent"))
                data = resp.get_json()
                assert data["items"] == []
                assert data["pagination"]["total"] == 0
                assert data["pagination"]["pages"] == 0
                assert data["pagination"]["has_next"] is False
                assert data["pagination"]["has_prev"] is False

    def test_has_next_has_prev(self, app, client, db_session):
        """has_next and has_prev reflect position correctly."""
        self._create_users(app, 10)

        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            # First page
            with app.test_request_context("/api/v1/test?page=1&per_page=3"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert data["pagination"]["has_prev"] is False
                assert data["pagination"]["has_next"] is True

            # Last page
            with app.test_request_context("/api/v1/test?page=4&per_page=3"):
                resp = paginated_response(User.query.filter(User.email.like("page%")))
                data = resp.get_json()
                assert data["pagination"]["has_prev"] is True
                assert data["pagination"]["has_next"] is False

    def test_custom_serializer(self, app, client, db_session):
        """Custom serialize function is applied to items."""
        self._create_users(app, 2)

        with app.app_context():
            from modules.base.core.models.user import User
            from system.api.pagination import paginated_response

            with app.test_request_context("/api/v1/test"):
                resp = paginated_response(
                    User.query.filter(User.email.like("page%")),
                    serialize=lambda u: {"email": u.email},
                )
                data = resp.get_json()
                for item in data["items"]:
                    assert list(item.keys()) == ["email"]
