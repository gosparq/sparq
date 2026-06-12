# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Project Model Integration Tests
#
# Tests for Project model database operations.
# -----------------------------------------------------------------------------


import pytest
from flask import g

from system.db.database import db


def _make_second_member(ws):
    """Create a second workspace member for co-owner/follower tests."""
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


@pytest.mark.integration
class TestProjectCreate:
    """Tests for Project creation."""

    def test_create_project(self, app, db_session, seeded_workspace):
        """Test basic project creation."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Test Project",
            created_by_id=ws["membership"].id,
            description="A test project",
            owner_id=ws["membership"].id,
            create_channel=False,
        )

        assert project.id is not None
        assert project.name == "Test Project"
        assert project.description == "A test project"
        assert project.owner_id == ws["membership"].id
        assert project.created_by_id == ws["membership"].id

    def test_create_project_default_status(self, app, db_session, seeded_workspace):
        """Test project gets default status on creation."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Status Project",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        # Default status should be either "current" or whatever ProjectStatus.get_default() returns
        assert project.status is not None
        assert project.status in Project.VALID_STATUSES

    def test_create_project_with_channel(self, app, db_session, seeded_workspace):
        """Test project creation auto-creates a channel."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Channeled Project",
            created_by_id=ws["membership"].id,
            create_channel=True,
        )

        assert project.channel_id is not None

    def test_create_project_name_truncated(self, app, db_session, seeded_workspace):
        """Test project name is truncated to 200 chars."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        long_name = "A" * 300
        project = Project.create(
            name=long_name,
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        assert len(project.name) == 200

    def test_create_private_project(self, app, db_session, seeded_workspace):
        """Test creating a private project."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Secret Project",
            created_by_id=ws["membership"].id,
            create_channel=False,
            is_private=True,
        )

        assert project.is_private is True

    def test_create_project_with_color_and_emoji(self, app, db_session, seeded_workspace):
        """Test project creation with color and emoji."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Colorful",
            created_by_id=ws["membership"].id,
            create_channel=False,
            color="#ff5733",
            emoji="🚀",
        )

        assert project.color == "#ff5733"
        assert project.emoji == "🚀"


@pytest.mark.integration
class TestProjectArchiveRestore:
    """Tests for Project archive and restore."""

    def test_archive_project(self, app, db_session, seeded_workspace):
        """Test archiving a project sets archived status and timestamp."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="To Archive",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        assert project.archived_at is None

        project.archive()

        assert project.archived_at is not None
        assert project.is_archived is True

    def test_unarchive_project(self, app, db_session, seeded_workspace):
        """Test unarchiving restores the project to default status."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Restore Me",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        project.archive()
        assert project.is_archived is True

        project.unarchive()

        assert project.archived_at is None
        assert project.is_archived is False

    def test_is_closed_matches_archive_status(self, app, db_session, seeded_workspace):
        """Test is_closed returns True only when project is archived."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Close Check",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        assert project.is_closed is False

        project.archive()
        assert project.is_closed is True


@pytest.mark.integration
class TestProjectStatusTracking:
    """Tests for Project status transitions."""

    def test_set_status_valid(self, app, db_session, seeded_workspace):
        """Test setting a valid status."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Status Test",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        project.set_status(Project.STATUS_ON_HOLD)
        assert project.status == Project.STATUS_ON_HOLD

    def test_set_status_invalid_raises(self, app, db_session, seeded_workspace):
        """Test setting an invalid status raises ValueError."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Invalid Status",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        with pytest.raises(ValueError, match="Invalid status"):
            project.set_status("nonexistent_status")

    def test_status_label_property(self, app, db_session, seeded_workspace):
        """Test status_label returns a human-readable label."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Label Test",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        label = project.status_label
        assert isinstance(label, str)
        assert len(label) > 0

    def test_status_color_property(self, app, db_session, seeded_workspace):
        """Test status_color returns a color string."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Color Test",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        color = project.status_color
        assert isinstance(color, str)
        assert color.startswith("#")


@pytest.mark.integration
class TestProjectUpdate:
    """Tests for Project.update()."""

    def test_update_project_fields(self, app, db_session, seeded_workspace):
        """Test updating project fields."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Original Name",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        project.update(
            name="Updated Name",
            description="New description",
            color="#000000",
        )

        assert project.name == "Updated Name"
        assert project.description == "New description"
        assert project.color == "#000000"


@pytest.mark.integration
class TestProjectQueries:
    """Tests for Project query methods."""

    def test_get_by_id(self, app, db_session, seeded_workspace):
        """Test get_by_id returns the correct project."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        project = Project.create(
            name="Find Me",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        found = Project.get_by_id(project.id)
        assert found is not None
        assert found.id == project.id
        assert found.name == "Find Me"

    def test_get_by_id_not_found(self, app, db_session, seeded_workspace):
        """Test get_by_id returns None for nonexistent project."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        assert Project.get_by_id(99999) is None

    def test_get_active_for_workspace(self, app, db_session, seeded_workspace):
        """Test get_active_for_workspace excludes archived projects."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        active = Project.create(
            name="Active Project",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        archived = Project.create(
            name="Archived Project",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        archived.archive()

        projects = Project.get_active_for_workspace()
        project_ids = [p.id for p in projects]
        assert active.id in project_ids
        assert archived.id not in project_ids

    def test_get_archived_for_workspace(self, app, db_session, seeded_workspace):
        """Test get_archived_for_workspace returns only archived projects."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        Project.create(
            name="Active",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        archived = Project.create(
            name="Archived",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        archived.archive()

        projects = Project.get_archived_for_workspace()
        project_ids = [p.id for p in projects]
        assert archived.id in project_ids


@pytest.mark.integration
class TestProjectCoOwners:
    """Tests for Project co-owner management."""

    def test_add_co_owner(self, app, db_session, seeded_workspace):
        """Test adding a co-owner."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Co-owned",
            created_by_id=ws["membership"].id,
            owner_id=ws["membership"].id,
            create_channel=False,
        )

        result = project.add_co_owner(member2.id)
        assert result is True
        assert project.is_co_owner(member2.id) is True

    def test_add_co_owner_idempotent(self, app, db_session, seeded_workspace):
        """Test adding the same co-owner twice returns False."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Idempotent Co-own",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        assert project.add_co_owner(member2.id) is True
        assert project.add_co_owner(member2.id) is False

    def test_remove_co_owner(self, app, db_session, seeded_workspace):
        """Test removing a co-owner."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Remove Co-own",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        project.add_co_owner(member2.id)

        result = project.remove_co_owner(member2.id)
        assert result is True
        assert project.is_co_owner(member2.id) is False

    def test_is_owner_or_co_owner(self, app, db_session, seeded_workspace):
        """Test is_owner_or_co_owner returns True for owner and co-owner."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Owner Check",
            created_by_id=ws["membership"].id,
            owner_id=ws["membership"].id,
            create_channel=False,
        )
        project.add_co_owner(member2.id)

        assert project.is_owner_or_co_owner(ws["membership"].id) is True
        assert project.is_owner_or_co_owner(member2.id) is True


@pytest.mark.integration
class TestProjectFollowers:
    """Tests for Project follower management."""

    def test_add_follower(self, app, db_session, seeded_workspace):
        """Test adding a follower."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Followed",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        result = project.add_follower(member2.id)
        assert result is True
        assert project.is_follower(member2.id) is True

    def test_add_follower_idempotent(self, app, db_session, seeded_workspace):
        """Test adding the same follower twice returns False."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Follow Idempotent",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )

        assert project.add_follower(member2.id) is True
        assert project.add_follower(member2.id) is False

    def test_remove_follower(self, app, db_session, seeded_workspace):
        """Test removing a follower."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Unfollow",
            created_by_id=ws["membership"].id,
            create_channel=False,
        )
        project.add_follower(member2.id)

        result = project.remove_follower(member2.id)
        assert result is True
        assert project.is_follower(member2.id) is False

    def test_can_follow_public_project(self, app, db_session, seeded_workspace):
        """Test any member can follow a public project."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Public Follow",
            created_by_id=ws["membership"].id,
            create_channel=False,
            is_private=False,
        )

        assert project.can_follow(member2.id) is True

    def test_can_follow_private_project_owner_only(self, app, db_session, seeded_workspace):
        """Test only owner/co-owner/creator can follow a private project."""
        from modules.base.projects.models.project import Project

        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id

        member2 = _make_second_member(ws)
        project = Project.create(
            name="Private Follow",
            created_by_id=ws["membership"].id,
            owner_id=ws["membership"].id,
            create_channel=False,
            is_private=True,
        )

        assert project.can_follow(ws["membership"].id) is True
        assert project.can_follow(member2.id) is False
