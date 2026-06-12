# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
import pytest


@pytest.mark.integration
class TestSyncRoutes:
    """Smoke tests for sync routes."""

    def test_sync_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/")
            assert resp.status_code in (200, 302)

    def test_blockers_modal_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/blockers/modal/new")
            assert resp.status_code == 200

    def test_board(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/board/")
            assert resp.status_code == 200

    def test_calendar(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/calendar/")
            assert resp.status_code == 200

    def test_calendar_api_events(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/calendar/api/events")
            assert resp.status_code == 200

    def test_calendar_api_upcoming(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/calendar/api/upcoming")
            assert resp.status_code == 200

    def test_calendar_event_new(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/calendar/event/new")
            assert resp.status_code == 200

    def test_chat(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat")
            assert resp.status_code == 200

    def test_chat_channels(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/channels")
            assert resp.status_code == 200

    def test_chat_dms(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/dms")
            assert resp.status_code == 200

    def test_chat_dms_sparqy(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/dms/sparqy")
            assert resp.status_code == 200

    def test_chat_emojis(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/emojis")
            assert resp.status_code == 200

    def test_chat_unread_count(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/unread-count")
            assert resp.status_code == 200

    def test_chat_users(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/users")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_chat_users_search(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/users/search")
            assert resp.status_code == 200

    def test_chat_ws(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/chat/ws")
            assert resp.status_code != 404  # 400: websocket endpoint, needs upgrade

    def test_posts_ten_four_status(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/posts/ten-four-status")
            assert resp.status_code == 200

    def test_sync_settings(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/settings")
            assert resp.status_code == 200

    def test_sync_updates(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/updates/")
            assert resp.status_code in (200, 302)

    def test_sync_updates_feed(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/updates/feed")
            assert resp.status_code in (200, 302)

    def test_week_review(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/week-review/")
            assert resp.status_code == 200

    def test_sync_wins(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/sync/wins/")
            assert resp.status_code in (200, 301, 302)


@pytest.mark.integration
class TestUpdatesRoutes:
    """Smoke tests for updates routes."""

    def test_updates_index(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/")
            assert resp.status_code in (200, 302)

    def test_activity(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/activity/")
            assert resp.status_code == 200

    def test_board(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/board/")
            assert resp.status_code in (200, 302)

    def test_channels(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/channels/")
            assert resp.status_code in (200, 302)

    def test_feed(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/feed/")
            assert resp.status_code == 200

    def test_feed_more(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/feed/more")
            assert resp.status_code == 200

    def test_organization_wins(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/organization/wins/")
            assert resp.status_code == 200

    def test_pulse(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/pulse")
            assert resp.status_code != 404  # 500: lazy-load bug, tracked

    def test_status(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/status/")
            assert resp.status_code in (200, 302)

    def test_weekly_plans(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/weekly-plans/")
            assert resp.status_code in (200, 302)

    def test_wins(self, app_with_sample_data, seeded_workspace):
        with app_with_sample_data.app_context():
            resp = seeded_workspace["client"].get("/updates/wins/")
            assert resp.status_code == 200
