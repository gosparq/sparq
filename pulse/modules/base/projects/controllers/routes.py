# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Projects controller — views and CRUD routes."""

import json

from flask import abort, g, jsonify, redirect, request, session, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.device.template import render_device_template

from . import blueprint
from ..models.project import Project
from ..models.project_status import ProjectStatus


def _get_github_context() -> tuple[bool, str]:
    try:
        from modules.integrations.models.integration_connection import IntegrationConnection
        conn = IntegrationConnection.get_active("github")
        return conn is not None, (conn.external_repo if conn else '')
    except Exception:
        return False, ''


def _get_member():
    """Get current user's WorkspaceUser record or abort 403."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)
    return member


def _get_all_members():
    """Get all active workspace members."""
    from sqlalchemy.orm import joinedload

    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser

    return (
        WorkspaceUser.scoped()
        .options(joinedload(WorkspaceUser.user))
        .filter_by(status=EmployeeStatus.ACTIVE)
        .order_by(WorkspaceUser.id)
        .all()
    )


def _infer_project_id(projects):
    """Apply project selection inference rules 1-4.

    Returns preselected project_id or None.
    """
    # Rule 1: URL context
    url_project_id = request.args.get("project_id", type=int)
    if url_project_id:
        return url_project_id

    # Rule 2: Most recently used
    last_id = session.get("last_project_id")
    if last_id:
        # Verify it's still active
        for p in projects:
            if p.id == last_id:
                return last_id

    # Rule 3: Only one active project
    if len(projects) == 1:
        return projects[0].id

    # Rule 4: No preselection
    return None


def _get_workspace_statuses() -> tuple[list, dict, dict]:
    """Return (ordered list, colors_dict, labels_dict) for workspace statuses.

    Falls back to Project constants if the project_status table is empty.

    Returns:
        Tuple of (statuses list, {code: color}, {code: label}).
    """
    try:
        statuses = ProjectStatus.get_for_workspace()
        if statuses:
            colors = {s.code: s.color for s in statuses}
            labels = {s.code: s.label for s in statuses}
            return statuses, colors, labels
    except Exception:
        pass
    # Fallback to model constants
    fallback = [
        type("S", (), {"code": c, "label": Project.STATUS_LABELS[c],
                       "color": Project.STATUS_COLORS[c],
                       "is_archived": c == Project.STATUS_ARCHIVED,
                       "is_default": c == Project.STATUS_CURRENT,
                       "sort_order": i})()
        for i, c in enumerate(Project.VALID_STATUSES)
    ]
    return (
        fallback,
        Project.STATUS_COLORS,
        Project.STATUS_LABELS,
    )


PROJECT_FILTER_PREF_KEY_PREFIX = "project_overview_filter"


def _project_filter_pref_key() -> str:
    workspace_id = getattr(g, "workspace_id", None) or 0
    return f"{PROJECT_FILTER_PREF_KEY_PREFIX}:{workspace_id}"


def _load_project_filter_pref(default_member_id: int) -> dict:
    """Load the saved project overview filter state for the current user."""
    from modules.base.core.models.user_setting import UserSetting

    raw = UserSetting.get(current_user.id, _project_filter_pref_key())
    if raw:
        try:
            parsed = json.loads(raw)
            if parsed.get("selectedMembers"):
                return {
                    "selectedMembers": [
                        int(x)
                        for x in parsed.get("selectedMembers", [])
                        if isinstance(x, (int, str)) and str(x).isdigit()
                    ],
                }
        except (ValueError, TypeError):
            pass
    return {
        "selectedMembers": [],
    }


# ── Views ─────────────────────────────────────────────────────────────────


@blueprint.route("/")
@login_required
def index() -> ResponseReturnValue:
    """Projects Overview — dashboard with aggregate stats + project list."""
    from datetime import date

    from modules.base.core.models.workspace_settings import WorkspaceSettings
    from ..queries.overview import get_project_overview

    member = _get_member()
    members = _get_all_members()

    stale_days = WorkspaceSettings.get_instance().stale_days or 3
    workspace_statuses, status_colors, status_labels = _get_workspace_statuses()
    status_config = {
        s.code: {"label": s.label, "color": s.color, "is_archived": s.is_archived}
        for s in workspace_statuses
    }
    projects = get_project_overview(
        g.organization_id, g.workspace_id, member.id,
        stale_days=stale_days, status_config=status_config,
    )

    overdue_total = sum(p.overdue_count for p in projects)
    stale_total = sum(1 for p in projects if p.is_stale)

    return render_device_template(
        "projects/desktop/index.html",
        projects=projects,
        members=members,
        current_member_id=member.id,
        initial_filter_pref=_load_project_filter_pref(member.id),
        initial_view_pref=_load_project_view_pref(),
        workspace_statuses=workspace_statuses,
        status_colors=status_colors,
        status_labels=status_labels,
        overdue_count=overdue_total,
        stale_count=stale_total,
        stale_days=stale_days,
        today=date.today(),
        active_page="projects",
    )


@blueprint.route("/filter-pref", methods=["POST"])
@login_required
def set_filter_pref() -> ResponseReturnValue:
    """Persist the current user's project overview filter state."""
    from modules.base.core.models.user_setting import UserSetting

    payload = request.get_json(silent=True) or {}
    sanitized = {
        "selectedMembers": [
            int(x) for x in payload.get("selectedMembers") or []
            if isinstance(x, (int, str)) and str(x).isdigit()
        ],
    }
    UserSetting.set(current_user.id, _project_filter_pref_key(), json.dumps(sanitized))
    return jsonify({"ok": True})


PROJECT_VIEW_PREF_KEY_PREFIX = "project_view_mode"


def _project_view_pref_key() -> str:
    workspace_id = getattr(g, "workspace_id", None) or 0
    return f"{PROJECT_VIEW_PREF_KEY_PREFIX}:{workspace_id}"


def _load_project_view_pref() -> str:
    """Load the saved project view mode for the current user.

    Returns:
        "list" or "board", defaults to "list".
    """
    from modules.base.core.models.user_setting import UserSetting

    raw = UserSetting.get(current_user.id, _project_view_pref_key())
    if raw in ("list", "board"):
        return raw
    return "list"


@blueprint.route("/view-pref", methods=["POST"])
@login_required
def set_view_pref() -> ResponseReturnValue:
    """Persist the current user's project view mode (list or board)."""
    from modules.base.core.models.user_setting import UserSetting

    payload = request.get_json(silent=True) or {}
    mode = payload.get("mode", "")
    if mode not in ("list", "board"):
        return jsonify({"ok": False}), 400
    UserSetting.set(current_user.id, _project_view_pref_key(), mode)
    return jsonify({"ok": True})


@blueprint.route("/new")
@login_required
def new():
    """Create project form."""
    member = _get_member()
    members = _get_all_members()
    return render_device_template(
        "projects/desktop/new.html",
        member=member,
        members=members,
        active_page="projects",
    )


@blueprint.route("/new", methods=["POST"])
@login_required
def create():
    """Create a new project."""
    member = _get_member()

    name = request.form.get("name", "").strip()
    if not name:
        abort(400)

    description = request.form.get("description", "").strip() or None
    owner_id = request.form.get("owner_id", type=int) or member.id
    color = request.form.get("color", "").strip() or None
    channel_name = request.form.get("channel_name", "").strip() or None
    if channel_name:
        channel_name = Project._slugify_name(channel_name) or None
    is_private = request.form.get("is_private") == "on"

    project = Project.create(
        name=name,
        created_by_id=member.id,
        description=description,
        owner_id=owner_id,
        color=color,
        create_channel=True,
        channel_name=channel_name,
        is_private=is_private,
    )

    session["last_project_id"] = project.id

    return redirect(url_for("projects_bp.detail", project_id=project.id))


VALID_PROJECT_TABS = ("board", "log", "attachments")


@blueprint.route("/<int:project_id>/")
@login_required
def detail(project_id):
    """Project detail page.

    Renders the project page with one of four tabs: board (default), log,
    docs, or files. The selected tab is read from ``?tab=`` and falls back to
    ``board`` when missing or unrecognized.

    Stats shown in the header:
        - Open: items with workflow_status in (todo, in_progress)
        - In Progress: workflow_status == 'in_progress'
        - Done: workflow_status == 'done'
        - Overdue: status == 'open' and due_date < today
    """
    from datetime import date

    from sqlalchemy.orm import joinedload

    from modules.base.core.models.workspace_user import WorkspaceUser

    project = (
        Project.scoped()
        .options(
            joinedload(Project.owner).joinedload(WorkspaceUser.user),
            joinedload(Project.channel),
            joinedload(Project.created_by).joinedload(WorkspaceUser.user),
        )
        .filter_by(id=project_id)
        .first()
    )
    if not project:
        abort(404)

    # Private projects: only visible to creator/owner/co-owners
    if project.is_private:
        member = _get_member()
        if member.id != project.created_by_id and not project.is_owner_or_co_owner(member.id):
            abort(404)

    session["last_project_id"] = project.id

    raw_tab = (request.args.get("tab") or "board").strip().lower()
    if raw_tab in ("docs", "files"):
        raw_tab = "attachments"
    active_tab = raw_tab if raw_tab in VALID_PROJECT_TABS else "board"

    open_items = project.get_open_tasks()
    closed_items = project.get_closed_tasks()
    recent_posts = project.get_recent_posts()

    from modules.base.tasks.models.task import get_tier_defaults, get_workflow_statuses

    # Group open items by urgency tier (for list view)
    tier_groups = {1: [], 2: [], 3: []}
    for item in open_items:
        tier_groups.setdefault(item.urgency_tier, []).append(item)

    # Group ALL items by workflow_status (for board view)
    all_items = open_items + closed_items
    workflow_statuses = get_workflow_statuses()
    workflow_groups = {s["key"]: [] for s in workflow_statuses}
    for item in all_items:
        ws = item.workflow_status or "todo"
        workflow_groups.setdefault(ws, []).append(item)

    today = date.today()
    todo_count = len(workflow_groups.get("todo", []))
    in_progress_count = len(workflow_groups.get("in_progress", []))
    done_count = len(workflow_groups.get("done", []))
    open_count = todo_count + in_progress_count
    overdue_count = sum(
        1
        for item in open_items
        if item.due_date is not None and item.due_date < today
    )
    eta_dates = [item.due_date for item in open_items if item.due_date is not None]
    project_eta = max(eta_dates) if eta_dates else None

    # Channel posts: full feed when on channel tab, preview only on board tab
    channel_posts: list = []
    channel_has_more = False
    channel_offset = 0
    if project.channel_id:
        if active_tab == "log":
            channel_offset = max(int(request.args.get("offset", 0) or 0), 0)
            channel_posts, channel_has_more = project.get_channel_posts(
                limit=20, offset=channel_offset
            )
        else:
            # Board tab preview: 3 posts (was 5)
            channel_posts, _ = project.get_channel_posts(limit=3)

    # Linked docs for board tab preview
    from modules.base.resources.models.attachment_link import AttachmentLink

    doc_links = AttachmentLink.get_for_entities(["project", "project_doc"], project_id)
    project_docs = [link.attachment for link in doc_links[:3]]

    # People involved: unique members from action item assignees + post authors
    people_set = {}
    for item in all_items:
        if item.assignee and item.assignee.user:
            people_set[item.assignee_id] = item.assignee
    for post in recent_posts:
        if post.member and post.member.user:
            people_set[post.member_id] = post.member
    for post in channel_posts:
        if post.member and post.member.user:
            people_set[post.member_id] = post.member
    people_involved = list(people_set.values())

    # Followers (interested parties)
    current_member = _get_member()
    followers = project.get_followers()
    follower_id_set = {f.id for f in followers}
    people_id_set = {m.id for m in people_involved}
    # Followers not already in people_involved (so they appear in the card without duplication)
    extra_followers = [f for f in followers if f.id not in people_id_set]
    is_following = project.is_follower(current_member.id)
    is_owner = project.is_owner_or_co_owner(current_member.id)
    is_primary_owner = current_member.id == project.owner_id

    # Co-owners
    co_owners = project.get_co_owners()
    co_owner_id_set = {c.id for c in co_owners}

    all_members = _get_all_members() if (is_owner or is_primary_owner) else []

    # Members the owner can add as followers (exclude owners/co-owners)
    non_follower_members = []
    if is_owner:
        non_follower_members = [
            m for m in all_members
            if m.id not in follower_id_set and not project.is_owner_or_co_owner(m.id)
        ]

    # Members the primary owner can add as co-owners
    non_co_owner_members = []
    if is_primary_owner:
        non_co_owner_members = [
            m for m in all_members
            if m.id not in co_owner_id_set and m.id != project.owner_id
        ]

    workspace_statuses, _, _ = _get_workspace_statuses()
    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "projects/desktop/detail.html",
        project=project,
        workspace_statuses=workspace_statuses,
        active_tab=active_tab,
        open_items=open_items,
        tier_groups=tier_groups,
        tier_defaults=get_tier_defaults(),
        closed_items=closed_items,
        recent_posts=recent_posts,
        channel_posts=channel_posts,
        channel_has_more=channel_has_more,
        channel_offset=channel_offset,
        people_involved=people_involved,
        followers=followers,
        follower_id_set=follower_id_set,
        extra_followers=extra_followers,
        is_following=is_following,
        is_owner=is_owner,
        is_primary_owner=is_primary_owner,
        current_member=current_member,
        non_follower_members=non_follower_members,
        co_owners=co_owners,
        co_owner_id_set=co_owner_id_set,
        non_co_owner_members=non_co_owner_members,
        workflow_statuses=workflow_statuses,
        workflow_groups=workflow_groups,
        open_count=open_count,
        in_progress_count=in_progress_count,
        done_count=done_count,
        overdue_count=overdue_count,
        project_eta=project_eta,
        today=today,
        project_docs=project_docs,
        github_connected=github_connected,
        github_repo=github_repo,
        active_page="projects",
    )


@blueprint.route("/<int:project_id>/posts/<int:post_id>/")
@login_required
def channel_thread(project_id, post_id):
    """Project-scoped channel thread view.

    Renders a single thread inside the project chrome so users browsing the
    Channel tab don't get punted to /updates/* when they click a thread.
    """
    from sqlalchemy.orm import joinedload as _jl_pct

    from modules.base.core.models.workspace_user import WorkspaceUser
    from modules.base.updates.models.channel_read_state import UpdateChannelReadState
    from modules.base.updates.models.post import UpdatePost
    from modules.base.updates.models.post_reaction import UpdatePostReaction

    project = (
        Project.scoped()
        .options(_jl_pct(Project.channel))
        .filter_by(id=project_id)
        .first()
    )
    if not project or not project.channel:
        abort(404)

    if project.is_private:
        member = _get_member()
        if member.id != project.created_by_id and not project.is_owner_or_co_owner(member.id):
            abort(404)

    channel = project.channel
    post = (
        UpdatePost.scoped()
        .options(_jl_pct(UpdatePost.member).joinedload(WorkspaceUser.user))
        .filter_by(id=post_id, channel_id=channel.id)
        .first()
    )
    if not post:
        return redirect(url_for("projects_bp.detail", project_id=project_id, tab="log"))

    if post.parent_id:
        root = post.get_root_post()
        return redirect(
            url_for("projects_bp.channel_thread", project_id=project_id, post_id=root.id)
        )

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if member:
        UpdateChannelReadState.mark_channel_read(member.id, channel.id)

    threaded_replies = post.get_threaded_replies()

    return render_device_template(
        "projects/desktop/channel_thread.html",
        project=project,
        channel=channel,
        post=post,
        threaded_replies=threaded_replies,
        UpdatePostReaction=UpdatePostReaction,
        is_organization_channel=False,
        active_page="projects",
    )


@blueprint.route("/<int:project_id>/edit")
@login_required
def edit(project_id):
    """Edit project form."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    if not current_user.is_admin and not project.is_owner_or_co_owner(member.id):
        abort(403)

    members = _get_all_members()
    return render_device_template(
        "projects/desktop/edit.html",
        project=project,
        members=members,
        active_page="projects",
    )


@blueprint.route("/<int:project_id>/edit", methods=["POST"])
@login_required
def update(project_id):
    """Update a project."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    if not current_user.is_admin and not project.is_owner_or_co_owner(member.id):
        abort(403)

    name = request.form.get("name", "").strip()
    if not name:
        abort(400)

    description = request.form.get("description", "").strip() or None
    owner_id = request.form.get("owner_id", type=int)
    color = request.form.get("color", "").strip() or None

    project.update(
        name=name,
        description=description,
        owner_id=owner_id,
        color=color,
    )

    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/status", methods=["POST"])
@login_required
def update_status(project_id: int) -> ResponseReturnValue:
    """Update project status (HTMX)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    if not current_user.is_admin and not project.is_owner_or_co_owner(member.id):
        abort(403)

    new_status = request.form.get("status", "").strip()
    valid_codes = ProjectStatus.get_codes() or Project.VALID_STATUSES
    if new_status not in valid_codes:
        abort(400)
    try:
        project.set_status(new_status)
    except ValueError:
        abort(400)

    # If HTMX request, return just the status pill
    if request.headers.get("HX-Request") == "true":
        return f'''<span class="badge" style="background:{project.status_color}22;color:{project.status_color};font-size:0.75rem;padding:0.25em 0.75em;border-radius:999px;">
            {project.status_label}</span>'''

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return "", 204

    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/archive", methods=["POST"])
@login_required
def archive(project_id):
    """Archive a project (HTMX)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    if not current_user.is_admin and not project.is_owner_or_co_owner(member.id):
        abort(403)

    project.archive()

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.index")}

    return redirect(url_for("projects_bp.index"))


@blueprint.route("/<int:project_id>/unarchive", methods=["POST"])
@login_required
def unarchive(project_id):
    """Unarchive a project (HTMX)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    if not current_user.is_admin and not project.is_owner_or_co_owner(member.id):
        abort(403)

    project.unarchive()

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.index")}

    return redirect(url_for("projects_bp.index"))


@blueprint.route("/archived")
@login_required
def archived():
    """Archived projects list."""
    projects = Project.get_archived_for_workspace()

    return render_device_template(
        "projects/desktop/archived.html",
        projects=projects,
        active_page="projects",
    )


@blueprint.route("/api/check-channel-name")
@login_required
def check_channel_name():
    """Check if a channel name is available. Returns JSON."""
    from modules.base.updates.models.channel import UpdateChannel

    raw = request.args.get("name", "").strip()
    slug = Project._slugify_name(raw) if raw else ""
    if not slug:
        return jsonify({"slug": "", "available": False})

    existing = UpdateChannel.get_by_name(slug)
    return jsonify({"slug": slug, "available": existing is None})


@blueprint.route("/<int:project_id>/follow", methods=["POST"])
@login_required
def follow(project_id):
    """Follow a project as an interested party.

    Any member can self-follow a project they can see. Project owners may also
    supply a ``member_id`` form field to add another member as a follower.
    """
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    current_member = _get_member()

    target_member_id = request.form.get("member_id", type=int)
    if target_member_id and target_member_id != current_member.id:
        # Only owner or co-owner can add someone else
        if not project.is_owner_or_co_owner(current_member.id):
            abort(403)
        follow_member_id = target_member_id
    else:
        # Self-follow: block if the project is private and not visible to them
        if not project.can_follow(current_member.id):
            abort(403)
        follow_member_id = current_member.id

    project.add_follower(follow_member_id)

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.detail", project_id=project_id)}
    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/unfollow", methods=["POST"])
@login_required
def unfollow(project_id):
    """Stop following a project as an interested party (self-unfollow)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    member = _get_member()
    project.remove_follower(member.id)

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.detail", project_id=project_id)}
    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/followers/<int:member_id>/remove", methods=["POST"])
@login_required
def remove_follower(project_id, member_id):
    """Remove a specific follower (owner-only)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    current_member = _get_member()
    # Owner/co-owner can remove anyone; members can remove themselves
    if not project.is_owner_or_co_owner(current_member.id) and current_member.id != member_id:
        abort(403)

    project.remove_follower(member_id)

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.detail", project_id=project_id)}
    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/co_owners/add", methods=["POST"])
@login_required
def add_co_owner(project_id):
    """Add a co-owner to a project (primary owner only)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    current_member = _get_member()
    # Only the primary owner may promote co-owners (prevent privilege escalation)
    if current_member.id != project.owner_id:
        abort(403)

    member_id = request.form.get("member_id", type=int)
    if not member_id:
        abort(400)

    project.add_co_owner(member_id)

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.detail", project_id=project_id)}
    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/<int:project_id>/co_owners/<int:member_id>/remove", methods=["POST"])
@login_required
def remove_co_owner(project_id, member_id):
    """Remove a co-owner from a project (primary owner only)."""
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    current_member = _get_member()
    if current_member.id != project.owner_id:
        abort(403)

    project.remove_co_owner(member_id)

    if request.headers.get("HX-Request") == "true":
        return "", 200, {"HX-Redirect": url_for("projects_bp.detail", project_id=project_id)}
    return redirect(url_for("projects_bp.detail", project_id=project_id))


@blueprint.route("/api/list")
@login_required
def api_list():
    """JSON list of active projects for dropdown population."""
    projects = Project.get_active_for_workspace()
    last_project_id = session.get("last_project_id")

    return jsonify([
        {
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "status_color": p.status_color,
            "is_last_used": p.id == last_project_id,
        }
        for p in projects
    ])
