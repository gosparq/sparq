# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestDashboardRoutes:
    """Smoke tests for dashboard routes."""

    def test_dashboard_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/dashboard/")
            assert resp.status_code == 200

    def test_dashboard_happening_feed(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/dashboard/happening-feed")
            assert resp.status_code == 200

    def test_dashboard_pulse_tab(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/dashboard/pulse-tab")
            assert resp.status_code == 200

    def test_dashboard_search(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/dashboard/search")
            assert resp.status_code == 200

    def test_dashboard_widgets(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/dashboard/widgets")
            assert resp.status_code == 200
