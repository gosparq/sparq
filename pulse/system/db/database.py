# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Database configuration and base model setup for SQLAlchemy integration.
#     Provides the central database instance used throughout the application.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Database configuration and SQLAlchemy setup.

This module provides the central database instance used throughout sparQ.
All models should import `db` from here.

Example:
    Creating a model::

        from system.db.database import db
        from system.db.decorators import ModelRegistry

        @ModelRegistry.register
        class MyModel(db.Model):
            __tablename__ = "my_model"

            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(255), nullable=False)

Attributes:
    db: The Flask-SQLAlchemy database instance. Use this for all database
        operations including model definitions, queries, and session management.
"""

import sqlalchemy as sa
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Store VARCHAR instead of native ENUM on all backends so SQLite works
# without per-model changes.
_original_enum_init = sa.Enum.__init__


def _enum_init_no_native(self, *args, **kwargs):
    kwargs.setdefault("native_enum", False)
    _original_enum_init(self, *args, **kwargs)


sa.Enum.__init__ = _enum_init_no_native

# db.UUID (uppercase) renders as "UUID" on every backend. SQLite gives
# "UUID" columns NUMERIC affinity, silently casting all-digit hex strings
# to integers.  Override both visit names to force TEXT-affinity VARCHAR.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "VARCHAR(32)"
SQLiteTypeCompiler.visit_uuid = lambda self, type_, **kw: "VARCHAR(32)"


class Base(DeclarativeBase):  # type: ignore[misc]
    pass


db = SQLAlchemy(model_class=Base)
"""Flask-SQLAlchemy database instance.

Use this for:
- Defining models (inherit from db.Model)
- Database queries (Model.query or db.session.query)
- Session management (db.session.add, db.session.commit)
- Column types (db.Column, db.Integer, db.String, etc.)
- Relationships (db.relationship, db.ForeignKey)
"""
