# Audit Trail Pattern

Track who created and last updated records using an `AuditMixin`.

## Overview

The `AuditMixin` provides automatic tracking of:
- **created_by** - User who created the record (set once, never changes)
- **updated_by** - User who last modified the record (updated on each save)

These are system-managed, readonly fields from the user's perspective.

## Implementation

### 1. Create the Mixin

```python
# system/db/mixins.py
from sqlalchemy.ext.declarative import declared_attr
from system.db.database import db

class AuditMixin:
    """Mixin to track who created and last updated records."""

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
        """Return full name of creator."""
        if self.created_by:
            return f"{self.created_by.first_name} {self.created_by.last_name}"
        return ""

    @property
    def updated_by_name(self) -> str:
        """Return full name of last updater."""
        if self.updated_by:
            return f"{self.updated_by.first_name} {self.updated_by.last_name}"
        return ""
```

### 2. Apply to Models

```python
from flask_login import current_user
from system.db.mixins import AuditMixin

@ModelRegistry.register
class Contact(db.Model, AuditMixin):
    __tablename__ = "contact"
    # ... fields ...

    @classmethod
    def create(cls, **kwargs) -> "Contact":
        item = cls(**kwargs)
        if current_user and current_user.is_authenticated:
            item.created_by_id = current_user.id
        item.validate()
        db.session.add(item)
        db.session.commit()
        return item

    def update(self, **kwargs) -> "Contact":
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if current_user and current_user.is_authenticated:
            self.updated_by_id = current_user.id
        self.validate()
        db.session.commit()
        return self
```

### 3. Display in Templates

```html
<!-- In detail views -->
<div class="text-muted small">
    <p>Created: {{ item.created_at.strftime('%Y-%m-%d') }}
       {% if item.created_by_name %}by {{ item.created_by_name }}{% endif %}
    </p>
    {% if item.updated_by_name %}
    <p>Last updated by {{ item.updated_by_name }}</p>
    {% endif %}
</div>
```

## Key Points

- Fields are **nullable** to handle existing records and public submissions
- Use `@declared_attr` for relationships in mixins (SQLAlchemy requirement)
- Check `current_user.is_authenticated` before accessing `.id`
- The `*_name` properties provide convenient display formatting
- Use `lazy="joined"` to avoid N+1 queries when displaying lists
