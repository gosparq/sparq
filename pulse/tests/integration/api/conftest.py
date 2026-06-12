# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - API Test Fixtures
#
# JWT-specific fixtures for mobile API integration tests.
# -----------------------------------------------------------------------------

import uuid

import pytest


@pytest.fixture
def api_workspace(app, db_session):
    """Create a workspace with organization for API tests."""
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.workspace import Workspace
    from system.db.database import db

    with app.app_context():
        org = Organization(
            id=uuid.uuid4(), name="API Test Org", slug=f"api-test-{uuid.uuid4().hex[:8]}",
        )
        db.session.add(org)
        db.session.flush()

        ws = Workspace(
            id=uuid.uuid4(), slug=f"api-ws-{uuid.uuid4().hex[:8]}",
            name="API Test Workspace", organization_id=org.id,
        )
        db.session.add(ws)
        db.session.commit()
        yield {"organization": org, "workspace": ws}


@pytest.fixture
def api_user(app, db_session, api_workspace):
    """Create a test user for API tests with workspace membership."""
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    with app.app_context():
        user = User.create(
            email="apiuser@example.com",
            password="ApiPass123!",
            first_name="API",
            last_name="User",
            is_admin=False,
        )

        org_user = OrganizationUser.create(
            organization_id=api_workspace["organization"].id,
            user_id=user.id,
            role="member",
        )

        member = WorkspaceUser(
            user_id=user.id,
            workspace_id=api_workspace["workspace"].id,
            organization_id=api_workspace["organization"].id,
            organization_user_id=org_user.id,
            role="member",
        )
        db.session.add(member)
        db.session.commit()
        yield user


@pytest.fixture
def api_admin(app, db_session, api_workspace):
    """Create an admin user for API tests with workspace membership."""
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    with app.app_context():
        user = User.create(
            email="apiadmin@example.com",
            password="AdminPass123!",
            first_name="API",
            last_name="Admin",
            is_admin=True,
        )

        org_user = OrganizationUser.create(
            organization_id=api_workspace["organization"].id,
            user_id=user.id,
            role="admin",
        )

        member = WorkspaceUser(
            user_id=user.id,
            workspace_id=api_workspace["workspace"].id,
            organization_id=api_workspace["organization"].id,
            organization_user_id=org_user.id,
            role="admin",
        )
        db.session.add(member)
        db.session.commit()
        yield user


@pytest.fixture
def auth_token(app, api_user):
    """Generate a valid JWT access token for the test user."""
    with app.app_context():
        from system.api.jwt import create_access_token
        token, _ = create_access_token(api_user.id)
        return token


@pytest.fixture
def admin_auth_token(app, api_admin):
    """Generate a valid JWT access token for the admin user."""
    with app.app_context():
        from system.api.jwt import create_access_token
        token, _ = create_access_token(api_admin.id)
        return token


@pytest.fixture
def auth_headers(auth_token):
    """Authorization headers with a valid Bearer token."""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture
def admin_auth_headers(admin_auth_token):
    """Authorization headers with a valid admin Bearer token."""
    return {"Authorization": f"Bearer {admin_auth_token}", "Content-Type": "application/json"}


@pytest.fixture
def refresh_token(app, api_user):
    """Generate a valid refresh token for the test user."""
    with app.app_context():
        from system.api.jwt import create_refresh_token
        return create_refresh_token(api_user.id, device_info="test-device")
