# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - User Model Integration Tests
#
# Tests for User model database operations.
# -----------------------------------------------------------------------------

import pytest


@pytest.mark.integration
class TestUserModel:
    """Tests for User model CRUD operations."""

    def test_create_user(self, app, db_session, user_data):
        """Test creating a new user."""
        from modules.base.core.models.user import User

        with app.app_context():
            user = User.create(
                email=user_data["email"],
                password=user_data["password"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
            )

            assert user.id is not None
            assert user.email == user_data["email"]
            assert user.first_name == user_data["first_name"]
            assert user.last_name == user_data["last_name"]
            assert user.check_password(user_data["password"])

    def test_create_admin_user(self, app, db_session, admin_data):
        """Test creating an admin user via workspace membership."""
        import uuid
        from flask import g
        from modules.base.core.models.user import User
        from modules.base.core.models.organization import Organization
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.workspace_user import WorkspaceUser
        from system.db.database import db

        with app.app_context():
            user = User.create(
                email=admin_data["email"],
                password=admin_data["password"],
                first_name=admin_data["first_name"],
                last_name=admin_data["last_name"],
            )

            # is_admin is derived from workspace/org membership, not a User column
            org = Organization(
                id=uuid.uuid4(), name="Admin Org",
                slug=f"admin-org-{uuid.uuid4().hex[:6]}",
            )
            db.session.add(org)
            db.session.flush()
            g.organization_id = org.id

            ws = Workspace(
                id=uuid.uuid4(), slug=f"admin-ws-{uuid.uuid4().hex[:6]}",
                name="Admin WS", organization_id=org.id,
            )
            db.session.add(ws)
            db.session.flush()
            g.workspace_id = ws.id

            org_user = OrganizationUser.create(
                organization_id=org.id, user_id=user.id, role="admin",
            )

            member = WorkspaceUser(
                user_id=user.id, workspace_id=ws.id,
                organization_id=org.id, organization_user_id=org_user.id,
                role="admin",
            )
            db.session.add(member)
            db.session.commit()

            assert user.is_admin is True

    def test_get_user_by_email(self, app, db_session, test_user):
        """Test retrieving user by email."""
        from modules.base.core.models.user import User

        with app.app_context():
            found = User.get_by_email(test_user.email)
            assert found is not None
            assert found.id == test_user.id

    def test_get_user_by_id(self, app, db_session, test_user):
        """Test retrieving user by ID."""
        from modules.base.core.models.user import User

        with app.app_context():
            found = User.get_by_id(test_user.id)
            assert found is not None
            assert found.email == test_user.email

    def test_password_hashing(self, app, db_session, user_data):
        """Test that passwords are hashed, not stored in plaintext."""
        from modules.base.core.models.user import User

        with app.app_context():
            user = User.create(
                email=user_data["email"],
                password=user_data["password"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
            )

            # Password should not be stored in plaintext
            assert user.password_hash != user_data["password"]
            # But should verify correctly
            assert user.check_password(user_data["password"])
            # Wrong password should fail
            assert not user.check_password("wrongpassword")

    def test_user_full_name(self, app, db_session, test_user):
        """Test user full_name property."""
        with app.app_context():
            assert test_user.full_name == "Test User"

    def test_user_avatar_initials(self, app, db_session, test_user):
        """Test user avatar_initials property."""
        with app.app_context():
            assert test_user.avatar_initials == "TU"

    def test_duplicate_email_prevention(self, app, db_session, test_user):
        """Test that duplicate emails are prevented."""
        from modules.base.core.models.user import User
        from sqlalchemy.exc import IntegrityError

        with app.app_context():
            with pytest.raises(IntegrityError):
                User.create(
                    email=test_user.email,  # Same email as test_user
                    password="anotherpass",
                    first_name="Another",
                    last_name="User",
                )


@pytest.mark.integration
class TestUserAuthentication:
    """Tests for User authentication methods."""

    def test_password_reset_token(self, app, db_session, test_user):
        """Test password reset token generation and validation."""
        with app.app_context():
            token = test_user.generate_password_reset_token()

            assert token is not None
            assert test_user.is_password_reset_token_valid(token)
            assert not test_user.is_password_reset_token_valid("invalid-token")

    def test_magic_link_token(self, app, db_session, test_user):
        """Test magic link token generation and validation."""
        with app.app_context():
            token = test_user.generate_magic_link_token()

            assert token is not None
            assert test_user.is_magic_link_valid(token)
            assert not test_user.is_magic_link_valid("invalid-token")

    def test_clear_magic_link_token(self, app, db_session, test_user):
        """Test clearing magic link token."""
        with app.app_context():
            token = test_user.generate_magic_link_token()
            test_user.clear_magic_link_token()

            assert not test_user.is_magic_link_valid(token)
