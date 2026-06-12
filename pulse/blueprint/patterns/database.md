# Database Patterns

> SQLAlchemy with ModelRegistry, module-scoped models, and query patterns.

---

## Table of Contents

- [Development vs Production Mode](#development-vs-production-mode)
- [Database Setup](#database-setup)
- [ModelRegistry Pattern](#modelregistry-pattern)
- [Model Conventions](#model-conventions)
- [Enumerations & Lookup Tables](#enumerations--lookup-tables)
- [Query Patterns](#query-patterns)
- [Sample Data Pattern](#sample-data-pattern)
- [Relationships](#relationships)
- [Loading Strategy Rules](#loading-strategy-rules)
- [The Read / Write Split](#the-read--write-split)
- [Tenant Isolation](#tenant-isolation)
- [Composite Indexes](#composite-indexes)
- [Query Budgets and Enforcement](#query-budgets-and-enforcement)
- [Transactions](#transactions)
- [Multi-Workspace](#multi-workspace)
- [Performance](#performance)

---

## Development vs Production Mode

> **CRITICAL:** When a `VERSION` file exists, sparQ uses migrations for schema changes. Any model changes MUST include a migration file. See [Post-Release Workflow](#post-release-workflow) below.

sparQ operates in two modes controlled by the presence of a `VERSION` file in the project root.

### Two Environments

| Environment | Database Workflow | Data Persistence |
|-------------|------------------|------------------|
| **Local Dev** | `make reset && make demo && make run` | Reset freely - it's your local data |
| **Production** | Migrations only | Real data - never reset |

### Local Development

Use the standard workflow:

```bash
make reset && make demo && make run
```

- `make reset` drops all tables, recreates from models, stamps at HEAD
- `make demo` seeds Crystal Clear Cleaning demo data
- `make run` starts Flask development server

You can reset freely during development - it's your local database.

### Production Mode

When the `VERSION` file exists:

- **Migrations auto-run** on startup via `initialize_database()`
- **Schema changes require migrations** - never modify models without one
- **Data persists** - no resets, no demo seeding

Migrations run automatically on application startup.

### What Happens on Startup

| Scenario | Behavior |
|----------|----------|
| **Fresh install** (no DB) | `db.create_all()` creates tables, stamps HEAD |
| **Existing with migrations** | Runs pending migrations only |
| **Legacy install** (tables, no alembic_version) | Stamps baseline, runs migrations |

### Post-Release Workflow

**After v0.5.0, all model changes require migrations:**

```bash
# 1. Make your model changes (add column, new table, etc.)
# Edit your model file (e.g., data/modules/apps/yourapp/models/yourmodel.py)

# 2. Generate migration
flask db migrate -m "Add field_name to table_name"

# 3. Review the generated migration
# Check migrations/versions/xxxx_add_field_name.py

# 4. Apply locally
flask db upgrade

# 5. Commit BOTH model and migration together
git add modules/... migrations/versions/...
git commit -m "Add field_name to table_name"
```

> **Important:** Always commit the model change AND migration file together. Production installs will run the migration to update their schema.

### Checking Current Mode

```python
from system.version import is_production, get_version

if is_production():
    print(f"Production mode (v{get_version()})")
    # Migrations handle schema changes
else:
    print("Development mode")
    # db.create_all() used directly
```

---

## Database Setup

### SQLite (Default)

SQLite is the default - no setup required. Database file created at `app.db`.

```python
# In app.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "app.db"
)
```

**SQLite works great for:**
- Development and prototyping
- Small to medium production apps
- Single-server deployments

### Database Instance

The SQLAlchemy instance is centralized in the system layer:

```python
# system/db/database.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
```

All modules import from this location:

```python
from system.db.database import db
```

---

## ModelRegistry Pattern

sparQ uses `@ModelRegistry.register` to track all models across modules.

### Basic Usage

```python
# data/modules/apps/yourapp/models/item.py
from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class Item(db.Model):
    __tablename__ = "yourapp_item"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
```

### Association Tables

For many-to-many relationships:

```python
# modules/core/models/user_group.py
from system.db.database import db
from system.db.decorators import ModelRegistry

user_group = db.Table(
    "user_group",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id")),
    db.UniqueConstraint("user_id", "group_id"),
)

# Register with explicit module name
ModelRegistry.register_table(user_group, "core")
```

### Registry Output

On startup, the registry prints a summary:

```
Database Model Registry:
--------   ----------   --------------------
Module     Model        Table
--------   ----------   --------------------
core       User         user
core       Group        group
core       user_group   user_group
team       Employee     employee
tasks      Task         task
```

### Registry Internals

```python
# system/db/decorators.py
class ModelRegistry:
    models = []
    registration_order = 1
    MODULE_ORDER = ["core", "team"]  # Load order priority

    @classmethod
    def register(cls, model_class):
        """Decorator to register a model."""
        # Extract module name from path
        module_path = model_class.__module__.split(".")
        if "modules" in module_path:
            module_name = module_path[module_path.index("modules") + 1]
        else:
            module_name = "core"

        cls.models.append({
            "module": module_name,
            "model": model_class.__name__,
            "table": model_class.__tablename__,
            "order": cls.registration_order,
        })
        cls.registration_order += 1
        return model_class
```

---

## Model Conventions

### Naming

- **Tables**: lowercase, singular (`user`, `task`, `employee`)
- **Columns**: snake_case (`created_at`, `user_id`, `first_name`)
- **Foreign keys**: `<entity>_id` (`user_id`, `group_id`)
- **Models**: PascalCase, singular (`User`, `Task`, `Employee`)
- **Tablename**: Always explicit with `__tablename__`

### Standard Model Structure

```python
# data/modules/apps/yourapp/models/item.py
from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class Item(db.Model):
    __tablename__ = "yourapp_item"

    # --- Columns ---
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())

    # --- Relationships ---
    # user = db.relationship("User", backref="items")

    # --- Class Methods (CRUD) ---
    @classmethod
    def create(cls, name, description=None):
        """Create a new item."""
        item = cls(name=name, description=description)
        db.session.add(item)
        db.session.commit()
        return item

    @classmethod
    def get_all(cls):
        """Get all items."""
        return cls.query.all()

    @classmethod
    def get_by_id(cls, item_id):
        """Get item by ID."""
        return cls.query.get(item_id)

    @classmethod
    def delete(cls, item_id):
        """Delete an item."""
        item = cls.query.get(item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            return True
        return False

    @classmethod
    def update(cls, item_id, **kwargs):
        """Update an item."""
        item = cls.query.get(item_id)
        if item:
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            db.session.commit()
            return item
        return None

    # --- Static Methods ---
    @staticmethod
    def get_active():
        """Get active items."""
        return Item.query.filter_by(is_active=True).all()

    # --- Sample Data ---
    @classmethod
    def create_sample_data(cls):
        """Create sample data if table is empty."""
        if not cls.query.first():
            cls.create("Sample Item 1", "Description 1")
            cls.create("Sample Item 2", "Description 2")
```

---

## Enumerations & Lookup Tables

When modeling finite sets of values (statuses, types, categories), choose between Python Enums and database lookup tables based on who controls the values.

### Quick Decision Guide

| Question | If Yes → Use |
|----------|--------------|
| Are values tied to code logic (workflow states, conditionals)? | Enum |
| Will values never change without a code release? | Enum |
| Do admins need to add/modify/disable values? | Lookup Table |
| Are values industry or business-specific? | Lookup Table |

### When to Use Enums

Use Python Enums for **code-controlled values** — fixed sets that drive application logic and require code changes anyway.

**Good candidates:**
- Workflow states (draft → active → completed)
- Type classifications with distinct code paths
- Frequency/recurrence patterns
- System-defined status codes

```python
# modules/apps/service/models/job.py
from enum import Enum
from system.db.database import db
from system.db.decorators import ModelRegistry


class JobStatus(Enum):
    """Workflow states - tied to business logic."""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class JobType(Enum):
    """Job classifications - finite set."""
    ONE_OFF = "one_off"
    RECURRING = "recurring"


@ModelRegistry.register
class Job(db.Model):
    __tablename__ = "service_job"

    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(20), default=JobStatus.DRAFT.value)
    job_type = db.Column(db.String(20), default=JobType.ONE_OFF.value)

    def can_start(self):
        """Enum enables type-safe logic checks."""
        return self.status == JobStatus.SCHEDULED.value

    def complete(self):
        """Workflow transitions are code-controlled."""
        if self.status == JobStatus.IN_PROGRESS.value:
            self.status = JobStatus.COMPLETED.value
            db.session.commit()
```

**Benefits:**
- IDE autocompletion and type checking
- Invalid values caught at development time
- Workflow logic is explicit in code
- No database queries for value lists

### When to Use Lookup Tables

Use lookup tables for **user-controlled values** — sets that admins need to customize without code changes.

**Good candidates:**
- Service/product categories
- Industry-specific classifications
- User-defined tags or labels
- Options that vary by business

```python
# modules/apps/service/models/visit_type.py
from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class VisitType(db.Model):
    """User-configurable visit types.

    Admins can add, rename, disable, and reorder.
    """
    __tablename__ = "service_visit_type"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)  # Soft delete
    sort_order = db.Column(db.Integer, default=0)    # Custom ordering

    @classmethod
    def get_active(cls):
        """Get active types for dropdowns."""
        return cls.query.filter_by(is_active=True).order_by(cls.sort_order).all()

    @classmethod
    def create_sample_data(cls):
        """Seed sensible defaults."""
        if not cls.query.first():
            defaults = [
                ("Initial Consultation", "First meeting with client"),
                ("Regular Service", "Standard service visit"),
                ("Follow-up", "Check on previous work"),
                ("Emergency", "Urgent unscheduled visit"),
            ]
            for i, (name, desc) in enumerate(defaults):
                db.session.add(cls(name=name, description=desc, sort_order=i))
            db.session.commit()
```

**Lookup table conventions:**
- Include `is_active` for soft delete (don't break existing references)
- Include `sort_order` for admin-controlled display order
- Provide `create_sample_data()` with sensible defaults
- Use `get_active()` pattern for dropdown population

### Hybrid Pattern

Sometimes you need both: code-controlled states with user-customizable metadata.

```python
class JobStatus(Enum):
    """Fixed workflow states."""
    DRAFT = "draft"
    COMPLETED = "completed"


@ModelRegistry.register
class JobStatusDisplay(db.Model):
    """User-customizable display for fixed statuses."""
    __tablename__ = "service_job_status_display"

    status = db.Column(db.String(20), primary_key=True)  # Matches enum value
    display_name = db.Column(db.String(50))              # Custom label
    color = db.Column(db.String(20))                     # UI color code
```

This lets admins customize how statuses appear (rename "Draft" to "Pending Review", change colors) without affecting the underlying workflow logic.

---

## Query Patterns

### Basic Queries

```python
# Get by ID
item = Item.query.get(1)
item = Item.query.get_or_404(1)  # Raises 404 if not found

# Filter
item = Item.query.filter_by(name="Test").first()
items = Item.query.filter(Item.is_active == True).all()

# Order and limit
items = Item.query.order_by(Item.created_at.desc()).limit(10).all()

# Count
count = Item.query.count()

# First or None
item = Item.query.filter_by(name="Test").first()
```

### Pagination

```python
@classmethod
def list_paginated(cls, page=1, per_page=20):
    """List items with pagination."""
    return cls.query.order_by(cls.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

# Usage
pagination = Item.list_paginated(page=1)
items = pagination.items
total_pages = pagination.pages
has_next = pagination.has_next
```

### Eager Loading (Avoid N+1)

All relationships use `lazy=LAZY` (imported from `system.db.raise_on_lazy`). In dev/test (`SPARQ_RAISE_ON_LAZY=1`), this resolves to `"raise_on_sql"` and forces explicit loaders. In production (env var unset), it falls back to `"select"` so missing loaders cause N+1 queries instead of 500 errors. See [Loading Strategy Rules](#loading-strategy-rules) for details.

```python
from sqlalchemy.orm import joinedload, selectinload

# joinedload for many-to-one / one-to-one
entry = TimeEntry.scoped().options(joinedload(TimeEntry.clock_punch)).filter_by(id=eid).first()

# selectinload for one-to-many / many-to-many
project = Project.scoped().options(selectinload(Project.action_items)).filter_by(id=pid).first()

# Chain for nested access
posts = UpdatePost.scoped().options(
    joinedload(UpdatePost.member).joinedload(WorkspaceUser.user),
    joinedload(UpdatePost.template),
).all()
```

---

## Sample Data Pattern

Every model should have a `create_sample_data()` method:

```python
@classmethod
def create_sample_data(cls):
    """Create sample data for development/demo.

    Called from module's init_database() hook.
    Must be idempotent (safe to call multiple times).
    """
    if not cls.query.first():  # Only if table is empty
        cls.create("Sample 1")
        cls.create("Sample 2")
```

**In module.py:**

```python
@hookimpl
def init_database(self):
    """Initialize database."""
    db.create_all()
    try:
        from .models.item import Item
        Item.create_sample_data()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Sample data error: {e}")
```

---

## Relationships

Every `relationship()` must set `lazy=` explicitly. See [Loading Strategy Rules](#loading-strategy-rules) for the allowed values.

### One-to-Many

```python
# Parent (User)
@ModelRegistry.register
class User(db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    tasks = db.relationship("Task", backref="user", lazy="dynamic")


# Child (Task)
@ModelRegistry.register
class Task(db.Model):
    __tablename__ = "task"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
```

### Many-to-Many

```python
# Association table
user_group = db.Table(
    "user_group",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id")),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id")),
)
ModelRegistry.register_table(user_group, "core")


# User model
@ModelRegistry.register
class User(db.Model):
    __tablename__ = "user"
    groups = db.relationship("Group", secondary=user_group, backref="users", lazy=LAZY)


# Group model
@ModelRegistry.register
class Group(db.Model):
    __tablename__ = "group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
```

### One-to-One

```python
# User
@ModelRegistry.register
class User(db.Model):
    __tablename__ = "user"
    employee_profile = db.relationship("Employee", uselist=False, backref="user")


# Employee
@ModelRegistry.register
class Employee(db.Model):
    __tablename__ = "employee"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True)
```

---

## Loading Strategy Rules

Every `relationship()` must set `lazy=` explicitly.

### Allowed strategies

| Strategy | When to use |
|---|---|
| `lazy=LAZY` | **Default for all new relationships.** Import from `system.db.raise_on_lazy`. Resolves to `"raise_on_sql"` in dev/test, `"select"` in production. |
| `lazy="joined"` | AuditMixin / SoftDeleteMixin backrefs (one row, always needed). |
| `lazy="dynamic"` | Collection queries where the caller filters/paginates (e.g. `user.posts.filter_by(...)`). |
| `lazy="select"` | Only with explicit justification in a code comment. |

### Environment-gated enforcement

The `SPARQ_RAISE_ON_LAZY` environment variable controls two layers of lazy-load enforcement:

1. **Relationship-level:** The `LAZY` constant (from `system.db.raise_on_lazy`) resolves to `"raise_on_sql"` when enabled, `"select"` when disabled.
2. **Session-level:** A `do_orm_execute` event listener applies `raiseload('*')` to every SELECT, catching any lazy load not covered by explicit loaders.

In dev/test (`SPARQ_RAISE_ON_LAZY=1`), both layers are active — missing `joinedload`/`selectinload` calls throw `InvalidRequestError` immediately. In production (env var unset), relationships fall back to normal lazy loading so missing loaders cause N+1 queries instead of 500 errors.

```python
# system/db/raise_on_lazy.py
LAZY = "raise_on_sql" if SPARQ_RAISE_ON_LAZY else "select"

# Usage in models:
from system.db.raise_on_lazy import LAZY

user = db.relationship("User", lazy=LAZY)
```

### Eager loading at query time

Read queries that hydrate ORM objects must declare loaders for every relationship the caller will access:

```python
from sqlalchemy.orm import joinedload, selectinload

entry = (
    TimeEntry.scoped()
    .options(
        joinedload(TimeEntry.clock_punch),
        joinedload(TimeEntry.member).joinedload(WorkspaceUser.user),
    )
    .filter_by(id=entry_id)
    .first_or_404()
)
```

Rules:
- Use `joinedload` for many-to-one and one-to-one (small parent row).
- Use `selectinload` for one-to-many and many-to-many (issues `WHERE id IN (...)`).
- Never use `subqueryload` — it is superseded by `selectinload`.
- Chain loaders for nested access: `joinedload(cls.member).joinedload(WorkspaceUser.user)`.
- If loading more than three levels deep, rewrite as a projection query instead.
- `.options().get_or_404()` is invalid on the legacy Query API — use `.options().filter_by(id=X).first_or_404()`.

---

## The Read / Write Split

Reads and writes have different shapes. Write paths need full ORM objects with the unit-of-work. Read paths need flat rows for templates.

### Write paths: use ORM models

Mutations, creations, and operations that depend on domain invariants use full ORM objects in model class methods:

```python
@classmethod
def resolve(cls, action_item_id: int, resolver_id: int) -> Self:
    item = cls.scoped().get_or_404(action_item_id)
    item.status = "resolved"
    item.resolved_by_id = resolver_id
    db.session.commit()
    return item
```

### Read paths: use projection queries

List pages, dashboards, and search results use frozen dataclasses with explicit `select()` statements. These live in `queries/` directories within each module:

```
modules/base/projects/queries/overview.py
modules/base/action_items/queries/mine.py
modules/base/action_items/queries/raised.py
modules/base/people/queries/directory.py
modules/base/dashboard/queries/widgets.py
```

```python
# modules/base/action_items/queries/mine.py

from dataclasses import dataclass
from sqlalchemy import select, func

@dataclass(frozen=True)
class MyActionItemRow:
    id: int
    title: str
    status: str
    project_name: str | None
    due_date: date | None

def get_mine_open(org_id, ts_id, assignee_id) -> list[MyActionItemRow]:
    stmt = (
        select(
            ActionItem.id,
            ActionItem.title,
            ActionItem.status,
            Project.name,
            ActionItem.due_date,
        )
        .outerjoin(Project, ActionItem.project_id == Project.id)
        .where(
            ActionItem.organization_id == org_id,
            ActionItem.workspace_id == ts_id,
            ActionItem.assignee_id == assignee_id,
            ActionItem.status == "open",
        )
    )
    return [MyActionItemRow(*row) for row in db.session.execute(stmt).all()]
```

### When to use which

| Scenario | Approach |
|----------|----------|
| Mutating state | ORM model methods |
| List of 5+ items for display | Projection query |
| Detail page with full domain object + 1-2 collections | ORM with explicit eager loads |
| Data from 3+ tables stitched together | Projection query |

Rules:
- Projection queries return frozen dataclasses. Never raw `Row` objects to templates.
- Projection dataclasses live in the same file as the query that produces them.
- Joins are explicit — do not rely on relationship configuration.
- Templates never traverse relationships. They render data from `queries/` or from a single hydrated ORM object.

---

## Tenant Isolation

### Global tenant filter

Every model that inherits `WorkspaceMixin` is automatically filtered by `organization_id` and `workspace_id` on every read via a `do_orm_execute` session event using `with_loader_criteria`. This includes eager-loaded relationships.

```python
# system/startup/request_hooks.py

@event.listens_for(Session, "do_orm_execute")
def _add_tenant_filter(execute_state):
    if not execute_state.is_select:
        return
    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            WorkspaceMixin,
            lambda cls: cls.organization_id == g.organization_id,
            include_aliases=True,
        )
    )
```

### Rules

- Every content-bearing model inherits `WorkspaceMixin`. The `User` table is authentication-only and does not.
- Projection queries must still include `WHERE organization_id = ...` explicitly. The global filter is defense in depth, not a substitute.
- Cross-tenant operations (admin tooling, internal jobs) must explicitly opt out and require justification in a code comment.

---

## Composite Indexes

Every `WorkspaceMixin` table needs a composite index leading with the tenant scoping columns for each query predicate shape. Adding a new query pattern means adding or extending the composite index via an Alembic migration.

### Rules

- Lead with the columns used in the query's `WHERE` clause — typically `organization_id`, `workspace_id`, then the discriminator.
- Do not rely on PostgreSQL to combine separate single-column indexes.
- Declare indexes in both the Alembic migration and the model's `__table_args__`.

### Example

```python
# In the model
__table_args__ = (
    db.Index("ix_project_org_ts_status", "organization_id", "workspace_id", "status"),
    db.Index("ix_project_owner", "owner_id", "status"),
    db.Index("ix_project_channel", "channel_id"),
)
```

```python
# In the Alembic migration
op.create_index("ix_project_org_ts_status", "project",
                ["organization_id", "workspace_id", "status"])
```

### Current composite indexes

| Table | Index | Covers |
|-------|-------|--------|
| `project` | `ix_project_org_ts_status` | Overview query |
| `project` | `ix_project_owner` | Owner lookup |
| `project` | `ix_project_channel` | Post aggregation join |
| `action_item` | `ix_action_item_assignee_open` | Mine open/closed |
| `action_item` | `ix_action_item_raised_by` | Raised open/closed |
| `action_item` | `ix_action_item_blocker` | Blocker queries |
| `action_item` | `ix_action_item_project_org` | Overview aggregation |
| `update_post` | `ix_update_post_type_date` | Feed by type |
| `update_post` | `ix_update_post_template_date` | Feed by template |
| `update_post` | `ix_update_post_member_date` | Feed by member |
| `update_post` | `ix_update_post_channel_org` | Overview post aggregation |
| `workspace_user` | `ix_workspace_user_org_ts_active` | Directory listing |
| `activity_log` | `ix_activity_log_org_ts_date` | Dashboard recent activities |
| `time_entry` | `ix_time_entry_member_date` | Day/week views |
| `time_entry` | `ix_time_entry_status` | Approval queue |
| `clock_punch` | `ix_clock_punch_member_time` | Clock queries |
| `leave_request` | `ix_leave_request_member_dates` | PTO calendar |
| `leave_request` | `ix_leave_request_status` | PTO approval queue |

---

## Query Budgets and Enforcement

### Budgets

| Surface | Max queries | Max DB time |
|---|---|---|
| Dashboard / list pages | 6 | 150 ms |
| Detail pages | 10 | 200 ms |
| Mutation endpoints | 5 | 100 ms |
| Auth / signup | 8 | 200 ms |

Requests exceeding 20 queries are logged at WARN level. Sustained budget violations are bugs.

### Per-request observability

Every request logs query count and DB time via `system/startup/request_hooks.py`. The dev UI System Info panel shows these per-request for in-app spot checks.

### CI assertions

Critical endpoints have integration tests using the `assert_max_queries` context manager:

```python
# tests/helpers/query_counter.py
from tests.helpers.query_counter import assert_max_queries

def test_dashboard_query_budget(app, seeded_workspace):
    client = seeded_workspace["client"]
    with app.app_context():
        with assert_max_queries(6, "dashboard index"):
            resp = client.get("/dashboard/")
        assert resp.status_code == 200
```

Budget test ceilings in `tests/integration/test_query_budgets.py` reflect current query counts as regression gates. They will tighten as endpoints are refactored to use projection queries.

### Migration plan for existing endpoints

Existing endpoints exceeding budget are refactored on a rolling basis:

1. Write a CI test asserting the current (bad) query count as a baseline.
2. Refactor: convert read paths to projection queries, add explicit eager loads where ORM hydration is correct.
3. Update the test to assert the new budget.
4. Ship. Each refactor is its own PR with before/after query count in the description.

---

## Transactions

### Automatic Commits

Each model method commits automatically:

```python
@classmethod
def create(cls, name):
    item = cls(name=name)
    db.session.add(item)
    db.session.commit()  # Commits here
    return item
```

### Manual Transaction

```python
def transfer_credits(from_id, to_id, amount):
    """Atomic credit transfer."""
    try:
        from_user = User.query.get(from_id)
        to_user = User.query.get(to_id)

        from_user.credits -= amount
        to_user.credits += amount

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
```

### Context Manager Pattern

```python
from contextlib import contextmanager

@contextmanager
def transaction():
    """Transaction context manager."""
    try:
        yield db.session
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


# Usage
with transaction():
    user1.credits -= 100
    user2.credits += 100
```

---

## Multi-Workspace

> **CRITICAL: Workspace isolation is the #1 security invariant in sparQ. Every query that touches workspace-scoped data MUST be filtered by workspace. A missing workspace filter means data from one customer leaks to another.**

### WorkspaceMixin

All workspace-scoped models use `WorkspaceMixin`, which adds a `workspace_id` FK column and query helpers:

```python
from system.db.workspace import WorkspaceMixin

@ModelRegistry.register
class Contact(db.Model, WorkspaceMixin, AuditMixin):
    __tablename__ = "contact"
    # workspace_id is added automatically by WorkspaceMixin
    # ondelete="CASCADE" — deleting a workspace cascades to all scoped rows
```

### Querying Workspace-Scoped Data

**ALWAYS use `.scoped()` for workspace-scoped models.** This filters by `g.workspace_id` automatically:

```python
# CORRECT — scoped to current workspace
contacts = Contact.scoped().filter_by(active=True).all()
employee = Employee.scoped().get_or_404(employee_id)

# WRONG — returns data from ALL workspaces (data leak!)
contacts = Contact.query.filter_by(active=True).all()
```

### Joins with Workspace-Scoped Models

When joining from a non-scoped model (like `User.query`) to a scoped model, you MUST add a workspace filter manually:

```python
# CORRECT — explicit workspace filter on the joined model
from flask import g
query = User.query.join(Employee).filter(
    Employee.workspace_id == g.workspace_id,
)

# WRONG — returns users from ALL workspaces (data leak!)
query = User.query.join(Employee)
```

**Rule: If you start a query from `Model.query` instead of `Model.scoped()`, you are responsible for adding the workspace filter yourself.**

### Association Tables

All FKs in association tables that reference workspace-scoped models MUST have `ondelete="CASCADE"` so that workspace deletion cascades cleanly:

```python
user_group = db.Table(
    "user_group",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE")),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id", ondelete="CASCADE")),
)
```

### Checklist for New Features

Before merging any feature that touches data:

- [ ] Every model with business data extends `WorkspaceMixin`
- [ ] Every query uses `.scoped()` or explicitly filters by `workspace_id`
- [ ] Joins from `User.query` to scoped models include `workspace_id == g.workspace_id`
- [ ] Association table FKs have `ondelete="CASCADE"`
- [ ] Test: seed two workspaces, verify each only sees its own data

---

## Performance

### Indexes

```python
# Single column index
email = db.Column(db.String(255), index=True)

# Unique index
email = db.Column(db.String(255), unique=True)

# Composite index
__table_args__ = (
    db.Index("ix_setting_user_key", "user_id", "key"),
)
```

### Query Optimization

```python
# Limit columns fetched
users = User.query.options(db.load_only(User.id, User.email)).all()

# Batch inserts
db.session.bulk_insert_mappings(User, [
    {"email": "user1@example.com", "name": "User 1"},
    {"email": "user2@example.com", "name": "User 2"},
])
db.session.commit()

# Batch updates
User.query.filter(User.is_active == False).update({"is_active": True})
db.session.commit()
```

### Avoid N+1 Queries

With `SPARQ_RAISE_ON_LAZY=1` (dev/test), accessing an unloaded relationship throws `InvalidRequestError`. In production, it falls back to a lazy SQL query (N+1). Always declare loaders explicitly:

```python
from sqlalchemy.orm import joinedload

# BAD — raises in dev, N+1 in production
users = User.query.all()
for user in users:
    print(user.tasks)  # Throws in dev!

# GOOD — explicit eager load
users = User.query.options(joinedload(User.tasks)).all()
for user in users:
    print(user.tasks)  # Already loaded

# BEST — for lists of 5+ items, use a projection query instead (see Read / Write Split)
```

---

## Query Performance

A page render in sparQ touches the same row from many places — context
processors, sidebar partials, the controller, the template itself. Without
deliberate care this collapses into hundreds of duplicate SELECTs. The patterns
below are the conventions for keeping query counts low; they are also what
`sparq-blueprint-audit` checks against.

### Feed-style methods eager-load what templates touch

A method that returns a list of rows for a template (e.g. `get_feed`,
`get_for_member`) MUST `joinedload` every relationship the template will
access. The templates are the source of N+1 — by the time you're in Jinja
it's too late to batch.

```python
# GOOD — feed query loads template, member→user, area in one statement
@classmethod
def get_feed(cls, ...):
    from sqlalchemy.orm import joinedload
    return (
        cls.scoped()
        .options(
            joinedload(cls.template),
            joinedload(cls.member).joinedload(WorkspaceUser.user),
            joinedload(cls.area),
        )
        .filter(...)
        .all()
    )
```

If the template touches `post.member.user.full_name`, you need
`joinedload(cls.member).joinedload(WorkspaceUser.user)` — both legs.

### Provide batch lookups alongside per-row ones

When a model exposes a per-row helper used inside template loops
(`UpdatePostReaction.get_for_message(post_id)`,
`UpdatePostAck.get_for_post(post_id, member_id)`), it MUST also expose a
batched `get_for_posts(post_ids)` that takes a list and returns a
`dict[post_id, …]`. Controllers populate the dict once and pass it into the
template; templates read from the dict instead of calling the per-row helper.

```python
# Per-row helper — fine for single-post views
@classmethod
def get_for_message(cls, post_id): ...

# Batched companion — single SELECT for all visible posts
@classmethod
def get_for_posts(cls, post_ids: list[int]) -> dict[int, dict]:
    from sqlalchemy.orm import joinedload
    rows = (
        cls.scoped()
        .options(joinedload(cls.member).joinedload(WorkspaceUser.user))
        .filter(cls.post_id.in_(post_ids))
        .all()
    )
    result = {pid: {} for pid in post_ids}
    for r in rows:
        ...  # group into result[r.post_id]
    return result
```

Templates pick the map when present and fall back to the per-row helper so
non-feed callers (mobile, single-post pages) keep working unchanged:

```jinja
{% if reactions_map is defined %}
    {% set reactions = reactions_map.get(post.id, {}) %}
{% else %}
    {% set reactions = UpdatePostReaction.get_for_message(post.id) %}
{% endif %}
```

### Use `current_member()` instead of inline lookups

The current-user `WorkspaceUser` row is fetched by many context processors,
the active-page controller, and `User.workspace_membership`. Always go
through the cached helper:

```python
from system.auth.current_member import current_member

member = current_member()        # request-cached on g._current_member_cache
member_id = member.id if member else None
```

Never write `WorkspaceUser.get_by_user_id(current_user.id)` in a context
processor or controller — each call adds a duplicate SELECT.

### Memoize hot model properties per-instance

A `@property` on a model that issues a query and is called from many
templates (`User.workspace_membership`, `User.is_admin`) must memoize on the
instance. The SQLAlchemy identity map keeps `self` stable for the request,
so an instance attribute scopes naturally to the request:

```python
@property
def workspace_membership(self):
    from flask import g
    workspace_id = getattr(g, "workspace_id", None)
    if workspace_id is None:
        return None
    if getattr(self, "_ts_membership_cache_key", None) == workspace_id:
        return self._ts_membership_cache
    membership = WorkspaceUser.query.filter_by(
        user_id=self.id, workspace_id=workspace_id
    ).filter(WorkspaceUser.deleted_at.is_(None)).first()
    self._ts_membership_cache_key = workspace_id
    self._ts_membership_cache = membership
    return membership
```

Key the cache so it invalidates if the relevant context (here `workspace_id`)
changes mid-process.

### Memoize per-template-call helpers on `g`

A Jinja filter or helper that runs once per template invocation
(`format_datetime`, `format_date`) must NOT issue a fresh DB query on each
call. Cache the resolved value on `g` for the request:

```python
_TZ_UNSET = object()

def _resolve_user_timezone() -> str:
    cached = getattr(g, "_user_tz_name_cache", _TZ_UNSET)
    if cached is not _TZ_UNSET:
        return cached
    # ... resolve from UserSetting / company_settings / default ...
    g._user_tz_name_cache = tz_name
    return tz_name
```

### Memoize `get_for_*` lookups by args on `g`

Heavy classmethod lookups called from multiple context processors with the
same args (`UpdateTemplate.get_for_workspace(post_type)`) memoize a dict on
`g` keyed by their arguments:

```python
@classmethod
def get_for_workspace(cls, post_type=None):
    cache_key = (getattr(g, "workspace_id", None), post_type)
    try:
        cache = getattr(g, "_update_template_cache", None)
        if cache is None:
            cache = {}
            g._update_template_cache = cache
        if cache_key in cache:
            return cache[cache_key]
    except Exception:
        cache = None
    result = cls.query.filter(...).all()
    if cache is not None:
        cache[cache_key] = result
    return result
```

Use a sentinel or `try/except` — code can run outside a request context
(scripts, schedulers) where `g` is unavailable.

### Auditing query counts

Use the test client with a SQLAlchemy `before_cursor_execute` hook to
snapshot a real request's query log. Group by table + caller stack to find
duplicates and N+1s:

```python
from collections import Counter
import re, traceback
from sqlalchemy import event
from system.db.database import db

stmts = []
@event.listens_for(db.engine, "before_cursor_execute")
def _log(conn, cursor, statement, params, context, executemany):
    s = " ".join(statement.split())
    m = re.match(r"(SELECT|INSERT|UPDATE|DELETE).*?(FROM|INTO|UPDATE)\s+([\w.]+)", s)
    stmts.append(f"{m.group(1)} {m.group(3)}" if m else s.split()[0])

# resp = client.get("/some/route/")
# Counter(stmts).most_common(10)  →  any count > visible-rows is suspicious
```

For duplicates, capture the user-code frame from `traceback.extract_stack()`
to identify the responsible caller. Dev pages also expose a System Info
panel showing per-request `DB queries` and `DB time` for in-app spot checks.

---

## Cross-Module References

When referencing models from other modules:

```python
# In modules/team/models/employee.py
from modules.core.models.user import User

@ModelRegistry.register
class Employee(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref="employee_profile")
```

**Note:** Direct imports create coupling. Only depend on core module unless necessary.

---

**Next:** [Module System](module-system.md) | [MVC Pattern](mvc.md) | [Testing](testing.md)
