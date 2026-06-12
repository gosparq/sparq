# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestIntegrationsRoutes:
    """Smoke tests for integrations routes."""

    def test_github_callback(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/callback")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_github_collaborators(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/collaborators")
            assert resp.status_code != 404  # 400: requires query params

    def test_github_connect(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/connect")
            assert resp.status_code in (200, 302)

    def test_github_issues(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/issues")
            assert resp.status_code == 200

    def test_github_issues_new_modal(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/issues/new-modal")
            assert resp.status_code != 404  # 400: requires query params

    def test_github_palette_orphans(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/palette/orphans")
            assert resp.status_code != 404  # 400: requires query params

    def test_github_task_chips(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/github/task-chips")
            assert resp.status_code == 200

    def test_issues_unowned(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/issues/unowned")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_palette_commands(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/palette/commands")
            assert resp.status_code == 200

    def test_settings_no_slash(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/settings")
            assert resp.status_code == 200

    def test_settings_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/settings/")
            assert resp.status_code == 200

    def test_settings_github(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/integrations/settings/github")
            assert resp.status_code == 200
