# -----------------------------------------------------------------------------
# sparQ — Model Serialization Mixin
#
# Provides automatic to_dict() for SQLAlchemy models. Handles type coercion
# (datetime→ISO 8601, Decimal→float) and field exclusion for sensitive data.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import enum
from datetime import date, datetime
from decimal import Decimal


class SerializableMixin:
    """Mixin for SQLAlchemy models to enable JSON serialization.

    Usage:
        class User(db.Model, SerializableMixin):
            _serialize_exclude = {'password_hash', 'secret_token'}

        user.to_dict()
        user.to_dict(exclude={'email'})
        user.to_dict(include={'groups': lambda g: g.to_dict()})
    """

    _serialize_exclude: set[str] = set()

    def to_dict(
        self,
        exclude: set[str] | None = None,
        include: dict | None = None,
    ) -> dict:
        """Convert model instance to dictionary.

        Args:
            exclude: Additional fields to exclude (merged with _serialize_exclude).
            include: Dict of relationship_name → serializer function.
                     e.g. {'groups': lambda g: {'id': g.id, 'name': g.name}}

        Returns:
            Dictionary of column values with type coercion applied.
        """
        excluded = self._serialize_exclude | (exclude or set())

        result = {}
        for col in self.__table__.columns:
            if col.name in excluded:
                continue
            value = getattr(self, col.name)
            result[col.name] = self._coerce_value(value)

        if include:
            for key, serializer in include.items():
                rel = getattr(self, key, None)
                if rel is None:
                    result[key] = None
                elif hasattr(rel, '__iter__'):
                    result[key] = [serializer(item) for item in rel]
                else:
                    result[key] = serializer(rel)

        return result

    @staticmethod
    def _coerce_value(value):
        """Coerce Python types to JSON-safe equivalents."""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, enum.Enum):
            return value.value
        return value
