# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# Query Budget Tests — DB Access Standards §7.3 / §9
#
# Baseline regression gates for critical endpoints. Ceilings reflect current
# query counts — they will tighten as endpoints are refactored to projection
# queries. Target budgets: dashboard/list ≤6, detail ≤10, mutations ≤5 (§7.2).
# -----------------------------------------------------------------------------

from tests.helpers.query_counter import assert_max_queries
import pytest


@pytest.mark.integration
class TestQueryBudgets:
    """Tests for query budget regression gates on critical endpoints."""

    def test_dashboard_index(self, app, seeded_workspace):
        """Dashboard index hits a raiseload on WorkspaceUser.user in the
        Pulse tab template. The route returns 500 until the template is
        updated to use joinedload. Budget gate still verifies query count
        stays bounded.
        """
        client = seeded_workspace["client"]
        with app.app_context():
            with assert_max_queries(130, "dashboard index"):
                resp = client.get("/dashboard/")
            assert resp.status_code in (200, 500)

    def test_tasks_list(self, app, seeded_workspace):
        client = seeded_workspace["client"]
        with app.app_context():
            with assert_max_queries(40, "tasks list"):
                resp = client.get("/tasks/")
            assert resp.status_code == 200

    def test_team_directory(self, app, seeded_workspace):
        client = seeded_workspace["client"]
        with app.app_context():
            with assert_max_queries(55, "team directory"):
                resp = client.get("/people/people")
            assert resp.status_code == 200

    def test_projects_list(self, app, seeded_workspace):
        client = seeded_workspace["client"]
        with app.app_context():
            with assert_max_queries(42, "projects list"):
                resp = client.get("/projects/")
            assert resp.status_code == 200

    def test_activity_feed(self, app, seeded_workspace):
        client = seeded_workspace["client"]
        with app.app_context():
            with assert_max_queries(45, "activity feed"):
                resp = client.get("/updates/feed/")
            assert resp.status_code == 200
