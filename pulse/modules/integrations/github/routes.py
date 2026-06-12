# Copyright (c) 2025-2026 remarQable LLC

"""GitHub App connect flow, settings, and issue search routes.

Defines github_bp. The api and webhook modules attach additional routes
to this blueprint when imported by module.py.
"""

import logging
import re
import secrets

from flask import flash, jsonify, redirect, request, session, url_for
from flask_login import login_required
from markupsafe import Markup, escape

from system.auth.current_member import current_member
from system.auth.decorators import admin_required
from system.device.template import render_device_template
from system.i18n.translation import translate as _

from flask import Blueprint

from modules.integrations.models.integration_connection import IntegrationConnection

logger = logging.getLogger(__name__)

github_bp = Blueprint(
    "github_bp",
    __name__,
    template_folder="views/templates",
)

_GH_TOKEN_RE = re.compile(r'\[GH-(\d+)\]')


# ── resolve_gh_chips Jinja2 filter ────────────────────────────────────────────

_TIER_COLORS = {1: '#dc2626', 2: '#d97706', 3: '#16a34a'}
_TIER_LABELS = {1: 'NOW', 2: 'LATER', 3: 'WHENEVER'}


def _build_chip_html(ref) -> str:
    """Build chip HTML for one IntegrationRef without a Jinja2 template."""
    from modules.base.people.utils.filters import timeago_filter

    state_data = ref.cached_state

    if state_data is None or ref.external_id is None:
        chip_state = 'broken'
    elif ref.linked_task_id and state_data.get('state') == 'open':
        chip_state = 'linked'
    elif state_data.get('state') == 'open':
        chip_state = 'open'
    else:
        chip_state = 'closed'

    raw_title = state_data.get('title', '') if state_data else ''
    display_title = (raw_title[:40] + '…') if len(raw_title) > 40 else raw_title

    chip_inner: list[str] = [
        '<span class="gh-chip__dot"></span>',
        f'<span class="gh-chip__title">#{escape(str(ref.external_id))}'
        + (f' {escape(display_title)}' if display_title else '')
        + '</span>',
    ]

    if chip_state == 'linked' and ref.linked_task:
        tier = ref.linked_task.urgency_tier
        tc = _TIER_COLORS.get(tier, '#6b7280')
        tl = _TIER_LABELS.get(tier, '')
        if tl:
            chip_inner.append(
                f'<span class="gh-chip__badge" style="background:{tc}22;color:{tc};">{tl}</span>'
            )

    if chip_state == 'broken':
        popover_body = (
            f'<span class="gh-popover__title" style="color:#999;font-style:italic;font-weight:400;">'
            f'#{escape(str(ref.external_id))} — {escape(_("Issue could not be found"))}'
            f'</span>'
        )
    else:
        issue_state = state_data.get('state', 'open')
        state_label = escape(_('Open') if issue_state == 'open' else _('Closed'))
        repo = escape(ref.external_repo or '')
        title = escape(state_data.get('title', ''))
        issue_num = escape(str(ref.external_id))

        meta_parts: list[str] = []
        if state_data.get('opened_by'):
            meta_parts.append(f'{escape(_("Opened by"))} <strong>{escape(state_data["opened_by"])}</strong>')
        if state_data.get('opened_at'):
            try:
                meta_parts.append(f' · {escape(timeago_filter(state_data["opened_at"]))}')
            except Exception:
                pass
        for lbl in state_data.get('labels', []):
            meta_parts.append(f'<span class="gh-popover__label">{escape(lbl)}</span>')

        action_parts: list[str] = []
        if state_data.get('html_url'):
            action_parts.append(
                f'<a href="{escape(state_data["html_url"])}" target="_blank" rel="noopener"'
                f' class="gh-popover__btn gh-popover__btn--github">{escape(_("Open in GitHub"))}</a>'
            )
        if ref.linked_task_id:
            task_url = escape(url_for('tasks_bp.detail', item_id=ref.linked_task_id))
            action_parts.append(
                f'<a href="{task_url}" class="gh-popover__btn">{escape(_("View task"))}</a>'
            )

        popover_body = (
            f'<span class="gh-popover__repo">{repo}</span>'
            f'<span class="gh-popover__status gh-popover__status--{issue_state}">'
            f'<span class="gh-popover__status-dot"></span>'
            f'<span>{state_label}</span></span>'
            f'<span class="gh-popover__title">'
            f'<span class="gh-popover__title-num">#{issue_num}</span>{title}</span>'
            f'<span class="gh-popover__meta">{"".join(meta_parts)}</span>'
            + (f'<span class="gh-popover__actions">{"".join(action_parts)}</span>' if action_parts else '')
        )

    chip_inner.append(f'<span class="gh-popover">{popover_body}</span>')
    return f'<span class="gh-chip gh-chip--{chip_state}">{"".join(chip_inner)}</span>'


@github_bp.app_template_filter('resolve_gh_chips')
def resolve_gh_chips(text: str, object_type: str = '', object_id: int = 0) -> Markup:
    """Replace [GH-N] tokens in text with chip HTML.

    Fetches all IntegrationRef rows for the given sparQ object in a single
    query (avoiding N+1), then substitutes each matching token. Non-token
    text is HTML-escaped. Stale tokens (no matching ref) render as broken chips.
    """
    if not text:
        return Markup('')

    from modules.integrations.models.integration_ref import IntegrationRef
    from sqlalchemy.orm import joinedload
    import types

    try:
        refs = (
            IntegrationRef.scoped()
            .options(joinedload(IntegrationRef.linked_task))
            .filter_by(object_type=object_type, object_id=object_id)
            .all()
            if object_id else []
        )
        ref_map = {r.external_id: r for r in refs}
    except Exception:
        ref_map = {}

    parts = _GH_TOKEN_RE.split(text)

    token_numbers = [parts[i] for i in range(1, len(parts), 2)]
    missing_numbers = [n for n in token_numbers if n not in ref_map]

    # Fallback 1: unbound refs (object_id=0) not yet rebound to this object.
    if missing_numbers and object_id:
        try:
            fallback1 = (
                IntegrationRef.scoped()
                .options(joinedload(IntegrationRef.linked_task))
                .filter(
                    IntegrationRef.object_type == object_type,
                    IntegrationRef.object_id == 0,
                    IntegrationRef.external_id.in_(missing_numbers),
                    IntegrationRef.cached_state.isnot(None),
                )
                .all()
            )
            for r in fallback1:
                if r.external_id not in ref_map:
                    ref_map[r.external_id] = r
        except Exception:
            pass

    # Fallback 2: any ref with matching external_id in this workspace — e.g. the
    # same issue was tagged on a task, so its cached state can still render the chip.
    still_missing = [n for n in missing_numbers if n not in ref_map]
    if still_missing:
        try:
            fallback2 = (
                IntegrationRef.scoped()
                .options(joinedload(IntegrationRef.linked_task))
                .filter(
                    IntegrationRef.provider == 'github',
                    IntegrationRef.external_id.in_(still_missing),
                    IntegrationRef.cached_state.isnot(None),
                )
                .all()
            )
            for r in fallback2:
                if r.external_id not in ref_map:
                    ref_map[r.external_id] = r
        except Exception:
            pass

    result: list[str] = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            result.append(str(escape(part)))
        else:
            number = part
            ref = ref_map.get(number)
            if ref is None:
                ref = types.SimpleNamespace(
                    external_id=number,
                    external_repo='',
                    cached_state=None,
                    linked_task_id=None,
                    linked_task=None,
                )
            try:
                result.append(_build_chip_html(ref))
            except Exception:
                result.append(f'[GH-{number}]')

    return Markup(''.join(result))


# ── GitHub — management page ──────────────────────────────────────────────────


@github_bp.route("/settings/github")
@login_required
@admin_required
def github_settings():
    """GitHub integration management page — connected or disconnected state."""
    connection = IntegrationConnection.get_active("github")
    return render_device_template(
        "github/desktop/github.html",
        connection=connection,
    )


# ── GitHub — people mapping (GitHub account ↔ sparQ member) ────────────────────


@github_bp.route("/github/people")
@login_required
def github_people():
    """Map GitHub collaborators to sparQ members.

    Admins map anyone (dropdown); any member can claim their own GitHub identity
    ("This is me"), which overrides an admin guess. Repo activity (commits/PRs)
    is then attributed to the mapped member's "Current" status. Matching is by
    the immutable GitHub numeric id, cross-referenced against the live roster.
    """
    from sqlalchemy.orm import joinedload
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from modules.base.core.models.oauth_connection import OAuthConnection
    from modules.base.core.models.workspace_user import WorkspaceUser, EmployeeStatus

    connection = IntegrationConnection.get_active("github")
    if not connection:
        flash(_("GitHub is not connected."), "error")
        return redirect(url_for("github_bp.github_settings"))

    try:
        client = GitHubClient(connection)
        collaborators = client.list_collaborators(connection.external_repo)
    except GitHubAPIError as exc:
        logger.error("github_people: collaborator fetch failed: %s", exc)
        flash(_("Could not fetch collaborators from GitHub."), "error")
        return redirect(url_for("github_bp.github_settings"))

    mappings = OAuthConnection.github_mappings_for_workspace()
    members = (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(status=EmployeeStatus.ACTIVE)
        .all()
    )
    current = current_member()
    mapped_count = sum(1 for c in collaborators if str(c.get("id", "")) in mappings)

    return render_device_template(
        "github/desktop/people.html",
        collaborators=collaborators,
        mappings=mappings,
        members=members,
        connection=connection,
        current_member_id=current.id if current else None,
        mapped_count=mapped_count,
    )


@github_bp.route("/github/people/map", methods=["POST"])
@login_required
@admin_required
def github_people_map():
    """Admin: set or clear the sparQ member mapped to a GitHub collaborator."""
    from modules.base.core.models.oauth_connection import OAuthConnection
    from modules.base.core.models.workspace_user import WorkspaceUser

    github_user_id = request.form.get("github_user_id", "").strip()
    member_id = request.form.get("member_id", "").strip()
    if not github_user_id:
        flash(_("Missing GitHub user."), "error")
        return redirect(url_for("github_bp.github_people"))

    if member_id.isdigit():
        member = WorkspaceUser.scoped().filter_by(id=int(member_id)).first()
        if member:
            OAuthConnection.set_github_mapping(github_user_id, member.user_id)
    else:
        OAuthConnection.clear_github_mapping(github_user_id)
    flash(_("GitHub mapping updated."), "success")
    return redirect(url_for("github_bp.github_people"))


@github_bp.route("/github/people/claim", methods=["POST"])
@login_required
def github_people_claim():
    """Any member: claim a GitHub identity as their own (overrides admin)."""
    from modules.base.core.models.oauth_connection import OAuthConnection

    github_user_id = request.form.get("github_user_id", "").strip()
    member = current_member()
    if not github_user_id or not member:
        flash(_("Could not link your GitHub identity."), "error")
        return redirect(url_for("github_bp.github_people"))

    OAuthConnection.set_github_mapping(github_user_id, member.user_id)
    flash(_("Linked your GitHub identity."), "success")
    return redirect(url_for("github_bp.github_people"))


# ── GitHub — connect flow ─────────────────────────────────────────────────────


@github_bp.route("/github/connect")
@login_required
@admin_required
def github_connect():
    """Render the auth-method choice page (GitHub App vs Personal Access Token).

    If the workspace is already connected, redirects to the settings page
    with a flash message to prevent accidental silent re-connections.

    The GitHub App card is hidden when GITHUB_APP_SLUG, GITHUB_APP_ID, or
    GITHUB_APP_PRIVATE_KEY are absent — the option is meaningless without them.
    """
    import os

    if IntegrationConnection.get_active("github"):
        flash(_("GitHub is already connected."), "info")
        return redirect(url_for("github_bp.github_settings"))

    app_configured = all([
        os.environ.get("GITHUB_APP_SLUG"),
        os.environ.get("GITHUB_APP_ID"),
        os.environ.get("GITHUB_APP_PRIVATE_KEY"),
    ])
    return render_device_template("github/desktop/connect.html", app_configured=app_configured)


@github_bp.route("/github/connect/app")
@login_required
@admin_required
def github_connect_app():
    """Redirect the admin to the GitHub App installation page.

    Stores a CSRF state token in the session for callback verification.
    """
    import os

    slug = os.environ.get("GITHUB_APP_SLUG", "")
    if not slug:
        flash(_("GitHub App is not configured (GITHUB_APP_SLUG missing)."), "error")
        return redirect(url_for("integrations_bp.settings_index"))

    state = secrets.token_urlsafe(32)
    session["github_install_state"] = state

    install_url = f"https://github.com/apps/{slug}/installations/new?state={state}"
    return redirect(install_url)


@github_bp.route("/github/connect/pat", methods=["POST"])
@login_required
@admin_required
def github_connect_pat():
    """Validate and save a Personal Access Token connection.

    Reads ``pat_token`` and ``repo`` from the form. Validates the token by
    calling ``GET /repos/{repo}`` on the GitHub API before storing it — if
    the call returns non-200 the form is re-rendered with an error flash.

    On success, calls ``IntegrationConnection.finalize_pat_connection()`` and
    redirects to the settings page.

    Returns:
        Redirect to settings on success; redirect to choice page on failure.
    """
    import requests as _requests

    pat_token = request.form.get("pat_token", "").strip()
    repo = request.form.get("repo", "").strip()

    if not pat_token or not repo:
        flash(_("Please provide both a token and a repository."), "error")
        return redirect(url_for("github_bp.github_connect"))

    # Validate: a 200 response from /repos/{repo} confirms the token works.
    try:
        resp = _requests.get(
            f"https://api.github.com/repos/{repo}",
            headers={
                "Authorization": f"token {pat_token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
    except Exception as exc:
        logger.error("PAT validation request failed: %s", exc)
        flash(_("Invalid token or repository not accessible."), "error")
        return redirect(url_for("github_bp.github_connect"))

    if not resp.ok:
        flash(_("Invalid token or repository not accessible."), "error")
        return redirect(url_for("github_bp.github_connect"))

    member = current_member()
    conn = IntegrationConnection.get_or_create("github")
    conn.finalize_pat_connection(
        pat_token=pat_token,
        repo=repo,
        member_id=member.id if member else None,
    )

    # Register a repo webhook so issue updates sync automatically. A valid
    # connection is kept even if this fails — the manual Sync button still works.
    from modules.integrations.github.provider import GitHubProvider

    status = GitHubProvider().register_webhook(conn)
    if status in ("registered", "reused"):
        flash(_("GitHub connected. Issue updates will sync automatically."), "success")
    elif status == "no_permission":
        flash(
            _(
                "GitHub connected, but automatic sync is off: the token needs the "
                "admin:repo_hook scope and repository admin rights. Use the Sync "
                "button to refresh manually until that's fixed."
            ),
            "warning",
        )
    else:
        flash(
            _(
                "GitHub connected, but automatic sync could not be enabled. Use the "
                "Sync button to refresh manually."
            ),
            "warning",
        )
    return redirect(url_for("github_bp.github_settings"))


@github_bp.route("/github/callback")
@login_required
@admin_required
def github_callback():
    """Handle the GitHub App installation callback.

    GitHub redirects here with ?installation_id=<id>&setup_action=install&state=<state>.
    Validates state, fetches accessible repos, and renders the repo-select form.
    """
    # Validate state to prevent CSRF.
    expected_state = session.pop("github_install_state", None)
    returned_state = request.args.get("state", "")
    if not expected_state or not secrets.compare_digest(expected_state, returned_state):
        flash(_("Invalid callback state. Please try connecting again."), "error")
        return redirect(url_for("integrations_bp.settings_index"))

    installation_id = request.args.get("installation_id", "")
    if not installation_id:
        flash(_("No installation ID received from GitHub."), "error")
        return redirect(url_for("integrations_bp.settings_index"))

    # Fetch the list of repos accessible to this installation.
    try:
        from modules.integrations.github.client import _exchange_installation_token, GitHubAPIError
        import requests as _requests

        plain_token, _expires = _exchange_installation_token(installation_id)
        headers = {
            "Authorization": f"token {plain_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = _requests.get(
            "https://api.github.com/installation/repositories",
            headers=headers,
            params={"per_page": 100},
            timeout=15,
        )
        repos = resp.json().get("repositories", []) if resp.ok else []
    except GitHubAPIError as exc:
        logger.error("GitHub repo fetch failed for installation %s: %s", installation_id, exc)
        flash(_("Could not fetch repositories from GitHub. Please try again."), "error")
        return redirect(url_for("integrations_bp.settings_index"))
    except Exception as exc:
        logger.error("GitHub callback error: %s", exc, exc_info=True)
        flash(_("GitHub connection failed. Please try again."), "error")
        return redirect(url_for("integrations_bp.settings_index"))

    return render_device_template(
        "github/desktop/partials/_repo_select.html",
        installation_id=installation_id,
        repos=repos,
    )


@github_bp.route("/github/select-repo", methods=["POST"])
@login_required
@admin_required
def github_select_repo():
    """Save the chosen repo and finalise the GitHub App connection.

    Accepts form fields: installation_id, repo (owner/repo string).
    CSRF is validated by the global middleware via the csrf_token form field.
    """
    installation_id = request.form.get("installation_id", "").strip()
    repo = request.form.get("repo", "").strip()

    if not installation_id or not repo:
        flash(_("Please select a repository."), "error")
        return redirect(url_for("integrations_bp.settings_index"))

    member = current_member()
    conn = IntegrationConnection.get_or_create("github")
    conn.finalize_connection(installation_id, repo, member.id if member else None)

    flash(_("GitHub connected successfully."), "success")
    return redirect(url_for("github_bp.github_settings"))


# ── GitHub — change connected repository ─────────────────────────────────────


@github_bp.route("/github/change-repo", methods=["GET", "POST"])
@login_required
@admin_required
def github_change_repo():
    """Render and handle the change-repository form.

    GET: For App auth, fetches accessible repos from GitHub and renders a
    dropdown pre-selected on the current repo. For PAT auth, renders a text
    input pre-filled with the current repo.

    POST: Validates the new repo using existing credentials (installation token
    for App, stored PAT for PAT), then calls ``update_repo()`` and redirects.
    """
    import requests as _requests

    connection = IntegrationConnection.get_active("github")
    if not connection:
        flash(_("GitHub is not connected."), "error")
        return redirect(url_for("github_bp.github_settings"))

    if request.method == "POST":
        repo = request.form.get("repo", "").strip()
        if not repo:
            flash(_("Please select a repository."), "error")
            return redirect(url_for("github_bp.github_change_repo"))

        if connection.auth_type == "app":
            try:
                from modules.integrations.github.client import _exchange_installation_token
                plain_token, _ = _exchange_installation_token(connection.installation_id)
                resp = _requests.get(
                    f"https://api.github.com/repos/{repo}",
                    headers={
                        "Authorization": f"token {plain_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=10,
                )
            except Exception as exc:
                logger.error("Repo validation failed during change-repo: %s", exc)
                flash(_("Could not verify repository access."), "error")
                return redirect(url_for("github_bp.github_change_repo"))

            if not resp.ok:
                flash(_("Repository not accessible to this GitHub App installation."), "error")
                return redirect(url_for("github_bp.github_change_repo"))

        else:  # PAT
            try:
                from system.oauth.token_manager import TokenManager
                plain_token = TokenManager.decrypt(connection.cached_token)
            except Exception as exc:
                logger.error("Could not decrypt PAT for repo validation: %s", exc)
                flash(_("Could not retrieve stored token."), "error")
                return redirect(url_for("github_bp.github_change_repo"))

            try:
                resp = _requests.get(
                    f"https://api.github.com/repos/{repo}",
                    headers={
                        "Authorization": f"token {plain_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    timeout=10,
                )
            except Exception as exc:
                logger.error("PAT repo validation failed during change-repo: %s", exc)
                flash(_("Could not verify repository access."), "error")
                return redirect(url_for("github_bp.github_change_repo"))

            if not resp.ok:
                flash(_("Token does not have access to that repository."), "error")
                return redirect(url_for("github_bp.github_change_repo"))

        # PAT webhooks are repo-scoped: move the hook to the new repo. App
        # connections receive events through the GitHub App, so skip them.
        if connection.auth_type == "pat":
            from modules.integrations.github.provider import GitHubProvider

            provider = GitHubProvider()
            provider.deregister_webhook(connection)  # old repo (still current)
            connection.update_repo(repo)
            provider.register_webhook(connection)    # new repo
        else:
            connection.update_repo(repo)

        flash(_("Repository updated successfully."), "success")
        return redirect(url_for("github_bp.github_settings"))

    # GET — fetch repo list for App auth
    repos = []
    if connection.auth_type == "app":
        try:
            from modules.integrations.github.client import _exchange_installation_token, GitHubAPIError
            plain_token, _ = _exchange_installation_token(connection.installation_id)
            resp = _requests.get(
                "https://api.github.com/installation/repositories",
                headers={
                    "Authorization": f"token {plain_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100},
                timeout=15,
            )
            repos = resp.json().get("repositories", []) if resp.ok else []
        except GitHubAPIError as exc:
            logger.error("Repo fetch failed during change-repo GET: %s", exc)
            flash(_("Could not fetch repositories from GitHub."), "error")
            return redirect(url_for("github_bp.github_settings"))
        except Exception as exc:
            logger.error("change-repo GET error: %s", exc, exc_info=True)
            flash(_("Could not fetch repositories from GitHub."), "error")
            return redirect(url_for("github_bp.github_settings"))

    return render_device_template(
        "github/desktop/partials/_repo_change.html",
        connection=connection,
        repos=repos,
    )


# ── GitHub — sync all refs ───────────────────────────────────────────────────


@github_bp.route("/github/sync-refs", methods=["POST"])
@login_required
@admin_required
def github_sync_refs():
    """Refresh cached_state for all IntegrationRef rows from the GitHub API.

    Runs synchronously (not in background) so the response confirms completion.

    Returns:
        JSON: {updated: int} on success; {error: str} on failure.
    """
    from modules.integrations.github.sync import sync_all_cached_refs

    connection = IntegrationConnection.get_active("github")
    if not connection:
        return jsonify({"error": "GitHub not connected"}), 400

    try:
        updated = sync_all_cached_refs(connection)
    except Exception as exc:
        logger.error("github_sync_refs failed: %s", exc, exc_info=True)
        return jsonify({"error": "Sync failed. Check server logs."}), 500

    return jsonify({"updated": updated})


# ── GitHub — disconnect ───────────────────────────────────────────────────────


@github_bp.route("/github/disconnect", methods=["POST"])
@login_required
@admin_required
def github_disconnect():
    """Disconnect the GitHub App from this workspace.

    CSRF is validated by the global middleware.
    """
    from modules.integrations.github.provider import GitHubProvider

    connection = IntegrationConnection.get_active("github")
    if not connection:
        flash(_("GitHub is not connected."), "warning")
        return redirect(url_for("integrations_bp.settings_index"))

    GitHubProvider().disconnect(connection)
    flash(_("GitHub disconnected."), "success")
    return redirect(url_for("integrations_bp.settings_index"))


# ── GitHub — issues search API ────────────────────────────────────────────────


@github_bp.route("/github/issues")
@login_required
def github_issues_search():
    """Search GitHub issues for the connected repo.

    Query params:
        q (str): Free-text search query.

    Returns:
        JSON: {connected: bool, issues: [{number, title, state, html_url}]}
    """
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from modules.integrations.models.integration_ref import IntegrationRef

    connection = IntegrationConnection.get_active("github")
    if not connection:
        return jsonify({"connected": False})

    query = request.args.get("q", "").strip()
    try:
        client = GitHubClient(connection)
        issues = client.search_issues(connection.external_repo, query)
    except GitHubAPIError as exc:
        logger.error("GitHub issue search failed: %s", exc)
        return jsonify({"connected": True, "error": str(exc), "issues": []})

    # Exclude issues already paired with a sparQ task in this workspace.
    linked_ids = {
        row.external_id
        for row in IntegrationRef.scoped()
        .filter(
            IntegrationRef.provider == "github",
            IntegrationRef.linked_task_id.isnot(None),
        )
        .with_entities(IntegrationRef.external_id)
        .all()
    }
    if linked_ids:
        issues = [i for i in issues if str(i["number"]) not in linked_ids]

    return jsonify({"connected": True, "issues": issues})
