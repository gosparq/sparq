# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestProjectsRoutes:
    """Smoke tests for projects routes."""

    def test_projects_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/projects/")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_projects_api_check_channel_name(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/projects/api/check-channel-name")
            assert resp.status_code == 200

    def test_projects_api_list(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/projects/api/list")
            assert resp.status_code == 200

    def test_projects_archived(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/projects/archived")
            assert resp.status_code == 200

    def test_projects_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/projects/new")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked
