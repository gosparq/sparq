# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Test Configuration
#
# Root conftest.py with shared fixtures for all tests.
# -----------------------------------------------------------------------------

import os
import sys

# Get project root (parent of tests directory)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add project root to path FIRST
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Change to project root so relative imports and file paths work
os.chdir(_project_root)

# Set test environment BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["FLASK_DEBUG"] = "False"
os.environ["SPARQ_RAISE_ON_LAZY"] = "1"

import pytest

from system.middleware.ratelimit import _buckets as _rate_limit_buckets


@pytest.fixture(autouse=True)
def _clear_rate_limit_buckets():
    """Clear rate limit buckets before each test to prevent cross-test contamination."""
    _rate_limit_buckets.clear()
    yield
    _rate_limit_buckets.clear()


# Lazy app creation - only import when fixture is used
_app = None


@pytest.fixture(scope="session")
def app():
    """Create Flask test application with in-memory SQLite database."""
    global _app
    if _app is None:
        from app import create_app
        _app = create_app()
        _app.config.update({
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
        })
    return _app


@pytest.fixture(scope="function")
def db_session(app):
    """Provide a clean database session for each test."""
    from system.db.database import db
    from sqlalchemy import text

    with app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        if db.engine.dialect.name == "sqlite":
            with db.engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys = OFF"))
                for table in reversed(db.metadata.sorted_tables):
                    conn.execute(table.delete())
                conn.execute(text("PRAGMA foreign_keys = ON"))
                conn.commit()
        else:
            with db.engine.connect() as conn:
                conn.execute(text(
                    "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
                ))
                conn.commit()


@pytest.fixture(scope="function")
def client(app):
    """Flask test client for making HTTP requests."""
    return app.test_client()


@pytest.fixture(scope="function")
def test_user(app, db_session):
    """Create a basic test user."""
    from modules.base.core.models.user import User

    with app.app_context():
        user = User.create(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
            is_admin=False,
        )
        yield user


@pytest.fixture(scope="function")
def admin_user(app, db_session):
    """Create an admin test user."""
    from modules.base.core.models.user import User

    with app.app_context():
        user = User.create(
            email="admin@example.com",
            password="adminpass123",
            first_name="Admin",
            last_name="User",
            is_admin=True,
        )
        yield user


@pytest.fixture(scope="function")
def authenticated_client(app, client, test_user):
    """Test client with an authenticated session."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user.id)
        sess["_fresh"] = True
    return client


@pytest.fixture(scope="function")
def admin_client(app, client, admin_user):
    """Test client authenticated as admin user."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["_fresh"] = True
    return client


@pytest.fixture(scope="function")
def seeded_workspace(app, client, db_session):
    """Full workspace context — routes render (200) instead of redirecting (302).

    Creates: Organization → Workspace → User → OrganizationUser → WorkspaceUser.
    Sets session keys so set_workspace_context resolves on every request.
    """
    import uuid as _uuid

    from flask import g

    from modules.base.core.models.organization import Organization
    from modules.base.core.models.organization_user import OrganizationUser
    from modules.base.core.models.workspace import Workspace
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.core.models.user import User
    from system.db.database import db as _db

    with app.app_context():
        org = Organization(
            id=_uuid.uuid4(), name="Test Org", slug=f"test-{_uuid.uuid4().hex[:8]}",
        )
        _db.session.add(org)
        _db.session.flush()
        g.organization_id = org.id

        ts = Workspace(
            id=_uuid.uuid4(), slug=f"ts-{_uuid.uuid4().hex[:8]}",
            name="Test Workspace", organization_id=org.id,
        )
        _db.session.add(ts)
        _db.session.flush()
        g.workspace_id = ts.id

        user = User.create(
            email=f"budget-{_uuid.uuid4().hex[:8]}@test.com",
            password="testpass123", first_name="Budget", last_name="Tester",
            is_admin=True,
        )

        org_user = OrganizationUser.create(
            organization_id=org.id, user_id=user.id, role="admin",
        )

        member = WorkspaceUser(
            user_id=user.id, workspace_id=ts.id,
            organization_id=org.id, organization_user_id=org_user.id,
            role="admin",
        )
        _db.session.add(member)
        _db.session.commit()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True
            sess["active_workspace_id"] = str(ts.id)

        yield {
            "client": client,
            "user": user,
            "workspace": ts,
            "organization": org,
            "membership": member,
        }


@pytest.fixture(scope="function")
def app_with_sample_data(app, db_session, seeded_workspace):
    """Flask app with sample data pre-loaded."""
    from flask import g
    from system.db.seed_sample import seed_sample_data

    with app.app_context():
        ws = seeded_workspace
        g.organization_id = ws["organization"].id
        g.workspace_id = ws["workspace"].id
        seed_sample_data(ws["workspace"].id, ws["user"].id, ws["membership"].id)
        yield app
