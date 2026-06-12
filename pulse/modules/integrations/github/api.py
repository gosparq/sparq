# Copyright (c) 2025-2026 remarQable LLC

"""GitHub JSON API — IntegrationRef creation, chip refresh, UC-6 issue creation, UC-7 orphans."""

import logging
from datetime import datetime

from flask import jsonify, render_template, request
from flask_login import login_required

from system.auth.current_member import current_member as _current_member

from .routes import github_bp
from modules.integrations.models.integration_connection import IntegrationConnection
from modules.integrations.models.integration_ref import IntegrationRef

logger = logging.getLogger(__name__)


def _normalize_issue_state(raw: dict) -> dict:
    """Extract a stable cached_state dict from a raw GitHub API issue response.

    Args:
        raw: Full GitHub API issue object.

    Returns:
        Normalized dict with keys: title, state, html_url, opened_by,
        opened_at, labels, assignee_login.
    """
    labels = [lbl.get("name", "") for lbl in raw.get("labels", [])]
    user = raw.get("user") or {}
    assignee = raw.get("assignee") or {}
    return {
        "title": raw.get("title", ""),
        "state": raw.get("state", "open"),
        "html_url": raw.get("html_url", ""),
        "opened_by": user.get("login", ""),
        "opened_at": raw.get("created_at", ""),
        "labels": labels,
        "assignee_login": assignee.get("login", ""),
    }


def _render_chip(ref: IntegrationRef) -> str:
    """Render the chip HTML for a ref, eager-loading the linked action item.

    Args:
        ref: IntegrationRef ORM instance (linked_task must be loaded).

    Returns:
        HTML string for the chip.
    """
    return render_template(
        'github/desktop/partials/_issue_chip.html',
        ref=ref,
    )


def _write_backlink(client: "object", repo: str, issue_number: "int | str", current_body: str, task_id: int) -> None:
    """Synchronously inject the sparQ backlink section into a GitHub issue body.

    Runs in the current request context so url_for works correctly. Errors
    are caught and logged — must never raise or break the caller's response.

    Args:
        client: Authenticated GitHubClient instance.
        repo: Owner/repo string.
        issue_number: GitHub issue number.
        current_body: Issue body already fetched by the caller (avoids an extra GET).
        task_id: Task.id to link back to.
    """
    try:
        from flask import url_for as _url_for

        from modules.base.tasks.models.task import Task
        from modules.integrations.github.sync import inject_backlink

        print(f"[backlink] entering task_id={task_id} issue #{issue_number} repo={repo}")
        task = Task.query.filter_by(id=task_id).first()
        if not task:
            print(f"[backlink] task_id={task_id} not found")
            return
        task_url = _url_for("tasks_bp.detail", item_id=task_id, _external=True)
        import re as _re
        clean_title = _re.sub(r"\s*\[GH-\d+\]\s*", " ", task.title or "").strip()
        print(f"[backlink] url={task_url!r} title={clean_title!r}")
        new_body = inject_backlink(current_body, clean_title, task_url)
        if new_body != current_body:
            client.update_issue_body(repo, int(issue_number), new_body)
            print(f"[backlink] PATCHED issue #{issue_number} for task={task_id}")
        else:
            print(f"[backlink] body unchanged for issue #{issue_number} (already present)")
    except Exception as exc:
        import traceback
        print(f"[backlink] FAILED task_id={task_id} issue #{issue_number}: {exc}")
        traceback.print_exc()


# ── POST /integrations/github/refs ───────────────────────────────────────────


@github_bp.route("/github/refs", methods=["POST"])
@login_required
def github_create_ref():
    """Create or update an IntegrationRef for a GitHub issue selection.

    Called by the JS trigger when a user selects an issue from the dropdown.

    JSON body:
        external_id (int): GitHub issue number.
        external_repo (str): Owner/repo string.
        object_type (str): sparQ entity type ("task", "post", "blocker").
        object_id (int): Primary key of the sparQ entity.

    Returns:
        JSON: {ref_id, chip_html} on success; {error} on failure.
    """
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from sqlalchemy.orm import joinedload

    data = request.get_json(silent=True) or {}
    external_id = str(data.get("external_id", "")).strip()
    external_repo = str(data.get("external_repo", "")).strip()
    object_type = str(data.get("object_type", "")).strip()
    object_id = int(data.get("object_id", 0) or 0)

    if not external_id or not external_repo or not object_type:
        return jsonify({"error": "external_id, external_repo, and object_type are required"}), 400

    connection = IntegrationConnection.get_active("github")
    if not connection:
        return jsonify({"error": "GitHub not connected"}), 400

    # Fetch current issue state from GitHub.
    client = None
    raw = None
    try:
        client = GitHubClient(connection)
        raw = client.get_issue(external_repo, int(external_id))
        cached_state = _normalize_issue_state(raw)
    except GitHubAPIError as exc:
        logger.warning("GitHub issue fetch failed for #%s: %s", external_id, exc)
        cached_state = None
    except Exception as exc:
        logger.error("Unexpected error fetching GitHub issue #%s: %s", external_id, exc, exc_info=True)
        cached_state = None

    # Create or update the ref row.
    ref = IntegrationRef.get_or_create(
        provider="github",
        external_id=external_id,
        external_repo=external_repo,
        object_type=object_type,
        object_id=object_id,
    )

    # Enforce one-issue-per-task: if this issue is already linked to a
    # different task, reject the request.
    if object_type == "task" and object_id:
        existing_task_id = ref.linked_task_id or (ref.object_id if ref.object_type == "task" and ref.object_id else None)
        if existing_task_id and existing_task_id != object_id:
            return jsonify({"error": "This GitHub issue is already linked to another task."}), 409

    if cached_state:
        ref.update_cached_state(cached_state)

    # When linked to a task, set linked_task_id so sync and chip state work correctly.
    from system.db.database import db
    if object_type == "task" and object_id and ref.linked_task_id != object_id:
        ref.linked_task_id = object_id
        db.session.commit()
        # Now linked — drop it from the orphan cache so it leaves the link list.
        from modules.integrations.github.provider import GitHubProvider
        GitHubProvider()._refresh_orphans_async(connection.id)

    # When called from the task-create modal (object_id=0), stash the ref ID
    # in the session so _bind_pending_refs can find it even if the ref already
    # existed with a different linked_task_id.
    if object_type == "task" and not object_id:
        from flask import session
        pending = list(session.get("pending_gh_ref_ids", []))
        if ref.id not in pending:
            pending.append(ref.id)
        session["pending_gh_ref_ids"] = pending

    # Write sparQ backlink into the GitHub issue body.
    if object_type == "task" and object_id and client is not None:
        _write_backlink(client, external_repo, external_id, (raw or {}).get("body") or "", object_id)

    # Re-fetch with eager-loaded relationship for chip rendering.
    ref = (
        IntegrationRef.scoped()
        .options(joinedload(IntegrationRef.linked_task))
        .filter_by(id=ref.id)
        .first()
    )

    try:
        chip_html = _render_chip(ref)
    except Exception as exc:
        logger.error("Chip render failed for ref %s: %s", ref.id, exc, exc_info=True)
        chip_html = f'[GH-{external_id}]'

    return jsonify({"ref_id": ref.id, "chip_html": chip_html})


# ── GET /integrations/github/chip/<ref_id> ───────────────────────────────────


@github_bp.route("/github/chip/<int:ref_id>")
@login_required
def github_chip_refresh(ref_id: int):
    """Refresh the cached state for an IntegrationRef and return chip HTML.

    Args:
        ref_id: Primary key of the IntegrationRef row.

    Returns:
        JSON: {chip_html} on success; {error} on failure.
    """
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from sqlalchemy.orm import joinedload

    ref = (
        IntegrationRef.scoped()
        .options(joinedload(IntegrationRef.linked_task))
        .filter_by(id=ref_id)
        .first()
    )
    if not ref:
        return jsonify({"error": "ref not found"}), 404

    connection = IntegrationConnection.get_active("github")
    if connection and ref.external_id and ref.external_repo:
        try:
            client = GitHubClient(connection)
            raw = client.get_issue(ref.external_repo, int(ref.external_id))
            ref.update_cached_state(_normalize_issue_state(raw))
        except GitHubAPIError as exc:
            logger.warning("Chip refresh failed for ref %s: %s", ref_id, exc)
        except Exception as exc:
            logger.error("Chip refresh error for ref %s: %s", ref_id, exc, exc_info=True)

    try:
        chip_html = _render_chip(ref)
    except Exception as exc:
        logger.error("Chip render failed for ref %s: %s", ref_id, exc, exc_info=True)
        chip_html = f'[GH-{ref.external_id}]'

    return jsonify({"chip_html": chip_html})


# ── GET /integrations/github/task-chips ──────────────────────────────────────


@github_bp.route("/github/task-chips")
@login_required
def github_task_chips():
    """Return fresh chip HTML for a list of task IDs.

    Query params:
        ids (str): Comma-separated list of task IDs.

    Returns:
        JSON: {task_id: chip_html_or_null} — null means no linked GitHub issue.
    """
    from sqlalchemy.orm import joinedload

    raw_ids = request.args.get("ids", "")
    try:
        task_ids = [int(i) for i in raw_ids.split(",") if i.strip().isdigit()]
    except Exception:
        return jsonify({}), 400

    if not task_ids:
        return jsonify({})

    refs = (
        IntegrationRef.scoped()
        .options(joinedload(IntegrationRef.linked_task))
        .filter(
            IntegrationRef.provider == "github",
            IntegrationRef.linked_task_id.in_(task_ids),
        )
        .all()
    )

    ref_by_task = {ref.linked_task_id: ref for ref in refs}
    result = {}
    for task_id in task_ids:
        ref = ref_by_task.get(task_id)
        if ref is None:
            result[task_id] = None
        else:
            try:
                result[task_id] = _render_chip(ref)
            except Exception as exc:
                logger.error("task-chips render failed for task %s: %s", task_id, exc)
                result[task_id] = None

    return jsonify(result)


# ── GET /integrations/github/collaborators ────────────────────────────────────


@github_bp.route("/github/collaborators")
@login_required
def github_collaborators():
    """Return repository contributors enriched with sparQ member context.

    Returns:
        JSON: [{login, avatar_url, contributions, sparq_member_id,
                sparq_display_name, now_count, blocker_count}]
    """
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from modules.base.core.models.oauth_connection import OAuthConnection
    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.tasks.models.task import Task

    connection = IntegrationConnection.get_active("github")
    if not connection:
        return jsonify({"error": "GitHub not connected"}), 400

    try:
        client = GitHubClient(connection)
        raw_contributors = client.list_contributors(connection.external_repo)
    except GitHubAPIError as exc:
        logger.error("GitHub contributors fetch failed: %s", exc)
        return jsonify({"error": str(exc)}), 502
    except Exception as exc:
        logger.error("GitHub contributors error: %s", exc, exc_info=True)
        return jsonify({"error": "unexpected error"}), 500

    oauth_rows = OAuthConnection.query.filter_by(provider="github").all()
    github_id_to_member: dict[str, WorkspaceUser] = {}
    for oauth in oauth_rows:
        if oauth.provider_user_id:
            member = WorkspaceUser.query.filter_by(
                workspace_id=connection.workspace_id, user_id=oauth.user_id
            ).first()
            if member:
                github_id_to_member[str(oauth.provider_user_id)] = member

    now_map = Task.open_tier1_counts_by_assignee()
    blocker_map = Task.open_blocker_counts_by_assignee()

    result = []
    for contrib in raw_contributors:
        login = contrib.get("login", "")
        avatar = contrib.get("avatar_url", "")
        contributions = contrib.get("contributions", 0)
        github_uid = str(contrib.get("id", ""))
        sparq_mid = None
        sparq_name = None
        now_count = 0
        bc = 0

        member = github_id_to_member.get(github_uid)
        if member:
            sparq_mid = member.id
            user = getattr(member, "user", None)
            if user:
                sparq_name = f"{user.first_name} {user.last_name}".strip()
            now_count = now_map.get(member.id, 0)
            bc = blocker_map.get(member.id, 0)

        result.append({
            "login": login,
            "avatar_url": avatar,
            "contributions": contributions,
            "sparq_member_id": sparq_mid,
            "sparq_display_name": sparq_name,
            "now_count": now_count,
            "blocker_count": bc,
        })

    return jsonify(result)


# ── GET /integrations/github/issues/new-modal ─────────────────────────────────


@github_bp.route("/github/issues/new-modal")
@login_required
def github_issues_new_modal():
    """Return the UC-6 create-issue modal HTML for HTMX swap.

    Query params:
        context (str): Pre-fill title from selected text.
        object_type (str): Originating sparQ entity type.
        object_id (int): Originating sparQ entity primary key.
        external_id (str): If set, "pair existing issue" mode (UC-7 Claim).

    Returns:
        HTML fragment for Bootstrap modal.
    """
    connection = IntegrationConnection.get_active("github")
    if not connection:
        return "GitHub not connected", 400

    context = request.args.get("context", "")
    object_type = request.args.get("object_type", "")
    object_id = request.args.get("object_id", type=int) or 0
    external_id = request.args.get("external_id", "")

    return render_template(
        "github/desktop/partials/_create_issue_modal.html",
        connection=connection,
        prefill_title=context,
        object_type=object_type,
        object_id=object_id,
        external_id=external_id,
        pair_mode=bool(external_id),
    )


# ── POST /integrations/github/issues ─────────────────────────────────────────


@github_bp.route("/github/issues", methods=["POST"])
@login_required
def github_issues_create():
    """Create a GitHub issue and optionally a paired sparQ Task.

    JSON body:
        title (str): Issue title.
        body (str): Issue body (Markdown).
        assignee_login (str): GitHub login to assign (optional).
        urgency (int): 1, 2, or 3 (maps to NOW/LATER/WHENEVER labels).
        create_action_item (bool): Whether to create a paired Task.
        object_type (str): Originating surface entity type.
        object_id (int): Originating surface entity PK.
        external_id (str): If set, pair with existing issue instead of creating.

    Returns:
        JSON: {chip_html, action_item_url} on success; {error} on failure.
    """
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from sqlalchemy.orm import joinedload

    member = _current_member()
    if not member:
        return jsonify({"error": "unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    title = str(data.get("title", "")).strip()
    body = str(data.get("body", "")).strip()
    _raw_assignee = data.get("assignee_login")
    assignee_login = str(_raw_assignee).strip() if _raw_assignee else None
    urgency = int(data.get("urgency", 2) or 2)
    urgency = max(1, min(3, urgency))
    create_ai = bool(data.get("create_action_item", False))
    object_type = str(data.get("object_type", "")).strip()
    object_id = int(data.get("object_id", 0) or 0)
    external_id = str(data.get("external_id", "")).strip()

    if not title and not external_id:
        return jsonify({"error": "title is required"}), 400

    connection = IntegrationConnection.get_active("github")
    if not connection:
        return jsonify({"error": "GitHub not connected"}), 400

    client = GitHubClient(connection)
    repo = connection.external_repo
    _TIER_LABELS_MAP = {1: "sparq:now", 2: "sparq:later", 3: "sparq:whenever"}
    _LABEL_COLORS = {"sparq:now": "dc2626", "sparq:later": "d97706", "sparq:whenever": "16a34a"}

    issue_number_str = external_id
    if not external_id:
        label_name = _TIER_LABELS_MAP.get(urgency, "sparq:later")
        try:
            for lname, lcolor in _LABEL_COLORS.items():
                try:
                    client.ensure_label(repo, lname, lcolor)
                except Exception:
                    pass
            raw_issue = client.create_issue(
                repo=repo,
                title=title,
                body=body,
                assignee_login=assignee_login,
                labels=[label_name],
            )
        except GitHubAPIError as exc:
            logger.error("GitHub issue creation failed: %s", exc)
            return jsonify({"error": str(exc)}), 400

        issue_number_str = str(raw_issue.get("number", ""))
        if not issue_number_str:
            return jsonify({"error": "GitHub API returned no issue number"}), 500
    else:
        try:
            raw_issue = client.get_issue(repo, int(external_id))
            title = title or raw_issue.get("title", "")
        except GitHubAPIError as exc:
            logger.error("GitHub issue fetch failed for pair mode: %s", exc)
            return jsonify({"error": str(exc)}), 400

    ref = IntegrationRef.get_or_create(
        provider="github",
        external_id=issue_number_str,
        external_repo=repo,
        object_type=object_type or "issue",
        object_id=object_id,
    )

    labels_list = [lbl.get("name", "") for lbl in raw_issue.get("labels", [])]
    user = raw_issue.get("user") or {}
    assignee_obj = raw_issue.get("assignee") or {}
    ref.update_cached_state({
        "title": raw_issue.get("title", title),
        "state": raw_issue.get("state", "open"),
        "html_url": raw_issue.get("html_url", ""),
        "opened_by": user.get("login", ""),
        "opened_at": raw_issue.get("created_at", ""),
        "labels": labels_list,
        "assignee_login": assignee_obj.get("login", ""),
    })

    from system.db.database import db as _db
    if object_type == "task" and object_id and ref.linked_task_id != object_id:
        ref.linked_task_id = object_id
        _db.session.commit()

    # When created from the task-create modal (object_id=0), stash the ref ID in
    # the session so _bind_pending_refs can reliably find it on task creation.
    if object_type == "task" and not object_id:
        from flask import session as _session
        pending = list(_session.get("pending_gh_ref_ids", []))
        if ref.id not in pending:
            pending.append(ref.id)
        _session["pending_gh_ref_ids"] = pending

    if object_type == "task" and object_id:
        try:
            from modules.base.tasks.models.task import Task as _Task
            _orig_task = _Task.query.get(object_id)
            if _orig_task:
                if f"[GH-{issue_number_str}]" not in (_orig_task.title or ""):
                    _orig_task.title = (_orig_task.title or "").rstrip() + f" [GH-{issue_number_str}]"
                if assignee_login:
                    from modules.base.core.models.oauth_connection import OAuthConnection
                    from modules.base.core.models.workspace_user import WorkspaceUser
                    _gh_uid = str((raw_issue.get("assignee") or {}).get("id", ""))
                    if _gh_uid:
                        _oauth = OAuthConnection.query.filter_by(
                            provider="github", provider_user_id=_gh_uid
                        ).first()
                        if _oauth:
                            _tm = WorkspaceUser.query.filter_by(
                                workspace_id=connection.workspace_id, user_id=_oauth.user_id
                            ).first()
                            if _tm and _orig_task.assignee_id != _tm.id:
                                _orig_task.assignee_id = _tm.id
                _db.session.commit()
        except Exception as exc:
            logger.error("Failed to update task from GitHub issue: %s", exc, exc_info=True)

    backlink_task_id = object_id if (object_type == "task" and object_id) else None

    action_item_url = None
    if create_ai:
        try:
            from modules.base.tasks.models.task import Task

            ai_assignee_id = member.id
            if assignee_login:
                pass  # TODO(human): resolve assignee_login → sparQ member via OAuthConnection

            new_task = Task.create(
                title=title[:200],
                urgency_tier=urgency,
                assignee_id=ai_assignee_id,
                raised_by_id=member.id,
                context_note=body[:500] if body else None,
            )
            if new_task:
                if not (object_type == "task" and object_id):
                    ref.link_task(new_task.id)
                from flask import url_for as _url_for
                action_item_url = _url_for("tasks_bp.detail", item_id=new_task.id)
                backlink_task_id = new_task.id
        except Exception as exc:
            logger.error("Paired Task creation failed: %s", exc, exc_info=True)

    if backlink_task_id:
        _write_backlink(client, repo, issue_number_str, raw_issue.get("body") or "", backlink_task_id)

    ref = (
        IntegrationRef.scoped()
        .options(joinedload(IntegrationRef.linked_task))
        .filter_by(id=ref.id)
        .first()
    )

    try:
        chip_html = _render_chip(ref)
    except Exception as exc:
        logger.error("Chip render failed for new issue: %s", exc, exc_info=True)
        chip_html = f'[GH-{issue_number_str}]'

    return jsonify({
        "chip_html": chip_html,
        "action_item_url": action_item_url,
        "gh_token": f"[GH-{issue_number_str}]",
    })


# ── GET /integrations/issues/unowned ─────────────────────────────────────────


@github_bp.route("/issues/unowned")
@login_required
def issues_unowned():
    """UC-7 Unowned GitHub Issues — list orphaned issues with Claim action.

    Returns:
        Rendered unowned.html page.
    """
    from system.device.template import render_device_template

    connection = IntegrationConnection.get_active("github")
    orphans = []
    if connection and connection.cached_orphan_ids:
        raw = connection.cached_orphan_ids or []
        try:
            raw.sort(key=lambda x: x.get("created_at", ""))
        except Exception:
            pass
        orphans = raw

    now = datetime.utcnow()
    for o in orphans:
        try:
            created = datetime.fromisoformat(o["created_at"].replace("Z", "+00:00").replace("+00:00", ""))
            o["age_days"] = (now - created).days
        except Exception:
            o["age_days"] = 0

    return render_device_template(
        "github/desktop/unowned.html",
        connection=connection,
        orphans=orphans,
    )


# ── GET /integrations/github/palette/create ──────────────────────────────────


@github_bp.route("/github/palette/create")
@login_required
def palette_create_panel():
    """Return the GitHub 'Create Issue' panel HTML for the slash palette.

    Query params:
        task_id (int): Task to link the new issue to (0 = unlinked).
        context (str): Pre-fill the issue title field.

    Returns:
        HTML fragment rendered into the palette action slot.
    """
    task_id = request.args.get("task_id", type=int) or 0
    context = request.args.get("context", "")
    return render_template(
        "github/desktop/partials/_palette_create_panel.html",
        task_id=task_id,
        prefill_title=context,
    )


# ── GET /integrations/github/palette/link ────────────────────────────────────


@github_bp.route("/github/palette/link")
@login_required
def palette_link_panel():
    """Return the GitHub 'Link Issue' panel HTML for the slash palette.

    Query params:
        task_id (int): Task to link the selected issue to (0 = unlinked).

    Returns:
        HTML fragment rendered into the palette action slot.
    """
    task_id = request.args.get("task_id", type=int) or 0
    return render_template(
        "github/desktop/partials/_palette_link_panel.html",
        task_id=task_id,
    )


# ── GET /integrations/github/palette/orphans ─────────────────────────────────


@github_bp.route("/github/palette/orphans")
@login_required
def palette_github_orphans():
    """Return filtered GitHub issues as an HTML fragment for the palette link step.

    Searches by issue number or title substring.  When the query is a bare
    number (e.g. ``42`` or ``#42``) and that number is not found in the local
    cache, the issue is fetched directly from the GitHub API so issues outside
    the cached set (already-linked issues, old issues, etc.) are still
    reachable.

    Query params:
        q (str): Issue number (``42`` or ``#42``) or title substring.
        task_id (int): Reserved — not used, included for future scoping.

    Returns:
        HTML fragment rendered from _palette_orphan_results.html.
    """
    connection = IntegrationConnection.get_active("github")
    if not connection:
        return "", 400

    q = request.args.get("q", "").strip()
    raw = connection.cached_orphan_ids or []

    if not q:
        return render_template(
            "github/desktop/partials/_palette_orphan_results.html",
            orphans=raw[:10],
        )

    q_lower = q.lower().lstrip("#")

    # Match by number prefix OR title substring.
    orphans = [
        o for o in raw
        if q_lower == str(o.get("number", ""))
        or q_lower in (o.get("title") or "").lower()
    ]

    # If the query looks like a bare issue number and we got no cache hit,
    # fetch it directly from GitHub so already-linked or uncached issues work.
    if not orphans and q_lower.isdigit():
        try:
            from modules.integrations.github.client import GitHubClient
            client = GitHubClient(connection)
            issue = client.get_issue(connection.external_repo, int(q_lower))
            orphans = [{
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "html_url": issue.get("html_url", ""),
            }]
        except Exception:
            pass

    return render_template(
        "github/desktop/partials/_palette_orphan_results.html",
        orphans=orphans[:10],
    )
