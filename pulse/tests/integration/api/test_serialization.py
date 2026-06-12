# sparQ — Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

# -----------------------------------------------------------------------------
# sparQ - Serialization Integration Tests
#
# Tests for SerializableMixin: to_dict, exclude, type coercion.
# -----------------------------------------------------------------------------

from datetime import datetime, timezone
from decimal import Decimal

import pytest


@pytest.mark.integration
class TestSerializableMixin:
    """Tests for SerializableMixin.to_dict()."""

    def test_basic_to_dict(self, app, db_session):
        """to_dict returns column values as a dictionary."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        # Use a simple model to test
        class _TestModel(db.Model, SerializableMixin):
            __tablename__ = "test_serializable"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50))

        with app.app_context():
            db.create_all()
            obj = _TestModel(id=1, name="test")
            result = obj.to_dict()
            assert result["id"] == 1
            assert result["name"] == "test"

    def test_serialize_exclude(self, app, db_session):
        """_serialize_exclude removes fields from output."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        class _TestExclude(db.Model, SerializableMixin):
            __tablename__ = "test_exclude"
            _serialize_exclude = {"secret"}
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50))
            secret = db.Column(db.String(50))

        with app.app_context():
            db.create_all()
            obj = _TestExclude(id=1, name="visible", secret="hidden")
            result = obj.to_dict()
            assert "name" in result
            assert "secret" not in result

    def test_per_call_exclude(self, app, db_session):
        """Per-call exclude parameter removes additional fields."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        class _TestPerCall(db.Model, SerializableMixin):
            __tablename__ = "test_percall"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50))
            email = db.Column(db.String(100))

        with app.app_context():
            db.create_all()
            obj = _TestPerCall(id=1, name="test", email="a@b.com")
            result = obj.to_dict(exclude={"email"})
            assert "name" in result
            assert "email" not in result

    def test_datetime_iso_format(self, app, db_session):
        """Datetime values are coerced to ISO 8601 strings."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        class _TestDatetime(db.Model, SerializableMixin):
            __tablename__ = "test_datetime"
            id = db.Column(db.Integer, primary_key=True)
            created = db.Column(db.DateTime)

        with app.app_context():
            db.create_all()
            dt = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
            obj = _TestDatetime(id=1, created=dt)
            result = obj.to_dict()
            assert result["created"] == "2026-03-20T12:00:00+00:00"

    def test_decimal_to_float(self, app, db_session):
        """Decimal values are coerced to floats."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        class _TestDecimal(db.Model, SerializableMixin):
            __tablename__ = "test_decimal"
            id = db.Column(db.Integer, primary_key=True)
            amount = db.Column(db.Numeric(10, 2))

        with app.app_context():
            db.create_all()
            obj = _TestDecimal(id=1, amount=Decimal("99.95"))
            result = obj.to_dict()
            assert result["amount"] == 99.95
            assert isinstance(result["amount"], float)

    def test_user_no_sensitive_fields(self, app, api_user):
        """User.to_dict() excludes sensitive fields."""
        with app.app_context():
            result = api_user.to_dict()
            assert "email" in result
            assert "first_name" in result
            assert "password_hash" not in result
            assert "password_reset_token" not in result
            assert "magic_link_token" not in result
            assert "sms_otp" not in result
            assert "failed_login_attempts" not in result
            assert "locked_until" not in result

    def test_include_relationships(self, app, db_session):
        """Include parameter serializes relationships."""
        from system.db.database import db
        from system.api.serialization import SerializableMixin

        class _TestParent(db.Model, SerializableMixin):
            __tablename__ = "test_parent"
            id = db.Column(db.Integer, primary_key=True)
            name = db.Column(db.String(50))
            children = db.relationship("_TestChild", backref="parent")

        class _TestChild(db.Model, SerializableMixin):
            __tablename__ = "test_child"
            id = db.Column(db.Integer, primary_key=True)
            parent_id = db.Column(db.Integer, db.ForeignKey("test_parent.id"))
            label = db.Column(db.String(50))

        with app.app_context():
            db.create_all()
            parent = _TestParent(id=1, name="parent")
            child = _TestChild(id=1, parent_id=1, label="child1")
            db.session.add_all([parent, child])
            db.session.flush()

            result = parent.to_dict(include={
                "children": lambda c: c.to_dict()
            })
            assert len(result["children"]) == 1
            assert result["children"][0]["label"] == "child1"
