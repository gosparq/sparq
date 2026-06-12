# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Instance Setup Wizard Tests
#
# Tests for the first-time setup wizard that bootstraps a fresh sparQ install.
# Covers: fresh-install detection, setup page access, form submission,
# validation, provisioning, and post-setup lockout.
# -----------------------------------------------------------------------------

import time as _time
import uuid
from unittest.mock import patch

import pytest
from flask import g

from system.db.database import db


DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
DEFAULT_WS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_setup_data(app, **overrides):
    """Build valid setup form data with a real form-timing token."""
    from system.middleware.form_timing import generate_form_timestamp

    with app.app_context():
        token = generate_form_timestamp()

    data = {
        "first_name": "Jane",
        "last_name": "Admin",
        "email": "jane@acmecorp.com",
        "password": "Str0ngPass!",
        "company_name": "Acme Corp",
        "color": "violet",
        "timezone": "America/Chicago",
        "default_language": "en",
        "_form_ts": token,
    }
    data.update(overrides)
    return data


def _post_setup(client, app, data=None, mock_breach=True, **overrides):
    """POST to /setup with valid form timing. Returns the response."""
    form_data = data if data is not None else _make_setup_data(app, **overrides)
    with patch("system.middleware.form_timing.time") as mock_time:
        mock_time.time.return_value = _time.time() + 5
        if mock_breach:
            with patch("modules.base.core.controllers.routes.is_breached", return_value=False):
                return client.post("/setup", data=form_data, follow_redirects=False)
        return client.post("/setup", data=form_data, follow_redirects=False)


@pytest.fixture()
def fresh_install(app, db_session):
    """Simulate a fresh sparQ install: default org + workspace, zero users.

    Mirrors what init_database() creates on first boot.
    """
    from modules.base.core.models.organization import Organization
    from modules.base.core.models.user import User
    from modules.base.core.models.workspace import Workspace

    with app.app_context():
        # Ensure zero users (earlier tests in the suite may have left some)
        User.query.delete()
        db.session.commit()

        org = Organization.query.get(DEFAULT_ORG_ID)
        if not org:
            org = Organization(id=DEFAULT_ORG_ID, name="Default", slug="default")
            db.session.add(org)
            db.session.flush()

        ws = Workspace.query.get(DEFAULT_WS_ID)
        if not ws:
            ws = Workspace(
                id=DEFAULT_WS_ID, slug="default",
                name="Default Workspace", organization_id=DEFAULT_ORG_ID,
            )
            db.session.add(ws)

        db.session.commit()

        # Enable the setup guard (skipped by default in test mode)
        app._test_setup_guard = True
        app._instance_setup_done = False
        yield {"organization": org, "workspace": ws}
        app._test_setup_guard = False


@pytest.fixture()
def fresh_client(app, fresh_install):
    """Test client pointing at a fresh install (no users)."""
    return app.test_client()


@pytest.mark.integration
class TestIsFreshInstall:
    """Unit tests for the is_fresh_install() detection function."""

    def test_true_when_no_users(self, app, fresh_install):
        with app.app_context():
            from modules.base.core.utils.instance_setup import is_fresh_install
            assert is_fresh_install() is True

    def test_false_when_users_exist(self, app, fresh_install):
        with app.app_context():
            from modules.base.core.models.user import User
            from modules.base.core.utils.instance_setup import is_fresh_install

            user = User(
                email="exists@test.com", first_name="A", last_name="B",
                password_hash="x", is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            assert is_fresh_install() is False


@pytest.mark.integration
class TestSetupPageAccess:
    """Test that /setup is accessible on fresh install and locked after."""

    def test_page_loads_on_fresh_install(self, fresh_client):
        resp = fresh_client.get("/setup")
        assert resp.status_code == 200
        assert b"Set Up sparQ" in resp.data

    def test_page_404_when_users_exist(self, app, fresh_install):
        with app.app_context():
            from modules.base.core.models.user import User

            db.session.add(User(
                email="exists@test.com", first_name="A", last_name="B",
                password_hash="x", is_active=True,
            ))
            db.session.commit()

        client = app.test_client()
        resp = client.get("/setup")
        assert resp.status_code == 404


@pytest.mark.integration
class TestSetupRedirect:
    """Test that fresh installs redirect all routes to /setup."""

    def test_login_redirects_to_setup(self, fresh_client):
        resp = fresh_client.get("/login")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_root_redirects_to_setup(self, fresh_client):
        resp = fresh_client.get("/")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_static_assets_not_redirected(self, fresh_client):
        resp = fresh_client.get("/static/css/base.css")
        assert resp.status_code != 302 or "/setup" not in resp.headers.get("Location", "")

    def test_health_not_redirected(self, fresh_client):
        resp = fresh_client.get("/health")
        assert resp.status_code == 200


@pytest.mark.integration
class TestSetupSubmission:
    """Test the setup wizard form submission and provisioning."""

    def test_successful_setup_creates_user(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app)
        assert resp.status_code == 302

        with app.app_context():
            from modules.base.core.models.user import User

            user = User.query.filter_by(email="jane@acmecorp.com").first()
            assert user is not None
            assert user.first_name == "Jane"
            assert user.last_name == "Admin"
            assert user.check_password("Str0ngPass!")

    def test_successful_setup_updates_org(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        with app.app_context():
            from modules.base.core.models.organization import Organization
            from modules.base.core.models.user import User

            org = Organization.query.get(DEFAULT_ORG_ID)
            user = User.query.filter_by(email="jane@acmecorp.com").first()
            assert org.name == "Acme Corp"
            assert org.slug == "acme-corp"
            assert org.owner_id == user.id
            assert org.claimed_domain == "acmecorp.com"

    def test_successful_setup_updates_workspace(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        with app.app_context():
            from modules.base.core.models.workspace import Workspace

            ws = Workspace.query.get(DEFAULT_WS_ID)
            assert ws.name == "Acme Corp"
            assert ws.color == "violet"

    def test_successful_setup_creates_memberships(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        with app.app_context():
            from modules.base.core.models.organization_user import OrganizationUser
            from modules.base.core.models.workspace_user import WorkspaceUser
            from modules.base.core.models.user import User

            user = User.query.filter_by(email="jane@acmecorp.com").first()

            org_user = OrganizationUser.query.filter_by(
                user_id=user.id, organization_id=DEFAULT_ORG_ID,
            ).first()
            assert org_user is not None
            assert org_user.role == "admin"

            ws_user = WorkspaceUser.query.filter_by(
                user_id=user.id, workspace_id=DEFAULT_WS_ID,
            ).first()
            assert ws_user is not None
            assert ws_user.role == "admin"

    def test_auto_login(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app)
        assert resp.status_code == 302

        with fresh_client.session_transaction() as sess:
            assert "active_workspace_id" in sess

    def test_sets_workspace_settings(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        with app.app_context():
            from modules.base.core.models.workspace_settings import WorkspaceSettings

            g.organization_id = DEFAULT_ORG_ID
            g.workspace_id = DEFAULT_WS_ID
            settings = WorkspaceSettings.get_instance()
            assert settings.company_name == "Acme Corp"
            assert settings.timezone == "America/Chicago"
            assert settings.default_language == "en"
            assert settings.onboarding_completed is True

    def test_sets_auth_settings(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        with app.app_context():
            from modules.base.core.models.auth_settings import AuthSettings

            g.organization_id = DEFAULT_ORG_ID
            g.workspace_id = DEFAULT_WS_ID
            auth = AuthSettings.get_instance()
            assert auth.local_auth_enabled is True

    def test_blocked_after_completion(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app)

        resp = fresh_client.get("/setup")
        assert resp.status_code == 404

        resp = _post_setup(fresh_client, app)
        assert resp.status_code == 404

    def test_free_email_no_domain_claim(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app, email="jane@gmail.com")

        with app.app_context():
            from modules.base.core.models.organization import Organization

            org = Organization.query.get(DEFAULT_ORG_ID)
            assert org.claimed_domain is None


@pytest.mark.integration
class TestSetupValidation:
    """Test form validation on the setup wizard."""

    def test_missing_first_name(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app, first_name="")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_missing_email(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app, email="")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_missing_password(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app, password="")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_missing_company_name(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app, company_name="")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_weak_password_rejected(self, app, fresh_client, fresh_install):
        resp = _post_setup(fresh_client, app, password="short")
        assert resp.status_code == 302
        assert "/setup" in resp.headers["Location"]

    def test_invalid_color_defaults_to_orange(self, app, fresh_client, fresh_install):
        _post_setup(fresh_client, app, color="neon-pink")

        with app.app_context():
            from modules.base.core.models.workspace import Workspace

            ws = Workspace.query.get(DEFAULT_WS_ID)
            assert ws.color == "orange"
