# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - UpdatePost Model Integration Tests
#
# Tests for UpdatePost model database operations.
# -----------------------------------------------------------------------------

from datetime import datetime

import pytest
from flask import g

from system.db.database import db


def _make_channel(member_id):
    """Create a test channel for post tests."""
    from modules.base.updates.models.channel import UpdateChannel

    return UpdateChannel.create(
        name="test-channel",
        description="Test channel",
        created_by_id=member_id,
    )


def _make_template(post_type="update"):
    """Create a test template for post tests."""
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate(
        workspace_id=g.workspace_id,
        post_type=post_type,
        name=f"Test {post_type.title()}",
        description=f"Test {post_type} template",
        fields=[
            {"key": "body", "type": "text", "label": "Body"},
        ],
        is_active=True,
    )
    db.session.add(template)
    db.session.commit()
    return template


@pytest.mark.integration
class TestUpdatePostCreate:
    """Tests for UpdatePost.create() and basic creation."""

    def test_create_post_with_template(self, app, db_session, seeded_workspace):
        """Test creating a post with a template."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Test content"},
        )

        assert post.id is not None
        assert post.template_id == template.id
        assert post.post_type == "update"
        assert post.member_id == ws["membership"].id
        assert post.payload == {"body": "Test content"}

    def test_create_post_default_visibility_is_team(self, app, db_session, seeded_workspace):
        """Test that default visibility is 'team'."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Test"},
        )

        assert post.visibility == "team"

    def test_create_post_off_track_sets_leads_visibility(self, app, db_session, seeded_workspace):
        """Test that off_track status sets visibility to 'leads'."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template(post_type="update")
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Test", "status": "off_track"},
        )

        assert post.visibility == "leads"

    def test_create_post_anonymous_hides_member(self, app, db_session, seeded_workspace):
        """Test that anonymous template hides the member_id."""
        from modules.base.updates.models.post import UpdatePost
        from modules.base.updates.models.template import UpdateTemplate

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = UpdateTemplate(
            workspace_id=g.workspace_id,
            post_type="update",
            name="Anon Template",
            description="Anonymous",
            fields=[{"key": "body", "type": "text", "label": "Body"}],
            anonymous=True,
            is_active=True,
        )
        db.session.add(template)
        db.session.commit()

        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Secret"},
        )

        assert post.member_id is None
        assert post.is_anonymous is True

    def test_create_template_free_post(self, app, db_session, seeded_workspace):
        """Test creating a post without a template (e.g., channel chat)."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        post = UpdatePost.create(
            template=None,
            member_id=ws["membership"].id,
            payload={"content": "Hello channel"},
            channel_id=channel.id,
            post_type="channel",
        )

        assert post.id is not None
        assert post.template_id is None
        assert post.post_type == "channel"
        assert post.channel_id == channel.id

    def test_create_board_post_sets_expiry(self, app, db_session, seeded_workspace):
        """Test that board posts get a 30-day expiry."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template(post_type="board")
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Board item"},
        )

        assert post.expires_at is not None
        # Should expire roughly 30 days from now
        delta = post.expires_at - datetime.utcnow()
        assert 29 <= delta.days <= 30

    def test_create_post_with_channel(self, app, db_session, seeded_workspace):
        """Test creating a post attached to a channel."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        channel = _make_channel(ws["membership"].id)
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Channel post"},
            channel_id=channel.id,
        )

        assert post.channel_id == channel.id

    def test_create_post_with_subject(self, app, db_session, seeded_workspace):
        """Test creating a post with a subject line."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        channel = _make_channel(ws["membership"].id)
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Discussion body"},
            channel_id=channel.id,
            subject="Important topic",
        )

        assert post.subject == "Important topic"

    def test_create_post_subject_truncated_to_300(self, app, db_session, seeded_workspace):
        """Test that subject is truncated to 300 chars."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        long_subject = "A" * 400
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Test"},
            subject=long_subject,
        )

        assert len(post.subject) == 300


@pytest.mark.integration
class TestUpdatePostReply:
    """Tests for reply creation and threading."""

    def test_create_channel_reply(self, app, db_session, seeded_workspace):
        """Test creating a reply to a post."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root post"},
            channel_id=channel.id,
        )

        reply = UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply text",
        )

        assert reply.id is not None
        assert reply.parent_id == parent.id
        assert reply.payload == {"content": "Reply text"}
        assert reply.post_type == parent.post_type

    def test_reply_increments_reply_count(self, app, db_session, seeded_workspace):
        """Test that creating a reply increments the root's reply_count."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )
        assert parent.reply_count == 0

        UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply 1",
        )
        db.session.refresh(parent)
        assert parent.reply_count == 1

        UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply 2",
        )
        db.session.refresh(parent)
        assert parent.reply_count == 2

    def test_reply_updates_last_reply_at(self, app, db_session, seeded_workspace):
        """Test that creating a reply updates the root's last_reply_at."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )
        assert parent.last_reply_at is None

        reply = UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply",
        )
        db.session.refresh(parent)
        assert parent.last_reply_at is not None
        assert parent.last_reply_at == reply.created_at

    def test_reply_updates_last_reply_member_id(self, app, db_session, seeded_workspace):
        """Test that creating a reply updates last_reply_member_id."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )

        UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply",
        )
        db.session.refresh(parent)
        assert parent.last_reply_member_id == ws["membership"].id

    def test_reply_to_nonexistent_parent_raises(self, app, db_session, seeded_workspace):
        """Test that replying to a nonexistent parent raises ValueError."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)

        with pytest.raises(ValueError, match="Parent post .* not found"):
            UpdatePost.create_channel_reply(
                member_id=ws["membership"].id,
                channel_id=channel.id,
                parent_id=99999,
                body="Orphan reply",
            )


@pytest.mark.integration
class TestUpdatePostProperties:
    """Tests for UpdatePost computed properties."""

    def test_is_reply_true_for_reply(self, app, db_session, seeded_workspace):
        """Test is_reply returns True for a reply post."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )
        reply = UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply",
        )

        assert parent.is_reply is False
        assert reply.is_reply is True

    def test_is_migrated_property(self, app, db_session, seeded_workspace):
        """Test is_migrated returns True when migrated_from is set."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Normal"},
        )
        assert post.is_migrated is False

        post.migrated_from = "legacy_sync"
        db.session.commit()
        assert post.is_migrated is True

    def test_preview_text_with_template_fields(self, app, db_session, seeded_workspace):
        """Test preview_text extracts text from payload using template fields."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Working on tests"},
        )

        assert "Working on tests" in post.preview_text()

    def test_preview_text_empty_payload(self, app, db_session, seeded_workspace):
        """Test preview_text returns empty string for empty payload."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        post = UpdatePost.create(
            template=None,
            member_id=ws["membership"].id,
            payload={},
            post_type="channel",
        )

        assert post.preview_text() == ""

    def test_content_property_for_chat_post(self, app, db_session, seeded_workspace):
        """Test content property returns payload content for chat posts."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        post = UpdatePost.create(
            template=None,
            member_id=ws["membership"].id,
            payload={"content": "Hello world"},
            post_type="channel",
        )

        assert post.content == "Hello world"

    def test_last_activity_at_without_replies(self, app, db_session, seeded_workspace):
        """Test last_activity_at falls back to created_at when no replies."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Test"},
        )

        assert post.last_activity_at == post.created_at


@pytest.mark.integration
class TestUpdatePostChannelFeed:
    """Tests for get_channel_feed and feed queries."""

    def test_get_channel_feed_returns_posts(self, app, db_session, seeded_workspace):
        """Test get_channel_feed returns posts in a channel."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Post 1"},
            channel_id=channel.id,
        )
        UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Post 2"},
            channel_id=channel.id,
        )

        posts, has_more = UpdatePost.get_channel_feed(channel.id)
        assert len(posts) == 2
        assert has_more is False

    def test_get_channel_feed_excludes_replies(self, app, db_session, seeded_workspace):
        """Test get_channel_feed excludes reply posts."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )
        UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply",
        )

        posts, _ = UpdatePost.get_channel_feed(channel.id)
        assert len(posts) == 1
        assert posts[0].id == parent.id

    def test_get_channel_feed_with_limit(self, app, db_session, seeded_workspace):
        """Test get_channel_feed pagination with limit."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        for i in range(5):
            UpdatePost.create(
                template=template,
                member_id=ws["membership"].id,
                payload={"body": f"Post {i}"},
                channel_id=channel.id,
            )

        posts, has_more = UpdatePost.get_channel_feed(channel.id, limit=3)
        assert len(posts) == 3
        assert has_more is True


@pytest.mark.integration
class TestUpdatePostSoftDelete:
    """Tests for soft delete behavior."""

    def test_soft_delete_sets_expires_at(self, app, db_session, seeded_workspace):
        """Test soft_delete sets expires_at to now."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Will be deleted"},
        )
        assert post.expires_at is None

        post.soft_delete()

        assert post.expires_at is not None
        assert post.is_expired is True

    def test_soft_delete_reply_decrements_parent_count(self, app, db_session, seeded_workspace):
        """Test soft deleting a reply decrements the parent's reply count."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        channel = _make_channel(ws["membership"].id)
        template = _make_template()

        parent = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Root"},
            channel_id=channel.id,
        )
        reply = UpdatePost.create_channel_reply(
            member_id=ws["membership"].id,
            channel_id=channel.id,
            parent_id=parent.id,
            body="Reply",
        )
        db.session.refresh(parent)
        assert parent.reply_count == 1

        reply.soft_delete()
        db.session.refresh(parent)
        assert parent.reply_count == 0

    def test_soft_deleted_post_is_expired(self, app, db_session, seeded_workspace):
        """Test that a soft-deleted post reports is_expired as True."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Expiring"},
        )
        post.soft_delete()

        assert post.is_expired is True


@pytest.mark.integration
class TestUpdatePostMiscMethods:
    """Tests for toggle_pin, delete_message, mark_as_win, and other methods."""

    def test_toggle_pin(self, app, db_session, seeded_workspace):
        """Test toggle_pin toggles the pinned flag."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        post = UpdatePost.create(
            template=None,
            member_id=ws["membership"].id,
            payload={"content": "Pin me"},
            post_type="channel",
        )
        assert post.pinned is False

        result = UpdatePost.toggle_pin(post.id)
        assert result is True

        result = UpdatePost.toggle_pin(post.id)
        assert result is False

    def test_mark_as_win(self, app, db_session, seeded_workspace):
        """Test mark_as_win and unmark_as_win."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        template = _make_template()
        post = UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "Victory!"},
            is_win=False,
        )
        assert post.is_win is False

        post.mark_as_win()
        assert post.is_win is True

        post.unmark_as_win()
        assert post.is_win is False

    def test_delete_message(self, app, db_session, seeded_workspace):
        """Test delete_message hard-deletes a post."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        post = UpdatePost.create(
            template=None,
            member_id=ws["membership"].id,
            payload={"content": "Delete me"},
            post_type="channel",
        )
        post_id = post.id

        result = UpdatePost.delete_message(post_id)
        assert result is True

        assert UpdatePost.get_by_id(post_id) is None

    def test_delete_message_nonexistent_returns_false(self, app, db_session, seeded_workspace):
        """Test delete_message returns False for nonexistent post."""
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        result = UpdatePost.delete_message(99999)
        assert result is False

    def test_parse_mentioned_ids(self, app, db_session, seeded_workspace):
        """Test _parse_mentioned_ids extracts member IDs from mention tokens."""
        from modules.base.updates.models.post import UpdatePost

        ids = UpdatePost._parse_mentioned_ids("Hey @[42] and @[7] check this out")
        assert ids == [42, 7]

    def test_parse_mentioned_ids_empty(self, app, db_session, seeded_workspace):
        """Test _parse_mentioned_ids returns empty list for no mentions."""
        from modules.base.updates.models.post import UpdatePost

        assert UpdatePost._parse_mentioned_ids("No mentions here") == []
        assert UpdatePost._parse_mentioned_ids(None) == []
