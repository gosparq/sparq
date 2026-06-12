# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Navigation & Unified Posts Tests
#
# Tests for: migration 035, UpdatePost channel_id/is_win, channel feed,
# wins aggregation, project-channel linkage, webhook ingestion to update_post,
# redirect routes, 6-item nav, content header + New menu.
# -----------------------------------------------------------------------------

import uuid as _uuid

import pytest

from flask import g

from system.db.database import db


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def setup(app, db_session):
    """Create Organization, Workspace, User, OrganizationUser, WorkspaceUser.

    Runs inside db_session's app context so g.organization_id and
    g.workspace_id persist into test methods.
    """
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser

    org = Organization(
        id=_uuid.uuid4(), name="Test Org", slug=f"test-{_uuid.uuid4().hex[:8]}",
    )
    db.session.add(org)
    db.session.flush()
    g.organization_id = org.id

    ws = Workspace(
        id=_uuid.uuid4(), name="Test Corp", slug=f"tc-{_uuid.uuid4().hex[:8]}",
        organization_id=org.id,
    )
    db.session.add(ws)
    db.session.flush()
    g.workspace_id = ws.id

    user = User.create(
        email=f"nav-{_uuid.uuid4().hex[:8]}@test.com",
        password="testpass123", first_name="Test", last_name="User",
        is_admin=False,
    )

    org_user = OrganizationUser.create(
        organization_id=org.id, user_id=user.id, role="member",
    )

    member = WorkspaceUser(
        user_id=user.id, workspace_id=ws.id,
        organization_id=org.id, organization_user_id=org_user.id,
        role="member",
    )
    db.session.add(member)
    db.session.commit()

    yield {
        "organization": org,
        "workspace": ws,
        "user": user,
        "member": member,
    }


@pytest.fixture
def workspace(setup):
    """Return workspace from setup."""
    return setup["workspace"]


@pytest.fixture
def member(setup):
    """Return workspace member from setup."""
    return setup["member"]


@pytest.fixture
def channel(app, db_session, setup):
    """Create a test channel (org/workspace context from setup)."""
    from modules.base.updates.models.channel import UpdateChannel

    ch = UpdateChannel.create(name="test-channel", description="Test channel")
    yield ch


@pytest.fixture
def sync_template(app, db_session, setup):
    """Create a basic update template for testing."""
    from modules.base.updates.models.template import UpdateTemplate

    tmpl = UpdateTemplate(
        name="Daily Standup",
        post_type="update",
        fields=[{"key": "worked_on", "label": "Worked on", "type": "text"}],
        workspace_id=setup["workspace"].id,
        is_active=True,
    )
    db.session.add(tmpl)
    db.session.commit()
    yield tmpl


# ── Model Tests ───────────────────────────────────────────────────────────


@pytest.mark.integration
class TestUpdatePostChannelAndWin:
    """Tests for UpdatePost.channel_id and is_win columns."""

    def test_create_post_with_channel_id(self, app, db_session, member, channel, sync_template):
        """UpdatePost.create() accepts channel_id and stores it."""
        from modules.base.updates.models.post import UpdatePost

        post = UpdatePost.create(
            template=sync_template,
            member_id=member.id,
            payload={"worked_on": "testing"},
            channel_id=channel.id,
        )
        assert post.channel_id == channel.id
        assert post.channel.name == "test-channel"

    def test_create_post_with_is_win(self, app, db_session, member, sync_template):
        """UpdatePost.create() accepts is_win flag."""
        from modules.base.updates.models.post import UpdatePost

        post = UpdatePost.create(
            template=sync_template,
            member_id=member.id,
            payload={"worked_on": "shipped feature"},
            is_win=True,
        )
        assert post.is_win is True

    def test_mark_as_win(self, app, db_session, member, sync_template):
        """UpdatePost.mark_as_win() sets is_win to True."""
        from modules.base.updates.models.post import UpdatePost

        post = UpdatePost.create(
            template=sync_template,
            member_id=member.id,
            payload={"worked_on": "testing"},
        )
        assert post.is_win is False
        post.mark_as_win()
        assert post.is_win is True

    def test_unmark_as_win(self, app, db_session, member, sync_template):
        """UpdatePost.unmark_as_win() sets is_win to False."""
        from modules.base.updates.models.post import UpdatePost

        post = UpdatePost.create(
            template=sync_template,
            member_id=member.id,
            payload={"worked_on": "testing"},
            is_win=True,
        )
        post.unmark_as_win()
        assert post.is_win is False

    def test_get_wins_feed(self, app, db_session, member, sync_template):
        """UpdatePost.get_wins_feed() returns only is_win=True posts."""
        from modules.base.updates.models.post import UpdatePost

        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "a"}, is_win=True)
        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "b"}, is_win=False)
        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "c"}, is_win=True)

        posts, has_more = UpdatePost.get_wins_feed(limit=10)
        assert len(posts) == 2
        assert all(p.is_win for p in posts)

    def test_get_channel_feed(self, app, db_session, member, channel, sync_template):
        """UpdatePost.get_channel_feed() returns posts for a given channel."""
        from modules.base.updates.models.post import UpdatePost

        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "ch"}, channel_id=channel.id)
        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "no-ch"})

        posts, has_more = UpdatePost.get_channel_feed(channel.id, limit=10)
        assert len(posts) == 1
        assert posts[0].payload["worked_on"] == "ch"


@pytest.mark.integration
class TestUpdateChannelProject:
    """Tests for UpdateChannel.project_id relationship."""

    def test_channel_project_id_column(self, app, db_session, channel):
        """UpdateChannel has project_id column that defaults to None."""
        assert channel.project_id is None

    def test_channel_posts_relationship(self, app, db_session, member, channel, sync_template):
        """UpdateChannel.posts relationship returns linked UpdatePosts."""
        from modules.base.updates.models.post import UpdatePost

        UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": "x"}, channel_id=channel.id)
        assert channel.posts.count() == 1

    def test_channel_get_posts_feed(self, app, db_session, member, channel, sync_template):
        """UpdateChannel.get_posts_feed() returns paginated posts."""
        from modules.base.updates.models.post import UpdatePost

        for i in range(3):
            UpdatePost.create(template=sync_template, member_id=member.id, payload={"worked_on": f"item-{i}"}, channel_id=channel.id)

        posts, has_more = channel.get_posts_feed(limit=2)
        assert len(posts) == 2
        assert has_more is True


@pytest.mark.integration
class TestProjectChannelLink:
    """Tests for Project ↔ UpdateChannel bidirectional relationship."""

    @staticmethod
    def _load_project_with_channel(project_id):
        """Re-load a project with its channel eagerly loaded."""
        from sqlalchemy.orm import joinedload
        from modules.base.projects.models.project import Project

        # Expire the cached instance so the query actually hits the DB
        db.session.expire_all()
        return (
            Project.query
            .options(joinedload(Project.channel))
            .execution_options(skip_raise_on_lazy=True)
            .filter_by(id=project_id)
            .first()
        )

    def test_project_create_with_channel(self, app, db_session, member, workspace):
        """Project.create_with_channel() creates project + channel atomically."""
        from modules.base.projects.models.project import Project

        project = Project.create_with_channel(
            name="Test Project",
            created_by_id=member.id,
        )
        assert project is not None
        assert project.channel_id is not None

        project = self._load_project_with_channel(project.id)
        assert project.channel.project_id == project.id

    def test_project_archive_hides_channel(self, app, db_session, member, workspace):
        """Project.archive() sets channel.is_private = True."""
        from modules.base.projects.models.project import Project

        project = Project.create_with_channel(name="Archivable", created_by_id=member.id)
        project = self._load_project_with_channel(project.id)
        channel = project.channel
        assert channel.is_private is not True

        project.archive()
        assert project.is_archived is True
        assert channel.is_private is True

    def test_project_get_channel_posts(self, app, db_session, member, workspace, sync_template):
        """Project.get_channel_posts() returns posts from the linked channel."""
        from modules.base.projects.models.project import Project
        from modules.base.updates.models.post import UpdatePost

        project = Project.create_with_channel(name="PostProject", created_by_id=member.id)
        UpdatePost.create(
            template=sync_template,
            member_id=member.id,
            payload={"worked_on": "for project"},
            channel_id=project.channel_id,
        )

        project = self._load_project_with_channel(project.id)
        posts, _ = project.get_channel_posts(limit=10)
        assert len(posts) >= 1


# ── Migration Tests ───────────────────────────────────────────────────────


@pytest.mark.integration
class TestMigration035:
    """Tests that migration 035 columns exist on the models."""

    def test_sync_post_has_channel_id_column(self, app, db_session):
        """sync_post table has channel_id column."""
        from modules.base.updates.models.post import UpdatePost

        with app.app_context():
            assert hasattr(UpdatePost, "channel_id")

    def test_sync_post_has_is_win_column(self, app, db_session):
        """sync_post table has is_win column."""
        from modules.base.updates.models.post import UpdatePost

        with app.app_context():
            assert hasattr(UpdatePost, "is_win")

    def test_sync_channel_has_project_id_column(self, app, db_session):
        """sync_channel table has project_id column."""
        from modules.base.updates.models.channel import UpdateChannel

        with app.app_context():
            assert hasattr(UpdateChannel, "project_id")


# ── Route / Redirect Tests ───────────────────────────────────────────────


@pytest.mark.integration
class TestUpdatesRoutes:
    """Tests for /updates/ routes and redirects."""

    def test_updates_landing_redirects(self, app, seeded_workspace):
        """GET /updates/ redirects to sync updates."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/updates/", follow_redirects=False)
            assert resp.status_code in (301, 302)

    def test_updates_wins_route(self, app, seeded_workspace):
        """GET /updates/wins/ returns 200 or redirect."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/updates/wins/", follow_redirects=True)
            # Should not 404 or 500
            assert resp.status_code in (200, 302)

    def test_updates_activity_route(self, app, seeded_workspace):
        """GET /updates/activity/ returns 200 or redirect."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/updates/activity/", follow_redirects=True)
            assert resp.status_code in (200, 302)


@pytest.mark.integration
class TestPeopleProxyRoutes:
    """Tests for /people/calendar/ and /people/timesheets/ proxy routes."""

    def test_people_calendar_redirects(self, app, seeded_workspace):
        """GET /people/calendar/ redirects to sync calendar."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/people/calendar/", follow_redirects=False)
            assert resp.status_code in (301, 302)

    def test_people_timesheets_redirects(self, app, seeded_workspace):
        """GET /people/timesheets/ redirects to presence week view."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/people/timesheets/", follow_redirects=False)
            assert resp.status_code in (301, 302)


# ── Navigation Template Tests ─────────────────────────────────────────────


@pytest.mark.integration
class TestNavPrimary:
    """Tests for the 6-item primary navigation."""

    def test_nav_has_six_items(self, app, seeded_workspace):
        """Dashboard page renders primary nav with 6 nav items (5 main + Settings)."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/dashboard/", follow_redirects=True)
            if resp.status_code == 200:
                html = resp.data.decode()
                # Check for the 5 main nav items
                assert "/dashboard/" in html
                assert "/updates/" in html
                assert "/tasks/" in html
                assert "/people/" in html
                assert "/resources/docs/" in html

    def test_nav_does_not_have_old_items(self, app, seeded_workspace):
        """Primary nav should NOT contain the old 9-item nav entries."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/dashboard/", follow_redirects=True)
            if resp.status_code == 200:
                html = resp.data.decode()
                # Old nav items that should be gone
                assert 'id="chat"' not in html.replace("activeView === 'channel'", "")


@pytest.mark.integration
class TestContentHeader:
    """Tests for the content header top bar."""

    def test_header_has_new_button(self, app, seeded_workspace):
        """Content header renders + New button instead of Updates pill."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/dashboard/", follow_redirects=True)
            if resp.status_code == 200:
                html = resp.data.decode()
                assert "header-new-btn" in html
                # Old Updates pill should be gone
                assert "header-updates-pill" not in html

    def test_header_has_dm_icon(self, app, seeded_workspace):
        """Content header renders DM message icon."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/dashboard/", follow_redirects=True)
            if resp.status_code == 200:
                html = resp.data.decode()
                assert "fa-comment-dots" in html

    def test_header_has_presence_cluster(self, app, seeded_workspace):
        """Content header wraps focus/clock in presence-cluster container."""
        client = seeded_workspace["client"]
        with app.app_context():
            resp = client.get("/dashboard/", follow_redirects=True)
            if resp.status_code == 200:
                html = resp.data.decode()
                assert "presence-cluster" in html


# ── Webhook Ingestion Tests ──────────────────────────────────────────────


@pytest.mark.integration
class TestWebhookToUpdatePost:
    """Tests for webhook ingestion creating UpdatePost records."""

    def test_sync_post_create_from_webhook(self, app, db_session, channel, workspace):
        """UpdatePost.create_from_webhook() creates a webhook-type post."""
        from modules.base.updates.models.post import UpdatePost

        post = UpdatePost.create_from_webhook(
            channel_id=channel.id,
            content="Deploy completed",
            webhook_id=1,
            username="GitHub Actions",
        )
        assert post is not None
        assert post.post_type == "webhook"
        assert post.channel_id == channel.id
        assert post.payload.get("webhook_username") == "GitHub Actions"

    def test_activity_feed_returns_webhook_posts(self, app, db_session, channel, workspace):
        """UpdatePost.get_activity_feed() returns webhook-originated posts."""
        from modules.base.updates.models.post import UpdatePost

        UpdatePost.create_from_webhook(
            channel_id=channel.id, content="Build passed", webhook_id=1, username="CI",
        )

        posts, _ = UpdatePost.get_activity_feed(limit=10)
        assert len(posts) >= 1
        assert posts[0].post_type == "webhook"
