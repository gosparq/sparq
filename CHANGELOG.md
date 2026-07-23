# Changelog

All notable changes to sparQ are documented in this file.
Format follows [Common Changelog](https://common-changelog.org).

## [1.2.0] - 2026-07-23

### Changed

- **Update service** — the daily update check now reports a small, non-identifying payload (sparQ version and edition, operating system, architecture, runtime version, locale, and installed module versions) so the update service can return compatible release and security information. It still sends no usernames, emails, customer or repository data, source code, or persistent installation identifier, and remains disableable with `SPARQ_UPDATE_CHECK=false`

### Added

- **First-boot update notice** — the setup wizard now discloses what the daily update check collects and how to disable it
- **Settings → Updates** — a page showing the current version, the latest available release, the exact information sent, and a manual "Check for updates" action
- **Add existing org members to a workspace** — admins can bulk-add people already in the organization to the current workspace from the People directory, and each added member gets an in-app notification

### Fixed

- **Onboarding magic link** — the Start Onboarding email link now reaches the wizard for anonymous new hires, and later steps save to the correct records so onboarding completes
- **Dark mode surfaces** — several dashboard, updates, kanban, and inbox surfaces that rendered with light backgrounds or unreadable text now adapt correctly to dark mode

## [1.1.0] - 2026-07-21

### Changed

- **Self-hosted frontend libraries** — vendored frontend assets instead of loading from a CDN, and cache them with per-file content hashes for faster, dependency-free page loads

### Added

- **Update check** — sparQ periodically checks for a newer release and logs when one is available. The check is anonymous (it transmits nothing about your instance) and can be disabled with `SPARQ_UPDATE_CHECK=false`
- **Expandable activity descriptions** — the task detail view now shows the full activity description instead of truncating it
- **Email gateway fallback transport** — an optional HTTP relay used for outbound email when no SMTP provider is configured
- **Production self-hosting guide** — documentation for deploying sparQ in production

### Fixed

- **iOS audio playback** — voice notes are transcoded to AAC/MP4 on upload so they play on all iPhones, not only newer iOS versions
- **Invite acceptance** — skip the password step when email is configured
- **Server admin (MSA) enablement** — evaluate MSA availability at request time so it reflects current configuration

## [1.0.0] - 2026-06-15

### Added

- **Self-hosted platform** — sparQ as a fully open-source, self-hosted developer experience platform
- **Pulse** — Standups, async updates, time tracking, people ops, projects, documents, chat, and more
- **SQLite by default** — Zero-config database, runs out of the box with no external dependencies
- **PostgreSQL support** — Optional PostgreSQL backend via `DATABASE_URL` environment variable
- **Docker support** — Single-command deployment with `docker compose up`
- **Real-time chat** — Channels, direct messages, @mentions, typing indicators, emoji reactions, webhooks
- **Time & attendance** — Clock in/out, PTO requests, schedules, punch corrections, kiosk mode
- **People management** — Directory, onboarding, 1-on-1s, hiring pipeline, offboarding
- **Projects & tasks** — Initiative tracking, action items, weekly plans, canned tasks
- **Documents** — Notes, e-signatures, knowledge base, working agreements
- **Finance** — Expense tracking and basic accounting
- **AI assistant** — Optional LLM-powered features (OpenAI or Anthropic)
- **Mobile API** — REST API with JWT authentication
- **Multi-language** — Built-in i18n with installable language packs
- **Progressive Web App** — Installable on mobile and desktop with push notifications
- **GitHub integration** — Sync commits, PRs, and activity
- **OAuth providers** — External authentication support
