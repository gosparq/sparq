<h1 align="center">sparQ</h1>

<p align="center">
  <strong>The first fully open-source Developer Experience suite for GitHub-native teams</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="v1.0.0">
  <img src="https://img.shields.io/badge/Python-3.13+-green.svg" alt="Python 3.13+">
  <img src="https://img.shields.io/badge/Flask-3.x-lightgrey.svg" alt="Flask 3.x">
  <img src="https://img.shields.io/badge/license-AGPL--3.0-orange.svg" alt="AGPL-3.0">
</p>

<p align="center">
  <a href="CHANGELOG.md">Changelog</a> &middot;
  <a href="CONTRIBUTING.md">Contributing</a> &middot;
  <a href="SECURITY.md">Security</a>
</p>

---

<p align="center">
  <img src=".github/assets/screenshot.png" alt="sparQ Dashboard" width="800">
  <br>
  <sub>Dashboard: team pulse, blockers, and activity at a glance</sub>
</p>

## What is sparQ

sparQ is the first fully open-source Developer Experience suite for GitHub-native teams. It's a set of focused products that share one self-hosted home. Start with Pulse today, with Metrics and Knowledge on the way.

| Product | Description | Status |
|---------|-------------|--------|
| **Pulse** | GitHub-native project management, async standups, team presence, and delivery visibility | Available |
| **Metrics** | DORA metrics and engineering analytics | Coming soon |
| **Knowledge** | LLM-powered knowledge base from your codebase | Coming soon |

## Pulse

GitHub-native project management, async standups, team presence, and delivery visibility for teams living in GitHub. Self-hosting is always free. Forever.

**Runs on SQLite out of the box. Zero external dependencies.**

### Features

- **GitHub Sync** — Projects, tasks, and status derived from PRs, issues, and commits
- **Async Standups** — Template-driven daily check-ins with audio recording and transcription
- **Blockers Board** — Track blockers with owners, urgency tiers, and automatic nudges
- **Presence** — See who's available, focused, blocked, or out across the team
- **Action Items** — Three-tier urgency system (Now / Later / Whenever), weekly plans
- **Chat & DMs** — Real-time messaging with channels, direct messages, and reactions
- **Documents** — Notes, e-signatures with audit trail, knowledge base
- **People** — Directory, onboarding, 1-on-1s, hiring pipeline
- **Time & Attendance** — Clock in/out, PTO requests, schedules, punch corrections
- **AI Assistant** — Optional LLM-powered features (OpenAI or Anthropic)
- **Mobile API** — Full REST API with JWT auth
- **Multi-language** — Built-in i18n with installable language packs

## Quick Start

### Option 1: Docker (recommended)

```bash
git clone https://github.com/sparqsoft/sparq.git
cd sparq
docker compose up
```

Open [http://localhost:8000](http://localhost:8000) to get started.

### Option 2: Local development

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/sparqsoft/sparq.git
cd sparq/pulse
make venv
source venv/bin/activate
make run
```

Open [http://localhost:8000](http://localhost:8000).

### Option 3: PostgreSQL

By default sparQ uses SQLite (zero-config). To use PostgreSQL, set `DATABASE_URL` in your `.env`:

```
DATABASE_URL=postgresql://sparq:sparq@localhost:5432/sparq
```

Then start a Postgres container and run:

```bash
cd pulse
make db-start
make run
```

## Configuration

Copy `.env.example` to `.env` in the `pulse/` directory. The app auto-generates one on first run if missing.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask session secret |
| `DATABASE_URL` | SQLite (`data/sparq.db`) | Database connection string |
| `FLASK_DEBUG` | `false` | Enable debug mode |
| `LLM_PROVIDER` | `openai` | AI provider (`openai` or `anthropic`) |
| `OPENAI_API_KEY` | -- | Required for AI features |
| `MSA_USER` | -- | Admin panel username (disabled if unset) |
| `MSA_PASS` | -- | Admin panel password (disabled if unset) |
| `SPARQ_UPDATE_CHECK` | `true` | Automatic update check (set `false` to disable) |

See [`pulse/.env.example`](pulse/.env.example) for the full list.

### Server Admin Panel (MSA)

sparQ includes a built-in admin console at `/msa` for managing organizations, workspaces, and users. It is **disabled by default**. Set both `MSA_USER` and `MSA_PASS` in your `.env` to enable it.

### Automatic Update Checks

**sparQ does not collect or store any information that identifies you or your installation.** The update check is anonymous: it contains no persistent identifier, and the data it sends cannot be connected back to you.

sparQ periodically (about once a day) contacts the sparQ update service to determine whether a newer or security-related version is available.

The update request may include:

- The installed sparQ version and edition
- Operating system and processor architecture
- Runtime version
- Locale
- Installed sparQ modules and their versions

The request does **not** include usernames, email addresses, customer or repository names, repository contents, source code, commits, pull requests, developer activity, or a persistent installation identifier. As with any internet request, the originating IP address is temporarily visible to the receiving infrastructure; sparQ does not use full IP addresses to identify installations or create profiles. The check never blocks startup and fails silently if offline.

Administrators running sparQ in an air-gapped or restricted environment may disable automatic update checks with `SPARQ_UPDATE_CHECK=false`. Disabling update checks may prevent the installation from receiving security and compatibility notices. See [gosparq.com/legal/telemetry](https://www.gosparq.com/legal/telemetry) for the full disclosure.

### Email Setup

sparQ sends transactional emails for signups, password resets, and magic link logins. Configure email from the admin panel or via environment variables.

**Option 1: Admin Panel (recommended)**

1. Enable the MSA admin panel (set `MSA_USER` and `MSA_PASS`)
2. Navigate to `/msa/email`
3. Select a provider (Gmail, Microsoft 365, SendGrid, Mailgun, AWS SES, or custom SMTP)
4. Enter your credentials and click **Save Configuration**
5. Use **Test Connection** and **Send Test Email** to verify

**Option 2: Environment Variables**

Set these in your `.env` to configure email without the admin panel:

| Variable | Description |
|----------|-------------|
| `SMTP_HOST` | SMTP server hostname (e.g., `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |
| `SMTP_USERNAME` | SMTP username or email address |
| `SMTP_PASSWORD` | SMTP password or app-specific password |
| `SMTP_FROM_EMAIL` | Sender email address |
| `SMTP_PROVIDER` | Provider name (e.g., `gmail`, `sendgrid`, `custom`) |

Environment variables take priority over admin panel settings. Fields locked by env vars are shown with a lock icon in the admin panel.

> **Gmail users:** Enable 2-Step Verification, then generate an [App Password](https://myaccount.google.com/apppasswords). Use the 16-character app password, not your regular password.

If no email provider is configured, signup falls back to direct password-based registration (no email confirmation).

### GitHub Integration

sparQ syncs tasks and blockers with GitHub Issues. Connect using a classic Personal Access Token (PAT):

1. Go to [GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens/new)
2. Create a new token with these scopes: `repo` and `admin:repo_hook`
3. In sparQ, go to **Settings → Integrations** and paste your token and repository (`owner/repo`)
4. Open **Settings → Integrations → GitHub → Match GitHub people** and map each GitHub account to a sparQ member, so commit and PR activity is attributed to the right person (unmapped accounts are skipped). Members can also self-map in their own settings.

That's it. Issues, labels, and assignees sync between sparQ and your repository, and commits and pull requests show up in the **Status** feed as each person's current activity.

> **Self-hosting behind a reverse proxy?** Set `GITHUB_WEBHOOK_BASE_URL` to your public URL (e.g. `https://app.example.com`) so the auto-registered webhook resolves correctly, and set `GITHUB_WEBHOOK_SECRET` to verify inbound webhooks (required in production).

## Project Structure

```
sparq/
├── pulse/                  # Main application (sparQ Pulse)
│   ├── app.py              # Application factory
│   ├── modules/            # Feature modules (core, updates, presence, etc.)
│   ├── system/             # Framework (db, auth, email, middleware, etc.)
│   ├── tests/              # Unit, integration, and e2e tests
│   ├── Makefile            # Dev commands (make run, make venv, etc.)
│   └── requirements.in     # Python dependencies
├── metrics/                # (coming soon)
├── knowledge/              # (coming soon)
└── docker-compose.yml
```

## Tech Stack

- **Backend**: Python, Flask, SQLAlchemy, Flask-SocketIO
- **Database**: SQLite (default) or PostgreSQL
- **Frontend**: Server-rendered Jinja2 templates, HTMX
- **Real-time**: WebSocket via Flask-SocketIO
- **Production**: Gunicorn

## Development

```bash
cd pulse

# Run tests
python -m pytest tests/

# Reset database
make reset

# Verbose startup (shows module loading)
make run V=1
```

## Contributing

We welcome contributions! Please read our [Contributing Guide](CONTRIBUTING.md) to get started.

If you find a security vulnerability, please follow our [Security Policy](SECURITY.md) instead of filing a public issue.

## License

This project is licensed under the [GNU Affero General Public License v3.0](LICENSE).

Copyright (c) 2025-2026 sparQ Software LLC.
