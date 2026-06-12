# Security

> Security measures built into sparQ — what we protect against, and how.

---

## Table of Contents

- [Security Checklist](#security-checklist)
- [Authentication Security](#authentication-security)
- [CSRF Protection](#csrf-protection)
- [Rate Limiting](#rate-limiting)
- [Input Safety](#input-safety)
- [Security Headers](#security-headers)
- [Secrets Management](#secrets-management)

---

## Security Checklist

- [x] CSRF protection on all state-changing requests
- [x] Rate limiting on authentication endpoints
- [x] Account lockout after failed attempts
- [x] Password policy with breach detection
- [x] Input validation (length, format, type)
- [x] Parameterized queries (SQLAlchemy)
- [x] Auto-escaping templates (Jinja2)
- [x] Secure session cookies (HttpOnly, Secure, SameSite)
- [x] Security headers on all responses
- [x] File upload validation
- [x] Content Security Policy (CSP)
- [x] HTTPS enforced in production

---

## Authentication Security

> Protects against credential brute-forcing, weak passwords, session forgery, and account takeover.

### Account Lockout

Accounts lock after **5 failed login attempts** for **15 minutes**. Counters reset on successful login. Error messages are generic — never reveal whether the account exists, is locked, or how many attempts remain.

> See `modules/base/core/models/user.py` for lockout fields and logic.

### Password Policy

| Rule | Value |
|------|-------|
| Minimum length | 8 characters |
| Maximum length | 128 characters |
| Complexity | At least one uppercase, one lowercase, one number |
| Breach check | HaveIBeenPwned API via k-anonymity (only first 5 chars of SHA1 sent) |

The breach check fails open — if the API is unreachable, registration proceeds.

```python
from system.auth.password_policy import validate_password, is_breached

errors = validate_password(new_password)
if is_breached(new_password):
    flash("This password has appeared in a data breach.", "error")
```

> See `system/auth/password_policy.py` for implementation.

### Session Security

- **SECRET_KEY fail-fast**: App refuses to start in production without a `SECRET_KEY`. Dev mode uses an insecure default with a console warning.
- **Cookie flags**: `Secure` (production), `HttpOnly`, `SameSite=Lax`
- **Session regeneration**: Session is cleared and regenerated on login to prevent fixation attacks.

> See `system/startup/config.py` for SECRET_KEY and cookie configuration.

---

## CSRF Protection

> Prevents cross-site request forgery — stops other websites from submitting forms on behalf of logged-in users.

A random token is generated per session and validated on all state-changing requests (`POST`, `PUT`, `DELETE`). Comparison uses `secrets.compare_digest` (timing-safe). Certain paths that use alternative authentication (e.g., token auth, OAuth callbacks) are exempt.

### Template Usage

```html
<!-- All forms include the hidden token -->
<form method="POST">
  <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
</form>

<!-- HTMX: set once on <body> to cover all requests -->
<body hx-headers='{"X-CSRF-Token": "{{ csrf_token }}"}'>
```

> See `system/middleware/csrf.py` for implementation.

---

## Rate Limiting

> Prevents credential brute-forcing, email enumeration, and SMS credit exhaustion.

In-memory, per-IP rate limiting applied via decorator. Appropriate for sparQ's single-worker Gunicorn architecture (1 worker + 4 threads). Multi-worker setups would need Redis-backed storage.

```python
@rate_limit(limit=10, window=60)
def login(): ...
```

### Default Limits

| Endpoint | Limit |
|----------|-------|
| Login | 10 per minute |
| Registration | 5 per minute |
| Forgot password | 5 per 5 minutes |
| Magic link | 5 per 5 minutes |
| SMS request | 3 per 5 minutes |
| SMS verify | 5 per 5 minutes |

> See `system/middleware/ratelimit.py` for implementation.

---

## Input Safety

> Protects against SQL injection, XSS, and malicious file uploads.

### Validation Strategy

Two-tier validation throughout the application:

- **Model-level**: Sanitize (strip, lowercase) and validate (format, length) before saving. Raise `ValueError` on invalid data.
- **Controller-level**: Truncate inputs to max length and reject missing required fields before passing to models.

### SQL Injection Prevention

SQLAlchemy parameterizes queries automatically. No manual escaping needed.

```python
# Safe — parameterized automatically
user = User.query.filter_by(email=email).first()
result = db.session.execute(text("SELECT * FROM user WHERE email = :email"), {"email": email})

# Never do this — string interpolation
result = db.session.execute(f"SELECT * FROM user WHERE email = '{email}'")
```

### XSS Prevention

- **Jinja2 auto-escaping**: All template variables are escaped by default.
- **`|safe` audit rule**: Every use of `|safe` must have an accompanying HTML sanitizer applied before storage. Grep for `|safe` and verify each data source.
- **Content Security Policy**: Nonce-based CSP for inline scripts. All `<script>` tags must include `nonce="{{ csp_nonce }}"`.

### File Upload Safety

The connect module accepts file attachments in chat. Uploads are validated before storage:

- **Extension whitelist** — images (`jpg`, `png`, `gif`, `webp`), documents (`pdf`, `docx`, `xls`, `csv`, `txt`, `rtf`), and text/code files (`json`, `md`, `py`, `yaml`, etc.)
- **Size limit** — 10MB maximum per file
- **Filename validation** — rejects empty filenames and files without extensions

> See `modules/base/connect/controllers/chat.py` for upload handling.

---

## Security Headers

> Prevents clickjacking, MIME-sniffing, HTTPS downgrade, and referrer leakage.

Applied to all responses via `after_request` handler:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer leakage |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=()` | Restrict browser APIs |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | Force HTTPS (production only) |
| `Content-Security-Policy` | See CSP section above | Script/style/connect source restrictions |

> See `system/startup/request_hooks.py` for implementation.

---

## Secrets Management

> Never commit secrets to git.

### Rules

- **Development**: Use `.env` file (local only, never committed)
- **Production**: Set secrets via environment variables
- **SECRET_KEY**: Auto-generated on first run if not provided

### .gitignore Patterns

```
.env
*.env
config/local.env
!config/local.env.example
*.pem
*.key
credentials.json
```

---

**Next:** [Testing](testing.md) | [Deployment](deployment.md)
