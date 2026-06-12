# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Database model mixins for common functionality.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Database mixins for shared model functionality.

Mixins provide reusable columns and methods that can be added to any model.
Use multiple inheritance to add mixin functionality to your models.

Example:
    Using AuditMixin to track who created/updated records::

        from system.db.database import db
        from system.db.mixins import AuditMixin
        from system.db.decorators import ModelRegistry

        @ModelRegistry.register
        class Document(db.Model, AuditMixin):
            __tablename__ = "document"

            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(255))

            # AuditMixin adds:
            # - created_by_id (foreign key to User)
            # - updated_by_id (foreign key to User)
            # - created_by (relationship to User)
            # - updated_by (relationship to User)
            # - created_by_name (property returning user's full name)
            # - updated_by_name (property returning user's full name)

    Using SoftDeleteMixin for soft deletion::

        from system.db.database import db
        from system.db.mixins import SoftDeleteMixin
        from system.db.decorators import ModelRegistry

        @ModelRegistry.register
        class Contact(db.Model, SoftDeleteMixin):
            __tablename__ = "contact"

            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(255))

            # SoftDeleteMixin adds:
            # - deleted_at (timestamp when deleted)
            # - deleted_by_id (foreign key to User who deleted)
            # - is_deleted (property)
            # - can_hard_delete (property - True for admins or within 5 min)
            # - soft_delete(user_id) (method)
            # - restore() (method)
            # - hard_delete(force) (method)
            # - active() (class method - filter non-deleted)
            # - deleted() (class method - filter only deleted)
            # - with_deleted() (class method - include all)
"""

from datetime import datetime, timedelta, timezone

from flask import g
from sqlalchemy.ext.declarative import declared_attr

from system.db.database import db


class AuditMixin:
    """Mixin to track who created and last updated records.

    Adds created_by_id and updated_by_id foreign keys to User model.
    These are readonly/system-managed fields set automatically from current_user.
    """

    created_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    @declared_attr
    def created_by(cls):
        return db.relationship(
            "User",
            foreign_keys=[cls.created_by_id],
            lazy="joined",
        )

    @declared_attr
    def updated_by(cls):
        return db.relationship(
            "User",
            foreign_keys=[cls.updated_by_id],
            lazy="joined",
        )

    @property
    def created_by_name(self) -> str:
        """Return the full name of the user who created this record."""
        if self.created_by:
            return f"{self.created_by.first_name} {self.created_by.last_name}"
        return ""

    @property
    def updated_by_name(self) -> str:
        """Return the full name of the user who last updated this record."""
        if self.updated_by:
            return f"{self.updated_by.first_name} {self.updated_by.last_name}"
        return ""


class SoftDeleteMixin:
    """Mixin to add soft delete functionality to models.

    Adds deleted_at timestamp and deleted_by_id foreign key.
    Provides methods for soft delete, restore, and hard delete operations.

    Hard delete rules:
    - Admins can always hard delete
    - Non-admins can hard delete within HARD_DELETE_WINDOW_MINUTES of creation
    - After the window, only soft delete is allowed for non-admins

    Example:
        @ModelRegistry.register
        class Contact(db.Model, SoftDeleteMixin):
            __tablename__ = "contact"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(255))

        # Query patterns
        Contact.active().all()       # Non-deleted records
        Contact.deleted().all()      # Deleted records only
        Contact.with_deleted().all() # All records

        # Operations
        contact.soft_delete(user_id=current_user.id)
        contact.restore()
        contact.hard_delete()  # Raises if not allowed
    """

    HARD_DELETE_WINDOW_MINUTES = 5

    deleted_at = db.Column(db.DateTime, nullable=True, index=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    @declared_attr
    def deleted_by(cls):
        """Relationship to the User who deleted this record."""
        return db.relationship(
            "User",
            foreign_keys=[cls.deleted_by_id],
            lazy="joined",
        )

    @property
    def is_deleted(self) -> bool:
        """Return True if this record has been soft deleted."""
        return self.deleted_at is not None

    @property
    def can_hard_delete(self) -> bool:
        """Check if hard delete is allowed for this record.

        Returns True if:
        - Current user is an admin, OR
        - Record was created within HARD_DELETE_WINDOW_MINUTES

        Requires flask-login's current_user and a created_at column.
        """
        from flask_login import current_user

        # Admins can always hard delete
        if hasattr(current_user, "is_admin") and current_user.is_admin:
            return True

        # Check if within time window (requires created_at column)
        if hasattr(self, "created_at") and self.created_at:
            window = timedelta(minutes=self.HARD_DELETE_WINDOW_MINUTES)
            created = self.created_at
            # Handle timezone-naive datetimes (SQLite stores without timezone)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) - created < window

        # No created_at column - only admins can hard delete
        return False

    def soft_delete(self, user_id: int = None) -> None:
        """Mark this record as deleted.

        Args:
            user_id: ID of the user performing the deletion. If None,
                    attempts to use current_user.id from flask-login.
        """
        if user_id is None:
            from flask_login import current_user

            if hasattr(current_user, "id"):
                user_id = current_user.id

        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by_id = user_id
        db.session.commit()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.deleted_at = None
        self.deleted_by_id = None
        db.session.commit()

    def hard_delete(self, force: bool = False) -> None:
        """Permanently delete this record from the database.

        Args:
            force: If True, bypass the can_hard_delete check.

        Raises:
            PermissionError: If hard delete is not allowed and force=False.
        """
        if not force and not self.can_hard_delete:
            raise PermissionError(
                f"Hard delete not allowed. Record must be less than "
                f"{self.HARD_DELETE_WINDOW_MINUTES} minutes old or user must be admin."
            )
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def _base_query(cls):
        """Return workspace-scoped query if g.workspace_id is set, else cls.query."""
        if hasattr(cls, "scoped") and getattr(g, "workspace_id", None) is not None:
            return cls.scoped()
        return cls.query

    @classmethod
    def active(cls):
        """Return a query filtered to non-deleted records only.

        Example:
            contacts = Contact.active().filter_by(is_vip=True).all()
        """
        return cls._base_query().filter(cls.deleted_at.is_(None))

    @classmethod
    def deleted(cls):
        """Return a query filtered to deleted records only.

        Example:
            deleted_contacts = Contact.deleted().all()
        """
        return cls._base_query().filter(cls.deleted_at.isnot(None))

    @classmethod
    def with_deleted(cls):
        """Return a query including both active and deleted records.

        Example:
            all_contacts = Contact.with_deleted().all()
        """
        return cls._base_query()

    @property
    def deleted_by_name(self) -> str:
        """Return the full name of the user who deleted this record."""
        if self.deleted_by:
            return f"{self.deleted_by.first_name} {self.deleted_by.last_name}"
        return ""
