# Authentication & Authorization

> Flask-Login with group-based access control for sparQ modules.

---

## Table of Contents

- [Overview](#overview)
- [Flask-Login Setup](#flask-login-setup)
- [User Model](#user-model)
- [Group-Based Access Control](#group-based-access-control)
- [Decorators](#decorators)
- [Login Flow](#login-flow)
- [Protected Routes](#protected-routes)
- [Template Patterns](#template-patterns)

---

## Overview

sparQ uses Flask-Login with a **group-based access control** system:

- **Flask-Login** handles session management
- **Groups** (`ALL`, `ADMIN`, custom) control permissions
- **Password authentication** (with hashing via werkzeug)
- **Decorators** protect routes (`@login_required`, `@admin_required`)

---

## Flask-Login Setup

### In app.py

```python
from flask_login import LoginManager
from modules.core.models.user import User

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "core_bp.login"  # Redirect for @login_required

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
```

### Configuration

```python
# In app.py or config
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")

# Session settings (optional)
app.config["SESSION_COOKIE_SECURE"] = True  # Production: HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
```

---

## User Model

### Core User Model

```python
# modules/core/models/user.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class User(db.Model, UserMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    # Relationships
    groups = db.relationship("Group", secondary="user_group", backref="users")

    # Password handling
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # Group membership
    @property
    def is_admin(self):
        return any(group.name == "ADMIN" for group in self.groups)

    def add_to_group(self, group):
        if group not in self.groups:
            self.groups.append(group)
            db.session.commit()

    def remove_from_group(self, group):
        if group in self.groups:
            self.groups.remove(group)
            db.session.commit()

    # CRUD
    @classmethod
    def create(cls, email, password, first_name, last_name, is_admin=False):
        user = cls(email=email, first_name=first_name, last_name=last_name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Add to ALL group
        from .group import Group
        all_group = Group.get_or_create("ALL", "Default group", True)
        user.add_to_group(all_group)

        if is_admin:
            admin_group = Group.get_or_create("ADMIN", "Administrators", True)
            user.add_to_group(admin_group)

        return user

    @staticmethod
    def get_by_email(email):
        return User.query.filter_by(email=email).first()
```

---

## Group-Based Access Control

### Group Model

```python
# modules/core/models/group.py
from system.db.database import db
from system.db.decorators import ModelRegistry


@ModelRegistry.register
class Group(db.Model):
    __tablename__ = "group"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(256))
    is_system = db.Column(db.Boolean, default=False)

    @classmethod
    def get_or_create(cls, name, description="", is_system=False):
        """Get existing group or create new one."""
        group = cls.query.filter_by(name=name).first()
        if not group:
            group = cls(name=name, description=description, is_system=is_system)
            db.session.add(group)
            db.session.commit()
        return group

    @classmethod
    def get_admin_group(cls):
        return cls.query.filter_by(name="ADMIN").first()

    @classmethod
    def get_all_group(cls):
        return cls.query.filter_by(name="ALL").first()
```

### User-Group Association Table

```python
# modules/core/models/user_group.py
from system.db.database import db
from system.db.decorators import ModelRegistry

user_group = db.Table(
    "user_group",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("group_id", db.Integer, db.ForeignKey("group.id"), primary_key=True),
    db.UniqueConstraint("user_id", "group_id"),
)

ModelRegistry.register_table(user_group, "core")
```

### Default Groups

Created in `app.py` during startup:

```python
# In app.py, after db.create_all()
Group.get_or_create("ALL", "Default group for all users", True)
Group.get_or_create("ADMIN", "Administrators group", True)
```

---

## Decorators

### admin_required Decorator

```python
# system/auth/decorators.py
from functools import wraps
from flask import redirect, url_for, flash
from flask_login import current_user


def admin_required(f):
    """Decorator that requires admin group membership."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("core_bp.login"))
        if not current_user.is_admin:
            flash("Admin access required.", "error")
            return redirect(url_for("core_bp.login"))
        return f(*args, **kwargs)
    return decorated_function


def group_required(group_name):
    """Decorator that requires membership in a specific group."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash("Please log in.", "warning")
                return redirect(url_for("core_bp.login"))
            if not any(g.name == group_name for g in current_user.groups):
                flash(f"Access requires {group_name} membership.", "error")
                return redirect(url_for("core_bp.login"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
```

### Usage

```python
from flask_login import login_required
from system.auth.decorators import admin_required, group_required

@blueprint.route("/")
@login_required
def index():
    """Any authenticated user."""
    return render_template("index.html")


@blueprint.route("/admin")
@login_required
@admin_required
def admin_panel():
    """Admin users only."""
    return render_template("admin.html")


@blueprint.route("/managers")
@login_required
@group_required("MANAGERS")
def managers_only():
    """Specific group required."""
    return render_template("managers.html")
```

---

## Login Flow

### Login Route

```python
# modules/core/controllers/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user
from ..models.user import User

blueprint = Blueprint("core_bp", __name__, ...)


@blueprint.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        user = User.get_by_email(email)

        if user and user.check_password(password):
            login_user(user, remember=True)
            flash("Welcome back!", "success")

            # Redirect to requested page or default
            next_page = request.args.get("next")
            return redirect(next_page or url_for("core_bp.index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@blueprint.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("core_bp.login"))
```

### Registration Route

```python
@blueprint.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("core_bp.index"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")

        if User.get_by_email(email):
            flash("Email already registered.", "error")
            return render_template("register.html")

        user = User.create(email, password, first_name, last_name)
        login_user(user)
        flash("Registration successful!", "success")
        return redirect(url_for("core_bp.index"))

    return render_template("register.html")
```

---

## Protected Routes

### In Modules

```python
# data/modules/apps/yourapp/controllers/routes.py
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from system.auth.decorators import admin_required

blueprint = Blueprint("yourapp_bp", __name__, ...)


@blueprint.route("/")
@login_required
def index():
    """Requires login."""
    return render_template("yourapp/desktop/index.html")


@blueprint.route("/admin")
@login_required
@admin_required
def admin():
    """Requires admin."""
    return render_template("yourapp/desktop/admin.html")
```

### API Routes (JSON Response)

```python
from flask import jsonify

def login_required_api(f):
    """API version - returns JSON instead of redirect."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated


@blueprint.route("/api/data")
@login_required_api
def api_data():
    return jsonify({"data": "..."})
```

---

## Template Patterns

### Checking Authentication

```html
{% if current_user.is_authenticated %}
    <span>Welcome, {{ current_user.first_name }}!</span>
    <a href="{{ url_for('core_bp.logout') }}">Logout</a>
{% else %}
    <a href="{{ url_for('core_bp.login') }}">Login</a>
{% endif %}
```

### Checking Admin Status

```html
{% if current_user.is_authenticated and current_user.is_admin %}
    <a href="{{ url_for('core_bp.admin_settings') }}">Admin Settings</a>
{% endif %}
```

### Login Form

```html
<!-- login.html -->
{% extends "core/desktop/base-auth.html" %}

{% block content %}
<form method="POST">
    <div class="mb-3">
        <label class="form-label">{{ _("Email") }}</label>
        <input type="email" name="email" class="form-control" required>
    </div>
    <div class="mb-3">
        <label class="form-label">{{ _("Password") }}</label>
        <input type="password" name="password" class="form-control" required>
    </div>
    <button type="submit" class="btn btn-primary">{{ _("Login") }}</button>
</form>
{% endblock %}
```

---

## User Group Management

### Adding/Removing Users from Groups

```python
# In admin controller
@blueprint.route("/settings/groups/users/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def update_user_groups(user_id):
    user = User.query.get_or_404(user_id)
    group_ids = request.form.getlist("groups")

    # Clear existing non-system groups
    user.groups = [g for g in user.groups if g.is_system]

    # Add selected groups
    for group_id in group_ids:
        group = Group.query.get(group_id)
        if group:
            user.add_to_group(group)

    flash("User permissions updated.", "success")
    return redirect(url_for("core_bp.manage_permissions"))
```

### Preventing Removal of Last Admin

```python
# In User model
@property
def is_sole_admin(self):
    """Check if user is the only admin."""
    if not self.is_admin:
        return False
    admin_group = Group.get_admin_group()
    return len(admin_group.users) == 1

def remove_from_group(self, group):
    if group.name == "ADMIN" and self.is_sole_admin:
        raise ValueError("Cannot remove the last admin")
    if group in self.groups:
        self.groups.remove(group)
        db.session.commit()
```

---

**Next:** [Module System](module-system.md) | [Database](database.md)
