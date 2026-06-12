# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Updates/Sync Model Integration Tests
#
# Tests for UpdateChannel, UpdateTemplate, Acknowledgment, Area,
# ChannelReadState, DM, Event, UpdateFollow, NudgeLog, PostReaction,
# UpdateWebhook, WeekReview, and WeeklyPlan models.
# -----------------------------------------------------------------------------

from datetime import date, datetime, time

import pytest
from flask import g

from system.db.database import db


# ── Helpers ──────────────────────────────────────────────────────────────────

def _setup_g(ws):
    """Set g.organization_id and g.workspace_id from seeded_workspace."""
    g.organization_id = ws["organization"].id
    g.workspace_id = ws["workspace"].id


def _make_channel(member_id):
    from modules.base.updates.models.channel import UpdateChannel

    return UpdateChannel.create(
        name="test-channel",
        description="Test channel",
        created_by_id=member_id,
    )


def _make_template(post_type="update"):
    from modules.base.updates.models.template import UpdateTemplate

    template = UpdateTemplate(
        workspace_id=g.workspace_id,
        post_type=post_type,
        name=f"Test {post_type.title()}",
        description=f"Test {post_type} template",
        fields=[{"key": "body", "type": "text", "label": "Body"}],
        is_active=True,
    )
    db.session.add(template)
    db.session.commit()
    return template


def _make_post(ws, channel=None):
    from modules.base.updates.models.post import UpdatePost

    template = _make_template()
    return UpdatePost.create(
        template=template,
        member_id=ws["membership"].id,
        payload={"body": "Test post"},
        channel_id=channel.id if channel else None,
    )


def _make_second_member(ws):
    import uuid as _uuid
    from modules.base.core.models.user import User
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace_user import WorkspaceUser

    user2 = User.create(
        email=f"member2-{_uuid.uuid4().hex[:8]}@test.com",
        password="testpass123",
        first_name="Second",
        last_name="Member",
        is_admin=False,
    )
    org_user2 = OrganizationUser.create(
        organization_id=ws["organization"].id,
        user_id=user2.id,
        role="member",
    )
    member2 = WorkspaceUser(
        user_id=user2.id,
        workspace_id=ws["workspace"].id,
        organization_id=ws["organization"].id,
        organization_user_id=org_user2.id,
        role="member",
    )
    db.session.add(member2)
    db.session.commit()
    return member2


# ═════════════════════════════════════════════════════════════════════════════
# UpdateChannel
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestUpdateChannel:
    """Tests for UpdateChannel CRUD, rename, and limits."""

    def test_create_channel(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        channel = UpdateChannel.create(
            name="dev-chat",
            description="Developer chat",
            created_by_id=ws["membership"].id,
        )

        assert channel.id is not None
        assert channel.name == "dev-chat"
        assert channel.description == "Developer chat"
        assert channel.is_private is False

    def test_get_by_name(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        UpdateChannel.create(name="lookup-test", created_by_id=ws["membership"].id)
        found = UpdateChannel.get_by_name("lookup-test")
        assert found is not None
        assert found.name == "lookup-test"

    def test_get_by_id(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.create(name="id-test", created_by_id=ws["membership"].id)
        found = UpdateChannel.get_by_id(ch.id)
        assert found is not None
        assert found.id == ch.id

    def test_get_or_create_default(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.get_or_create_default()
        assert ch.name == "general"

        ch2 = UpdateChannel.get_or_create_default()
        assert ch2.id == ch.id

    def test_delete_channel(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.create(name="deletable", created_by_id=ws["membership"].id)
        cid = ch.id
        result = UpdateChannel.delete_channel(cid)
        assert result is True
        assert UpdateChannel.get_by_id(cid) is None

    def test_delete_nonexistent_returns_false(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        assert UpdateChannel.delete_channel(99999) is False

    def test_rename_channel(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.create(name="old-name", created_by_id=ws["membership"].id)
        ch.rename("new-name")
        assert ch.name == "new-name"

    def test_rename_to_existing_raises(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        UpdateChannel.create(name="existing", created_by_id=ws["membership"].id)
        ch2 = UpdateChannel.create(name="other", created_by_id=ws["membership"].id)

        with pytest.raises(ValueError, match="already exists"):
            ch2.rename("existing")

    def test_is_org_wide_property(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.create(name="ws-scoped", created_by_id=ws["membership"].id)
        assert ch.is_org_wide is False

    def test_create_private_channel(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        ch = UpdateChannel.create(
            name="secret",
            created_by_id=ws["membership"].id,
            is_private=True,
        )
        assert ch.is_private is True

    def test_can_create_channel_limit(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel import UpdateChannel

        ws = seeded_workspace
        _setup_g(ws)

        assert UpdateChannel.can_create_channel() is True


# ═════════════════════════════════════════════════════════════════════════════
# UpdateTemplate
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestUpdateTemplate:
    """Tests for UpdateTemplate creation, fields, and nudge scope."""

    def test_create_template_and_retrieve(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.template import UpdateTemplate

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template("update")
        found = UpdateTemplate.get_by_id(template.id)
        assert found is not None
        assert found.post_type == "update"
        assert found.is_active is True

    def test_fields_property(self, app, db_session, seeded_workspace):

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        assert isinstance(template.fields, list)
        assert len(template.fields) == 1
        assert template.fields[0]["key"] == "body"

    def test_get_for_workspace(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.template import UpdateTemplate

        ws = seeded_workspace
        _setup_g(ws)

        _make_template("update")
        _make_template("board")
        templates = UpdateTemplate.get_for_workspace(post_type="update")
        assert any(t.post_type == "update" for t in templates)

    def test_get_by_name(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.template import UpdateTemplate

        ws = seeded_workspace
        _setup_g(ws)

        _make_template("update")
        found = UpdateTemplate.get_by_name("Test Update")
        assert found is not None
        assert found.name == "Test Update"

    def test_nudge_scope_property_defaults(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.template import UpdateTemplate

        ws = seeded_workspace
        _setup_g(ws)

        template = UpdateTemplate(
            workspace_id=g.workspace_id,
            post_type="update",
            name="Nudge Test",
            fields=[],
            is_active=True,
        )
        db.session.add(template)
        db.session.commit()

        assert template.nudge_scope is None

        template._nudge_scope = {"start": "09:00"}
        db.session.commit()
        scope = template.nudge_scope
        assert scope["start"] == "09:00"
        assert scope["end"] == "18:00"
        assert scope["days"] == [0, 1, 2, 3, 4]


# ═════════════════════════════════════════════════════════════════════════════
# Acknowledgment (UpdatePostAck / DMAck)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestAcknowledgment:
    """Tests for UpdatePostAck and DMAck acknowledgment flows."""

    def test_acknowledge_post(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.acknowledgment import UpdatePostAck

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        result = UpdatePostAck.acknowledge(post.id, ws["membership"].id)
        assert result["current_user_acked"] is True

    def test_acknowledge_idempotent(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.acknowledgment import UpdatePostAck

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        UpdatePostAck.acknowledge(post.id, ws["membership"].id)
        result = UpdatePostAck.acknowledge(post.id, ws["membership"].id)
        assert result["current_user_acked"] is True

    def test_member_acknowledged(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.acknowledgment import UpdatePostAck

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        assert UpdatePostAck.member_acknowledged(post.id, ws["membership"].id) is False
        UpdatePostAck.acknowledge(post.id, ws["membership"].id)
        assert UpdatePostAck.member_acknowledged(post.id, ws["membership"].id) is True

    def test_get_for_post_returns_dict(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.acknowledgment import UpdatePostAck

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        result = UpdatePostAck.get_for_post(post.id, ws["membership"].id)
        assert "acked" in result
        assert "pending" in result
        assert "all_acked" in result

    def test_dm_ack_create(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.acknowledgment import DMAck
        from modules.base.updates.models.dm import DMThread, DM

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        msg = DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Hello")

        ack = DMAck(message_id=msg.id, member_id=member2.id)
        db.session.add(ack)
        db.session.commit()

        assert ack.id is not None
        assert ack.message_id == msg.id


# ═════════════════════════════════════════════════════════════════════════════
# Area
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestArea:
    """Tests for UpdateArea CRUD, soft delete, and reorder."""

    def test_create_area(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea

        ws = seeded_workspace
        _setup_g(ws)

        area = UpdateArea.create(name="Infrastructure", color="#ff0000")
        assert area.id is not None
        assert area.name == "Infrastructure"
        assert area.color == "#ff0000"
        assert area.is_active is True

    def test_get_by_id(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea

        ws = seeded_workspace
        _setup_g(ws)

        area = UpdateArea.create(name="Sales")
        found = UpdateArea.get_by_id(area.id)
        assert found is not None
        assert found.name == "Sales"

    def test_update_area(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea

        ws = seeded_workspace
        _setup_g(ws)

        area = UpdateArea.create(name="Original")
        area.update(name="Updated", color="#00ff00")
        assert area.name == "Updated"
        assert area.color == "#00ff00"

    def test_soft_delete_area(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea

        ws = seeded_workspace
        _setup_g(ws)

        area = UpdateArea.create(name="Temp")
        area.delete()
        assert area.is_active is False

        active = UpdateArea.get_all()
        assert all(a.id != area.id for a in active)

    def test_max_areas_limit(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea, MAX_AREAS_PER_WORKSPACE

        ws = seeded_workspace
        _setup_g(ws)

        for i in range(MAX_AREAS_PER_WORKSPACE):
            UpdateArea.create(name=f"Area {i}")

        with pytest.raises(ValueError, match="Maximum"):
            UpdateArea.create(name="One Too Many")

    def test_reorder_areas(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.area import UpdateArea

        ws = seeded_workspace
        _setup_g(ws)

        a1 = UpdateArea.create(name="First")
        a2 = UpdateArea.create(name="Second")

        UpdateArea.reorder([a2.id, a1.id])
        db.session.refresh(a1)
        db.session.refresh(a2)
        assert a2.sort_order < a1.sort_order


# ═════════════════════════════════════════════════════════════════════════════
# ChannelReadState
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestChannelReadState:
    """Tests for channel read state tracking and unread counts."""

    def test_mark_channel_read(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel_read_state import UpdateChannelReadState

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        _make_post(ws, channel=channel)

        result = UpdateChannelReadState.mark_channel_read(ws["membership"].id, channel.id)
        assert result is True

        count = UpdateChannelReadState.get_unread_count(ws["membership"].id, channel.id)
        assert count == 0

    def test_unread_count_after_new_post(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel_read_state import UpdateChannelReadState
        from modules.base.updates.models.post import UpdatePost

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        _make_post(ws, channel=channel)
        UpdateChannelReadState.mark_channel_read(ws["membership"].id, channel.id)

        template = _make_template()
        UpdatePost.create(
            template=template,
            member_id=ws["membership"].id,
            payload={"body": "New post"},
            channel_id=channel.id,
        )

        # Clear cache on g
        if hasattr(g, "_channel_unread_cache"):
            delattr(g, "_channel_unread_cache")

        count = UpdateChannelReadState.get_unread_count(ws["membership"].id, channel.id)
        assert count == 1

    def test_mark_post_read(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.channel_read_state import UpdateChannelReadState

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        post = _make_post(ws, channel=channel)

        result = UpdateChannelReadState.mark_post_read(ws["membership"].id, post.id)
        assert result is True


# ═════════════════════════════════════════════════════════════════════════════
# DirectMessage (DM)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDirectMessage:
    """Tests for DM threads, messages, read state, and reactions."""

    def test_create_dm_thread_and_message(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread, DM

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        assert thread.id is not None
        assert thread.has_member(ws["membership"].id) is True
        assert thread.has_member(member2.id) is True

        msg = DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Hello!")
        assert msg.id is not None
        assert msg.content == "Hello!"

    def test_get_or_create_is_idempotent(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        t1 = DMThread.get_or_create(ws["membership"].id, member2.id)
        t2 = DMThread.get_or_create(member2.id, ws["membership"].id)
        assert t1.id == t2.id

    def test_mark_read(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread, DM

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        msg = DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Read me")

        assert msg.read_at is None
        DM.mark_read(msg.id)
        db.session.refresh(msg)
        assert msg.read_at is not None

    def test_mark_thread_read(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread, DM

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Msg 1")
        DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Msg 2")

        count = DM.mark_thread_read(thread.id, member2.id)
        assert count == 2

    def test_delete_message(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread, DM

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        msg = DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="Delete me")

        assert DM.delete_message(msg.id) is True
        assert DM.get_by_id(msg.id) is None

    def test_get_other_member(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        other = thread.get_other_member(ws["membership"].id)
        assert other.id == member2.id

    def test_dm_reaction_toggle(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.dm import DMThread, DM, DMReaction

        ws = seeded_workspace
        _setup_g(ws)

        member2 = _make_second_member(ws)
        thread = DMThread.get_or_create(ws["membership"].id, member2.id)
        msg = DM.create(thread_id=thread.id, member_id=ws["membership"].id, content="React")

        added, count = DMReaction.toggle(msg.id, member2.id, "thumbsup")
        assert added is True
        assert count == 1

        removed, count = DMReaction.toggle(msg.id, member2.id, "thumbsup")
        assert removed is False
        assert count == 0


# ═════════════════════════════════════════════════════════════════════════════
# Event
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestEvent:
    """Tests for Event CRUD, holiday population, and date range queries."""

    def test_create_event(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(
            title="All Hands",
            scheduled_date=date.today(),
            is_all_day=True,
        )
        assert event.id is not None
        assert event.title == "All Hands"
        assert event.is_all_day is True

    def test_event_with_times(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(
            title="Meeting",
            scheduled_date=date.today(),
            scheduled_start_time=time(14, 0),
            scheduled_end_time=time(15, 0),
            is_all_day=False,
            location="Room A",
        )
        assert event.location == "Room A"
        assert "14" in event.display_time or "2:" in event.display_time

    def test_get_by_id(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(title="Find Me", scheduled_date=date.today())
        found = Event.get_by_id(event.id)
        assert found is not None

    def test_update_event(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(title="Old Title", scheduled_date=date.today())
        event.update(title="New Title")
        assert event.title == "New Title"

    def test_delete_event(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(title="Temp", scheduled_date=date.today())
        eid = event.id
        event.delete()
        assert Event.get_by_id(eid) is None

    def test_display_time_all_day(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        event = Event.create(title="All Day", scheduled_date=date.today(), is_all_day=True)
        assert event.display_time == "All day"

    def test_populate_holidays(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        holidays = [
            (date(2026, 1, 1), "New Year"),
            (date(2026, 7, 4), "Independence Day"),
        ]
        count = Event.populate_holidays(holidays)
        assert count == 2

        count2 = Event.populate_holidays(holidays)
        assert count2 == 0

    def test_get_for_date_range(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.event import Event

        ws = seeded_workspace
        _setup_g(ws)

        Event.create(title="Today", scheduled_date=date.today())
        events = Event.get_for_date_range(date.today(), date.today())
        assert len(events) >= 1


# ═════════════════════════════════════════════════════════════════════════════
# UpdateFollow
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestUpdateFollow:
    """Tests for UpdateFollow toggle and batch follow lookups."""

    def test_toggle_follow(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.follow import UpdateFollow

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        is_following, data = UpdateFollow.toggle("channel", channel.id, ws["membership"].id)
        assert is_following is True
        assert data is not None

        is_following, data = UpdateFollow.toggle("channel", channel.id, ws["membership"].id)
        assert is_following is False
        assert data is None

    def test_is_following(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.follow import UpdateFollow

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        assert UpdateFollow.is_following("channel", channel.id, ws["membership"].id) is False
        UpdateFollow.toggle("channel", channel.id, ws["membership"].id)
        assert UpdateFollow.is_following("channel", channel.id, ws["membership"].id) is True

    def test_get_followed_ids(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.follow import UpdateFollow

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        UpdateFollow.toggle("channel", channel.id, ws["membership"].id)

        ids = UpdateFollow.get_followed_ids("channel", ws["membership"].id)
        assert channel.id in ids

    def test_get_followed_ids_batch(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.follow import UpdateFollow

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        UpdateFollow.toggle("status_template", template.id, ws["membership"].id)

        result = UpdateFollow.get_followed_ids_batch(
            ["status_template", "channel"], ws["membership"].id
        )
        assert template.id in result["status_template"]


# ═════════════════════════════════════════════════════════════════════════════
# NudgeLog
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestNudgeLog:
    """Tests for nudge logging, completion, and dismissal."""

    def test_log_nudge(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog, NudgeStatus

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        log = UpdateNudgeLog.log_nudge(template.id, ws["user"].id)
        assert log.id is not None
        assert log.status == NudgeStatus.SENT.value

    def test_was_nudged_today(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        assert UpdateNudgeLog.was_nudged_today(template.id, ws["user"].id, today_start) is False

        UpdateNudgeLog.log_nudge(template.id, ws["user"].id)
        db.session.commit()

        assert UpdateNudgeLog.was_nudged_today(template.id, ws["user"].id, today_start) is True

    def test_mark_completed(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog, NudgeStatus

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        log = UpdateNudgeLog.log_nudge(template.id, ws["user"].id)
        db.session.commit()

        UpdateNudgeLog.mark_completed(template.id, ws["user"].id)
        db.session.refresh(log)
        assert log.status == NudgeStatus.COMPLETED.value
        assert log.responded_at is not None

    def test_dismiss_nudge(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        log = UpdateNudgeLog.log_nudge(template.id, ws["user"].id)
        db.session.commit()

        log.dismiss()
        assert log.dismissed is True

    def test_respond_to_nudge(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        log = UpdateNudgeLog.log_nudge(template.id, ws["user"].id)
        db.session.commit()

        log.respond("on_track")
        assert log.response_value == "on_track"
        assert log.responded_at is not None

    def test_log_completed_directly(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.nudge_log import UpdateNudgeLog, NudgeStatus

        ws = seeded_workspace
        _setup_g(ws)

        template = _make_template()
        log = UpdateNudgeLog.log_completed(template.id, ws["user"].id)
        db.session.commit()
        assert log.status == NudgeStatus.COMPLETED.value


# ═════════════════════════════════════════════════════════════════════════════
# PostReaction
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestPostReaction:
    """Tests for post reaction toggling and aggregation."""

    def test_toggle_reaction(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.post_reaction import UpdatePostReaction

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        added, count = UpdatePostReaction.toggle(post.id, ws["membership"].id, "thumbsup")
        assert added is True
        assert count == 1

    def test_toggle_removes_reaction(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.post_reaction import UpdatePostReaction

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        UpdatePostReaction.toggle(post.id, ws["membership"].id, "thumbsup")
        removed, count = UpdatePostReaction.toggle(post.id, ws["membership"].id, "thumbsup")
        assert removed is False
        assert count == 0

    def test_member_reacted(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.post_reaction import UpdatePostReaction

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        assert UpdatePostReaction.member_reacted(post.id, ws["membership"].id, "fire") is False
        UpdatePostReaction.toggle(post.id, ws["membership"].id, "fire")
        assert UpdatePostReaction.member_reacted(post.id, ws["membership"].id, "fire") is True

    def test_get_for_message(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.post_reaction import UpdatePostReaction

        ws = seeded_workspace
        _setup_g(ws)

        post = _make_post(ws)
        UpdatePostReaction.toggle(post.id, ws["membership"].id, "thumbsup")
        reactions = UpdatePostReaction.get_for_message(post.id)
        assert "thumbsup" in reactions
        assert reactions["thumbsup"]["count"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# UpdateWebhook
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestUpdateWebhook:
    """Tests for UpdateWebhook token management and ten-four toggle."""

    def test_create_webhook(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.webhook import UpdateWebhook

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        webhook = UpdateWebhook.create(
            created_by_id=ws["membership"].id,
            channel_id=channel.id,
        )
        assert webhook.id is not None
        assert webhook.token is not None
        assert len(webhook.token) == 8
        assert webhook.channel_id == channel.id
        assert webhook.is_active is True

    def test_get_by_token(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.webhook import UpdateWebhook

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        webhook = UpdateWebhook.create(
            created_by_id=ws["membership"].id,
            channel_id=channel.id,
        )
        found = UpdateWebhook.get_by_token(webhook.token)
        assert found is not None
        assert found.id == webhook.id

    def test_regenerate_token(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.webhook import UpdateWebhook

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        webhook = UpdateWebhook.create(
            created_by_id=ws["membership"].id,
            channel_id=channel.id,
        )
        old_token = webhook.token
        new_token = webhook.regenerate_token()
        assert new_token != old_token

    def test_delete_webhook(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.webhook import UpdateWebhook

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        webhook = UpdateWebhook.create(
            created_by_id=ws["membership"].id,
            channel_id=channel.id,
        )
        assert UpdateWebhook.delete_webhook(webhook.id) is True
        assert UpdateWebhook.delete_webhook(webhook.id) is False

    def test_toggle_ten_four(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.webhook import UpdateWebhook

        ws = seeded_workspace
        _setup_g(ws)

        channel = _make_channel(ws["membership"].id)
        webhook = UpdateWebhook.create(
            created_by_id=ws["membership"].id,
            channel_id=channel.id,
        )
        assert webhook.enable_ten_four is False
        result = webhook.toggle_ten_four()
        assert result is True
        result = webhook.toggle_ten_four()
        assert result is False


# ═════════════════════════════════════════════════════════════════════════════
# WeekReview
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestWeekReview:
    """Tests for UpdateWeekReview creation and retrieval."""

    def test_get_or_create_for_week(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.week_review import UpdateWeekReview

        ws = seeded_workspace
        _setup_g(ws)

        monday = date(2026, 6, 1)
        review = UpdateWeekReview.get_or_create_for_week(monday)
        assert review.id is not None
        assert review.week_start == monday
        assert review.status == "draft"

        review2 = UpdateWeekReview.get_or_create_for_week(monday)
        assert review2.id == review.id

    def test_get_by_id(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.week_review import UpdateWeekReview

        ws = seeded_workspace
        _setup_g(ws)

        review = UpdateWeekReview.get_or_create_for_week(date(2026, 6, 1))
        found = UpdateWeekReview.get_by_id(review.id)
        assert found is not None

    def test_get_all(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.week_review import UpdateWeekReview

        ws = seeded_workspace
        _setup_g(ws)

        UpdateWeekReview.get_or_create_for_week(date(2026, 6, 1))
        UpdateWeekReview.get_or_create_for_week(date(2026, 6, 8))
        reviews = UpdateWeekReview.get_all()
        assert len(reviews) >= 2


# ═════════════════════════════════════════════════════════════════════════════
# WeeklyPlan
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestWeeklyPlan:
    """Tests for WeeklyPlan CRUD, goals, and completion tracking."""

    def test_create_plan(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(
            week_number=23,
            year=2026,
            title="Launch Prep",
            created_by_id=ws["membership"].id,
        )
        assert plan.id is not None
        assert plan.title == "Launch Prep"
        assert plan.week_number == 23

    def test_duplicate_plan_raises(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan

        ws = seeded_workspace
        _setup_g(ws)

        WeeklyPlan.create(week_number=24, year=2026)
        with pytest.raises(ValueError, match="already exists"):
            WeeklyPlan.create(week_number=24, year=2026)

    def test_get_by_week(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan

        ws = seeded_workspace
        _setup_g(ws)

        WeeklyPlan.create(week_number=25, year=2026)
        found = WeeklyPlan.get_by_week(2026, 25)
        assert found is not None

    def test_update_plan(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=26, year=2026, title="Old")
        plan.update(title="New")
        assert plan.title == "New"

    def test_display_name(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=27, year=2026, title="Sprint")
        assert "Week 27" in plan.display_name
        assert "Sprint" in plan.display_name

    def test_add_goal_and_toggle(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=28, year=2026)
        goal = WeeklyPlanGoal.add_to_plan(plan.id, "Ship feature X")
        assert goal.id is not None
        assert goal.text == "Ship feature X"
        assert goal.is_complete is False

        goal.toggle_complete()
        assert goal.is_complete is True

    def test_goal_update_text(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=29, year=2026)
        goal = WeeklyPlanGoal.add_to_plan(plan.id, "Draft")
        goal.update_text("Final Version")
        assert goal.text == "Final Version"

    def test_goal_delete(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=30, year=2026)
        goal = WeeklyPlanGoal.add_to_plan(plan.id, "Temp Goal")
        gid = goal.id
        goal.delete()
        assert db.session.get(WeeklyPlanGoal, gid) is None

    def test_goals_complete_count(self, app, db_session, seeded_workspace):
        from modules.base.updates.models.weekly_plan import WeeklyPlan, WeeklyPlanGoal

        ws = seeded_workspace
        _setup_g(ws)

        plan = WeeklyPlan.create(week_number=31, year=2026)
        g1 = WeeklyPlanGoal.add_to_plan(plan.id, "Goal 1")
        WeeklyPlanGoal.add_to_plan(plan.id, "Goal 2")
        g1.toggle_complete()

        assert plan.goals_complete_count == 1
        assert plan.goals_total_count == 2
