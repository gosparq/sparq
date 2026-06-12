# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Database package - SQLAlchemy configuration and utilities.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Database utilities for sparQ.

This package provides database configuration, model registration,
and common mixins for SQLAlchemy models.

Modules:
    database: Core SQLAlchemy instance and base model.
    decorators: Model registration decorators.
    mixins: Reusable model mixins (e.g., AuditMixin).

Example:
    Basic model definition::

        from system.db.database import db
        from system.db.decorators import ModelRegistry
        from system.db.mixins import AuditMixin

        @ModelRegistry.register
        class Product(db.Model, AuditMixin):
            __tablename__ = "product"

            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(255), nullable=False)
            price = db.Column(db.Numeric(10, 2))
"""

from system.db.database import db
from system.db.decorators import ModelRegistry
from system.db.mixins import AuditMixin
from system.db.workspace import OrganizationMixin, WorkspaceMixin

__all__ = ["db", "ModelRegistry", "AuditMixin", "OrganizationMixin", "WorkspaceMixin"]
