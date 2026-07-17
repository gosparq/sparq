# Deployment Guide

> Production deployment with Gunicorn, Docker, and cloud platforms

---

## Table of Contents

- [Application Startup](#application-startup)
- [Environment Variables](#environment-variables)
- [WSGI Server (Gunicorn)](#wsgi-server-gunicorn)
- [Docker Deployment](#docker-deployment)
- [Reverse Proxy](#reverse-proxy)
- [Cloud Platforms](#cloud-platforms)
- [Production Checklist](#production-checklist)
- [Graceful Shutdown](#graceful-shutdown)

---

## Application Startup

### Development Entry Point

```python
# run.py
"""Development server entry point."""

from dotenv import load_dotenv
load_dotenv('config/local.env')

from app import create_app

app = create_app()

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))

    print(f'\n  App running at:')
    print(f'  - Local:   http://localhost:{port}')
    print(f'  - Network: http://0.0.0.0:{port}\n')

    app.run(host='0.0.0.0', port=port, debug=True)
```

### Production Entry Point

```python
# wsgi.py
"""Production WSGI entry point."""

from app import create_app

app = create_app()
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Session encryption key | `secrets.token_hex(32)` |
| `DATABASE_URL` | Database connection string | `postgresql://user:pass@host/db` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_ENV` | Environment name | `dev` |
| `PORT` | Server port | `8000` |
| `DEBUG` | Debug mode | `false` |

### Example .env File

```bash
# config/local.env.example
APP_ENV=dev
PORT=8000
SECRET_KEY=dev-secret-key-change-in-production
DATABASE_URL=sqlite:///app.db
DEV_MAGIC=true
```

### Generating Secret Key

```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## WSGI Server (Gunicorn)

### Basic Usage

```bash
# Install
pip install gunicorn

# Run
gunicorn wsgi:app -w 4 -b 0.0.0.0:8000
```

### Production Configuration

```bash
# gunicorn.conf.py
import multiprocessing

# Binding
bind = "0.0.0.0:8000"

# Workers
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 30

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Security
limit_request_line = 4094
limit_request_fields = 100
```

```bash
# Run with config
gunicorn wsgi:app -c gunicorn.conf.py
```

### Makefile Target

```makefile
prod:
	gunicorn wsgi:app -w 4 -b 0.0.0.0:8000 --access-logfile - --error-logfile -
```

---

## Docker Deployment

### Dockerfile

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application
COPY . .

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["gunicorn", "wsgi:app", "-w", "4", "-b", "0.0.0.0:8000"]
```

### .dockerignore

```
# .dockerignore
.git
.gitignore
__pycache__
*.pyc
*.pyo
.pytest_cache
.coverage
htmlcov/
venv/
.env
config/local.env
*.db
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - APP_ENV=production
      - DATABASE_URL=postgresql://app:app@db:5432/app
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=app
      - POSTGRES_PASSWORD=app
      - POSTGRES_DB=app

volumes:
  postgres_data:
```

### Build and Run

```bash
# Build
docker build -t yourapp .

# Run
docker run -p 8000:8000 --env-file .env yourapp

# Docker Compose
docker-compose up -d
```

---

## Reverse Proxy

### Caddy (Recommended)

```
# Caddyfile
yourapp.com {
    reverse_proxy localhost:8000
}
```

Caddy provides:
- Automatic HTTPS (Let's Encrypt)
- HTTP/2
- Auto compression

### Nginx

```nginx
# /etc/nginx/sites-available/yourapp
server {
    listen 80;
    server_name yourapp.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourapp.com;

    ssl_certificate /etc/letsencrypt/live/yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourapp.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /app/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## Cloud Platforms

### Heroku

```bash
# Procfile
web: gunicorn wsgi:app -w 4
```

```bash
# Deploy
heroku create yourapp
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
heroku addons:create heroku-postgresql:mini
git push heroku main
heroku run flask db upgrade
```

### Google Cloud Run

```bash
# Deploy
gcloud run deploy yourapp \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars="APP_ENV=production"
```

### DigitalOcean App Platform

```yaml
# .do/app.yaml
name: yourapp
services:
  - name: web
    source:
      repo: https://github.com/yourorg/yourapp
      branch: main
    build_command: pip install -r requirements.txt
    run_command: gunicorn wsgi:app -w 4
    envs:
      - key: SECRET_KEY
        scope: RUN_TIME
        type: SECRET
```

### AWS Elastic Beanstalk

```yaml
# .ebextensions/01_flask.config
option_settings:
  aws:elasticbeanstalk:container:python:
    WSGIPath: wsgi:app
```

---

## Production Checklist

### Security

- [ ] `SECRET_KEY` is set and random
- [ ] `DEBUG=false`
- [ ] HTTPS enforced (redirect HTTP)
- [ ] Security headers configured
- [ ] CSRF protection enabled
- [ ] Rate limiting on auth endpoints
- [ ] Input validation on all forms

### Database

- [ ] SQLite: Database file in persistent volume (or PostgreSQL for high traffic)
- [ ] Migrations applied (`flask db upgrade`)
- [ ] Backups configured
- [ ] PostgreSQL: Connection pooling configured (if using Postgres)
- [ ] Indexes on frequently queried columns

### Application

- [ ] Gunicorn with multiple workers
- [ ] Health check endpoint (`/health`)
- [ ] Structured logging (JSON format)
- [ ] Error tracking (Sentry, etc.)
- [ ] Request ID tracking

### Infrastructure

- [ ] Reverse proxy (Caddy/Nginx)
- [ ] SSL/TLS certificate
- [ ] Static assets self-hosted (vendored under `/assets/vendor`) with long-lived cache + `?v=` busting — see [Static Asset Caching](#static-asset-caching)
- [ ] Log aggregation
- [ ] Monitoring and alerting
- [ ] Auto-scaling (if needed)

---

## Static Asset Caching

All static assets (module CSS/JS/images and the vendored frontend libraries
under `/assets/vendor`) are served by Flask with a long-lived browser cache in
production and cache-busted URLs, so repeat navigations serve from disk with no
network round-trips.

### How it works

- **`SEND_FILE_MAX_AGE_DEFAULT`** (`system/startup/config.py`) is set to
  `timedelta(days=365)` in production and `timedelta(0)` in debug. This flips
  the static `Cache-Control` header from `no-cache` (revalidate every request)
  to `public, max-age=31536000`. In debug it stays uncached so local edits show
  immediately.
- **Cache-busting** (`register_static_cache_busting` in
  `system/startup/templates.py`) registers an `@app.url_defaults` hook that
  appends `?v=<version>-<git hash>` (e.g. `?v=1.0.4-261ab44`) to every
  `static` / `<bp>.static` URL. The git hash — not the bare version — is the
  key: `get_version()` only changes on a manual VERSION bump in
  production/public-repo builds, so keying on it alone would fail to bust when
  assets change without a version bump. The git hash changes every
  commit/build, so any release refetches. (The build timestamp is avoided — its
  `get_build_info` fallback is `datetime.now()`, which would differ per worker
  and thrash the cache.)

### Why not just a long cache?

A long `max-age` without cache-busting would leave users on stale CSS/JS for up
to a year after a deploy. Pairing it with the `?v=` param is what makes the long
cache safe. Do not raise `max-age` without keeping the version param intact.

---

## Graceful Shutdown

### Signal Handling

Gunicorn handles SIGTERM gracefully by default:
1. Stop accepting new connections
2. Wait for workers to finish current requests
3. Shut down

### Health Check

```python
# app/controllers/main.py

@bp.route('/health')
def health():
    """Health check endpoint for load balancers."""
    return {'status': 'ok'}
```

### Database Cleanup

Flask-SQLAlchemy handles connection cleanup automatically when the app context ends.

For explicit cleanup:

```python
# In app factory
@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()
```

---

## Systemd Service

For Linux servers without Docker:

```ini
# /etc/systemd/system/yourapp.service
[Unit]
Description=Your Flask App
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/yourapp
Environment="PATH=/var/www/yourapp/venv/bin"
EnvironmentFile=/var/www/yourapp/.env
ExecStart=/var/www/yourapp/venv/bin/gunicorn wsgi:app -w 4 -b 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start
sudo systemctl enable yourapp
sudo systemctl start yourapp
sudo systemctl status yourapp
```

---

**Next:** [Security](security.md) | [Testing](testing.md)
