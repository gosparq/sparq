# HTMX Patterns

> Server-rendered interactivity without JavaScript frameworks

---

## Table of Contents

- [Philosophy](#philosophy)
- [Core Concepts](#core-concepts)
- [Common Patterns](#common-patterns)
- [Controller Patterns](#controller-patterns)
- [Form Handling](#form-handling)
- [Toast Notifications](#toast-notifications)
- [Loading States](#loading-states)
- [Error Handling](#error-handling)

---

## Philosophy

### HATEOAS (Hypermedia as the Engine of Application State)

- Server returns HTML, not JSON
- Links and forms drive application state
- Progressive enhancement (works without JS)
- No client-side routing or state management

### When to Use HTMX

✅ **Good for:**
- Form submissions
- Inline editing
- Loading more content
- Search/filter
- Settings updates
- Notifications

❌ **Not ideal for:**
- Real-time collaboration
- Complex drag-and-drop
- Offline-first apps

---

## Core Concepts

### Key Attributes

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `hx-get` | GET request | `hx-get="/users"` |
| `hx-post` | POST request | `hx-post="/settings"` |
| `hx-put` | PUT request | `hx-put="/users/1"` |
| `hx-delete` | DELETE request | `hx-delete="/users/1"` |
| `hx-trigger` | Event to trigger | `hx-trigger="click"` |
| `hx-target` | Where to put response | `hx-target="#result"` |
| `hx-swap` | How to swap content | `hx-swap="innerHTML"` |
| `hx-vals` | Extra values to send | `hx-vals='{"key": "value"}'` |

### Swap Methods

| Method | Description |
|--------|-------------|
| `innerHTML` | Replace inner HTML (default) |
| `outerHTML` | Replace entire element |
| `beforeend` | Append to end |
| `afterbegin` | Prepend to start |
| `delete` | Delete target element |
| `none` | Don't swap (for side effects) |

---

## Common Patterns

### Inline Edit

```html
<!-- Display mode -->
<div id="name-display">
  <span>{{ user.name }}</span>
  <button hx-get="/profile/edit-name"
          hx-target="#name-display"
          hx-swap="outerHTML"
          class="btn btn-sm btn-link">Edit</button>
</div>
```

```html
<!-- Edit mode (returned by server) -->
<form id="name-display"
      hx-post="/profile/name"
      hx-target="#name-display"
      hx-swap="outerHTML">
  <input type="text" name="name" value="{{ user.name }}" class="form-control">
  <button type="submit" class="btn btn-primary btn-sm">Save</button>
  <button type="button"
          hx-get="/profile/name-display"
          hx-target="#name-display"
          hx-swap="outerHTML"
          class="btn btn-secondary btn-sm">Cancel</button>
</form>
```

### Search with Debounce

```html
<input type="search"
       name="q"
       placeholder="Search..."
       hx-get="/search"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-results"
       class="form-control">

<div id="search-results">
  <!-- Results appear here -->
</div>
```

### Infinite Scroll

```html
<div id="items">
  {% for item in items %}
  <div class="item">{{ item.name }}</div>
  {% endfor %}

  {% if has_more %}
  <div hx-get="/items?page={{ next_page }}"
       hx-trigger="revealed"
       hx-swap="outerHTML"
       hx-target="this">
    <span class="spinner-border spinner-border-sm"></span> Loading...
  </div>
  {% endif %}
</div>
```

### Auto-Save Settings

```html
<select name="value"
        hx-post="/settings"
        hx-trigger="change"
        hx-vals='{"key": "theme"}'
        hx-target="#theme-status"
        class="form-select">
  <option value="light">Light</option>
  <option value="dark">Dark</option>
</select>
<div id="theme-status" class="form-text text-success"></div>
```

### Delete with Confirmation

```html
<button hx-delete="/items/{{ item.id }}"
        hx-confirm="Are you sure you want to delete this?"
        hx-target="closest .item"
        hx-swap="outerHTML"
        class="btn btn-danger btn-sm">
  Delete
</button>
```

---

## Controller Patterns

### Detecting HTMX Requests

```python
def is_htmx_request():
    """Check if request is from HTMX."""
    return request.headers.get('HX-Request') == 'true'


@bp.route('/profile')
@login_required
def profile():
    if is_htmx_request():
        # Return partial for HTMX
        return render_template('yourmodule/desktop/_profile_card.html', user=current_user)
    else:
        # Return full page for normal request
        return render_template('yourmodule/desktop/profile.html', user=current_user)
```

### Returning Partials

```python
@bp.route('/settings', methods=['POST'])
@login_required
def update_setting():
    key = request.form.get('key')
    value = request.form.get('value')

    Setting.set(current_user.id, key, value)

    # HTMX: return simple confirmation
    if is_htmx_request():
        return 'Saved'

    # Normal: redirect
    return redirect(url_for('settings.index'))
```

### HTMX Response Headers

```python
from flask import make_response

@bp.route('/items', methods=['POST'])
def create_item():
    item = Item.create(name=request.form['name'])

    response = make_response(render_template('yourmodule/desktop/_item.html', item=item))

    # Trigger client-side event
    response.headers['HX-Trigger'] = 'itemCreated'

    # Trigger with data
    response.headers['HX-Trigger'] = json.dumps({
        'showToast': {'message': 'Item created!', 'type': 'success'}
    })

    return response
```

---

## Form Handling

### Standard Form with HTMX

```html
<form hx-post="{{ url_for('users.edit_profile') }}"
      hx-target="#form-container"
      hx-swap="outerHTML">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">

  <div class="mb-3">
    <label for="name" class="form-label">Name</label>
    <input type="text" name="name" id="name"
           value="{{ user.name }}"
           class="form-control">
  </div>

  <button type="submit" class="btn btn-primary">Save</button>
</form>
```

### Form Validation Feedback

```python
@bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    name = request.form.get('name', '').strip()
    errors = {}

    if not name:
        errors['name'] = 'Name is required'
    elif len(name) > 100:
        errors['name'] = 'Name too long'

    if errors:
        return render_template('yourmodule/desktop/_edit_form.html',
                               user=current_user,
                               errors=errors), 422

    current_user.update(name=name)
    return render_template('yourmodule/desktop/_profile_card.html', user=current_user)
```

### Field-Level Validation

```html
<input type="email"
       name="email"
       hx-post="/validate/email"
       hx-trigger="blur"
       hx-target="#email-error"
       class="form-control">
<div id="email-error" class="invalid-feedback"></div>
```

```python
@bp.route('/validate/email', methods=['POST'])
def validate_email():
    email = request.form.get('email', '')
    if not email:
        return '<span class="text-danger">Email required</span>'
    if '@' not in email:
        return '<span class="text-danger">Invalid email</span>'
    return ''
```

---

## Toast Notifications

### Setup

```html
<!-- In base.html -->
<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3">
</div>

<script>
document.body.addEventListener('showToast', function(e) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = 'toast show';
  toast.innerHTML = `
    <div class="toast-header">
      <strong class="me-auto">${e.detail.title || 'Notification'}</strong>
      <button type="button" class="btn-close" data-bs-dismiss="toast"></button>
    </div>
    <div class="toast-body">${e.detail.message}</div>
  `;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
});
</script>
```

### Triggering from Server

```python
@bp.route('/items', methods=['DELETE'])
def delete_item():
    item.delete()

    response = make_response('', 200)
    response.headers['HX-Trigger'] = json.dumps({
        'showToast': {
            'title': 'Success',
            'message': 'Item deleted'
        }
    })
    return response
```

---

## Loading States

### Spinner During Request

```html
<button hx-post="/action"
        hx-target="#result"
        class="btn btn-primary">
  <span class="htmx-indicator spinner-border spinner-border-sm me-1"></span>
  Save
</button>

<style>
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline-block; }
</style>
```

### Disable During Request

```html
<form hx-post="/save" hx-disabled-elt="button">
  <input type="text" name="data">
  <button type="submit">Save</button>
</form>
```

### Skeleton Loading

```html
<div id="content"
     hx-get="/content"
     hx-trigger="load"
     hx-swap="innerHTML">
  <!-- Skeleton placeholder -->
  <div class="placeholder-glow">
    <span class="placeholder col-12"></span>
    <span class="placeholder col-8"></span>
  </div>
</div>
```

---

## Error Handling

### Server-Side Errors

```python
@bp.route('/action', methods=['POST'])
def action():
    try:
        # ... do something
        return 'Success'
    except ValidationError as e:
        return f'<span class="text-danger">{e.message}</span>', 400
    except Exception:
        return '<span class="text-danger">Something went wrong</span>', 500
```

### Client-Side Error Handling

```html
<div hx-post="/action"
     hx-target="#result"
     hx-on::response-error="alert('Request failed')">
  ...
</div>
```

### Global Error Handler

```javascript
document.body.addEventListener('htmx:responseError', function(e) {
  console.error('HTMX error:', e.detail.xhr.status);
  // Show error toast
});
```

---

**Next:** [Frontend](frontend.md) | [Security](security.md)
