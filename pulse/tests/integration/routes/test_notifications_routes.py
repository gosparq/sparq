# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestNotificationsRoutes:
    """Smoke tests for notifications routes."""

    def test_notifications_bare(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/notifications")
            assert resp.status_code == 200

    def test_notifications_all(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/notifications/all")
            assert resp.status_code in (200, 302)

    def test_notifications_count(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/notifications/count")
            assert resp.status_code == 200

    def test_notifications_inbox(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/notifications/inbox")
            assert resp.status_code == 200
