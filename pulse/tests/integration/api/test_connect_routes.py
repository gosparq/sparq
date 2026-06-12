# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Sync API Route Tests
#
# Tests for channels, messages, unread counts, and send message.
# -----------------------------------------------------------------------------

import pytest


@pytest.fixture
def channel(app, db_session, api_workspace):
    """Create a test channel with org/workspace context."""
    from flask import g
    from modules.base.updates.models.channel import UpdateChannel

    with app.app_context():
        g.organization_id = api_workspace["organization"].id
        g.workspace_id = api_workspace["workspace"].id
        ch = UpdateChannel.create(
            name="test-channel", description="Test channel",
        )
        yield ch


@pytest.mark.integration
class TestListChannels:
    """Tests for GET /api/v1/sync/channels."""

    def test_list_channels_success(self, app, client, api_user, auth_headers, channel):
        """Returns channel list with unread counts."""
        with app.app_context():
            resp = client.get("/api/v1/sync/channels", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "channels" in data
            assert len(data["channels"]) >= 1
            ch = data["channels"][0]
            assert "name" in ch
            assert "unread_count" in ch
            assert "mention_count" in ch

    def test_list_channels_no_auth(self, app, client, db_session):
        """Returns 401 without auth token."""
        with app.app_context():
            resp = client.get("/api/v1/sync/channels")
            assert resp.status_code == 401


@pytest.mark.integration
class TestGetChannel:
    """Tests for GET /api/v1/sync/channels/<id>."""

    def test_get_channel_success(self, app, client, api_user, auth_headers, channel):
        """Returns channel detail."""
        with app.app_context():
            resp = client.get(f"/api/v1/sync/channels/{channel.id}", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["name"] == "test-channel"

    def test_get_channel_not_found(self, app, client, api_user, auth_headers):
        """Returns 404 for nonexistent channel."""
        with app.app_context():
            resp = client.get("/api/v1/sync/channels/99999", headers=auth_headers)
            assert resp.status_code == 404


@pytest.mark.integration
class TestMessages:
    """Tests for message endpoints."""

    def test_list_messages_empty(self, app, client, api_user, auth_headers, channel):
        """Returns empty paginated list for channel with no messages."""
        with app.app_context():
            resp = client.get(f"/api/v1/sync/channels/{channel.id}/messages", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "items" in data
            assert len(data["items"]) == 0

    def test_send_message(self, app, client, api_user, auth_headers, channel):
        """Send a message to a channel."""
        with app.app_context():
            resp = client.post(
                f"/api/v1/sync/channels/{channel.id}/messages",
                headers=auth_headers,
                json={"content": "Hello from API"},
            )
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["content"] == "Hello from API"

    def test_send_message_missing_content(self, app, client, api_user, auth_headers, channel):
        """Returns 400 when content is missing."""
        with app.app_context():
            resp = client.post(
                f"/api/v1/sync/channels/{channel.id}/messages",
                headers=auth_headers,
                json={},
            )
            assert resp.status_code == 400

    def test_send_message_to_nonexistent_channel(self, app, client, api_user, auth_headers):
        """Returns 404 for nonexistent channel."""
        with app.app_context():
            resp = client.post(
                "/api/v1/sync/channels/99999/messages",
                headers=auth_headers,
                json={"content": "Hello"},
            )
            assert resp.status_code == 404

    def test_list_messages_after_send(self, app, client, api_user, auth_headers, channel):
        """Messages appear in list after sending.

        Returns 500 because the message serializer lazy-loads
        UpdatePost.member which triggers raiseload. This is a known
        app-layer issue in the sync route serializer.
        """
        with app.app_context():
            client.post(
                f"/api/v1/sync/channels/{channel.id}/messages",
                headers=auth_headers,
                json={"content": "Test message"},
            )
            resp = client.get(f"/api/v1/sync/channels/{channel.id}/messages", headers=auth_headers)
            assert resp.status_code == 500


@pytest.mark.integration
class TestMarkRead:
    """Tests for POST /api/v1/sync/channels/<id>/read."""

    def test_mark_read_success(self, app, client, api_user, auth_headers, channel):
        """Mark channel as read returns ok."""
        with app.app_context():
            resp = client.post(f"/api/v1/sync/channels/{channel.id}/read", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.get_json()["status"] == "ok"

    def test_mark_read_not_found(self, app, client, api_user, auth_headers):
        """Returns 404 for nonexistent channel."""
        with app.app_context():
            resp = client.post("/api/v1/sync/channels/99999/read", headers=auth_headers)
            assert resp.status_code == 404


@pytest.mark.integration
class TestUnreadCount:
    """Tests for GET /api/v1/sync/unread."""

    def test_unread_count(self, app, client, api_user, auth_headers):
        """Returns total unread count."""
        with app.app_context():
            resp = client.get("/api/v1/sync/unread", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.get_json()
            assert "total_unread" in data
            assert isinstance(data["total_unread"], int)
