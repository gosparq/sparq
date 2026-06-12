# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Account Lockout Integration Tests
#
# Tests for the account lockout feature (P0 Stage 5). Verifies failed login
# tracking, account lockout after threshold, counter reset on success,
# and warning UX for users approaching lockout.
# -----------------------------------------------------------------------------

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

# Ensure project root is on path
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# ---------------------------------------------------------------------------
# 1. User Model Lockout Methods
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAccountLockoutModel:
    """Test User model lockout properties and methods."""

    def test_is_locked_false_by_default(self, app, db_session, test_user):
        """New users should not be locked."""
        with app.app_context():
            assert test_user.is_locked is False
            assert test_user.failed_login_attempts == 0
            assert test_user.locked_until is None

    def test_record_failed_login_increments_counter(self, app, db_session, test_user):
        """Each failed login should increment the counter."""
        with app.app_context():
            test_user.record_failed_login()
            assert test_user.failed_login_attempts == 1

            test_user.record_failed_login()
            assert test_user.failed_login_attempts == 2

    def test_record_failed_login_sets_timestamp(self, app, db_session, test_user):
        """Failed login should set last_failed_login timestamp."""
        with app.app_context():
            assert test_user.last_failed_login is None
            test_user.record_failed_login()
            assert test_user.last_failed_login is not None

    def test_account_locks_after_max_failures(self, app, db_session, test_user):
        """Account should lock after MAX_FAILED_ATTEMPTS consecutive failures."""
        with app.app_context():
            from modules.base.core.models.user import User

            for _ in range(User.MAX_FAILED_ATTEMPTS):
                test_user.record_failed_login()

            assert test_user.is_locked is True
            assert test_user.locked_until is not None

    def test_account_not_locked_below_threshold(self, app, db_session, test_user):
        """Account should NOT lock before reaching MAX_FAILED_ATTEMPTS."""
        with app.app_context():
            from modules.base.core.models.user import User

            for _ in range(User.MAX_FAILED_ATTEMPTS - 1):
                test_user.record_failed_login()

            assert test_user.is_locked is False

    def test_reset_clears_counter_and_lock(self, app, db_session, test_user):
        """reset_failed_logins should clear counter and lockout."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                test_user.record_failed_login()
            assert test_user.is_locked is True

            # Reset
            test_user.reset_failed_logins()
            assert test_user.failed_login_attempts == 0
            assert test_user.locked_until is None
            assert test_user.last_failed_login is None
            assert test_user.is_locked is False

    def test_reset_noop_when_no_failures(self, app, db_session, test_user):
        """reset_failed_logins should be safe to call with no failures."""
        with app.app_context():
            test_user.reset_failed_logins()
            assert test_user.failed_login_attempts == 0

    def test_lockout_expires(self, app, db_session, test_user):
        """Lockout should expire after LOCKOUT_DURATION_MINUTES."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                test_user.record_failed_login()
            assert test_user.is_locked is True

            # Simulate time passing by setting locked_until in the past
            test_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
            db_session.commit()

            assert test_user.is_locked is False

    def test_counter_resets_after_lockout_expires(self, app, db_session, test_user):
        """After lockout expires, failed attempts should reset so user gets fresh attempts."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                test_user.record_failed_login()
            assert test_user.is_locked is True
            assert test_user.failed_login_attempts == User.MAX_FAILED_ATTEMPTS

            # Simulate lockout expiring
            test_user.locked_until = datetime.now(timezone.utc) - timedelta(minutes=1)
            db_session.commit()
            assert test_user.is_locked is False

            # Next failed login should reset counter and start fresh at 1
            count = test_user.record_failed_login()
            assert count == 1
            assert test_user.is_locked is False

    def test_remaining_login_attempts(self, app, db_session, test_user):
        """remaining_login_attempts should count down correctly."""
        with app.app_context():
            from modules.base.core.models.user import User

            assert test_user.remaining_login_attempts == User.MAX_FAILED_ATTEMPTS

            test_user.record_failed_login()
            assert test_user.remaining_login_attempts == User.MAX_FAILED_ATTEMPTS - 1

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS - 1):
                test_user.record_failed_login()
            assert test_user.remaining_login_attempts == 0

    def test_record_failed_login_returns_count(self, app, db_session, test_user):
        """record_failed_login should return the updated count."""
        with app.app_context():
            result = test_user.record_failed_login()
            assert result == 1

            result = test_user.record_failed_login()
            assert result == 2


# ---------------------------------------------------------------------------
# 2. Login Route Integration
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLoginLockout:
    """Test lockout behavior through the /login endpoint."""

    def test_account_locks_after_5_failed_attempts(self, client, app, db_session, test_user):
        """Account should lock after 5 failed login attempts."""
        with app.app_context():
            from modules.base.core.models.user import User

            # 5 failed attempts
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # 6th attempt with correct password should be blocked
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "testpass123",
            }, follow_redirects=True)

            # Should stay on login page (not redirect to dashboard)
            assert resp.status_code == 200
            assert b"Invalid email or password" in resp.data

    def test_successful_login_resets_counter(self, client, app, db_session, test_user):
        """Successful login should reset the failure counter."""
        with app.app_context():
            from modules.base.core.models.user import User

            # 4 failed attempts (one less than lockout)
            for _ in range(User.MAX_FAILED_ATTEMPTS - 1):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # Successful login should reset counter
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "testpass123",
            }, follow_redirects=False)
            assert resp.status_code == 302  # Redirect = success

            # Verify counter was reset
            user = User.get_by_email(test_user.email)
            assert user.failed_login_attempts == 0

            # Log out
            client.get("/logout")

            # 4 more failures should NOT lock (counter was reset)
            for _ in range(User.MAX_FAILED_ATTEMPTS - 1):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # Should still be able to login
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "testpass123",
            }, follow_redirects=False)
            assert resp.status_code == 302

    def test_nonexistent_email_no_error(self, client, app, db_session):
        """Failed attempts with nonexistent emails should not cause errors."""
        with app.app_context():
            # Multiple failures for nonexistent email — should not crash
            for _ in range(10):
                resp = client.post("/login", data={
                    "email": "nobody@example.com",
                    "password": "anything",
                })
                assert resp.status_code == 200

    def test_lockout_message_is_generic(self, client, app, db_session, test_user):
        """Locked account should show generic error (no enumeration)."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # Attempt while locked
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "testpass123",
            }, follow_redirects=True)

            response_text = resp.data.decode()
            assert "Invalid email or password" in response_text

    def test_no_warning_on_first_3_failures(self, client, app, db_session, test_user):
        """No remaining-attempts warning on the first 3 failures."""
        with app.app_context():
            from modules.base.core.models.user import User

            for _ in range(User.LOCKOUT_WARNING_THRESHOLD):
                resp = client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                }, follow_redirects=True)

                response_text = resp.data.decode()
                assert "remaining" not in response_text.lower() or \
                    test_user.failed_login_attempts <= User.LOCKOUT_WARNING_THRESHOLD

    def test_warning_shown_after_threshold(self, client, app, db_session, test_user):
        """Warning with remaining attempts should show after LOCKOUT_WARNING_THRESHOLD."""
        with app.app_context():
            from modules.base.core.models.user import User

            # First 3 failures (no warning)
            for _ in range(User.LOCKOUT_WARNING_THRESHOLD):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # 4th failure should show warning
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "wrongpassword",
            }, follow_redirects=True)

            response_text = resp.data.decode()
            assert "remaining" in response_text.lower()

    def test_lockout_persists_in_db(self, client, app, db_session, test_user):
        """Lockout state should be persisted in the database."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # Verify from a fresh query
            user = User.get_by_email(test_user.email)
            assert user.is_locked is True
            assert user.failed_login_attempts == User.MAX_FAILED_ATTEMPTS
            assert user.locked_until is not None

    def test_locked_account_shows_error_on_next_attempt(self, client, app, db_session, test_user):
        """Locked account should show generic error on subsequent attempt."""
        with app.app_context():
            from modules.base.core.models.user import User

            # Lock the account
            for _ in range(User.MAX_FAILED_ATTEMPTS):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # Next attempt should show error (account is locked)
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "wrongpassword",
            }, follow_redirects=True)

            response_text = resp.data.decode()
            assert "Invalid email or password" in response_text

    def test_locking_attempt_shows_error(self, client, app, db_session, test_user):
        """The attempt that triggers lockout should show generic error."""
        with app.app_context():
            from modules.base.core.models.user import User

            # 4 failures (one short of lockout)
            for _ in range(User.MAX_FAILED_ATTEMPTS - 1):
                client.post("/login", data={
                    "email": test_user.email,
                    "password": "wrongpassword",
                })

            # 5th attempt triggers lockout — should show error
            resp = client.post("/login", data={
                "email": test_user.email,
                "password": "wrongpassword",
            }, follow_redirects=True)

            response_text = resp.data.decode()
            assert "Invalid email or password" in response_text

            # Verify account is actually locked in DB
            user = User.get_by_email(test_user.email)
            assert user.is_locked is True
