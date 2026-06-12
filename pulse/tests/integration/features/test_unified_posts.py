# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Integration tests for unified UpdatePost data model (Part B).

Tests threading metadata, denormalized fields, channel feed sort order,
template-free posts, and model properties.
"""

import pytest

from system.db.database import db


@pytest.fixture
def setup(app, db_session):
    """Create all required objects for unified post tests.

    Runs inside db_session's app context so g values persist into tests.
    """
    import uuid as _uuid
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.updates.models.channel import UpdateChannel
    from modules.base.updates.models.template import UpdateTemplate
    from flask import g

    org = Organization(
        id=_uuid.uuid4(), name="Test Org", slug=f"test-{_uuid.uuid4().hex[:8]}",
    )
    db.session.add(org)
    db.session.flush()
    g.organization_id = org.id

    ts = Workspace(
        id=_uuid.uuid4(), name="Test Co", slug=f"test-co-{_uuid.uuid4().hex[:8]}",
        organization_id=org.id,
    )
    db.session.add(ts)
    db.session.flush()
    g.workspace_id = ts.id

    user = User.create(
        email="unified-test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
        is_admin=False,
    )

    org_user = OrganizationUser.create(
        organization_id=org.id, user_id=user.id, role="member",
    )

    member = WorkspaceUser(
        user_id=user.id,
        workspace_id=ts.id,
        organization_id=org.id,
        organization_user_id=org_user.id,
        role="member",
    )
    db.session.add(member)
    db.session.flush()

    channel = UpdateChannel(
        name="test-unified", description="Test channel",
    )
    db.session.add(channel)
    db.session.flush()

    template = UpdateTemplate(
        post_type="update",
        name="Test Update",
        fields=[{"key": "body", "type": "text", "label": "Body"}],
        is_active=True,
        workspace_id=ts.id,
    )
    db.session.add(template)
    db.session.commit()

    yield {
        "app": app,
        "workspace": ts,
        "organization": org,
        "member": member,
        "channel": channel,
        "template": template,
    }


@pytest.mark.integration
class TestReplyDenormalization:
    """Test that reply_count and last_reply_at are maintained."""

    def test_reply_increments_count(self, setup):
        """Creating a reply increments parent's reply_count."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        parent = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Thread start"},
            channel_id=s["channel"].id,
        )
        assert parent.reply_count == 0
        assert parent.last_reply_at is None

        UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=parent.id,
            body="First reply",
        )

        db.session.refresh(parent)
        assert parent.reply_count == 1
        assert parent.last_reply_at is not None

    def test_multiple_replies(self, setup):
        """Multiple replies accumulate correctly."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        parent = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Thread start"},
            channel_id=s["channel"].id,
        )

        for i in range(3):
            UpdatePost.create_channel_reply(
                member_id=s["member"].id,
                channel_id=s["channel"].id,
                parent_id=parent.id,
                body=f"Reply {i}",
            )

        db.session.refresh(parent)
        assert parent.reply_count == 3

    def test_soft_delete_decrements_count(self, setup):
        """Soft-deleting a reply decrements parent's reply_count."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        parent = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Thread start"},
            channel_id=s["channel"].id,
        )

        reply = UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=parent.id,
            body="To be deleted",
        )

        db.session.refresh(parent)
        assert parent.reply_count == 1

        reply.soft_delete()
        db.session.refresh(parent)
        assert parent.reply_count == 0


@pytest.mark.integration
class TestChannelFeedSort:
    """Test channel feed sorts by last activity."""

    def test_reply_bumps_thread(self, setup):
        """A reply should bump the thread in channel feed ordering."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        older = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Older thread"},
            channel_id=s["channel"].id,
        )
        newer = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Newer thread"},
            channel_id=s["channel"].id,
        )

        # Before any replies, newer should be first
        posts, _ = UpdatePost.get_channel_feed(s["channel"].id)
        assert posts[0].id == newer.id

        # Reply to older thread — should bump it to the top
        UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=older.id,
            body="Bump!",
        )

        posts, _ = UpdatePost.get_channel_feed(s["channel"].id)
        assert posts[0].id == older.id


@pytest.mark.integration
class TestTemplateFreePost:
    """Test posts with template_id=NULL (migrated chat messages)."""

    def test_create_without_template(self, setup):
        """Can create a post with template=None."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        post = UpdatePost.create(
            template=None,
            member_id=s["member"].id,
            payload={"content": "Hello from chat"},
            channel_id=s["channel"].id,
            post_type="channel",
        )

        assert post.id is not None
        assert post.template_id is None
        assert post.post_type == "channel"

    def test_preview_text_without_template(self, setup):
        """preview_text() works for template-free posts."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        post = UpdatePost.create(
            template=None,
            member_id=s["member"].id,
            payload={"content": "Hello world"},
            channel_id=s["channel"].id,
            post_type="channel",
        )

        assert "Hello world" in post.preview_text()

    def test_reply_to_template_free_post(self, setup):
        """Can reply to a post that has no template."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        parent = UpdatePost.create(
            template=None,
            member_id=s["member"].id,
            payload={"content": "Chat message"},
            channel_id=s["channel"].id,
            post_type="channel",
        )

        reply = UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=parent.id,
            body="Reply to chat",
        )

        assert reply.parent_id == parent.id
        db.session.refresh(parent)
        assert parent.reply_count == 1


@pytest.mark.integration
class TestModelProperties:
    """Test is_reply, is_migrated, last_activity_at properties."""

    def test_is_reply_property(self, setup):
        """is_reply returns True for replies, False for root posts."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        parent = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Parent"},
            channel_id=s["channel"].id,
        )
        reply = UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=parent.id,
            body="Reply",
        )

        assert not parent.is_reply
        assert reply.is_reply

    def test_is_migrated_property(self, setup):
        """is_migrated returns True for migrated posts."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        post = UpdatePost(
            post_type="channel",
            member_id=s["member"].id,
            payload={"content": "migrated"},
            channel_id=s["channel"].id,
            migrated_from="sync_message",
            workspace_id=s["workspace"].id,
        )
        db.session.add(post)
        db.session.commit()

        assert post.is_migrated

        normal = UpdatePost.create(
            template=None,
            member_id=s["member"].id,
            payload={"content": "new"},
            channel_id=s["channel"].id,
            post_type="channel",
        )
        assert not normal.is_migrated

    def test_last_activity_at_without_replies(self, setup):
        """last_activity_at returns created_at when no replies."""
        from modules.base.updates.models.post import UpdatePost

        s = setup
        post = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "No replies"},
            channel_id=s["channel"].id,
        )

        assert post.last_activity_at == post.created_at

    def test_last_activity_at_with_replies(self, setup):
        """last_activity_at returns last_reply_at when replies exist."""
        from modules.base.updates.models.post import UpdatePost
        import time

        s = setup
        parent = UpdatePost.create(
            template=s["template"],
            member_id=s["member"].id,
            payload={"body": "Parent"},
            channel_id=s["channel"].id,
        )

        # Small delay to ensure timestamps differ
        time.sleep(0.01)

        UpdatePost.create_channel_reply(
            member_id=s["member"].id,
            channel_id=s["channel"].id,
            parent_id=parent.id,
            body="Reply",
        )

        db.session.refresh(parent)
        assert parent.last_activity_at == parent.last_reply_at
        assert parent.last_activity_at >= parent.created_at
