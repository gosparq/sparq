# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Password Policy Integration Tests
#
# Tests for password policy enforcement (P0 Stage 8). Verifies that complexity
# validation and breach checking are enforced at all password entry points:
# registration, password reset, settings password change, and sysadmin
# password change.
# -----------------------------------------------------------------------------

import os
import sys
from unittest.mock import patch

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# Passwords used in tests
WEAK_NO_UPPER = "alllower1"
WEAK_NO_LOWER = "ALLUPPER1"
WEAK_NO_DIGIT = "NoDigitsHere"
WEAK_TOO_SHORT = "Ab1"
STRONG_PASSWORD = "Xk9mP2vL7n"
NEW_STRONG_PASSWORD = "Qw8rT5yU2p"


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRegisterPasswordPolicy:
    """Test password policy enforcement on the /signup endpoint."""

    def _signup(self, client, app, password, email="newuser@example.com"):
        """Submit signup form with a valid form timing token."""
        from system.middleware.form_timing import generate_form_timestamp

        with app.app_context():
            token = generate_form_timestamp()

        # Mock time so the form timing check passes (pretend 3+ seconds elapsed)
        with patch("system.middleware.form_timing.time") as mock_time:
            mock_time.time.return_value = __import__("time").time() + 5
            return client.post("/signup", data={
                "email": email,
                "password": password,
                "first_name": "New",
                "last_name": "User",
                "_form_ts": token,
            }, follow_redirects=True)

    def test_register_weak_too_short_rejected(self, client, app, db_session):
        """Registration with a too-short password should be rejected."""
        resp = self._signup(client, app, WEAK_TOO_SHORT)
        assert b"at least 8 characters" in resp.data

    def test_register_weak_no_uppercase_rejected(self, client, app, db_session):
        """Registration without uppercase should be rejected."""
        resp = self._signup(client, app, WEAK_NO_UPPER)
        assert b"uppercase" in resp.data

    def test_register_weak_no_lowercase_rejected(self, client, app, db_session):
        """Registration without lowercase should be rejected."""
        resp = self._signup(client, app, WEAK_NO_LOWER)
        assert b"lowercase" in resp.data

    def test_register_weak_no_digit_rejected(self, client, app, db_session):
        """Registration without a digit should be rejected."""
        resp = self._signup(client, app, WEAK_NO_DIGIT)
        assert b"number" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=True)
    def test_register_breached_password_rejected(self, mock_breached, client, app, db_session):
        """Registration with a breached password should be rejected."""
        resp = self._signup(client, app, STRONG_PASSWORD)
        assert b"data breach" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=False)
    def test_register_strong_password_succeeds(self, mock_breached, client, app, db_session):
        """Registration with a strong, non-breached password should succeed (email confirmation or direct login)."""
        resp = self._signup(client, app, STRONG_PASSWORD)
        # With email configured: shows "check your email" page
        # Without email: provisions immediately and redirects to dashboard/shell
        # Either way, the signup should NOT show an error flash
        assert b"at least 8 characters" not in resp.data
        assert b"uppercase" not in resp.data
        assert b"data breach" not in resp.data

    def test_register_user_not_created_on_weak_password(self, client, app, db_session):
        """Weak password should not create a user record."""
        from modules.base.core.models.user import User

        self._signup(client, app, WEAK_TOO_SHORT, email="shouldnotexist@example.com")
        with app.app_context():
            assert User.get_by_email("shouldnotexist@example.com") is None


# ---------------------------------------------------------------------------
# 2. Password Reset
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestResetPasswordPolicy:
    """Test password policy enforcement on the /auth/reset-password endpoint."""

    @pytest.fixture
    def user_with_token(self, app, db_session):
        """Create a test user and generate a reset token."""
        from modules.base.core.models.user import User

        with app.app_context():
            user = User.create(
                email="reset@example.com",
                password="OldPass123",
                first_name="Reset",
                last_name="User",
            )
            token = user.generate_password_reset_token()
            db_session.commit()
            return {"token": token, "email": user.email}

    def _reset(self, client, token, password):
        return client.post(f"/auth/reset-password/{token}", data={
            "new_password": password,
            "confirm_password": password,
        }, follow_redirects=True)

    def test_reset_weak_too_short_rejected(self, client, app, db_session, user_with_token):
        """Password reset with a too-short password should be rejected."""
        with app.app_context():
            resp = self._reset(client, user_with_token["token"], WEAK_TOO_SHORT)
            assert b"at least 8 characters" in resp.data

    def test_reset_weak_no_uppercase_rejected(self, client, app, db_session, user_with_token):
        """Password reset without uppercase should be rejected."""
        with app.app_context():
            resp = self._reset(client, user_with_token["token"], WEAK_NO_UPPER)
            assert b"uppercase" in resp.data

    def test_reset_weak_no_digit_rejected(self, client, app, db_session, user_with_token):
        """Password reset without a digit should be rejected."""
        with app.app_context():
            resp = self._reset(client, user_with_token["token"], WEAK_NO_DIGIT)
            assert b"number" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=True)
    def test_reset_breached_password_rejected(self, mock_breached, client, app, db_session, user_with_token):
        """Password reset with a breached password should be rejected."""
        with app.app_context():
            resp = self._reset(client, user_with_token["token"], STRONG_PASSWORD)
            assert b"data breach" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=False)
    def test_reset_strong_password_succeeds(self, mock_breached, client, app, db_session, user_with_token):
        """Password reset with a strong password should succeed."""
        with app.app_context():
            resp = self._reset(client, user_with_token["token"], STRONG_PASSWORD)
            assert b"password has been reset" in resp.data

    def test_reset_weak_password_preserves_token(self, client, app, db_session, user_with_token):
        """Failed reset should not consume the token — user can retry."""
        from modules.base.core.models.user import User

        with app.app_context():
            self._reset(client, user_with_token["token"], WEAK_TOO_SHORT)
            user = User.get_by_email(user_with_token["email"])
            assert user.password_reset_token is not None


# ---------------------------------------------------------------------------
# 3. Settings — Password Change (authenticated user)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSettingsPasswordPolicy:
    """Test password policy enforcement on /settings/security/password."""

    @pytest.fixture(autouse=True)
    def _workspace_context(self, app, db_session, test_user):
        """Set up workspace context so AuthSettings.get_instance() works on redirect."""
        import uuid as _uuid

        from modules.base.core.models.organization import Organization
        from modules.base.core.models.organization_user import OrganizationUser
        from modules.base.core.models.workspace import Workspace
        from modules.base.core.models.workspace_user import WorkspaceUser
        from system.db.database import db

        with app.app_context():
            org = Organization(
                id=_uuid.uuid4(), name="PP Org", slug=f"pp-{_uuid.uuid4().hex[:8]}",
            )
            db.session.add(org)
            db.session.flush()

            ws = Workspace(
                id=_uuid.uuid4(), slug=f"pp-ws-{_uuid.uuid4().hex[:8]}",
                name="PP Workspace", organization_id=org.id,
            )
            db.session.add(ws)
            db.session.flush()

            org_user = OrganizationUser.create(
                organization_id=org.id, user_id=test_user.id, role="admin",
            )

            member = WorkspaceUser(
                user_id=test_user.id, workspace_id=ws.id,
                organization_id=org.id, organization_user_id=org_user.id,
                role="admin",
            )
            db.session.add(member)
            db.session.commit()

            self._workspace_id = ws.id

    def _change_password(self, client, new_password, current_password="testpass123"):
        with client.session_transaction() as sess:
            sess["active_workspace_id"] = str(self._workspace_id)
        return client.post("/settings/security/password", data={
            "current_password": current_password,
            "new_password": new_password,
            "confirm_password": new_password,
        }, follow_redirects=True)

    def test_change_weak_too_short_rejected(self, authenticated_client, app, db_session):
        """Changing to a too-short password should be rejected."""
        resp = self._change_password(authenticated_client, WEAK_TOO_SHORT)
        assert b"at least 8 characters" in resp.data

    def test_change_weak_no_uppercase_rejected(self, authenticated_client, app, db_session):
        """Changing to a password without uppercase should be rejected."""
        resp = self._change_password(authenticated_client, WEAK_NO_UPPER)
        assert b"uppercase" in resp.data

    def test_change_weak_no_digit_rejected(self, authenticated_client, app, db_session):
        """Changing to a password without a digit should be rejected."""
        resp = self._change_password(authenticated_client, WEAK_NO_DIGIT)
        assert b"number" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=True)
    def test_change_breached_password_rejected(self, mock_breached, authenticated_client, app, db_session):
        """Changing to a breached password should be rejected."""
        resp = self._change_password(authenticated_client, NEW_STRONG_PASSWORD)
        assert b"data breach" in resp.data

    @patch("modules.base.core.controllers.routes.is_breached", return_value=False)
    def test_change_strong_password_succeeds(self, mock_breached, authenticated_client, app, db_session):
        """Changing to a strong password with correct current password should succeed."""
        resp = self._change_password(authenticated_client, NEW_STRONG_PASSWORD)
        assert b"Password updated successfully" in resp.data


# ---------------------------------------------------------------------------
# 4. Breach check fail-open
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBreachCheckFailOpen:
    """Verify that breach checking fails open when API is unreachable."""

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_breach_check_returns_false_on_network_error(self, mock_urlopen):
        """The is_breached function should return False on network error."""
        from system.auth.password_policy import is_breached

        mock_urlopen.side_effect = ConnectionError("Network unreachable")
        assert is_breached(STRONG_PASSWORD) is False

    @patch("system.auth.password_policy.urllib.request.urlopen")
    def test_breach_check_returns_false_on_timeout(self, mock_urlopen):
        """The is_breached function should return False on timeout."""
        from urllib.error import URLError
        from system.auth.password_policy import is_breached

        mock_urlopen.side_effect = URLError("timeout")
        assert is_breached(STRONG_PASSWORD) is False
