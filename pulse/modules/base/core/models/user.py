# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Core user model that handles authentication, user management, and
#     provides base user functionality for the entire application. Implements
#     Flask-Login integration and password hashing.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from __future__ import annotations

import logging
import random
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from flask_login import UserMixin
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash

from .user_setting import UserSetting
from system.api.serialization import SerializableMixin
from system.db.database import db
from system.db.decorators import ModelRegistry

if TYPE_CHECKING:
    from .organization_user import OrganizationUser
    from .workspace_user import WorkspaceUser

logger = logging.getLogger(__name__)


_AVATAR_COLOR_MAP = {
    "#2563EB": "#4A7EC0",
    "#7C3AED": "#7A65B0",
    "#DB2777": "#B06088",
    "#DC2626": "#B05858",
    "#EA580C": "#DC7A28",
    "#65A30D": "#6E9438",
    "#0D9488": "#3D8C84",
    "#0284C7": "#3D88B8",
    "#6366F1": "#6E70C0",
    "#9333EA": "#9068B8",
    "#C026D3": "#A058A8",
    "#E11D48": "#B05868",
    "#F97316": "#E88C30",
    "#84CC16": "#7EA038",
    "#14B8A6": "#3DA898",
}


def generate_avatar_color():
    return random.choice(list(_AVATAR_COLOR_MAP.values()))


@ModelRegistry.register
class User(db.Model, UserMixin, SerializableMixin):
    """Core user model for authentication and basic user info"""

    __tablename__ = "user"

    _serialize_exclude = {
        "password_hash",
        "password_reset_token",
        "password_reset_expires",
        "magic_link_token",
        "magic_link_expires",
        "sms_otp",
        "sms_otp_expires",
        "failed_login_attempts",
        "locked_until",
        "last_failed_login",
    }

    # Account lockout thresholds
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 15
    LOCKOUT_WARNING_THRESHOLD = 3

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)  # Nullable for OAuth-only users
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    _avatar_color = db.Column("avatar_color", db.String(7), default=generate_avatar_color)

    @property
    def avatar_color(self):
        c = (self._avatar_color or "").upper()
        return _AVATAR_COLOR_MAP.get(c, self._avatar_color) or self._avatar_color

    @avatar_color.setter
    def avatar_color(self, value):
        self._avatar_color = value
    created_at = db.Column(db.DateTime, default=db.func.now())
    is_active = db.Column(db.Boolean, default=True)
    is_sample = db.Column(db.Boolean, default=False)
    needs_password_setup = db.Column(db.Boolean, default=False)

    # Password reset
    password_reset_token = db.Column(db.String(100), nullable=True, index=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)

    # Magic link authentication
    magic_link_token = db.Column(db.String(100), nullable=True, index=True)
    magic_link_expires = db.Column(db.DateTime, nullable=True)

    # SMS authentication
    phone_number = db.Column(db.String(20), nullable=True, index=True)
    phone_verified = db.Column(db.Boolean, default=False)
    sms_otp = db.Column(db.String(6), nullable=True)
    sms_otp_expires = db.Column(db.DateTime, nullable=True)

    # Presence tracking
    last_seen = db.Column(db.DateTime, nullable=True)

    # Last-used workspace (persisted for session-recovery on login)
    last_workspace_id = db.Column(db.Uuid, nullable=True)

    # Personal information (person-level, not workspace-level)
    birthday = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(30), nullable=True)
    personal_phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(100), nullable=True)
    address_2 = db.Column(db.String(100), nullable=True)
    city = db.Column(db.String(50), nullable=True)
    state = db.Column(db.String(50), nullable=True)
    zip_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(50), nullable=True)
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    emergency_contact_relationship = db.Column(db.String(50), nullable=True)
    social_media = db.Column(db.String(100), nullable=True)

    # Account lockout
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_failed_login = db.Column(db.DateTime, nullable=True)

    # -------------------------------------------------------------------------
    # Workspace Membership
    # -------------------------------------------------------------------------

    @property
    def workspace_membership(self) -> WorkspaceUser | None:
        """Get WorkspaceUser for the active workspace (from g.workspace_id).

        Walks OrganizationUser → WorkspaceUser. Returns the user's membership
        record in the current workspace context. Returns None if no workspace
        context or no membership found.
        """
        from flask import g
        from modules.base.core.models.workspace_user import WorkspaceUser

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            return None
        # Per-instance memoize: this property is called from many templates
        # (is_admin, sidebar partials, controllers) and the row doesn't change
        # mid-request. Stash on the instance — the SQLAlchemy session identity
        # map keeps `self` stable for the request, so the cache scopes naturally.
        cache_key = getattr(self, "_ts_membership_cache_key", None)
        if cache_key == workspace_id:
            return self._ts_membership_cache
        membership = WorkspaceUser.query.filter_by(
            user_id=self.id, workspace_id=workspace_id
        ).filter(WorkspaceUser.deleted_at.is_(None)).first()
        self._ts_membership_cache_key = workspace_id
        self._ts_membership_cache = membership
        return membership

    @property
    def organization_membership(self) -> OrganizationUser | None:
        """Get OrganizationUser for the active organization (from g.organization_id).

        Returns None if no organization context or no membership found.
        """
        from flask import g
        from modules.base.core.models.organization_user import OrganizationUser

        organization_id = getattr(g, "organization_id", None)
        if organization_id is None:
            return None
        return OrganizationUser.get_for_user(self.id, organization_id)

    @property
    def is_admin(self) -> bool:
        """Check if user is admin in current workspace.

        Organization admins are always treated as workspace admins.
        """
        membership = self.workspace_membership
        if membership is not None and membership.role == "admin":
            return True
        org_membership = self.organization_membership
        if org_membership is not None and org_membership.is_organization_admin:
            return True
        return False

    def has_access(self, area: str) -> bool:
        """Check if user has access to a permission area.

        Args:
            area: Permission area to check (hr, finance, operations)

        Returns:
            True if user is admin OR has the specified permission area
        """
        if self.is_admin:
            return True
        membership = self.workspace_membership
        if membership is None:
            return False
        return membership.has_permission(area)

    @property
    def is_sole_admin(self) -> bool:
        """Check if user is the only administrator in current workspace."""
        if not self.is_admin:
            return False

        from modules.base.core.models.workspace_user import WorkspaceUser
        from flask import g

        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id is None:
            return False
        admin_count = WorkspaceUser.query.filter_by(
            workspace_id=workspace_id, role="admin"
        ).filter(WorkspaceUser.deleted_at.is_(None)).count()
        return admin_count <= 1

    @property
    def password(self):
        raise AttributeError("password is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash. Returns False if no password set."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def has_password(self) -> bool:
        """Check if user has a password set (vs OAuth-only)."""
        return bool(self.password_hash)

    # -------------------------------------------------------------------------
    # Account Lockout
    # -------------------------------------------------------------------------

    @property
    def is_locked(self) -> bool:
        """Check if account is currently locked.

        Returns:
            True if account is locked and lockout has not expired.
        """
        if self.locked_until:
            now = datetime.now(timezone.utc)
            locked = self.locked_until
            if locked.tzinfo is None:
                locked = locked.replace(tzinfo=timezone.utc)
            if locked > now:
                return True
        return False

    @property
    def remaining_login_attempts(self) -> int:
        """Number of login attempts remaining before lockout."""
        return max(0, self.MAX_FAILED_ATTEMPTS - self.failed_login_attempts)

    def record_failed_login(self) -> int:
        """Record a failed login attempt. Locks account after threshold.

        If a previous lockout has expired, the counter resets before
        recording the new failure so the user gets a fresh set of attempts.

        Returns:
            Updated failed_login_attempts count.
        """
        # Reset counter if a previous lockout has expired
        if self.locked_until and not self.is_locked:
            self.failed_login_attempts = 0
            self.locked_until = None

        self.failed_login_attempts += 1
        self.last_failed_login = datetime.now(timezone.utc)
        if self.failed_login_attempts >= self.MAX_FAILED_ATTEMPTS:
            self.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES
            )
        db.session.commit()
        return self.failed_login_attempts

    def reset_failed_logins(self) -> None:
        """Reset failed login counter on successful login."""
        if self.failed_login_attempts > 0:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.last_failed_login = None
            db.session.commit()

    def generate_password_reset_token(self, expires_hours: int = 1) -> str:
        """Generate a password reset token.

        Args:
            expires_hours: Hours until token expires (default 1)

        Returns:
            The reset token
        """
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
        db.session.commit()
        return self.password_reset_token

    def clear_password_reset_token(self) -> None:
        """Clear the password reset token."""
        self.password_reset_token = None
        self.password_reset_expires = None
        db.session.commit()

    def is_password_reset_token_valid(self, token: str) -> bool:
        """Check if a password reset token is valid.

        Args:
            token: The token to validate

        Returns:
            True if token is valid and not expired
        """
        if not self.password_reset_token or not self.password_reset_expires:
            return False

        if not secrets.compare_digest(self.password_reset_token, token):
            return False

        now = datetime.now(timezone.utc)
        expires = self.password_reset_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now < expires

    @classmethod
    def get_by_reset_token(cls, token: str) -> "User | None":
        """Find user by password reset token.

        Args:
            token: The reset token

        Returns:
            User if found and token valid, None otherwise
        """
        user = cls.query.filter_by(password_reset_token=token).first()
        if user and user.is_password_reset_token_valid(token):
            return user
        return None

    # -------------------------------------------------------------------------
    # Magic Link Authentication
    # -------------------------------------------------------------------------

    def generate_magic_link_token(self, expires_minutes: int = 15) -> str:
        """Generate a magic link token for passwordless email login.

        Args:
            expires_minutes: Minutes until token expires (default 15)

        Returns:
            The magic link token
        """
        self.magic_link_token = secrets.token_urlsafe(32)
        self.magic_link_expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        db.session.commit()
        return self.magic_link_token

    def is_magic_link_valid(self, token: str) -> bool:
        """Check if a magic link token is valid and not expired.

        Args:
            token: The token to validate

        Returns:
            True if token is valid and not expired
        """
        if not self.magic_link_token or not self.magic_link_expires:
            return False

        if not secrets.compare_digest(self.magic_link_token, token):
            return False

        now = datetime.now(timezone.utc)
        expires = self.magic_link_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now < expires

    def clear_magic_link_token(self) -> None:
        """Clear the magic link token after use."""
        self.magic_link_token = None
        self.magic_link_expires = None
        db.session.commit()

    @classmethod
    def get_by_magic_link_token(cls, token: str) -> "User | None":
        """Find user by magic link token.

        Args:
            token: The magic link token

        Returns:
            User if found and token valid, None otherwise
        """
        user = cls.query.filter_by(magic_link_token=token).first()
        if user and user.is_magic_link_valid(token):
            return user
        return None

    # -------------------------------------------------------------------------
    # SMS OTP Authentication
    # -------------------------------------------------------------------------

    def generate_sms_otp(self, expires_minutes: int = 5) -> str:
        """Generate a 6-digit OTP for SMS verification.

        Args:
            expires_minutes: Minutes until OTP expires (default 5)

        Returns:
            The 6-digit OTP code
        """
        self.sms_otp = str(secrets.randbelow(900000) + 100000)
        self.sms_otp_expires = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
        db.session.commit()
        return self.sms_otp

    def is_sms_otp_valid(self, otp: str) -> bool:
        """Check if SMS OTP is valid and not expired.

        Args:
            otp: The OTP to validate

        Returns:
            True if OTP is valid and not expired
        """
        if not self.sms_otp or not self.sms_otp_expires:
            return False

        if self.sms_otp != otp:
            return False

        now = datetime.now(timezone.utc)
        expires = self.sms_otp_expires
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        return now < expires

    def clear_sms_otp(self) -> None:
        """Clear SMS OTP after use or expiration."""
        self.sms_otp = None
        self.sms_otp_expires = None
        db.session.commit()

    @classmethod
    def get_by_phone(cls, phone: str) -> "User | None":
        """Find user by phone number.

        Args:
            phone: Phone number (will be normalized)

        Returns:
            User if found, None otherwise
        """
        # Normalize phone number - keep only digits
        normalized = "".join(filter(str.isdigit, phone))
        if not normalized:
            return None

        # Search for users with matching phone (normalized)
        users = cls.query.filter(cls.phone_number.isnot(None)).all()
        for user in users:
            user_phone_normalized = "".join(filter(str.isdigit, user.phone_number or ""))
            if user_phone_normalized == normalized:
                return user
        return None

    @classmethod
    def count(cls) -> int:
        """Count all users."""
        return cls.query.count()

    @staticmethod
    def get_by_id(user_id):
        """Get user by ID"""
        return User.query.get(int(user_id))

    @classmethod
    def get_by_ids(cls, user_ids: list[int]) -> list["User"]:
        """Get multiple users by their IDs."""
        if not user_ids:
            return []
        return cls.query.filter(cls.id.in_(user_ids)).all()

    @staticmethod
    def get_by_email(email):
        """Get user by email"""
        return User.query.filter_by(email=email).first()

    @classmethod
    def create(cls, email, password, first_name=None, last_name=None, **kwargs):
        """Create new user.

        Args:
            email: User email address.
            password: User password (will be hashed).
            first_name: First name.
            last_name: Last name.

        Returns:
            Created User instance.
        """
        user = cls(email=email, first_name=first_name, last_name=last_name)
        user.password = password
        db.session.add(user)
        db.session.commit()
        return user

    @classmethod
    def create_from_oauth(
        cls,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        **kwargs,
    ) -> "User":
        """Create a new user from OAuth login (no password).

        Args:
            email: User's email address.
            first_name: User's first name.
            last_name: User's last name.

        Returns:
            Created User instance.
        """
        user = cls(email=email, first_name=first_name, last_name=last_name)
        db.session.add(user)
        db.session.commit()
        return user

    def update_setting(self, key, value):
        """Update or create a user setting"""
        try:
            # Try to get existing setting
            setting = UserSetting.scoped().filter_by(user_id=self.id, key=key).first()

            if setting:
                # Update existing setting
                setting.value = value
            else:
                # Create new setting
                setting = UserSetting(user_id=self.id, key=key, value=value)
                db.session.add(setting)

            db.session.commit()
            return True

        except Exception as e:
            db.session.rollback()
            print(f"Error updating user setting: {str(e)}")
            return False

    @property
    def full_name(self):
        """Get user's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email.split("@")[0]

    @property
    def avatar_initials(self):
        """Get user's initials for avatar"""
        if self.first_name and self.last_name:
            return (self.first_name[0] + self.last_name[0]).upper()
        return self.email[:2].upper()

    @property
    def is_online(self) -> bool:
        """Check if user is currently online (active within last 5 minutes)."""
        if not self.last_seen:
            return False
        now = datetime.now(timezone.utc)
        last_seen = self.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        return (now - last_seen) < timedelta(minutes=5)

    @property
    def presence_status(self) -> str:
        """Return presence status: 'online', 'away', 'offline'."""
        if not self.last_seen:
            return "offline"
        now = datetime.now(timezone.utc)
        last_seen = self.last_seen
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)
        delta = now - last_seen
        if delta < timedelta(minutes=5):
            return "online"
        if delta < timedelta(minutes=15):
            return "away"
        return "offline"

    def update_last_seen(self) -> None:
        """Update user's last seen timestamp."""
        self.last_seen = datetime.now(timezone.utc)
        db.session.commit()

    def save_last_workspace(self, ts_id: uuid.UUID) -> None:
        """Persist last-used workspace for session-recovery on next login."""
        if self.last_workspace_id != ts_id:
            self.last_workspace_id = ts_id
            db.session.commit()

    @property
    def full_address(self):
        """Return formatted full address."""
        parts = [self.address, self.address_2, self.city, self.state, self.zip_code, self.country]
        return ", ".join(filter(None, parts))

    @staticmethod
    def generate_random_password(length: int = 16) -> str:
        """Generate a random password for programmatic user creation."""
        return secrets.token_urlsafe(length)

    @classmethod
    def get_all_active(cls) -> list["User"]:
        """Get all active users for user list."""
        return (
            cls.query.filter_by(is_active=True)
            .order_by(cls.first_name, cls.last_name)
            .all()
        )

    @property
    def email_domain(self) -> str:
        """Extract the domain portion of this user's email address."""
        from system.utils.email_domain import extract_domain
        return extract_domain(self.email)
