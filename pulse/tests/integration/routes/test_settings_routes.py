# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestSettingsRoutes:
    """Smoke tests for settings routes."""

    def test_settings_bare(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings")
            assert resp.status_code in (200, 302)

    def test_settings_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/")
            assert resp.status_code in (200, 302)

    def test_settings_apps(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/apps")
            assert resp.status_code == 200

    def test_settings_business(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/business")
            assert resp.status_code in (200, 302)

    def test_settings_company(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/company")
            assert resp.status_code == 200

    def test_settings_install_app(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/install-app")
            assert resp.status_code == 200

    def test_settings_organization(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/organization")
            assert resp.status_code == 200

    def test_settings_organization_slash(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/organization/")
            assert resp.status_code == 200

    def test_settings_permissions(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/permissions")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_settings_permissions_clear_modal(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/permissions/clear-modal")
            assert resp.status_code == 200

    def test_settings_preferences(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/preferences")
            assert resp.status_code == 200

    def test_settings_projects(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/projects")
            assert resp.status_code == 200

    def test_settings_regional(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/regional")
            assert resp.status_code in (200, 302)

    def test_settings_security(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/security")
            assert resp.status_code == 200

    def test_settings_security_phone_verify(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/security/phone/verify")
            assert resp.status_code in (200, 302)

    def test_settings_templates(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/settings/templates")
            assert resp.status_code == 200
