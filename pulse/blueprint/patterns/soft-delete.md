# Soft Delete Pattern

> Keep records recoverable instead of permanently deleting them.

---

## Table of Contents

- [Overview](#overview)
- [SoftDeleteMixin](#softdeletemixin)
- [Query Patterns](#query-patterns)
- [Hard Delete Rules](#hard-delete-rules)
- [Template Helpers](#template-helpers)
- [Controller Patterns](#controller-patterns)
- [Migration Guide](#migration-guide)

---

## Overview

Soft delete marks records as deleted without removing them from the database. This allows:

- **Recovery**: Users can restore accidentally deleted items
- **Audit trail**: Track who deleted what and when
- **Data integrity**: Maintain referential integrity for related records
- **Compliance**: Meet data retention requirements

### When to Use

| Scenario | Recommendation |
|----------|----------------|
| User-facing data (contacts, quotes) | Use soft delete |
| System/config records | Use hard delete |
| Temporary/cache data | Use hard delete |
| Audit logs | Never delete |

---

## SoftDeleteMixin

Add the mixin to any model that needs soft delete support:

```python
from system.db.database import db
from system.db.mixins import SoftDeleteMixin
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class Contact(db.Model, SoftDeleteMixin):
    __tablename__ = "contact"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
```

### Columns Added

| Column | Type | Description |
|--------|------|-------------|
| `deleted_at` | DateTime | Timestamp when deleted (null = active) |
| `deleted_by_id` | Integer (FK) | User who performed deletion |

### Properties

| Property | Returns | Description |
|----------|---------|-------------|
| `is_deleted` | bool | True if record is soft deleted |
| `can_hard_delete` | bool | True if hard delete is allowed |
| `deleted_by_name` | str | Full name of user who deleted |

### Methods

| Method | Description |
|--------|-------------|
| `soft_delete(user_id=None)` | Mark as deleted, auto-commits |
| `restore()` | Remove deleted status, auto-commits |
| `hard_delete(force=False)` | Permanently delete if allowed |

---

## Query Patterns

The mixin provides class methods for filtering by deletion status:

```python
# Default: active (non-deleted) records only
contacts = Contact.active().all()
contacts = Contact.active().filter_by(is_vip=True).all()

# Deleted records only (admin trash view)
deleted = Contact.deleted().all()

# All records including deleted (reports, activity logs)
all_contacts = Contact.with_deleted().all()
```

### Summary

| Method | Returns | Use Case |
|--------|---------|----------|
| `Model.active()` | Non-deleted only | Default user-facing queries |
| `Model.deleted()` | Deleted only | Admin trash/archive view |
| `Model.with_deleted()` | All records | Activity logs, reports |

### Updating Existing Queries

When adding soft delete to a model, update queries:

```python
# Before (returns all including deleted)
contacts = Contact.query.filter_by(workspace_id=workspace_id).all()

# After (returns only active)
contacts = Contact.active().filter_by(workspace_id=workspace_id).all()
```

---

## Hard Delete Rules

Hard delete permanently removes records. Rules prevent accidental data loss:

| User Role | Record Age | Can Hard Delete |
|-----------|------------|-----------------|
| Admin | Any | Yes |
| Non-Admin | < 5 minutes | Yes |
| Non-Admin | >= 5 minutes | No (soft delete only) |

### Configuration

The time window is configurable per model:

```python
class Contact(db.Model, SoftDeleteMixin):
    HARD_DELETE_WINDOW_MINUTES = 10  # Override default of 5
```

### Checking Permission

```python
if contact.can_hard_delete:
    contact.hard_delete()
else:
    contact.soft_delete()
```

### Force Delete (Admin Only)

```python
# Bypass permission check (use with caution)
contact.hard_delete(force=True)
```

---

## Template Helpers

Import the macros in your templates:

```jinja
{% from "core/desktop/macros/_soft_delete.html" import
    deleted_badge,
    deleted_row_class,
    display_name_with_status,
    render_delete_actions,
    deleted_filter_tabs
%}
```

### Deleted Badge

Pink pill indicator for deleted items:

```jinja
{# Basic badge #}
{{ deleted_badge(contact) }}

{# With deletion date #}
{{ deleted_badge(contact, show_date=True) }}
```

### Table Row Styling

Apply CSS class to deleted rows:

```jinja
<tr class="{{ deleted_row_class(contact) }}">
    <td>{{ contact.name }}</td>
</tr>
```

### Name with Status

Strikethrough and badge for deleted items:

```jinja
{{ display_name_with_status(contact, contact.name) }}
```

### Action Buttons

Delete/restore buttons based on status:

```jinja
{{ render_delete_actions(
    contact,
    delete_url=url_for('contacts.delete', id=contact.id),
    restore_url=url_for('contacts.restore', id=contact.id),
    hard_delete_url=url_for('contacts.hard_delete', id=contact.id)
) }}
```

### Filter Tabs

Tabs to switch between active/deleted/all views:

```jinja
{{ deleted_filter_tabs(
    active_filter=request.args.get('filter', 'active'),
    base_url=url_for('contacts.index'),
    counts={'active': active_count, 'deleted': deleted_count, 'all': total_count}
) }}
```

### Parent Deleted Badge

Pink pill indicator for child entities when their parent is deleted:

```jinja
{# Import the macro #}
{% from "core/desktop/macros/_soft_delete.html" import parent_deleted_badge %}

{# Basic usage - shows "Contact deleted" when quote's contact is deleted #}
{{ parent_deleted_badge(quote.contact) }}

{# Custom label - shows "Customer deleted" instead #}
{{ parent_deleted_badge(invoice.contact, "Customer") }}
```

Use this on child entity list/detail pages to indicate when the parent contact has been soft-deleted. The badge shows a pink pill with a user-slash icon and includes a tooltip with deletion details (date and who deleted it).

For row-level highlighting, also apply the `deleted-row` class to table rows when the parent is deleted:

```jinja
<tr class="{{ 'deleted-row' if quote.contact.is_deleted else '' }}">
    <td>{{ quote.contact.display_name }}{{ parent_deleted_badge(quote.contact) }}</td>
</tr>
```

**When to use:**
- Quote list/detail views showing contact
- Request list/detail views showing contact
- Invoice list/detail views showing contact
- Any child entity where the parent can be soft-deleted

---

## Controller Patterns

### Standard CRUD with Soft Delete

```python
from flask import Blueprint, flash, redirect, url_for
from flask_login import login_required, current_user

bp = Blueprint("contacts", __name__)


@bp.route("/contacts")
@login_required
def index():
    """List contacts with filter support."""
    filter_type = request.args.get("filter", "active")

    if filter_type == "deleted":
        contacts = Contact.deleted().all()
    elif filter_type == "all":
        contacts = Contact.with_deleted().all()
    else:
        contacts = Contact.active().all()

    return render_template("contacts/index.html", contacts=contacts)


@bp.route("/contacts/<int:id>/delete", methods=["DELETE"])
@login_required
def delete(id):
    """Soft delete a contact."""
    contact = Contact.query.get_or_404(id)
    contact.soft_delete(user_id=current_user.id)
    flash("Contact deleted.", "success")
    return redirect(url_for("contacts.index"))


@bp.route("/contacts/<int:id>/restore", methods=["POST"])
@login_required
def restore(id):
    """Restore a deleted contact."""
    contact = Contact.query.get_or_404(id)
    contact.restore()
    flash("Contact restored.", "success")
    return redirect(url_for("contacts.index"))


@bp.route("/contacts/<int:id>/hard-delete", methods=["DELETE"])
@login_required
def hard_delete(id):
    """Permanently delete a contact."""
    contact = Contact.query.get_or_404(id)

    if not contact.can_hard_delete:
        flash("Cannot permanently delete. Record is older than 5 minutes.", "error")
        return redirect(url_for("contacts.index"))

    contact.hard_delete()
    flash("Contact permanently deleted.", "success")
    return redirect(url_for("contacts.index"))
```

### HTMX Delete Handler

For inline deletion with HTMX:

```python
@bp.route("/contacts/<int:id>/delete", methods=["DELETE"])
@login_required
def delete(id):
    """Soft delete with HTMX support."""
    contact = Contact.query.get_or_404(id)
    contact.soft_delete(user_id=current_user.id)

    # Return empty response to remove row, or updated row
    if request.headers.get("HX-Request"):
        return "", 200  # Row will be removed by hx-swap="delete"

    flash("Contact deleted.", "success")
    return redirect(url_for("contacts.index"))
```

---

## Migration Guide

### Adding Soft Delete to Existing Model

1. **Add mixin to model:**

```python
class Contact(db.Model, SoftDeleteMixin):
    # existing columns...
```

2. **Create migration:**

```bash
flask db migrate -m "Add soft delete to contact"
```

3. **Update all queries** from `Contact.query` to `Contact.active()`:

```python
# Search for these patterns in your codebase
Contact.query.all()           -> Contact.active().all()
Contact.query.filter_by(...)  -> Contact.active().filter_by(...)
Contact.query.filter(...)     -> Contact.active().filter(...)
```

4. **Add restore route** to controller

5. **Update templates** with delete macros

### Rollout Order

Apply soft delete to models in dependency order:

1. **Phase 1**: Contact, ServiceLocation
2. **Phase 2**: ServiceRequest, Quote
3. **Phase 3**: Invoice, TimeEntry, Document

---

## CSS Classes

The following CSS classes are available in `base.css`:

| Class | Description |
|-------|-------------|
| `.deleted-indicator` | Pink pill badge for deleted items |
| `.deleted-row` | Pink table row background |
| `.deleted-name` | Strikethrough text |
| `.deleted-item` | Container styling |
| `.btn-restore` | Restore button |
| `.parent-deleted-indicator` | Pink pill badge for child entities with deleted parent |

---

**Next:** [Database Patterns](database.md) | [MVC Pattern](mvc.md) | [HTMX Patterns](htmx.md)
