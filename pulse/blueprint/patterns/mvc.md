# MVC Pattern Reference

> Complete guide to Models, Views, and Controllers in Flask applications

---

## Table of Contents

- [Philosophy](#philosophy)
- [Models (Fat Models)](#models-fat-models)
- [Views (Templates)](#views-templates)
- [Controllers (Thin Controllers)](#controllers-thin-controllers)
- [Request Flow](#request-flow)
- [Best Practices](#best-practices)

---

## Philosophy

### Fat Models, Thin Controllers

**Models** contain:
- Business logic (validation, calculations)
- Database access (CRUD, queries)
- Domain rules

**Controllers** contain:
- Parse input (query params, form data, JSON)
- Call model methods
- Render view or return JSON
- Handle HTTP-specific concerns (status codes, headers)

**Views** contain:
- Jinja2 templates
- Minimal logic (loops, conditions)
- HTMX attributes for interactivity

### Why Fat Models?

**Models own their domain.** A `Job` model knows how to `publish()`, `close()`, `hold()`. You don't need a `JobService.publish(job)` indirection — the object itself has the behavior.

**No service layer tax.** Service layers add a whole new concept to navigate. Every feature now has 3 places to look (model, service, controller) instead of 2 (model, controller). For a small-to-mid-size codebase, this extra layer is overhead with no payoff.

**Creation lives on the model.** Class methods like `Employee.create(...)` or `Job.create(...)` keep factory logic next to the schema definition. No separate factory classes or service objects needed.

**Avoids "anemic models."** DDD-with-services often produces models that are just data bags, with all logic extracted into services. Fat models keep data + behavior together — the original promise of object-oriented design.

**Mental model stays simple.** MVC is well-understood. Adding bounded contexts, aggregates, repositories, and application services is justified in large enterprise systems but adds cognitive load that doesn't serve a modular Flask app.

**When you'd reconsider:** If a single model file grows past ~500 lines of business logic, extract a mixin or helper — but still keep it on the model, not in a service.

---

## Models (Fat Models)

### Base Model

```python
# app/models/base.py
"""Base model with common fields and methods."""

from datetime import datetime
from app.extensions import db


class BaseModel(db.Model):
    """Abstract base model with timestamps."""

    __abstract__ = True

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    def save(self):
        """Save model to database."""
        if hasattr(self, 'validate'):
            self.validate()
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        """Delete model from database."""
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def get_by_id(cls, id: int):
        """Get record by ID."""
        return cls.query.get(id)

    @classmethod
    def get_or_404(cls, id: int):
        """Get record by ID or raise 404."""
        from app.platform.errors import NotFoundError
        record = cls.query.get(id)
        if record is None:
            raise NotFoundError(f'{cls.__name__} not found')
        return record
```

### User Model (Primary Example)

```python
# app/models/user.py
"""User model - example of a fat model."""

import re
from typing import Optional, List
from flask_login import UserMixin
from app.extensions import db
from app.platform.errors import ValidationError, NotFoundError
from .base import BaseModel


class User(BaseModel, UserMixin):
    """User model with authentication support."""

    __tablename__ = 'user'

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationships
    settings = db.relationship('Setting', backref='user', lazy='dynamic',
                               cascade='all, delete-orphan')

    def validate(self):
        """Validate user data before saving."""
        self.email = self.email.strip().lower() if self.email else ''
        self.name = self.name.strip() if self.name else ''

        if not self.email:
            raise ValidationError('Email is required')
        if not self._is_valid_email(self.email):
            raise ValidationError('Invalid email format')
        if not self.name:
            raise ValidationError('Name is required')
        if len(self.name) > 100:
            raise ValidationError('Name too long (max 100 chars)')

        # Check email uniqueness
        existing = User.query.filter_by(email=self.email).first()
        if existing and existing.id != self.id:
            raise ValidationError('Email already registered')

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def update(self, name: Optional[str] = None, avatar_url: Optional[str] = None):
        """Update user profile."""
        if name is not None:
            self.name = name
        if avatar_url is not None:
            self.avatar_url = avatar_url
        return self.save()

    def get_initials(self) -> str:
        """Get user's initials for avatar placeholder."""
        return self.name[0].upper() if self.name else self.email[0].upper()

    # -------------------------------------------------------------------------
    # Query methods (class-level)
    # -------------------------------------------------------------------------

    @classmethod
    def get_by_email(cls, email: str) -> Optional['User']:
        """Get user by email address."""
        email = email.strip().lower() if email else ''
        return cls.query.filter_by(email=email).first()

    @classmethod
    def list_all(cls, limit: int = 50, offset: int = 0) -> List['User']:
        """List all users with pagination."""
        return cls.query.order_by(cls.created_at.desc()) \
            .limit(limit).offset(offset).all()

    @classmethod
    def create(cls, email: str, name: str, avatar_url: Optional[str] = None) -> 'User':
        """Create a new user."""
        user = cls(email=email, name=name, avatar_url=avatar_url)
        return user.save()
```

### Setting Model (Key-Value Pattern)

```python
# app/models/setting.py
"""Setting model - key-value storage per user."""

from typing import Optional, Dict
from app.extensions import db
from app.platform.errors import ValidationError
from .base import BaseModel


class Setting(BaseModel):
    """User setting model (key-value pairs)."""

    __tablename__ = 'setting'

    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    key = db.Column(db.String(100), nullable=False)
    value = db.Column(db.Text, nullable=False, default='')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'key', name='uq_setting_user_key'),
    )

    def validate(self):
        """Validate setting data."""
        self.key = self.key.strip() if self.key else ''
        if not self.key:
            raise ValidationError('Setting key is required')
        if not self.user_id:
            raise ValidationError('User ID is required')

    @classmethod
    def get_for_user(cls, user_id: int, key: str) -> Optional['Setting']:
        """Get a specific setting for a user."""
        return cls.query.filter_by(user_id=user_id, key=key).first()

    @classmethod
    def get_value(cls, user_id: int, key: str, default: str = '') -> str:
        """Get setting value with default fallback."""
        setting = cls.get_for_user(user_id, key)
        return setting.value if setting else default

    @classmethod
    def get_map(cls, user_id: int) -> Dict[str, str]:
        """Get all settings for a user as a dictionary."""
        settings = cls.query.filter_by(user_id=user_id).all()
        return {s.key: s.value for s in settings}

    @classmethod
    def set(cls, user_id: int, key: str, value: str) -> 'Setting':
        """Create or update a setting (upsert pattern)."""
        setting = cls.get_for_user(user_id, key)
        if setting:
            setting.value = value
        else:
            setting = cls(user_id=user_id, key=key, value=value)
        return setting.save()
```

---

## Views (Templates)

### Base Layout

```html
<!-- app/views/layouts/base.html -->
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ 'rtl' if is_rtl else 'ltr' }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Your App{% endblock %}</title>

  <link href="/static/css/bootstrap.min.css" rel="stylesheet">
  <link href="/static/css/app.css" rel="stylesheet">
  <script src="/static/js/htmx.min.js"></script>

  {% block head %}{% endblock %}
</head>
<body class="bg-light">
  {% include 'partials/_navbar.html' %}

  <main class="container py-4">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% for category, message in messages %}
      <div class="alert alert-{{ 'danger' if category == 'error' else category }} alert-dismissible fade show">
        {{ message }}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
      </div>
      {% endfor %}
    {% endwith %}

    {% block content %}{% endblock %}
  </main>

  <script src="/static/js/bootstrap.bundle.min.js"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

### User Profile Page

```html
<!-- app/views/users/profile.html -->
{% extends 'core/desktop/base.html' %}

{% block title %}{{ user.name }} - Profile{% endblock %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    <div class="card">
      <div class="card-body">
        <div class="d-flex align-items-center mb-4">
          {% if user.avatar_url %}
          <img src="{{ user.avatar_url }}" class="rounded-circle me-3" width="80" height="80">
          {% else %}
          <div class="rounded-circle bg-primary text-white d-flex align-items-center justify-content-center me-3"
               style="width: 80px; height: 80px; font-size: 2rem;">
            {{ user.get_initials() }}
          </div>
          {% endif %}

          <div class="flex-grow-1">
            <h2 class="mb-0">{{ user.name }}</h2>
            <p class="text-muted mb-0">{{ user.email }}</p>
          </div>

          <a href="{{ url_for('users.edit_profile') }}" class="btn btn-outline-primary">
            Edit Profile
          </a>
        </div>

        <hr>

        <dl class="row mb-0">
          <dt class="col-sm-3">Member Since</dt>
          <dd class="col-sm-9">{{ user.created_at.strftime('%B %d, %Y') }}</dd>
        </dl>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

### Settings Form with HTMX

```html
<!-- app/views/settings/index.html -->
{% extends 'core/desktop/base.html' %}

{% block content %}
<div class="row justify-content-center">
  <div class="col-md-8">
    <h2 class="mb-4">Settings</h2>

    <div class="card">
      <div class="card-body">
        <!-- Theme Setting with HTMX -->
        <div class="mb-3">
          <label for="theme" class="form-label">Theme</label>
          <select id="theme" name="value" class="form-select"
                  hx-post="{{ url_for('settings.update') }}"
                  hx-trigger="change"
                  hx-vals='{"key": "theme"}'
                  hx-target="#theme-status"
                  hx-swap="innerHTML">
            <option value="light" {{ 'selected' if settings.theme == 'light' }}>Light</option>
            <option value="dark" {{ 'selected' if settings.theme == 'dark' }}>Dark</option>
          </select>
          <div id="theme-status" class="form-text text-success"></div>
        </div>
      </div>
    </div>
  </div>
</div>
{% endblock %}
```

---

## Controllers (Thin Controllers)

### Main Controller

```python
# app/controllers/main.py
"""Main controller - public pages."""

from flask import Blueprint
from system.device.template import render_device_template

bp = Blueprint('main', __name__)


@bp.route('/')
def index():
    """Home page."""
    return render_device_template('yourmodule/desktop/index.html')


@bp.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'ok'}
```

### Users Controller

```python
# app/controllers/users.py
"""Users controller - profile management."""

from flask import Blueprint, request, redirect, url_for, flash
from flask_login import login_required, current_user
from system.device.template import render_device_template
from app.models import User
from app.platform.errors import ValidationError
from app.platform.logger import get_logger

bp = Blueprint('users', __name__)
log = get_logger()


@bp.route('/profile')
@login_required
def profile():
    """Show current user's profile."""
    return render_device_template('yourmodule/desktop/profile.html', user=current_user)


@bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit current user's profile."""
    errors = {}

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        avatar_url = request.form.get('avatar_url', '').strip()

        try:
            current_user.update(name=name, avatar_url=avatar_url or None)
            log.info('profile_updated', user_id=current_user.id)
            flash('Profile updated successfully', 'success')
            return redirect(url_for('users.profile'))

        except ValidationError as e:
            errors['form'] = e.message

    return render_device_template('yourmodule/desktop/edit.html', user=current_user, errors=errors)
```

### Settings Controller (HTMX)

```python
# app/controllers/settings.py
"""Settings controller - user preferences."""

from flask import Blueprint, request, redirect, url_for
from flask_login import login_required, current_user
from system.device.template import render_device_template
from app.models import Setting

bp = Blueprint('settings', __name__)


@bp.route('/settings')
@login_required
def index():
    """Show settings page."""
    settings = Setting.get_map(current_user.id)

    # Provide defaults
    defaults = {'theme': 'light', 'language': 'en'}
    for key, default in defaults.items():
        if key not in settings:
            settings[key] = default

    return render_device_template('yourmodule/desktop/settings/index.html', settings=settings)


@bp.route('/settings', methods=['POST'])
@login_required
def update():
    """Update a single setting (HTMX endpoint)."""
    key = request.form.get('key', '').strip()
    value = request.form.get('value', '').strip()

    if not key:
        return 'Key required', 400

    Setting.set(current_user.id, key, value)

    # HTMX response
    if request.headers.get('HX-Request') == 'true':
        return 'Saved'

    return redirect(url_for('settings.index'))
```

---

## Request Flow

### Typical Request Lifecycle

1. **Request arrives** → Flask router
2. **Before request hooks** run (auth, request ID)
3. **Route matched** → Controller function called
4. **Decorators** run (@login_required, etc.)
5. **Controller**:
   - Extract user from `current_user`
   - Parse input (request.form, request.args)
   - Call model method
   - Handle errors
   - Render template or return JSON
6. **Response sent** to client

---

## Best Practices

### Models

✅ **Do:**
- Keep all business logic in models
- Use class methods for queries
- Validate in `validate()` method before save
- Return `self` from `save()` for chaining

❌ **Don't:**
- Don't access Flask request/session in models
- Don't log in models (raise errors instead)
- Don't hardcode values (use constants or config)

### Controllers

✅ **Do:**
- Keep controllers thin (just HTTP orchestration)
- Use `current_user` for authenticated user
- Check `HX-Request` header for HTMX requests
- Log actions with context

❌ **Don't:**
- Don't put business logic in controllers
- Don't write raw SQL in controllers
- Don't return internal error details to users

### Views

✅ **Do:**
- Use partials for reusable components (prefix with `_`)
- Use HTMX attributes for interactivity
- Use Bootstrap classes exclusively
- Use i18n for all user-visible text

❌ **Don't:**
- Don't put complex logic in templates
- Don't use inline styles
- Don't hardcode text strings
- Don't use `|safe` unless content is trusted

---

**Next:** [Database Patterns](database.md) | [HTMX Patterns](htmx.md) | [Testing](testing.md)
