# Type Safety with mypy --strict

> **Complete guide to writing type-safe Python code in sparQ modules.**
> All code must pass `mypy --strict` for consistency and maintainability.

---

## Quick Start

```bash
# Install type checking dependencies
pip install mypy sqlalchemy[mypy] types-Flask

# Run type checker on your module
mypy data/modules/apps/yourapp/

# Run on entire codebase
mypy modules/
```

---

## Table of Contents

- [Setup](#setup)
- [Flask Route Patterns](#flask-route-patterns)
- [SQLAlchemy Model Patterns](#sqlalchemy-model-patterns)
- [Module Class Patterns](#module-class-patterns)
- [Manifest Typing](#manifest-typing)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Setup

### Configuration

sparQ uses `pyproject.toml` for mypy configuration:

```toml
[tool.mypy]
python_version = "3.11"
strict = true
plugins = ["sqlalchemy.ext.mypy.plugin"]

[[tool.mypy.overrides]]
module = ["flask_login.*", "pluggy.*", "flask_sqlalchemy.*"]
ignore_missing_imports = true
```

### What `strict = true` Enables

- `disallow_untyped_defs` - All functions must have type annotations
- `disallow_incomplete_defs` - Partial annotations not allowed
- `check_untyped_defs` - Type check function bodies
- `disallow_untyped_decorators` - Decorators must be typed
- `warn_return_any` - Warn when returning `Any`
- `no_implicit_reexport` - Explicit `__all__` required for re-exports

---

## Flask Route Patterns

### Basic Route

```python
from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue
from flask_login import login_required

blueprint: Blueprint = Blueprint(
    "yourmodule_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
)


@blueprint.route("/")
@login_required
def index() -> ResponseReturnValue:
    """Module home page."""
    return render_template("yourmodule/desktop/index.html")
```

### Route with Parameters

```python
from flask import request, redirect, url_for, flash
from flask.typing import ResponseReturnValue


@blueprint.route("/items/<int:item_id>")
@login_required
def detail(item_id: int) -> ResponseReturnValue:
    """Item detail page."""
    from ..models.item import Item
    item = Item.get_by_id(item_id)
    if item is None:
        flash("Item not found", "error")
        return redirect(url_for("yourmodule_bp.index"))
    return render_template("yourmodule/desktop/detail.html", item=item)
```

### POST Route

```python
@blueprint.route("/items/add", methods=["POST"])
@login_required
def add_item() -> ResponseReturnValue:
    """Create new item."""
    name = request.form.get("name")
    if name:
        from ..models.item import Item
        Item.create(name)
        flash("Item created", "success")
    return redirect(url_for("yourmodule_bp.index"))
```

### HTMX Partial Response

```python
from flask import Response


@blueprint.route("/items/list")
@login_required
def list_partial() -> ResponseReturnValue:
    """Return HTML partial for HTMX."""
    from ..models.item import Item
    items = Item.get_all()
    return render_template("yourmodule/desktop/partials/_list.html", items=items)
```

---

## SQLAlchemy Model Patterns

sparQ uses **SQLAlchemy 2.0** style with `Mapped[T]` for full type inference.

### Basic Model

```python
from datetime import datetime
from typing import ClassVar, Self

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class Item(db.Model):  # type: ignore[name-defined]
    """Item model with full type annotations."""

    __tablename__: ClassVar[str] = "yourmodule_item"

    # Columns use Mapped[T] for type inference
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime, default=func.current_timestamp()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.current_timestamp()
    )
```

### CRUD Class Methods

```python
    @classmethod
    def create(cls, name: str, description: str | None = None) -> Self:
        """Create a new item."""
        item = cls(name=name, description=description)
        db.session.add(item)
        db.session.commit()
        return item

    @classmethod
    def get_all(cls) -> list[Self]:
        """Get all items."""
        return list(cls.query.all())

    @classmethod
    def get_by_id(cls, item_id: int) -> Self | None:
        """Get item by ID."""
        return cls.query.get(item_id)  # type: ignore[return-value]

    @classmethod
    def delete(cls, item_id: int) -> bool:
        """Delete an item by ID."""
        item = cls.query.get(item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            return True
        return False

    @classmethod
    def update(cls, item_id: int, **kwargs: str | None) -> Self | None:
        """Update an item."""
        item = cls.query.get(item_id)
        if item:
            for key, value in kwargs.items():
                if hasattr(item, key):
                    setattr(item, key, value)
            db.session.commit()
        return item  # type: ignore[return-value]
```

### Relationships

```python
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Task(db.Model):  # type: ignore[name-defined]
    __tablename__: ClassVar[str] = "task"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))

    # Relationship with type annotation
    user: Mapped["User"] = relationship(back_populates="tasks")


class User(db.Model):  # type: ignore[name-defined]
    __tablename__: ClassVar[str] = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))

    # One-to-many relationship
    tasks: Mapped[list["Task"]] = relationship(back_populates="user")
```

---

## Module Class Patterns

### Basic Module

```python
from typing import TYPE_CHECKING

from system.db.database import db
from system.module.hooks import hookimpl

if TYPE_CHECKING:
    from flask import Blueprint


class YourModuleModule:
    """Module class implementing lifecycle hooks."""

    def get_routes(self) -> list[tuple["Blueprint", str]]:
        """Return list of (blueprint, url_prefix) tuples."""
        from .controllers.routes import blueprint

        return [(blueprint, "/yourmodule")]

    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables and sample data."""
        db.create_all()
```

### Module with Sample Data

```python
    @hookimpl
    def init_database(self) -> None:
        """Initialize database tables and sample data."""
        db.create_all()

        try:
            from .models.item import Item

            Item.create_sample_data()
        except Exception as e:
            import logging

            logging.getLogger(__name__).error(f"Sample data error: {e}")
```

### Module `__init__.py`

```python
"""Module initialization - exports the module_instance for the loader."""

from .module import YourModuleModule

module_instance: YourModuleModule = YourModuleModule()

__all__: list[str] = ["module_instance"]
```

---

## Manifest Typing

Use `TypedDict` for structured manifest typing:

```python
"""Module manifest - defines metadata for the module loader."""

from typing import Literal, TypedDict


class ModuleManifest(TypedDict):
    """Type definition for module manifest structure."""

    name: str
    version: str
    main_route: str
    type: Literal["App", "System"]
    depends: list[str]
    icon_class: str
    color: str
    description: str
    long_description: str


manifest: ModuleManifest = {
    "name": "YourModule",
    "version": "1.0",
    "main_route": "/yourmodule",
    "type": "App",
    "depends": ["core"],
    "icon_class": "fa-solid fa-cube",
    "color": "#007bff",
    "description": "Short description",
    "long_description": "Detailed description of features.",
}
```

---

## Common Patterns

### Optional Parameters

```python
def search(
    query: str,
    limit: int = 50,
    offset: int = 0,
    active_only: bool = True,
) -> list[Item]:
    """Search with optional parameters."""
    ...
```

### Dictionary Return Types

```python
from typing import TypedDict


class ItemDict(TypedDict):
    id: int
    name: str
    created_at: str


def to_dict(item: Item) -> ItemDict:
    """Convert item to dictionary."""
    return {
        "id": item.id,
        "name": item.name,
        "created_at": item.created_at.isoformat() if item.created_at else "",
    }
```

### Callable Types

```python
from collections.abc import Callable


def with_retry(
    func: Callable[[], T],
    retries: int = 3,
) -> T:
    """Execute function with retry logic."""
    ...
```

### Context Managers

```python
from contextlib import contextmanager
from collections.abc import Generator


@contextmanager
def transaction() -> Generator[None, None, None]:
    """Database transaction context manager."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
```

---

## Troubleshooting

### Common Errors and Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| `error: Name "db.Model" is not defined` | Dynamic base class | Add `# type: ignore[name-defined]` to class |
| `error: Returning Any from function` | Untyped query result | Wrap with `list()` or add type ignore |
| `error: Missing return type annotation` | No `-> Type` on function | Add return type annotation |
| `error: Function is missing type annotation for parameter` | Untyped parameter | Add `: Type` to parameter |
| `error: Incompatible return value type` | Wrong return type | Check actual return vs annotation |

### Flask-SQLAlchemy Query Returns

The `cls.query.get()` method returns `Any` in Flask-SQLAlchemy. Solutions:

```python
# Option 1: Type ignore (recommended for simple cases)
@classmethod
def get_by_id(cls, item_id: int) -> Self | None:
    return cls.query.get(item_id)  # type: ignore[return-value]

# Option 2: Explicit cast (more verbose)
from typing import cast

@classmethod
def get_by_id(cls, item_id: int) -> Self | None:
    result = cls.query.get(item_id)
    return cast(Self | None, result)
```

### Circular Imports

Use `TYPE_CHECKING` to avoid circular imports:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Blueprint
    from ..models.item import Item


def get_routes(self) -> list[tuple["Blueprint", str]]:
    # Import at runtime, not at type-check time
    from .controllers.routes import blueprint
    return [(blueprint, "/yourmodule")]
```

### Untyped Decorators

For decorators without type stubs (like `@hookimpl`), ensure the decorated function has explicit types:

```python
@hookimpl
def init_database(self) -> None:  # Explicit return type required
    db.create_all()
```

---

## Checklist for New Modules

Before committing, verify:

- [ ] All functions have parameter type annotations
- [ ] All functions have return type annotations
- [ ] Models use `Mapped[T]` for columns
- [ ] `__manifest__.py` uses `ModuleManifest` TypedDict
- [ ] `__init__.py` has typed `module_instance`
- [ ] Routes return `ResponseReturnValue`
- [ ] `mypy data/modules/apps/yourapp/` passes with no errors

---

## Resources

- [mypy Documentation](https://mypy.readthedocs.io/)
- [SQLAlchemy 2.0 Typing](https://docs.sqlalchemy.org/en/20/orm/mapped_attributes.html)
- [Flask Type Hints](https://flask.palletsprojects.com/en/latest/typing/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 604 - Union Syntax](https://peps.python.org/pep-0604/)
