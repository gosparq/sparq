# -----------------------------------------------------------------------------
# sparQ - Template Configuration
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# Template Configuration
#
# Registers Jinja2 filters, globals, and context processors.
# -----------------------------------------------------------------------------

from typing import Any

from flask import Flask, g
from flask_login import current_user
from markupsafe import Markup

from system.auth.current_member import current_member as _current_member


def nl2br(value: str | None) -> Markup:
    """Convert newlines to HTML <br> tags."""
    if not value:
        return Markup("")
    # Escape HTML first, then convert newlines to <br>
    from markupsafe import escape
    escaped = escape(value)
    return Markup(escaped.replace("\n", "<br>\n"))


def simple_markdown(value: str | None) -> Markup:
    """Convert markdown to HTML using the markdown library."""
    if not value:
        return Markup("")

    import re

    import markdown as md

    value = re.sub(r"<[^>]+>", lambda m: m.group().replace("<", "&lt;").replace(">", "&gt;"), value)

    _UL_RE = re.compile(r"[ \t]*[-*+][ \t]")
    _LIST_RE = re.compile(r"[ \t]*(?:[-*+]|\d+\.)[ \t]")
    lines = value.split("\n")
    out: list[str] = []
    for i, line in enumerate(lines):
        if i > 0 and _LIST_RE.match(line):
            prev = lines[i - 1]
            if prev.strip() and not _LIST_RE.match(prev):
                out.append("")
            elif prev.strip() and _LIST_RE.match(prev):
                if bool(_UL_RE.match(prev)) != bool(_UL_RE.match(line)):
                    out.extend(["", "<!-- -->", ""])
        out.append(line)
    value = "\n".join(out)

    html = md.markdown(value, extensions=["fenced_code", "tables", "nl2br"])

    html = re.sub(r'href="(?!https?://|mailto:|tel:|/|#)', 'href="https://', html)
    html = re.sub(r"<a ", '<a target="_blank" rel="noopener" ', html)

    return Markup(html)


def github_preview(content: str) -> str:
    """Extract a clean preview from a GITHUB_HTML:: chat message.

    Strips HTML tags, removes the repo footer line, and reformats
    "N commits pushed to branch by user" as "pushed by user to branch".
    """
    import re

    # Strip the prefix
    text = content[13:] if content.startswith("GITHUB_HTML::") else content
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Remove commit detail lines (sha - message)
    text = re.sub(r"[a-f0-9]{7} - .+", "", text)
    # Remove "... and N more"
    text = re.sub(r"\.\.\. and \d+ more", "", text)
    # Remove repo footer (org/repo at end)
    text = re.sub(r"\s*[\w-]+/[\w.-]+\s*$", "", text)
    # Clean up whitespace
    text = " ".join(text.split()).strip()
    # Reformat: "N commit(s) pushed to branch by user" → "pushed by user · branch"
    m = re.match(r"(\d+ new commits?) pushed to (\S+) by (.+)", text)
    if m:
        count, branch, user = m.groups()
        text = f"pushed by {user} · {branch} · {count}"
    return text


def strip_gh_tokens(text: str | None) -> str:
    """Remove [GH-N] inline tokens from display text.

    These tokens are inserted by the GitHub issue trigger JS when a user
    selects an issue. The chip renders separately; the token itself is noise.
    """
    if not text:
        return text or ""
    import re
    return re.sub(r"\s*\[GH-\d+\]\s*", " ", text).strip()


def render_mentions(text: str | None) -> Markup:
    """Convert @[member_id] tokens to styled spans and linkify URLs (XSS-safe).

    Looks up each mentioned WorkspaceUser by ID and renders:
        <span class="mention" data-member-id="{id}">@FirstName</span>

    Also wraps bare URLs in <a> tags. HTML-escapes the input before
    substitution so it is safe to mark as Markup.

    Args:
        text: Raw text that may contain @[member_id] tokens and/or URLs.

    Returns:
        Markup with mention tokens replaced by styled spans and URLs linked.
    """
    if not text:
        return Markup("")
    import re as _re
    import html as _html

    escaped = _html.escape(text)

    def _replace_mention(match) -> str:
        mid = int(match.group(1))
        try:
            cache = getattr(g, "_mention_name_cache", None)
            if cache is None:
                g._mention_name_cache = {}
                cache = g._mention_name_cache
            if mid not in cache:
                from modules.base.core.models.workspace_user import WorkspaceUser
                member = WorkspaceUser.scoped().filter_by(id=mid).first()
                cache[mid] = _html.escape(member.user.first_name) if member and member.user else None
            name = cache[mid]
            if name:
                return f'<span class="mention" data-member-id="{mid}">@{name}</span>'
        except Exception:
            pass
        return match.group(0)

    result = _re.sub(r"@\[(\d+)\]", _replace_mention, escaped)

    def _replace_url(match) -> str:
        url = match.group(0)
        href = url if url.startswith(("http://", "https://")) else f"https://{url}"
        return f'<a href="{href}" target="_blank" rel="noopener noreferrer">{url}</a>'

    result = _re.sub(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", _replace_url, result)

    return Markup(result)


def register_template_filters(app: Flask) -> None:
    """Register Jinja2 filters for the Flask application."""
    from system.i18n.translation import format_date, format_day_name, format_datetime, format_number, translate

    # Add translation function to globals
    app.jinja_env.globals["_"] = translate

    # Add formatting filters
    app.jinja_env.filters["format_date"] = format_date
    app.jinja_env.filters["format_day_name"] = format_day_name
    app.jinja_env.filters["format_datetime"] = format_datetime
    app.jinja_env.filters["format_number"] = format_number
    app.jinja_env.filters["nl2br"] = nl2br
    app.jinja_env.filters["markdown"] = simple_markdown
    app.jinja_env.filters["github_preview"] = github_preview
    app.jinja_env.filters["render_mentions"] = render_mentions
    app.jinja_env.filters["strip_gh_tokens"] = strip_gh_tokens

    # Add module availability check to templates
    from system.module.registry import module_enabled
    app.jinja_env.globals["module_enabled"] = module_enabled


def register_static_cache_busting(app: Flask) -> None:
    """Append ?v=<version> to every static URL for cache busting.

    Pairs with SEND_FILE_MAX_AGE_DEFAULT (see config.py): static assets are
    cached long-term by the browser, and this token changes whenever the build
    changes so the URL changes and browsers refetch. Covers the app's `static`
    endpoint and every blueprint's `<bp>.static` endpoint without touching
    templates. The token is resolved once at startup since it is fixed per
    build.

    The token is ``<version>-<git hash>`` (e.g. ``1.0.4-261ab44``). The git
    hash is included deliberately: ``get_version()`` alone only changes on a
    manual VERSION bump in production/public-repo builds, so keying on it would
    fail to bust the cache when assets change without a version bump. The git
    hash changes on every commit/build. The build timestamp is intentionally
    NOT used — its ``get_build_info`` fallback is ``datetime.now()``, which
    would differ per worker/restart and thrash the cache.

    Args:
        app: Flask application instance.
    """
    from system.version import get_build_info, get_version

    git_hash, _ = get_build_info()
    static_version = f"{get_version()}-{git_hash}"

    @app.url_defaults
    def add_static_version(endpoint: str, values: dict) -> None:
        """Inject the version param into static URLs when not already set."""
        if endpoint == "static" or endpoint.endswith(".static"):
            values.setdefault("v", static_version)


def register_context_processors(app: Flask) -> None:
    """Register Jinja2 context processors for the Flask application."""

    @app.context_processor
    def inject_csp_nonce() -> dict[str, str]:
        """Inject CSP nonce into all templates for script tag authorization."""
        from flask import g

        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.context_processor
    def inject_version() -> dict[str, str]:
        """Inject sparQ version into all templates."""
        from datetime import datetime
        from flask import g
        import pytz
        from system.version import get_version, get_full_version, get_display_version, get_build_info

        # Build date string — timestamp from git/BUILD is already in local time
        _, timestamp = get_build_info()
        build_date = timestamp  # fallback
        try:
            dt = datetime.strptime(timestamp, "%y%m%d-%H%M")
            hour_12 = dt.hour % 12 or 12
            am_pm = "AM" if dt.hour < 12 else "PM"
            tz_name = getattr(getattr(g, "company_settings", None), "timezone", None) or "America/Chicago"
            abbr = pytz.timezone(tz_name).localize(dt).strftime("%Z")
            build_date = dt.strftime(f"%b %-d, {hour_12}:%M{am_pm} ({abbr})")
        except (ValueError, pytz.exceptions.UnknownTimeZoneError):
            pass

        return {
            "sparq_version": get_version(),
            "sparq_full_version": get_full_version(),
            "sparq_display_version": get_display_version(),
            "sparq_build_date": build_date,
        }

    @app.context_processor
    def inject_today() -> dict:
        """Inject today's date for due-date comparisons in templates."""
        from datetime import date

        return {"today": date.today()}

    @app.context_processor
    def inject_sidebar_config() -> dict[str, Any]:
        """Inject sidebar config, nav sections, and admin status into all templates."""
        from modules.base.core.models.workspace_settings import WorkspaceSettings
        from system.nav import NAV_SECTIONS, DEFAULT_SECTION_ORDER, DEFAULT_PINNED_MODULES

        is_admin = current_user.is_authenticated and current_user.is_admin

        # WorkspaceSettings requires workspace context — gracefully degrade on
        # pages rendered before workspace is resolved (login, signup, etc.)
        workspace_id = getattr(g, "workspace_id", None)
        if workspace_id:
            settings = WorkspaceSettings.get_instance()
            sidebar_config = settings.get_sidebar_config()
        else:
            sidebar_config = {}

        return {
            "sidebar_config": sidebar_config,
            "nav_sections": NAV_SECTIONS,
            "default_section_order": DEFAULT_SECTION_ORDER,
            "default_pinned_modules": DEFAULT_PINNED_MODULES,
            "is_admin": is_admin,
        }

    @app.context_processor
    def inject_auth_settings() -> dict[str, Any]:
        """Inject auth settings for login page."""
        from modules.base.core.models.auth_settings import AuthSettings
        from system.oauth.providers import PROVIDERS

        # No workspace context (bare domain) — return defaults without DB access
        if getattr(g, "workspace_id", None) is None:
            return {"auth_settings": None, "oauth_providers": []}

        auth_settings = AuthSettings.get_instance()
        enabled_providers = []

        for provider_name in ["google", "microsoft", "github", "linkedin"]:
            if auth_settings.is_provider_enabled(provider_name):
                provider_config = PROVIDERS.get(provider_name)
                if provider_config:
                    enabled_providers.append(provider_config)

        return {
            "auth_settings": auth_settings,
            "oauth_providers": enabled_providers,
        }

    @app.context_processor
    def inject_notification_count() -> dict[str, int]:
        """Inject notification count for badge in header."""
        ctx = getattr(g, "_page_context", None)
        if ctx is not None:
            return {"notification_count": ctx.notification_count}
        if current_user.is_authenticated and getattr(g, "workspace_id", None) is not None and getattr(g, "organization_id", None) is not None:
            from modules.base.core.models.notification import SystemNotification

            count = SystemNotification.get_unread_count(current_user)
            if current_user.is_admin:
                count += SystemNotification.get_system_alerts_count()
            return {"notification_count": count}
        return {"notification_count": 0}

    @app.context_processor
    def inject_ai_helpers() -> dict:
        """Inject AI pending action helper for chat templates."""
        def get_pending_action(action_id: int):
            """Get an AI pending action by ID for rendering in templates."""
            try:
                from modules.base.ai.models import AIPendingAction

                return AIPendingAction.get_by_id(action_id)
            except Exception:
                return None

        return {"get_pending_action": get_pending_action}

    @app.context_processor
    def inject_calendar_settings() -> dict[str, list[str]]:
        """Inject weekday headers respecting company first-day-of-week setting."""
        from system.utils.calendar_utils import get_weekday_headers

        return {
            "weekday_headers_short": get_weekday_headers("short"),
            "weekday_headers_min": get_weekday_headers("min"),
        }

    @app.context_processor
    def inject_device_info() -> dict[str, Any]:
        """Inject device type info into all templates."""
        from flask import g

        return {
            "device_type": getattr(g, "device_type", "desktop"),
            "is_mobile": getattr(g, "is_mobile", False),
        }

    @app.context_processor
    def inject_current_member_id() -> dict[str, int | None]:
        """Inject current member (workspace_user) ID for templates."""
        member = _current_member()
        return {"current_member_id": member.id if member else None}

    @app.context_processor
    def inject_chat_unread_count() -> dict[str, int]:
        """Inject chat unread count for sidebar badge."""
        ctx = getattr(g, "_page_context", None)
        if ctx is not None:
            g._dm_total_unread_count = ctx.dm_unread_count
            return {"chat_unread_count": ctx.channel_unread_count + ctx.dm_unread_count}
        member = _current_member()
        if not member:
            return {"chat_unread_count": 0}
        try:
            from modules.base.updates.models.channel_read_state import UpdateChannelReadState
            from modules.base.updates.models.dm import DMThread

            channel_unread = UpdateChannelReadState.get_total_unread_count(member.id)
            dm_unread = DMThread.get_total_unread_count(member.id)
            g._dm_total_unread_count = dm_unread
            return {"chat_unread_count": channel_unread + dm_unread}
        except Exception:
            return {"chat_unread_count": 0}

    @app.context_processor
    def inject_tasks_count() -> dict[str, int]:
        """Inject action item counts for sidebar badges.
        - tasks_open_count: items assigned to me, excluding system nudges (rail badge)
        - open_blockers_count: all open blockers in the workspace (sidebar Blockers badge)
        - my_tasks_inbox_count: all items assigned to me including system nudges (Inbox badge)
        """
        ctx = getattr(g, "_page_context", None)
        if ctx is not None:
            return {
                "tasks_open_count": ctx.tasks_open_count,
                "open_blockers_count": ctx.open_blockers_count,
                "my_tasks_inbox_count": ctx.my_tasks_inbox_count,
            }
        member = _current_member()
        if member:
            try:
                from modules.base.tasks.models.task import Task

                return {
                    "tasks_open_count": Task.get_mine_open_count(member.id),
                    "open_blockers_count": Task.get_open_blockers_count(),
                    "my_tasks_inbox_count": len(Task.get_mine_open(member.id)),
                }
            except Exception:
                pass
        return {"tasks_open_count": 0, "open_blockers_count": 0, "my_tasks_inbox_count": 0}

    @app.context_processor
    def inject_projects_nav() -> dict[str, Any]:
        """Formerly injected project/plan nav data — all variables proved unused by templates."""
        return {}

    @app.context_processor
    def inject_connect_nav() -> dict[str, Any]:
        """Inject UpdateChannelReadState class reference for chat/channel templates (zero queries)."""
        from flask import request as req

        if not current_user.is_authenticated or not (
            req.path.startswith("/sync") or req.path.startswith("/updates")
        ):
            return {}
        from modules.base.updates.models.channel_read_state import UpdateChannelReadState

        return {"UpdateChannelReadState": UpdateChannelReadState}

    @app.context_processor
    def inject_presence_nav() -> dict[str, Any]:
        """Inject Presence data (time clock, board visibility) — only on /presence pages."""
        from flask import request as req

        if not current_user.is_authenticated or not (
            req.path.startswith("/presence") or req.path.startswith("/sync/calendar")
        ):
            return {}
        try:
            from modules.base.presence.models.settings import TimeTrackingSettings

            settings = TimeTrackingSettings.get()
            return {
                "time_clock_enabled": settings.time_clock_enabled,
                "board_visible": TimeTrackingSettings.is_board_visible_to_user(current_user),
            }
        except Exception:
            return {}

    @app.context_processor
    def inject_resources_nav() -> dict[str, Any]:
        """Inject resources sidebar data (pinned/recent notes, folders, recent docs)."""
        from flask import request as req

        if not current_user.is_authenticated or not req.path.startswith("/resources"):
            return {}
        try:
            member = _current_member()
            result: dict[str, Any] = {}

            # Notes sidebar data
            try:
                from modules.base.resources.models.note import Note

                if member:
                    all_notes = Note.get_for_member(member.id)
                    result["nav_pinned_notes"] = [n for n in all_notes if n.is_pinned][:5]
                    result["nav_recent_notes"] = [n for n in all_notes if not n.is_pinned][:5]
            except Exception:
                pass

            # Docs sidebar data
            try:
                from modules.base.resources.models.document import Document
                from modules.base.resources.models.folder import Folder

                result["nav_folders"] = Folder.scoped().order_by(Folder.name).limit(10).all()
                result["nav_recent_docs"] = Document.scoped().order_by(Document.updated_at.desc()).limit(5).all()
            except Exception:
                pass

            return result
        except Exception:
            return {}

    @app.context_processor
    def inject_header_presence() -> dict[str, Any]:
        """Inject focus status and clock status for the top bar badges."""
        ctx = getattr(g, "_page_context", None)
        if ctx is not None:
            result: dict[str, Any] = {}
            result["header_focus_status"] = ctx.focus_signal_value or "available"
            result["header_time_clock_enabled"] = ctx.time_clock_enabled
            if ctx.time_clock_enabled and ctx.clock_punch_type == "in" and ctx.clock_punch_time:
                from datetime import datetime
                elapsed = datetime.utcnow() - ctx.clock_punch_time
                total_seconds = int(elapsed.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                result["header_clock_status"] = {
                    "is_clocked_in": True,
                    "clock_in_time": ctx.clock_punch_time,
                    "elapsed": elapsed,
                    "elapsed_str": f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m",
                    "outside_geofence": ctx.clock_outside_geofence,
                }
            elif ctx.time_clock_enabled:
                result["header_clock_status"] = {
                    "is_clocked_in": False,
                    "clock_in_time": None,
                    "elapsed": None,
                    "elapsed_str": None,
                    "outside_geofence": False,
                }
            else:
                result["header_clock_status"] = None
            return result
        if not current_user.is_authenticated or getattr(g, "workspace_id", None) is None:
            return {}
        try:
            from modules.base.core.models.user_setting import UserSetting
            from system.module.registry import module_enabled

            result = {}

            if not module_enabled("Presence"):
                return result

            member = _current_member()
            if not member:
                return result

            focus_value = "available"
            legacy = UserSetting.get(current_user.id, "flow_status", default="free")
            focus_value = "focus" if legacy == "flow" else "available"
            result["header_focus_status"] = focus_value

            # Clock status
            from modules.base.presence.models.settings import TimeTrackingSettings

            time_clock_enabled = TimeTrackingSettings.is_time_clock_enabled()
            result["header_time_clock_enabled"] = time_clock_enabled

            if time_clock_enabled:
                from modules.base.presence.models.clock_punch import ClockPunch

                clock_status = ClockPunch.get_current_status(member.id)
                result["header_clock_status"] = clock_status
            else:
                result["header_clock_status"] = None

            return result
        except Exception:
            return {}

    @app.context_processor
    def inject_header_post_templates() -> dict[str, Any]:
        """Inject update/win/board post templates for the header + New menu."""
        if not current_user.is_authenticated or getattr(g, "workspace_id", None) is None:
            return {}
        try:
            from system.module.registry import module_enabled

            if not module_enabled("Updates"):
                return {}

            from modules.base.updates.models.template import UpdateTemplate

            all_templates = UpdateTemplate.get_for_workspace()
            update_templates = [t for t in all_templates if t.post_type == "update"]
            win_templates = [t for t in all_templates if t.post_type == "win"]
            board_templates = [t for t in all_templates if t.post_type == "board"]

            # Cross-populate per-type cache so downstream callers get hits
            try:
                cache = getattr(g, "_update_template_cache", None)
                if cache is not None:
                    ts_id = getattr(g, "workspace_id", None)
                    cache[(ts_id, "update")] = update_templates
                    cache[(ts_id, "win")] = win_templates
                    cache[(ts_id, "board")] = board_templates
            except Exception:
                pass

            return {"header_post_templates": update_templates + win_templates + board_templates}
        except Exception:
            return {}

    @app.context_processor
    def inject_header_dm_unread() -> dict[str, Any]:
        """Inject DM unread count for the header DM icon badge."""
        if not current_user.is_authenticated or getattr(g, "workspace_id", None) is None:
            return {}
        try:
            cached = getattr(g, "_dm_total_unread_count", None)
            if cached is not None:
                return {"header_dm_unread_count": cached}

            from system.module.registry import module_enabled

            if not module_enabled("Updates"):
                return {}

            from modules.base.updates.models.dm import DMThread

            member = _current_member()
            if not member:
                return {}

            return {"header_dm_unread_count": DMThread.get_total_unread_count(member.id)}
        except Exception:
            return {}

    @app.context_processor
    def inject_company_timezone() -> dict[str, str]:
        """Inject company timezone name for JS date formatting."""
        tz_name = getattr(getattr(g, "company_settings", None), "timezone", None) or "America/Chicago"
        return {"company_timezone": tz_name}

    @app.context_processor
    def inject_system_info() -> dict[str, Any]:
        """Inject system info dict for admin System Info modal."""
        if not current_user.is_authenticated:
            return {"system_info": None}

        import os
        import socket
        import time

        from flask import g, request
        from system.version import get_version

        render_time_ms = None
        start = getattr(g, "request_start_time", None)
        if start is not None:
            render_time_ms = round((time.monotonic() - start) * 1000, 1)

        db_time_raw = getattr(g, "db_query_time", 0.0)

        # Workspace slug from host
        host = request.host.split(":")[0]
        parts = host.split(".")
        workspace = parts[0] if len(parts) >= 2 and parts[0] not in ("www", "app", "localhost", "127") else host

        return {
            "system_info": {
                "workspace": workspace,
                "user": current_user.email,
                "request_id": getattr(g, "request_id", "—"),
                "render_time": f"{render_time_ms / 1000:.2f}s" if render_time_ms is not None else "—",
                "render_time_ms": render_time_ms or 0,
                "db_queries": getattr(g, "db_query_count", 0),
                "db_time": f"{db_time_raw:.2f}s",
                "server": socket.gethostname(),
                "worker_pid": os.getpid(),
                "version": get_version(),
                "browser": request.headers.get("User-Agent", "—"),
            }
        }

    @app.context_processor
    def inject_workspace_colors() -> dict[str, Any]:
        """Inject workspace color palette for color picker UI."""
        from modules.base.core.models.workspace import WORKSPACE_COLORS

        return {"workspace_colors": WORKSPACE_COLORS}

    @app.context_processor
    def inject_workspace_list() -> dict[str, Any]:
        """Inject the user's workspace memberships within the ACTIVE organization.

        Phase 3 — the top-left workspace switcher only shows workspaces under
        the current organization. Cross-org switching happens via the account
        dropdown (top-right). Also exposes `user_organizations` (list of all
        OrganizationUser memberships) and `is_organization_admin` for the
        top-right dropdown, plus `current_organization` metadata.
        """
        if not current_user.is_authenticated:
            return {
                "user_workspaces": [],
                "active_workspace_id": None,
                "user_organizations": [],
                "is_organization_admin": False,
                "current_organization": None,
            }

        try:
            from modules.base.core.models.organization import Organization
            from modules.base.core.models.organization_user import OrganizationUser
            from modules.base.core.models.workspace import Workspace
            from modules.base.core.models.workspace_user import WorkspaceUser

            organization_id = getattr(g, "organization_id", None)

            # Workspaces scoped to the current organization only.
            # Archived workspaces (deleted_at IS NOT NULL) are excluded — they
            # no longer appear in the switcher. Restore happens from Org
            # Settings → Workspaces.
            workspaces: list[dict[str, Any]] = []
            if organization_id is not None:
                memberships = (
                    WorkspaceUser.query
                    .filter_by(user_id=current_user.id)
                    .filter(WorkspaceUser.deleted_at.is_(None))
                    .join(Workspace, WorkspaceUser.workspace_id == Workspace.id)
                    .filter(Workspace.organization_id == organization_id)
                    .filter(Workspace.is_active.is_(True))
                    .filter(Workspace.deleted_at.is_(None))
                    .add_entity(Workspace)
                    .all()
                )
                workspaces = [
                    {
                        "id": str(ws.id),
                        "name": ws.name,
                        "slug": ws.slug,
                        "role": mu.role,
                        "color": ws.color_hex,
                    }
                    for mu, ws in memberships
                ]

            # All active organization memberships (for top-right switcher).
            org_rows = (
                OrganizationUser.query
                .filter_by(user_id=current_user.id, is_active=True)
                .join(Organization, OrganizationUser.organization_id == Organization.id)
                .filter(Organization.is_active.is_(True))
                .add_entity(Organization)
                .order_by(OrganizationUser.joined_at.asc())
                .all()
            )
            user_organizations = [
                {
                    "id": str(org.id),
                    "name": org.name,
                    "slug": org.slug,
                    "role": ou.role,
                    "is_active": ou.is_active,
                    "is_current": organization_id is not None and org.id == organization_id,
                }
                for ou, org in org_rows
            ]

            is_organization_admin = any(
                o["is_current"] and o["role"] == "admin" for o in user_organizations
            )

            current_organization = next(
                (o for o in user_organizations if o["is_current"]), None
            )

            return {
                "user_workspaces": workspaces,
                "active_workspace_id": str(g.workspace_id) if getattr(g, "workspace_id", None) else None,
                "user_organizations": user_organizations,
                "is_organization_admin": is_organization_admin,
                "current_organization": current_organization,
            }
        except Exception:
            return {
                "user_workspaces": [],
                "active_workspace_id": None,
                "user_organizations": [],
                "is_organization_admin": False,
                "current_organization": None,
            }

    @app.context_processor
    def inject_nav_badges() -> dict[str, dict]:
        """Inject badge counts for dashboard sidebar nav items."""
        ctx = getattr(g, "_page_context", None)
        if ctx is not None:
            badges: dict[str, int] = {}
            if ctx.pending_leave_count:
                badges["/presence/pto/"] = ctx.pending_leave_count
            if ctx.pending_correction_count:
                badges["/presence/timesheets/day"] = ctx.pending_correction_count
            return {"nav_badges": badges}
        if current_user.is_authenticated and current_user.is_admin:
            badges = {}
            try:
                from modules.base.presence.models.leave_request import LeaveRequest
                from modules.base.presence.models.punch_correction_request import PunchCorrectionRequest

                pto_count = LeaveRequest.pending_count()
                approval_count = PunchCorrectionRequest.pending_count()
                if pto_count:
                    badges["/presence/pto/"] = pto_count
                if approval_count:
                    badges["/presence/timesheets/day"] = approval_count
            except Exception:
                pass
            return {"nav_badges": badges}
        return {"nav_badges": {}}

    @app.context_processor
    def inject_sample_data_modal() -> dict[str, bool]:
        """Inject flag for one-time sample data info modal on first login."""
        if not current_user.is_authenticated:
            return {"show_sample_data_modal": False}
        try:
            from modules.base.core.models.user import User
            from modules.base.core.models.user_setting import UserSetting
            from modules.base.core.models.workspace_user import WorkspaceUser

            dismissed = (
                UserSetting.query
                .execution_options(skip_tenant_filter=True)
                .filter_by(user_id=current_user.id, key="sample_data_modal_dismissed")
                .first()
            )
            if dismissed:
                return {"show_sample_data_modal": False}

            has_sample = (
                WorkspaceUser.scoped()
                .join(User, WorkspaceUser.user_id == User.id)
                .filter(
                    User.is_sample.is_(True),
                    WorkspaceUser.deleted_at.is_(None),
                )
                .first()
            ) is not None
            return {"show_sample_data_modal": has_sample}
        except Exception:
            return {"show_sample_data_modal": False}
