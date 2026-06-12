# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Tasks controller — views and CRUD routes."""

import json
import logging
from urllib.parse import urlencode, urlsplit

logger = logging.getLogger(__name__)

from flask import abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from modules.base.core.models.workspace_user import WorkspaceUser
from system.i18n.translation import translate as _

from system.device.template import render_device_template

from . import blueprint
from ..models.task import Task, get_tier_defaults, get_workflow_statuses, get_done_status_code
from ..models.task_log import TaskLog
from ..models.canned_task import CannedTask, MAX_CANNED_TASKS


def _get_member():
    """Get current user's WorkspaceUser record or abort 403."""
    from modules.base.core.models.workspace_user import WorkspaceUser
    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)
    return member


def _get_all_members():
    """Get all active workspace members for the assignee picker."""
    from modules.base.core.models.workspace_user import EmployeeStatus
    return (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(status=EmployeeStatus.ACTIVE)
        .order_by(WorkspaceUser.id)
        .all()
    )


def _bind_pending_refs(item_ids: list[int]) -> None:
    """Rebind IntegrationRef rows with object_id=0 to the real task ID.

    Called after creation to resolve the object_id=0 placeholder written by
    the # trigger in the create modal (before the item had a real ID).
    Also writes the sparQ backlink into each bound GitHub issue.

    Since each issue can only link to one task, only the first item_id is used.

    Args:
        item_ids: List of newly created ActionItem primary keys.
    """
    if not item_ids:
        return
    try:
        from datetime import datetime, timedelta
        from flask import session
        from system.db.database import db
        from modules.integrations.models.integration_ref import IntegrationRef

        task_id = item_ids[0]

        # Prefer session-tracked ref IDs (set by github_create_ref when object_id=0).
        # This handles cases where the issue was previously linked to another task,
        # so object_id is already non-zero and the fallback filter would miss it.
        pending_ids = list(session.pop("pending_gh_ref_ids", []))
        if pending_ids:
            pending = IntegrationRef.query.filter(IntegrationRef.id.in_(pending_ids)).all()
        else:
            # Fallback: find fresh refs created in the last 30 s with object_id=0.
            cutoff = datetime.utcnow() - timedelta(seconds=30)
            pending = (
                IntegrationRef.scoped()
                .filter_by(object_type="task", object_id=0)
                .filter(IntegrationRef.created_at >= cutoff)
                .all()
            )

        if not pending:
            return

        for ref in pending:
            ref.object_id = task_id
            ref.linked_task_id = task_id

        db.session.commit()

        # Write backlink into each bound GitHub issue now that we have the real task ID.
        _write_backlinks_for_refs(pending, task_id)
    except Exception:
        pass  # Non-fatal: chips won't render on first load but webhooks will fix state


def _write_backlinks_for_refs(refs, task_id: int) -> None:
    """Write sparQ backlink into GitHub issues that were just bound to a task."""
    try:
        from flask import url_for as _url_for
        from modules.integrations.models.integration_connection import IntegrationConnection
        from modules.base.tasks.models.task import Task

        try:
            from modules.integrations.github.client import GitHubClient
            from modules.integrations.github.sync import inject_backlink
            _GITHUB_AVAILABLE = True
        except ImportError:
            _GITHUB_AVAILABLE = False

        if not _GITHUB_AVAILABLE:
            return

        task = Task.query.filter_by(id=task_id).first()
        if not task:
            print(f"[backlink] _bind: task_id={task_id} not found")
            return
        task_url = _url_for("tasks_bp.detail", item_id=task_id, _external=True)
        print(f"[backlink] _bind: task_url={task_url!r} title={task.title!r}")

        connection = IntegrationConnection.get_active("github")
        if not connection:
            print("[backlink] _bind: no active GitHub connection")
            return
        client = GitHubClient(connection)

        for ref in refs:
            if ref.provider != "github" or not ref.external_id or not ref.external_repo:
                continue
            try:
                raw = client.get_issue(ref.external_repo, int(ref.external_id))
                current_body = raw.get("body") or ""
                new_body = inject_backlink(current_body, task.title, task_url)
                if new_body != current_body:
                    client.update_issue_body(ref.external_repo, int(ref.external_id), new_body)
                    print(f"[backlink] _bind: PATCHED issue #{ref.external_id} for task={task_id}")
                else:
                    print(f"[backlink] _bind: body unchanged for issue #{ref.external_id}")
            except Exception as exc:
                import traceback
                print(f"[backlink] _bind: FAILED issue #{ref.external_id}: {exc}")
                traceback.print_exc()
    except Exception as exc:
        import traceback
        print(f"[backlink] _bind: outer error: {exc}")
        traceback.print_exc()


def _handle_deferred_integrations(task, form) -> None:
    """Submit deferred integration actions to a background thread.

    Captures request-context values (task URL) before handing off, then fires
    and forgets via submit_task so the HTTP response is not blocked by provider
    API calls (GitHub issue creation etc.).
    """
    raw = (form.get("integration_actions") or "").strip()
    if not raw:
        return
    try:
        import json
        actions = json.loads(raw)
    except Exception:
        logger.warning("_handle_deferred_integrations: invalid JSON in integration_actions")
        return
    if not actions:
        return

    # Capture the task URL while still in request context; providers need it
    # for backlink writing but url_for(_external=True) won't work in a thread.
    try:
        from flask import url_for as _uf
        task_url = _uf("tasks_bp.detail", item_id=task.id, _external=True)
    except Exception:
        task_url = ""

    from system.background import submit_task
    submit_task(_dispatch_deferred_integrations, task.id, actions, task_url)


def _dispatch_deferred_integrations(task_id: int, actions: dict, task_url: str) -> None:
    """Background: load the task and call each provider's handle_deferred_action."""
    from modules.base.tasks.models.task import Task as _Task
    from modules.integrations.registry import get as _get_provider

    task = _Task.query.filter_by(id=task_id).first()
    if not task:
        return

    for provider_name, action in actions.items():
        provider_cls = _get_provider(provider_name)
        if provider_cls:
            try:
                # Inject the pre-computed URL so providers don't need url_for.
                action_with_url = dict(action, _sparq_task_url=task_url)
                provider_cls().handle_deferred_action(task, action_with_url)
            except Exception as exc:
                logger.error(
                    "_dispatch_deferred_integrations: %s raised: %s", provider_name, exc, exc_info=True
                )


def _get_github_context() -> tuple[bool, str]:
    """Return (github_connected, github_repo) for template context.

    Returns:
        Tuple of (bool, str). False/"" when integrations module unavailable.
    """
    try:
        from modules.integrations.models.integration_connection import IntegrationConnection
        conn = IntegrationConnection.get_active("github")
        return conn is not None, (conn.external_repo if conn else "")
    except Exception:
        return False, ""




# ── API ───────────────────────────────────────────────────────────────────

@blueprint.route("/api/mine")
@login_required
def api_mine():
    """Return current user's actionable items as JSON for sync post references.

    Returns open items (todo + in_progress) plus items resolved today.
    """
    from datetime import datetime

    member = _get_member()
    open_items = Task.get_mine_open(member.id)

    # Items resolved today — exclude auto-resolved check-in items (posting the
    # status update is itself what resolves them, so they'd pre-fill the EOD
    # "shipped" list with redundant "completed your status update" entries).
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    resolved_today = (
        Task.scoped()
        .options(joinedload(Task.project))
        .filter(
            Task.assignee_id == member.id,
            Task.status == "resolved",
            Task.resolved_at >= today_start,
            or_(Task.source_type.is_(None), Task.source_type.notin_(["missed_checkin", "missed_periodic"])),
        )
        .order_by(Task.resolved_at.desc())
        .all()
    )

    def _serialize(item):
        result = {
            "id": item.id,
            "title": item.title,
            "urgency_tier": item.urgency_tier,
            "tier_color": item.tier_color(),
            "workflow_status": item.workflow_status,
            "status": item.status,
            "is_blocker": getattr(item, 'is_blocker', False),
            "project_id": item.project_id,
        }
        if item.project:
            result["project_name"] = item.project.name[:20]
        return result

    return jsonify({
        "open": [_serialize(i) for i in open_items if i.workflow_status != get_done_status_code()],
        "resolved_today": [_serialize(i) for i in resolved_today],
    })


@blueprint.route("/api/search")
@login_required
def api_search():
    """Search action items for autocomplete in structured list fields.

    Query params:
        q: Search text (ILIKE match on title)
        project_id: Optional project filter
    """
    _get_member()
    q = request.args.get("q", "").strip()
    project_id = request.args.get("project_id", type=int)

    if not q or len(q) < 2:
        return jsonify({"results": []})

    query = Task.scoped().options(
        joinedload(Task.project),
    ).filter(
        Task.status == "open",
        Task.raised_by_id.isnot(None),
        Task.title.ilike(f"%{q}%"),
    )
    if project_id:
        query = query.filter(Task.project_id == project_id)

    results = query.order_by(Task.created_at.desc()).limit(10).all()

    return jsonify({
        "results": [
            {
                "id": item.id,
                "title": item.title,
                "urgency_tier": item.urgency_tier,
                "tier_color": item.tier_color(),
                "workflow_status": item.workflow_status,
                "project_id": item.project_id,
                "project_name": item.project.name[:20] if item.project else None,
            }
            for item in results
        ]
    })


@blueprint.route("/api/suggestions")
@login_required
def api_suggestions():
    """Return action item suggestions for the status update pill bar.

    Delegates to Task.suggestions_for — see model for full priority logic.

    Returns:
        JSON with a ``suggestions`` list of serialized action items.
    """
    member = _get_member()
    items = Task.suggestions_for(member.id)

    return jsonify({
        "suggestions": [
            {
                "id": item.id,
                "title": item.title,
                "urgency_tier": item.urgency_tier,
                "tier_color": item.tier_color(),
                "project_id": item.project_id,
                "project_name": item.project.name[:20] if item.project else None,
            }
            for item in items
        ]
    })


# ── Preview ──────────────────────────────────────────────────────────────

@blueprint.route("/markdown-preview", methods=["POST"])
@login_required
def markdown_preview() -> str:
    """Render markdown text as HTML fragment for HTMX preview."""
    from system.startup.templates import simple_markdown

    text = request.form.get("text", "")
    return simple_markdown(text)


# ── Views ─────────────────────────────────────────────────────────────────

@blueprint.route("/")
@login_required
def index():
    """My Tasks — default view, grouped by tier."""
    from ..queries.mine import get_mine_closed, get_mine_open

    member = _get_member()

    items = get_mine_open(member.id, g.organization_id, g.workspace_id)
    closed_items = get_mine_closed(member.id, g.organization_id, g.workspace_id)

    tier_groups: dict[int, list] = {1: [], 2: [], 3: []}
    for item in items:
        tier_groups.setdefault(item.urgency_tier, []).append(item)

    github_connected, _ = _get_github_context()
    return render_device_template(
        "tasks/desktop/mine.html",
        tier_groups=tier_groups,
        closed_items=closed_items,
        tier_defaults=get_tier_defaults(),
        github_connected=github_connected,
        active_page="mine",
    )


@blueprint.route("/raised")
@login_required
def raised():
    """Raised by Me — items I've raised, with broadcast aggregation."""
    from ..queries.raised import get_raised_closed, get_raised_open

    member = _get_member()
    open_items = get_raised_open(member.id, g.organization_id, g.workspace_id)
    closed_items = get_raised_closed(member.id, g.organization_id, g.workspace_id)

    # Group open items by tier
    open_by_tier: dict[int, list] = {1: [], 2: [], 3: []}
    for item in open_items:
        open_by_tier.setdefault(item.urgency_tier, []).append(item)

    # Aggregate broadcast groups
    broadcast_groups: dict[str, dict] = {}
    for item in list(open_items) + list(closed_items):
        if item.broadcast_group_id:
            gid = str(item.broadcast_group_id)
            if gid not in broadcast_groups:
                broadcast_groups[gid] = Task.get_broadcast_summary(item.broadcast_group_id)

    github_connected, _ = _get_github_context()
    return render_device_template(
        "tasks/desktop/raised.html",
        open_by_tier=open_by_tier,
        closed_items=closed_items,
        broadcast_groups=broadcast_groups,
        tier_defaults=get_tier_defaults(),
        github_connected=github_connected,
        active_page="raised",
    )


@blueprint.route("/team")
@login_required
def team():
    """Team view — all open items grouped by assignee."""
    items = Task.get_team_open()

    # Group by assignee
    assignee_groups = {}
    for item in items:
        aid = item.assignee_id
        if aid not in assignee_groups:
            assignee_groups[aid] = {"member": item.assignee, "items": []}
        assignee_groups[aid]["items"].append(item)

    github_connected, _ = _get_github_context()
    return render_device_template(
        "tasks/desktop/team.html",
        assignee_groups=assignee_groups,
        tier_defaults=get_tier_defaults(),
        github_connected=github_connected,
        active_page="team",
    )


def _load_filter_pref(default_member_id: int) -> dict:
    """Load the saved Overview filter pill state for the current user.

    Falls back to selecting the current member's own pill when nothing has
    been saved yet, mirroring the client-side default logic.

    Args:
        default_member_id: The current member's ID, used as the fallback
            selectedMembers value on first visit.

    Returns:
        dict with keys selectedMembers (list[int]), raisedByMe (bool),
        showUnassigned (bool).
    """
    from modules.base.core.models.user_setting import UserSetting

    raw = UserSetting.get(current_user.id, _filter_pref_key())
    if raw:
        try:
            parsed = json.loads(raw)
            return {
                "selectedMembers": [
                    int(x)
                    for x in parsed.get("selectedMembers", [])
                    if isinstance(x, (int, str)) and str(x).isdigit()
                ],
                "raisedByMe": bool(parsed.get("raisedByMe", False)),
                "showUnassigned": bool(parsed.get("showUnassigned", False)),
            }
        except (ValueError, TypeError):
            pass
    return {
        "selectedMembers": [default_member_id] if default_member_id else [],
        "raisedByMe": False,
        "showUnassigned": False,
    }


@blueprint.route("/blockers")
@login_required
def blockers():
    """Blockers — all open action items marked as blockers."""
    member = _get_member()
    items = Task.get_open_blockers()
    resolved = Task.get_resolved_blockers(limit=20)
    github_connected, _ = _get_github_context()
    return render_device_template(
        "tasks/desktop/blockers.html",
        items=items,
        resolved=resolved,
        current_member_id=member.id,
        github_connected=github_connected,
        active_page="blockers",
    )


@blueprint.route("/board")
@login_required
def board():
    """Team Board — company-wide dashboard with stats, per-person cards, and filtered list/kanban."""
    from collections import defaultdict

    member = _get_member()
    members = _get_all_members()
    all_items = Task.get_team_all()
    workflow_statuses = get_workflow_statuses()

    # Split system vs human-raised items
    human_items = [i for i in all_items if not i.is_system_raised]
    system_count = len(all_items) - len(human_items)

    # Group human items by workflow status
    workflow_groups = defaultdict(list)
    for item in human_items:
        workflow_groups[item.workflow_status].append(item)

    # Done column: most recently updated first
    if workflow_groups["done"]:
        from datetime import datetime
        workflow_groups["done"].sort(
            key=lambda i: i.updated_at or datetime.min, reverse=True
        )

    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "tasks/desktop/board.html",
        members=members,
        human_items=human_items,
        system_count=system_count,
        workflow_statuses=workflow_statuses,
        workflow_groups=workflow_groups,
        tier_defaults=get_tier_defaults(),
        current_member_id=member.id,
        initial_filter_pref=_load_filter_pref(member.id),
        initial_view_pref=_load_view_pref(),
        github_connected=github_connected,
        github_repo=github_repo,
        active_page="board",
    )


FILTER_PREF_KEY_PREFIX = "overview_filter_pill"


def _filter_pref_key() -> str:
    """Per-workspace key for the Overview filter pill state.

    The user_setting unique constraint is (user_id, key) — it ignores
    workspace_id — so the workspace must live in the key itself for users
    who belong to more than one workspace.
    """
    workspace_id = getattr(g, "workspace_id", None) or 0
    return f"{FILTER_PREF_KEY_PREFIX}:{workspace_id}"


@blueprint.route("/board/filter-pref", methods=["GET"])
@login_required
def get_board_filter_pref():
    """Return the current user's saved Overview filter pill state.

    Returns:
        JSON: {"selectedMembers": list[int], "raisedByMe": bool, "showUnassigned": bool}
        Empty defaults when nothing has been saved yet.
    """
    from modules.base.core.models.user_setting import UserSetting

    raw = UserSetting.get(current_user.id, _filter_pref_key())
    default = {"selectedMembers": [], "raisedByMe": False, "showUnassigned": False}
    if not raw:
        return jsonify(default)
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return jsonify(default)
    return jsonify({
        "selectedMembers": [int(x) for x in parsed.get("selectedMembers", []) if isinstance(x, (int, str)) and str(x).isdigit()],
        "raisedByMe": bool(parsed.get("raisedByMe", False)),
        "showUnassigned": bool(parsed.get("showUnassigned", False)),
    })


@blueprint.route("/board/filter-pref", methods=["POST"])
@login_required
def set_board_filter_pref():
    """Persist the current user's Overview filter pill state."""
    from modules.base.core.models.user_setting import UserSetting

    payload = request.get_json(silent=True) or {}
    sanitized = {
        "selectedMembers": [int(x) for x in payload.get("selectedMembers") or [] if isinstance(x, (int, str)) and str(x).isdigit()],
        "raisedByMe": bool(payload.get("raisedByMe", False)),
        "showUnassigned": bool(payload.get("showUnassigned", False)),
    }
    UserSetting.set(current_user.id, _filter_pref_key(), json.dumps(sanitized))
    return jsonify({"ok": True})


TASK_VIEW_PREF_KEY_PREFIX = "board_view_mode"


def _view_pref_key() -> str:
    workspace_id = getattr(g, "workspace_id", None) or 0
    return f"{TASK_VIEW_PREF_KEY_PREFIX}:{workspace_id}"


def _load_view_pref() -> str:
    """Load the saved board view mode for the current user.

    Returns:
        "list" or "board", defaults to "list".
    """
    from modules.base.core.models.user_setting import UserSetting

    raw = UserSetting.get(current_user.id, _view_pref_key())
    if raw in ("list", "board"):
        return raw
    return "list"


@blueprint.route("/board/view-pref", methods=["POST"])
@login_required
def set_board_view_pref():
    """Persist the current user's board view mode (list or board)."""
    from modules.base.core.models.user_setting import UserSetting

    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode", "")
    if mode not in ("list", "board"):
        return jsonify({"ok": False}), 400
    UserSetting.set(current_user.id, _view_pref_key(), mode)
    return jsonify({"ok": True})


@blueprint.route("/unassigned")
@login_required
def unassigned():
    """Unassigned Tasks — open and closed items with no assignee."""
    data = Task.get_unassigned()

    tier_groups = {1: [], 2: [], 3: []}
    for item in data["open"]:
        tier_groups.setdefault(item.urgency_tier, []).append(item)

    github_connected, _ = _get_github_context()
    return render_device_template(
        "tasks/desktop/unassigned.html",
        tier_groups=tier_groups,
        closed_items=data["closed"],
        tier_defaults=get_tier_defaults(),
        github_connected=github_connected,
        active_page="unassigned",
    )


@blueprint.route("/<int:item_id>")
@login_required
def detail(item_id):
    """Detail view for a single Task."""
    from sqlalchemy.orm import selectinload

    member = _get_member()
    item = (
        Task.scoped()
        .options(
            joinedload(Task.assignee).joinedload(WorkspaceUser.user),
            joinedload(Task.raised_by).joinedload(WorkspaceUser.user),
            joinedload(Task.resolved_by).joinedload(WorkspaceUser.user),
            joinedload(Task.project),
            joinedload(Task.area),
            selectinload(Task.watchers).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        abort(404)

    SYSTEM_EVENT_TYPES = {'nudge_sent', 'escalation_sent'}
    logs = [entry for entry in TaskLog.get_for_item(item_id) if entry.event_type not in SYSTEM_EVENT_TYPES]

    from ..models.task_comment import TaskComment
    from ..models.task_comment_like import TaskCommentLike
    comments = TaskComment.get_for_item(item_id)
    comment_ids = [c.id for c in comments]
    like_data = TaskCommentLike.get_like_data(comment_ids, member.id)

    # Check if current user is raiser, assignee, or admin
    is_assignee = item.assignee_id == member.id
    is_raiser = item.raised_by_id == member.id
    is_admin = current_user.is_admin

    # Linked blocker display (SyncBlocker table has been dropped)
    linked_blocker = None

    is_unassigned = item.assignee_id is None

    post_now_url = item.post_now_url

    back_url = request.args.get("back_url") or url_for("tasks_bp.index")
    referrer = request.referrer
    if not request.args.get("back_url") and referrer:
        ref = urlsplit(referrer)
        if (
            ref.netloc == request.host
            and ref.path != request.path
            and not ref.path.endswith("/edit")
        ):
            back_url = ref.path
            if ref.query:
                back_url += "?" + ref.query

    github_connected, github_repo = _get_github_context()

    gh_ref = None
    if github_connected:
        from modules.integrations.models.integration_ref import IntegrationRef
        from sqlalchemy.orm import joinedload as _jl
        gh_ref = (
            IntegrationRef.scoped()
            .options(_jl(IntegrationRef.linked_task))
            .filter_by(provider="github", linked_task_id=item.id)
            .first()
        )

    from datetime import date as _date

    can_inline_edit = (
        (is_raiser or is_admin)
        and not item.is_system_raised
        and item.status == "open"
    )

    return render_device_template(
        "tasks/desktop/detail.html",
        item=item,
        logs=logs,
        comments=comments,
        like_data=like_data,
        current_member=member,
        is_assignee=is_assignee,
        is_raiser=is_raiser,
        is_admin=is_admin,
        is_unassigned=is_unassigned,
        linked_blocker=linked_blocker,
        tier_defaults=get_tier_defaults(),
        workflow_statuses=get_workflow_statuses(),
        watchers=item.watchers,
        post_now_url=post_now_url,
        back_url=back_url,
        github_connected=github_connected,
        github_repo=github_repo,
        gh_ref=gh_ref,
        can_inline_edit=can_inline_edit,
        today=_date.today(),
        active_page="detail",
    )


# ── Edit ──────────────────────────────────────────────────────────────────

@blueprint.route("/<int:item_id>/edit")
@login_required
def edit(item_id):
    """Edit action item form (raiser or admin only, open items only)."""
    member = _get_member()
    item = (
        Task.scoped()
        .options(
            joinedload(Task.assignee).joinedload(WorkspaceUser.user),
            joinedload(Task.raised_by).joinedload(WorkspaceUser.user),
            joinedload(Task.project),
            joinedload(Task.area),
            selectinload(Task.watchers).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        abort(404)

    is_raiser = item.raised_by_id == member.id
    is_admin = current_user.is_admin
    if not (is_raiser or is_admin):
        abort(403)
    if item.status != "open":
        abort(403)

    list_url = request.args.get("back_url", "")

    members = _get_all_members()

    # Load areas for dropdown
    areas = []
    try:
        from modules.base.updates.models.area import UpdateArea
        areas = UpdateArea.get_all()
    except Exception:
        pass

    # Load projects for dropdown (exclude on-hold projects)
    projects = []
    try:
        from modules.base.projects.models.project import Project
        projects = [
            p for p in Project.get_active_for_workspace()
            if p.status != Project.STATUS_ON_HOLD
        ]
    except Exception:
        pass

    current_watcher_ids = [w.id for w in item.watchers]

    # Eligible watchers: exclude raiser and sample users
    eligible_watchers = [
        m for m in members
        if m.id != item.raised_by_id and m.user and not m.user.is_sample
    ]

    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "tasks/desktop/edit.html",
        item=item,
        members=members,
        eligible_watchers=eligible_watchers,
        tier_defaults=get_tier_defaults(),
        workflow_statuses=get_workflow_statuses(),
        projects=projects,
        areas=areas,
        current_watcher_ids=current_watcher_ids,
        list_url=list_url,
        github_connected=github_connected,
        github_repo=github_repo,
        active_page="detail",
    )


@blueprint.route("/<int:item_id>/edit", methods=["POST"])
@login_required
def update(item_id):
    """Update a task (raiser or admin only, open items only)."""
    from sqlalchemy.orm import selectinload

    from system.db.database import db

    member = _get_member()
    item = Task.scoped().options(
        selectinload(Task.watchers),
    ).filter_by(id=item_id).first()
    if not item:
        abort(404)

    is_raiser = item.raised_by_id == member.id
    is_admin = current_user.is_admin
    if not (is_raiser or is_admin):
        abort(403)
    if item.status != "open":
        abort(403)

    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    try:
        urgency_tier = max(1, min(3, int(request.form.get("urgency_tier", "2"))))
    except (ValueError, TypeError):
        urgency_tier = item.urgency_tier

    assignee_id = request.form.get("assignee_id", type=int) or item.assignee_id
    context_note = request.form.get("context_note", "").strip() or None
    project_id = request.form.get("project_id", type=int) or None
    area_id = request.form.get("area_id", type=int) or None

    due_date = None
    due_date_str = request.form.get("due_date", "").strip()
    if due_date_str:
        try:
            from datetime import date
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            pass

    # Workflow status
    workflow_status = request.form.get("workflow_status", "").strip()
    valid_ws_keys = {s["key"] for s in get_workflow_statuses()}
    if workflow_status not in valid_ws_keys:
        workflow_status = item.workflow_status

    old_workflow_status = item.workflow_status

    item.title = title[:200]
    item.urgency_tier = urgency_tier
    item.assignee_id = assignee_id
    item.context_note = context_note
    item.project_id = project_id
    item.area_id = area_id
    item.due_date = due_date
    item.workflow_status = workflow_status

    done_code = get_done_status_code()
    # If moved to done status via edit, resolve the item
    if workflow_status == done_code and item.status == "open":
        from datetime import datetime
        item.status = "resolved"
        item.resolved_at = datetime.utcnow()
        item.resolved_by_id = member.id
    # If moved out of done status, reopen the item
    elif workflow_status != done_code and item.status in ("resolved", "dismissed"):
        item.status = "open"
        item.resolved_at = None
        item.resolved_by_id = None
        item.resolution_note = None

    db.session.commit()

    if workflow_status == done_code and old_workflow_status != done_code:
        Task._notify_project_followers_resolved(item)

    # Update watchers
    watcher_ids = request.form.getlist("watcher_ids", type=int)
    item.set_watchers(watcher_ids)

    from ..models.task_log import TaskLog
    TaskLog.log(item.id, "edited", member.id)

    next_url = request.form.get("next", "")
    detail_url = url_for("tasks_bp.detail", item_id=item_id)
    if next_url:
        detail_url += "?" + urlencode({"back_url": next_url})
    return redirect(detail_url)


# ── Inline Editing ────────────────────────────────────────────────────────


def _load_inline_task(item_id):
    """Load a task with eager joins needed for inline edit partials.

    Returns:
        Tuple of (task, member) or aborts with 404/403.
    """
    member = _get_member()
    item = (
        Task.scoped()
        .options(
            joinedload(Task.assignee).joinedload(WorkspaceUser.user),
            joinedload(Task.raised_by).joinedload(WorkspaceUser.user),
            joinedload(Task.area),
            selectinload(Task.watchers).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=item_id)
        .first()
    )
    if not item:
        abort(404)
    return item, member


def _check_inline_edit_permission(item, member):
    """Abort 403 if the current user cannot inline-edit this task."""
    is_raiser = item.raised_by_id == member.id
    is_admin = current_user.is_admin
    if not (is_raiser or is_admin):
        abort(403)
    if item.is_system_raised:
        abort(403)
    if item.status != "open":
        abort(403)


def _inline_display_context(item, member):
    """Build the shared template context for inline display partials."""
    from datetime import date

    is_raiser = item.raised_by_id == member.id
    is_admin = current_user.is_admin
    can_inline_edit = (
        (is_raiser or is_admin)
        and not item.is_system_raised
        and item.status == "open"
    )

    github_connected, _ = _get_github_context()

    return {
        "item": item,
        "can_inline_edit": can_inline_edit,
        "tier_defaults": get_tier_defaults(),
        "watchers": item.watchers,
        "today": date.today(),
        "github_connected": github_connected,
    }


# ── Inline: Title ──


@blueprint.route("/<int:item_id>/inline/title")
@login_required
def inline_edit_title(item_id):
    """Return the inline title edit form partial."""
    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)
    return render_template(
        "tasks/desktop/partials/_inline_title_edit.html",
        item=item,
    )


@blueprint.route("/<int:item_id>/inline/title", methods=["POST"])
@login_required
def inline_save_title(item_id):
    """Save inline title edit, return display partial."""
    from system.db.database import db

    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)

    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    item.title = title[:200]
    db.session.commit()

    TaskLog.log(item.id, "edited", member.id, "Title updated")

    return render_template(
        "tasks/desktop/partials/_inline_title_display.html",
        **_inline_display_context(item, member),
    )


@blueprint.route("/<int:item_id>/inline/title/display")
@login_required
def inline_display_title(item_id):
    """Return the title display partial (for cancel)."""
    item, member = _load_inline_task(item_id)
    return render_template(
        "tasks/desktop/partials/_inline_title_display.html",
        **_inline_display_context(item, member),
    )


# ── Inline: Description ──


@blueprint.route("/<int:item_id>/inline/description")
@login_required
def inline_edit_description(item_id):
    """Return the inline description edit form partial."""
    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)
    return render_template(
        "tasks/desktop/partials/_inline_description_edit.html",
        item=item,
    )


@blueprint.route("/<int:item_id>/inline/description", methods=["POST"])
@login_required
def inline_save_description(item_id):
    """Save inline description edit, return display partial."""
    from system.db.database import db

    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)

    context_note = request.form.get("context_note", "").strip() or None
    item.context_note = context_note
    db.session.commit()

    TaskLog.log(item.id, "edited", member.id, "Description updated")

    return render_template(
        "tasks/desktop/partials/_inline_description_display.html",
        **_inline_display_context(item, member),
    )


@blueprint.route("/<int:item_id>/inline/description/display")
@login_required
def inline_display_description(item_id):
    """Return the description display partial (for cancel)."""
    item, member = _load_inline_task(item_id)
    return render_template(
        "tasks/desktop/partials/_inline_description_display.html",
        **_inline_display_context(item, member),
    )


# ── Inline: Per-Property ──

_PROP_TEMPLATES = {
    "assignee": "_inline_prop_assignee_edit.html",
    "urgency": "_inline_prop_urgency_edit.html",
    "due_date": "_inline_prop_due_date_edit.html",
    "area": "_inline_prop_area_edit.html",
}


def _prop_display_partial(prop, item, member):
    """Render a single property row display partial."""
    ctx = _inline_display_context(item, member)
    partials = {
        "assignee": "tasks/desktop/partials/_inline_prop_assignee_display.html",
        "urgency": "tasks/desktop/partials/_inline_prop_urgency_display.html",
        "due_date": "tasks/desktop/partials/_inline_prop_due_date_display.html",
        "area": "tasks/desktop/partials/_inline_prop_area_display.html",
    }
    return render_template(partials[prop], **ctx)


@blueprint.route("/<int:item_id>/inline/prop/<prop>")
@login_required
def inline_edit_prop(item_id, prop):
    """Return the inline edit form for a single property."""
    if prop not in _PROP_TEMPLATES:
        abort(404)

    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)

    ctx = {"item": item, "tier_defaults": get_tier_defaults()}

    if prop == "assignee":
        ctx["members"] = _get_all_members()
    elif prop == "area":
        areas = []
        try:
            from modules.base.updates.models.area import UpdateArea
            areas = UpdateArea.get_all()
        except Exception:
            pass
        ctx["areas"] = areas

    return render_template(
        f"tasks/desktop/partials/{_PROP_TEMPLATES[prop]}",
        **ctx,
    )


@blueprint.route("/<int:item_id>/inline/prop/<prop>", methods=["POST"])
@login_required
def inline_save_prop(item_id, prop):
    """Save a single property inline edit, return the display partial."""
    from system.db.database import db

    if prop not in _PROP_TEMPLATES:
        abort(404)

    item, member = _load_inline_task(item_id)
    _check_inline_edit_permission(item, member)

    if prop == "assignee":
        item.assignee_id = request.form.get("assignee_id", type=int) or None
    elif prop == "urgency":
        try:
            item.urgency_tier = max(1, min(3, int(request.form.get("urgency_tier", "2"))))
        except (ValueError, TypeError):
            pass
    elif prop == "due_date":
        due_date_str = request.form.get("due_date", "").strip()
        if due_date_str:
            try:
                from datetime import date
                item.due_date = date.fromisoformat(due_date_str)
            except ValueError:
                pass
        else:
            item.due_date = None
    elif prop == "area":
        item.area_id = request.form.get("area_id", type=int) or None

    db.session.commit()

    TaskLog.log(item.id, "edited", member.id)

    item, member = _load_inline_task(item_id)
    return _prop_display_partial(prop, item, member)


@blueprint.route("/<int:item_id>/inline/prop/<prop>/display")
@login_required
def inline_display_prop(item_id, prop):
    """Return a single property display partial (for cancel)."""
    if prop not in _PROP_TEMPLATES:
        abort(404)

    item, member = _load_inline_task(item_id)
    return _prop_display_partial(prop, item, member)


# ── Creation ──────────────────────────────────────────────────────────────

@blueprint.route("/create-modal")
@login_required
def create_modal():
    """Return HTMX partial with the creation form modal."""
    member = _get_member()
    members = _get_all_members()
    canned_tasks = CannedTask.get_all()

    # Area dropdown data
    areas = []
    try:
        from modules.base.updates.models.area import UpdateArea
        areas = UpdateArea.get_all()
    except Exception:
        pass

    # Project dropdown data
    projects = []
    preselected_project_id = None
    last_project_id = None
    return_url = None
    try:
        from modules.base.projects.models.project import Project
        from flask import session

        url_project_id = request.args.get("project_id", type=int)
        all_active = Project.get_active_for_workspace()
        projects = [
            p for p in all_active
            if p.status != Project.STATUS_ON_HOLD or p.id == url_project_id
        ]
        last_project_id = session.get("last_project_id")

        # Rule 1: URL context
        if url_project_id:
            preselected_project_id = url_project_id
            return_url = url_for("projects_bp.detail", project_id=url_project_id)
        # Rule 2: Last used
        elif last_project_id and any(p.id == last_project_id for p in projects):
            preselected_project_id = last_project_id
        # Rule 3: Only one active project
        elif len(projects) == 1:
            preselected_project_id = projects[0].id
    except Exception:
        pass

    # Eligible watchers: exclude current user and sample users
    eligible_watchers = [
        m for m in members
        if m.id != member.id and m.user and not m.user.is_sample
    ]

    default_is_blocker = request.args.get("is_blocker", "0") == "1"
    if not return_url:
        next_arg = request.args.get("next", "")
        if next_arg and next_arg.startswith("/") and not next_arg.startswith("//"):
            return_url = next_arg

    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "tasks/desktop/_create_modal.html",
        members=members,
        current_member=member,
        eligible_watchers=eligible_watchers,
        tier_defaults=get_tier_defaults(),
        canned_tasks=canned_tasks,
        projects=projects,
        preselected_project_id=preselected_project_id,
        last_project_id=last_project_id,
        return_url=return_url,
        areas=areas,
        default_is_blocker=default_is_blocker,
        github_connected=github_connected,
        github_repo=github_repo,
    )


@blueprint.route("/create", methods=["POST"])
@login_required
def create():
    """Create one or more Tasks from form submission."""
    member = _get_member()

    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    try:
        urgency_tier = int(request.form.get("urgency_tier", "2"))
    except (ValueError, TypeError):
        urgency_tier = 2
    context_note = request.form.get("context_note", "").strip() or None
    source_type = request.form.get("source_type") or None
    source_id = request.form.get("source_id", type=int) or None
    watcher_ids = request.form.getlist("watcher_ids", type=int)

    # Assignee handling: single, multi, all, or unassigned
    assign_mode = request.form.get("assign_mode", "single")
    assignee_ids = request.form.getlist("assignee_ids", type=int)
    single_assignee_id = request.form.get("assignee_id", type=int)

    if assign_mode == "unassigned":
        # No assignee — item is pickup-able by anyone
        assignee_ids = [None]
    elif assign_mode == "all":
        all_members = _get_all_members()
        assignee_ids = [m.id for m in all_members if m.id != member.id]
    elif assign_mode == "multi":
        if len(assignee_ids) == 1:
            # Single selection in multi mode — normalize to single assignment
            single_assignee_id = assignee_ids[0]
            assignee_ids = [single_assignee_id]
        elif not assignee_ids:
            abort(400)
    else:
        # Single assignee
        if not single_assignee_id:
            abort(400)
        assignee_ids = [single_assignee_id]

    if not assignee_ids:
        abort(400)

    # Save as canned action on-the-fly
    if request.form.get("save_as_canned"):
        CannedTask.create(title, default_tier=urgency_tier, created_by_id=member.id)

    # Due date
    due_date = None
    due_date_str = request.form.get("due_date", "").strip()
    if due_date_str:
        try:
            from datetime import date
            due_date = date.fromisoformat(due_date_str)
        except ValueError:
            pass

    # Area tagging
    area_id = request.form.get("area_id", type=int) or None

    # Project tagging
    project_id = request.form.get("project_id", type=int) or None
    if project_id:
        from flask import session
        session["last_project_id"] = project_id

    is_blocker = request.form.get("is_blocker") == "1"
    created_items = []

    if len(assignee_ids) == 1:
        item = Task.create(
            title=title,
            urgency_tier=urgency_tier,
            assignee_id=assignee_ids[0],
            raised_by_id=member.id,
            context_note=context_note,
            source_type=source_type,
            source_id=source_id,
            watcher_ids=watcher_ids or None,
            is_blocker=is_blocker,
        )
        if (project_id or due_date or area_id) and item:
            from system.db.database import db
            if project_id:
                item.project_id = project_id
            if due_date:
                item.due_date = due_date
            if area_id:
                item.area_id = area_id
            db.session.commit()
        if item:
            created_items.append(item)
    else:
        items = Task.create_broadcast(
            title=title,
            urgency_tier=urgency_tier,
            assignee_ids=assignee_ids,
            raised_by_id=member.id,
            context_note=context_note,
            source_type=source_type,
            source_id=source_id,
            watcher_ids=watcher_ids or None,
            is_blocker=is_blocker,
        )
        if (project_id or due_date or area_id) and items:
            from system.db.database import db
            for item in items:
                if project_id:
                    item.project_id = project_id
                if due_date:
                    item.due_date = due_date
                if area_id:
                    item.area_id = area_id
            db.session.commit()
        if items:
            created_items.extend(items)

    # Attach uploaded files to all created action items
    files = request.files.getlist("files")
    if created_items and files:
        from modules.base.resources.models.attachment import Attachment
        Attachment.create_from_uploads(
            files=files,
            entity_type="task",
            entity_ids=[item.id for item in created_items],
        )

    # Rebind any IntegrationRef rows with object_id=0 that were created by the
    # # trigger during this modal session (within the last 30 seconds).
    if created_items:
        _bind_pending_refs([item.id for item in created_items])
        if len(created_items) == 1:
            _handle_deferred_integrations(created_items[0], request.form)

    next_url = request.form.get("next", "").strip()
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("tasks_bp.board"))


# ── Workflow Status ───────────────────────────────────────────────────────

@blueprint.route("/<int:item_id>/workflow-status", methods=["POST"])
@login_required
def set_workflow_status(item_id):
    """Change the workflow status of a task (HTMX or form POST)."""
    from datetime import datetime
    from system.db.database import db

    member = _get_member()
    item = Task.scoped().filter_by(id=item_id).first()
    if not item:
        abort(404)

    new_ws = request.form.get("workflow_status", "").strip()
    valid_keys = {s["key"] for s in get_workflow_statuses()}
    if new_ws not in valid_keys:
        abort(400)

    old_ws = item.workflow_status
    if new_ws == old_ws:
        return redirect(request.referrer or url_for("tasks_bp.index"))

    item.workflow_status = new_ws

    done_code = get_done_status_code()
    # Sync lifecycle status with workflow status
    if new_ws == done_code and item.status == "open":
        item.status = "resolved"
        item.resolved_at = datetime.utcnow()
        item.resolved_by_id = member.id
        TaskLog.log(item.id, "resolved", member.id, "Moved to Done")
    elif new_ws != done_code and item.status in ("resolved", "dismissed"):
        item.status = "open"
        item.resolved_at = None
        item.resolved_by_id = None
        item.resolution_note = None
        TaskLog.log(item.id, "reopened", member.id, f"Moved to {new_ws}")

    db.session.commit()

    if new_ws == done_code and old_ws != done_code:
        from modules.base.dashboard.models.activity_log import ActivityLog
        ActivityLog.log(
            action="tasks.resolved",
            model_type="Task",
            record_id=item.id,
            member_id=member.id,
            title="Task completed",
            description=item.title[:100],
            icon="fa-check-circle",
            color="success",
            url=f"/tasks/{item.id}",
        )
        Task._notify_project_followers_resolved(item)

    if new_ws == "needs_review" and old_ws != "needs_review":
        Task._notify_project_owners_review(item)

    # AJAX / drag-and-drop: return 204 No Content
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return "", 204

    # Regular form POST / HTMX: redirect back
    next_url = request.referrer or url_for("tasks_bp.index")
    return redirect(next_url)


# ── State Transitions ─────────────────────────────────────────────────────

@blueprint.route("/<int:item_id>/resolve", methods=["POST"])
@login_required
def resolve(item_id):
    """Resolve a Task."""
    member = _get_member()
    item = Task.scoped().filter_by(id=item_id).first()
    if not item:
        abort(404)

    # Only assignee or admin can resolve (unassigned items must be claimed first)
    if item.assignee_id != member.id and not current_user.is_admin:
        abort(403)

    # System-generated items cannot be manually resolved
    if item.is_system_raised:
        abort(403)

    note = request.form.get("resolution_note", "").strip() or None
    result = Task.resolve(item_id, member.id, note)
    if not result:
        abort(404)

    next_url = request.form.get("next", "")
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("tasks_bp.index")
    return redirect(next_url)


@blueprint.route("/<int:item_id>/dismiss", methods=["POST"])
@login_required
def dismiss(item_id):
    """Dismiss a Task."""
    member = _get_member()
    item = Task.scoped().filter_by(id=item_id).first()
    if not item:
        abort(404)

    # Only assignee or admin can dismiss (unassigned items must be claimed first)
    if item.assignee_id != member.id and not current_user.is_admin:
        abort(403)

    result = Task.dismiss(item_id, member.id)
    if not result:
        abort(404)

    next_url = request.form.get("next", "")
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("tasks_bp.index")
    return redirect(next_url)


@blueprint.route("/<int:item_id>/cancel", methods=["POST"])
@login_required
def cancel(item_id):
    """Cancel a Task (raiser only)."""
    member = _get_member()
    result = Task.cancel(item_id, member.id)
    if not result:
        abort(404)

    next_url = request.form.get("next", "")
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("tasks_bp.board")
    return redirect(next_url)


@blueprint.route("/<int:item_id>/reopen", methods=["POST"])
@login_required
def reopen(item_id):
    """Reopen a resolved Task (raiser only, within 24hrs)."""
    member = _get_member()
    result = Task.reopen(item_id, member.id)
    if not result:
        abort(404)

    return redirect(url_for("tasks_bp.detail", item_id=item_id))


@blueprint.route("/<int:item_id>/claim", methods=["POST"])
@login_required
def claim(item_id):
    """Claim an unassigned Task — assign it to the current user."""
    from system.db.database import db

    member = _get_member()
    item = Task.scoped().filter_by(id=item_id, status="open").first()
    if not item:
        abort(404)

    if item.assignee_id is not None:
        abort(403)

    item.assignee_id = member.id
    db.session.commit()

    TaskLog.log(item.id, "claimed", member.id, "Assigned to self")

    next_url = request.form.get("next", "")
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("tasks_bp.detail", item_id=item_id)
    return redirect(next_url)


@blueprint.route("/<int:item_id>/snooze", methods=["POST"])
@login_required
def snooze(item_id):
    """Snooze a Tier 1 Task for 30 minutes (one-time)."""
    member = _get_member()
    result = Task.snooze(item_id, member.id)
    if not result:
        abort(404)

    next_url = request.form.get("next", "")
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        next_url = url_for("tasks_bp.index")
    return redirect(next_url)


# ── Comments ──────────────────────────────────────────────────────────────


def _render_comments(item, member):
    """Render the comments list partial with like data."""
    from ..models.task_comment import TaskComment
    from ..models.task_comment_like import TaskCommentLike

    comments = TaskComment.get_for_item(item.id)
    comment_ids = [c.id for c in comments]
    like_data = TaskCommentLike.get_like_data(comment_ids, member.id)
    return render_template(
        "tasks/desktop/partials/_comments_list.html",
        item=item,
        comments=comments,
        current_member=member,
        like_data=like_data,
    )


@blueprint.route("/<int:item_id>/comments", methods=["POST"])
@login_required
def create_comment(item_id):
    """Create a new comment on a task (HTMX partial return)."""
    from ..models.task_comment import TaskComment

    member = _get_member()
    item = Task.scoped().filter_by(id=item_id).first()
    if not item:
        abort(404)

    content = request.form.get("content", "").strip()
    if not content:
        abort(400)

    TaskComment.create(
        task_id=item_id,
        content=content,
        author_id=member.id,
        user_id=current_user.id,
    )

    return _render_comments(item, member)


@blueprint.route("/<int:item_id>/comments/<int:comment_id>", methods=["POST"])
@login_required
def update_comment(item_id, comment_id):
    """Update an existing comment (author only, HTMX partial return)."""
    from ..models.task_comment import TaskComment

    member = _get_member()
    comment = TaskComment.active().filter_by(
        id=comment_id, task_id=item_id
    ).first()
    if not comment:
        abort(404)

    if comment.author_id != member.id:
        abort(403)

    content = request.form.get("content", "").strip()
    if not content:
        abort(400)

    comment.update_content(content, current_user.id)

    item = Task.scoped().filter_by(id=item_id).first()
    return _render_comments(item, member)


@blueprint.route("/<int:item_id>/comments/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(item_id, comment_id):
    """Soft-delete a comment (author only, HTMX partial return)."""
    from ..models.task_comment import TaskComment

    member = _get_member()
    comment = TaskComment.active().filter_by(
        id=comment_id, task_id=item_id
    ).first()
    if not comment:
        abort(404)

    if comment.author_id != member.id:
        abort(403)

    comment.soft_delete(user_id=current_user.id)

    item = Task.scoped().filter_by(id=item_id).first()
    return _render_comments(item, member)


@blueprint.route("/<int:item_id>/comments/<int:comment_id>/like", methods=["POST"])
@login_required
def toggle_comment_like(item_id, comment_id):
    """Toggle a like on a comment (HTMX partial return)."""
    from ..models.task_comment import TaskComment
    from ..models.task_comment_like import TaskCommentLike

    member = _get_member()
    comment = TaskComment.active().filter_by(
        id=comment_id, task_id=item_id
    ).first()
    if not comment:
        abort(404)

    TaskCommentLike.toggle(comment_id=comment_id, member_id=member.id)

    item = Task.scoped().filter_by(id=item_id).first()
    return _render_comments(item, member)


@blueprint.route("/<int:item_id>/comments/<int:comment_id>/edit-form")
@login_required
def comment_edit_form(item_id, comment_id):
    """Return the inline edit form for a comment (HTMX partial)."""
    from ..models.task_comment import TaskComment

    member = _get_member()
    comment = TaskComment.active().filter_by(
        id=comment_id, task_id=item_id
    ).first()
    if not comment:
        abort(404)

    if comment.author_id != member.id:
        abort(403)

    return render_template(
        "tasks/desktop/partials/_comment_edit_form.html",
        item_id=item_id,
        comment=comment,
    )


# ── Canned Actions (on-the-fly) ─────────────────────────────────────────

@blueprint.route("/canned/save", methods=["POST"])
@login_required
def canned_save():
    """Save a canned action on-the-fly during creation."""
    member = _get_member()
    title = request.form.get("title", "").strip()
    default_tier = request.form.get("default_tier", type=int)
    if not title:
        abort(400)

    result = CannedTask.create(title, default_tier=default_tier, created_by_id=member.id)
    if not result:
        # At limit
        return jsonify({"error": "limit_reached", "max": MAX_CANNED_TASKS}), 422

    return jsonify({"id": result.id, "title": result.title, "default_tier": result.default_tier})


# ── Canned Actions (Settings CRUD) ──────────────────────────────────────

@blueprint.route("/settings")
@login_required
def settings():
    """Task settings — workflow statuses, urgency tiers, and canned actions."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus, MAX_TASK_STATUSES
    from system.db.database import db

    task_statuses = TaskStatus.get_for_workspace()
    if not task_statuses:
        TaskStatus.seed_defaults()
        db.session.commit()
        task_statuses = TaskStatus.get_for_workspace()

    actions = CannedTask.get_all()
    return render_device_template(
        "tasks/desktop/settings.html",
        canned_tasks=actions,
        max_canned=MAX_CANNED_TASKS,
        tier_defaults=get_tier_defaults(),
        task_statuses=task_statuses,
        max_task_statuses=MAX_TASK_STATUSES,
        active_page="tasks_settings",
        module_home="core_bp.settings",
    )


@blueprint.route("/settings/statuses/add", methods=["POST"])
@login_required
def settings_statuses_add():
    """Add a new workflow status for this workspace."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus

    ts, err = TaskStatus.add(
        label=request.form.get("label", "").strip(),
        code=request.form.get("code", "").strip().lower().replace(" ", "_"),
        color=request.form.get("color", "#6b7280").strip(),
        is_default=request.form.get("is_default") == "on",
    )
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status added."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/statuses/<int:status_id>/update", methods=["POST"])
@login_required
def settings_statuses_update(status_id):
    """Update label, color, is_done, or is_default for a workflow status."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus

    ok, err = TaskStatus.update(
        status_id,
        label=request.form.get("label", "").strip(),
        color=request.form.get("color", "#6b7280").strip(),
        is_done=request.form.get("is_done") == "on",
        is_default=request.form.get("is_default") == "on",
    )
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status updated."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/statuses/<int:status_id>/delete", methods=["POST"])
@login_required
def settings_statuses_delete(status_id):
    """Delete a workflow status."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus

    ok, err = TaskStatus.delete(status_id)
    if err:
        flash(_(err), "error")
    else:
        flash(_("Status deleted."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/statuses/<int:status_id>/set-default", methods=["POST"])
@login_required
def settings_statuses_set_default(status_id):
    """Set a workflow status as the default for new tasks."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus

    ok, err = TaskStatus.set_default(status_id)
    if err:
        flash(_(err), "error")
    else:
        flash(_("Default status updated."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/statuses/reorder", methods=["POST"])
@login_required
def settings_statuses_reorder():
    """Bulk-reorder workflow statuses via JSON body."""
    if not current_user.is_admin:
        abort(403)

    from ..models.task_status import TaskStatus

    data = request.get_json(silent=True) or []
    TaskStatus.bulk_reorder(data)
    return ("", 204)


@blueprint.route("/settings/tier-labels", methods=["POST"])
@login_required
def settings_tier_labels():
    """Save custom tier labels."""
    if not current_user.is_admin:
        abort(403)

    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from system.db.database import db

    settings = WorkspaceSettings.get_instance()
    labels = {}
    for t in [1, 2, 3]:
        label = request.form.get(f"tier_{t}", "").strip()
        if label:
            labels[str(t)] = label[:30]

    settings.tasks_tier_labels = labels if labels else None
    db.session.commit()

    flash(_("Tier labels updated."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/create", methods=["POST"])
@login_required
def settings_create():
    """Create a canned action from settings."""
    if not current_user.is_admin:
        abort(403)

    member = _get_member()
    title = request.form.get("title", "").strip()
    default_tier = request.form.get("default_tier", type=int) or None
    if not title:
        flash(_("Title is required."), "error")
        return redirect(url_for("tasks_bp.settings"))

    result = CannedTask.create(title, default_tier=default_tier, created_by_id=member.id)
    if not result:
        flash(_("Maximum of %(max)s canned actions reached.") % {"max": MAX_CANNED_TASKS}, "error")
    else:
        flash(_("Canned action created."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/<int:action_id>/edit", methods=["POST"])
@login_required
def settings_edit(action_id):
    """Edit a canned action from settings."""
    if not current_user.is_admin:
        abort(403)

    title = request.form.get("title", "").strip()
    default_tier = request.form.get("default_tier", type=int) or None
    result = CannedTask.update(action_id, title=title, default_tier=default_tier)

    if not result:
        flash(_("Canned action not found."), "error")
    else:
        flash(_("Canned action updated."), "success")
    return redirect(url_for("tasks_bp.settings"))


@blueprint.route("/settings/<int:action_id>/delete", methods=["POST"])
@login_required
def settings_delete(action_id):
    """Delete a canned action from settings."""
    if not current_user.is_admin:
        abort(403)

    if CannedTask.delete(action_id):
        flash(_("Canned action deleted."), "success")
    else:
        flash(_("Canned action not found."), "error")
    return redirect(url_for("tasks_bp.settings"))
