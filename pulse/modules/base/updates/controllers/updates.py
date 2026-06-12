# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Updates controller — /updates/ routes for the unified navigation.

Provides the main updates feed, channel feeds, wins aggregation, activity feed,
and backwards-compat redirects from legacy /sync/* URLs.
"""

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.db.database import db
from system.device.detection import is_mobile
from system.device.template import render_device_template
from system.i18n.translation import translate as _

updates_bp = Blueprint(
    "updates_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/updates/assets",
)


def _get_github_context() -> tuple[bool, str]:
    try:
        from modules.integrations.models.integration_connection import IntegrationConnection
        conn = IntegrationConnection.get_active("github")
        return conn is not None, (conn.external_repo if conn else "")
    except Exception:
        return False, ""


def _extract_feed_refs(posts):
    """Extract task_ids and project_ids from post payloads."""
    feed_ai_ids = set()
    feed_project_ids = set()
    for p in posts:
        for field in (p.template_fields or []):
            val = p.payload.get(field.get("key", ""))
            if field.get("type") == "structured_list" and isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        if item.get("action_item_id"):
                            feed_ai_ids.add(item["action_item_id"])
                        if item.get("project_id"):
                            feed_project_ids.add(item["project_id"])
        ai_refs = p.payload.get("action_item_refs")
        if ai_refs and isinstance(ai_refs, list):
            feed_ai_ids.update(ai_refs)
        if p.template_name == "I'm blocked":
            ai_id = (p.payload or {}).get("action_item_id")
            if ai_id:
                feed_ai_ids.add(ai_id)
    return feed_ai_ids, feed_project_ids


def _build_blocker_names_map(posts, feed_task_map, Task):
    """Build a map of post_id -> list of 'blocked by' first names."""
    blocker_names_map = {}
    seen_groups = {}
    for p in posts:
        if p.template_name != "I'm blocked":
            continue
        ai_id = (p.payload or {}).get("action_item_id")
        if not ai_id:
            continue
        ai = feed_task_map.get(ai_id)
        if not ai:
            continue

        if ai.broadcast_group_id:
            group_id = ai.broadcast_group_id
            if group_id not in seen_groups:
                summary = Task.get_broadcast_summary(group_id)
                names = []
                for item in summary.get("items", []):
                    if item.assignee and item.assignee.user:
                        names.append(item.assignee.user.first_name)
                seen_groups[group_id] = names
            blocker_names_map[p.id] = seen_groups[group_id]
        elif ai.assignee and ai.assignee.user:
            blocker_names_map[p.id] = [ai.assignee.user.first_name]

    return blocker_names_map


# ── Landing ────────────────────────────────────────────────────────────────

@updates_bp.route("/")
@login_required
def index():
    """Updates landing — redirect to the updates feed."""
    return redirect(url_for("updates_bp.updates_index"))


# ── Updates Feed (main) ───────────────────────────────────────────────────

@updates_bp.route("/feed/")
@login_required
def updates_index():
    """List all status posts (updates + wins), optionally filtered by template."""
    from ..models.acknowledgment import UpdatePostAck
    from ..models.post_reaction import UpdatePostReaction
    from ..models.template import UpdateTemplate
    from ..queries.feed import build_ack_member_info, get_active_members, get_feed_posts

    _member = getattr(g, "_current_member_cache", None)
    _current_member_id = _member.id if _member else None

    filter_template_id = request.args.get("template", type=int)
    filter_member_id = request.args.get("member", type=int)
    filter_area_id = request.args.get("area", type=int)
    view = request.args.get("view", "feed")
    LIMIT = 10

    posts, has_more = get_feed_posts(
        g.organization_id, g.workspace_id,
        post_type=["update", "win"],
        template_id=filter_template_id,
        member_id=filter_member_id,
        area_id=filter_area_id,
        limit=LIMIT,
        offset=0,
    )

    # Templates — single call, cache on g so inject_header_post_templates skips re-fetch
    all_templates_full = UpdateTemplate.get_for_workspace()
    g._update_templates_all = all_templates_full
    all_templates = [t for t in all_templates_full if t.post_type in ("update", "win")]
    try:
        cache = getattr(g, "_update_template_cache", {})
        ts_id = g.workspace_id
        cache[(ts_id, "update")] = [t for t in all_templates_full if t.post_type == "update"]
        cache[(ts_id, "win")] = [t for t in all_templates_full if t.post_type == "win"]
        cache[(ts_id, "board")] = [t for t in all_templates_full if t.post_type == "board"]
        g._update_template_cache = cache
    except Exception:
        pass

    # Detect special template types (from cached list, no extra query)
    selected_template = next(
        (t for t in all_templates_full if t.id == filter_template_id), None
    ) if filter_template_id else None
    is_daily_template = selected_template and selected_template.schedule_type == "daily"
    is_blocked_template = selected_template and selected_template.name == "I'm blocked"

    # Active members — projection query (no ORM lazy-load risk)
    active_members = get_active_members(g.organization_id, g.workspace_id)

    # Digest data: only for daily-scheduled templates (Standup, EOD)
    digest_responses = []
    digest_pending = []
    is_digest = False
    if filter_template_id and view == "digest" and is_daily_template:
        is_digest = True
        today_posts, _ = get_feed_posts(
            g.organization_id, g.workspace_id,
            post_type=["update", "win"],
            template_id=filter_template_id,
            today_only=True,
        )
        responded_ids = set()
        for post in today_posts:
            if post.member_id:
                responded_ids.add(post.member_id)
                digest_responses.append(post)
        digest_pending = [m for m in active_members if m.id not in responded_ids]

    blocker_map = {}

    # Areas for filter dropdown
    from ..models.area import UpdateArea

    areas = UpdateArea.get_all()

    # Hydrate structured list items: collect project_ids and action_item_ids
    from modules.base.tasks.models.task import Task

    feed_ai_ids, feed_project_ids = _extract_feed_refs(posts)

    feed_task_map = Task.get_by_ids(list(feed_ai_ids)) if feed_ai_ids else {}

    blocker_names_map = _build_blocker_names_map(posts, feed_task_map, Task)

    # Fetch active projects once — serves both the blocker modal and feed refs
    blocker_projects = getattr(g, "_active_projects_cache", None)
    if blocker_projects is None:
        try:
            from modules.base.projects.models.project import Project
            blocker_projects = Project.get_active_for_workspace()
        except Exception:
            blocker_projects = []
    feed_project_map = (
        {p.id: p for p in blocker_projects if p.id in feed_project_ids}
        if feed_project_ids else {}
    )

    reactions_map = UpdatePostReaction.get_for_posts([p.id for p in posts])
    ack_map = UpdatePostAck.get_for_posts(
        posts, _current_member_id, member_info=build_ack_member_info(active_members),
    )
    github_connected, github_repo = _get_github_context()

    return render_device_template(
        "updates/desktop/updates.html",
        posts=posts,
        has_more=has_more,
        next_offset=LIMIT,
        templates=all_templates,
        filter_template_id=filter_template_id,
        filter_member_id=filter_member_id,
        filter_area_id=filter_area_id,
        active_members=active_members,
        areas=areas,
        is_digest=is_digest,
        is_daily_template=is_daily_template,
        is_blocked_template=is_blocked_template,
        digest_responses=digest_responses,
        digest_pending=digest_pending,
        blocker_map=blocker_map,
        UpdatePostAck=UpdatePostAck,
        UpdatePostReaction=UpdatePostReaction,
        reactions_map=reactions_map,
        ack_map=ack_map,
        feed_task_map=feed_task_map,
        feed_project_map=feed_project_map,
        blocker_names_map=blocker_names_map,
        members=active_members,
        projects=blocker_projects,
        active_page="updates",
        module_home="updates_bp.index",
        github_connected=github_connected,
        github_repo=github_repo,
    )


# ── Updates Feed Page (HTMX infinite scroll) ─────────────────────────────

@updates_bp.route("/feed/more")
@login_required
def updates_feed_page():
    """HTMX endpoint: return next batch of posts for infinite scroll."""
    from ..models.acknowledgment import UpdatePostAck
    from ..models.post_reaction import UpdatePostReaction
    from ..queries.feed import get_feed_posts

    offset = request.args.get("offset", 0, type=int)
    filter_template_id = request.args.get("template", type=int)
    filter_member_id = request.args.get("member", type=int)
    filter_area_id = request.args.get("area", type=int)
    last_date = request.args.get("last_date", "")
    LIMIT = 10

    posts, has_more = get_feed_posts(
        g.organization_id, g.workspace_id,
        post_type=["update", "win"],
        template_id=filter_template_id,
        member_id=filter_member_id,
        area_id=filter_area_id,
        limit=LIMIT,
        offset=offset,
    )

    blocker_map = {}

    from modules.base.tasks.models.task import Task

    feed_ai_ids, feed_project_ids = _extract_feed_refs(posts)

    feed_task_map = Task.get_by_ids(list(feed_ai_ids)) if feed_ai_ids else {}

    blocker_names_map = _build_blocker_names_map(posts, feed_task_map, Task)

    from ..queries.feed import build_ack_member_info, get_active_members
    blocker_members = get_active_members(g.organization_id, g.workspace_id)
    blocker_projects = getattr(g, "_active_projects_cache", None)
    if blocker_projects is None:
        try:
            from modules.base.projects.models.project import Project
            blocker_projects = Project.get_active_for_workspace()
        except Exception:
            blocker_projects = []
    feed_project_map = (
        {p.id: p for p in blocker_projects if p.id in feed_project_ids}
        if feed_project_ids else {}
    )

    from system.auth.current_member import current_member as _current_member
    _member = _current_member()
    _current_member_id = _member.id if _member else None
    reactions_map = UpdatePostReaction.get_for_posts([p.id for p in posts])
    gh_connected, gh_repo = _get_github_context()
    ack_map = UpdatePostAck.get_for_posts(
        posts, _current_member_id, member_info=build_ack_member_info(blocker_members),
    )

    return render_template(
        "updates/desktop/partials/_updates_feed.html",
        posts=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        filter_template_id=filter_template_id,
        filter_member_id=filter_member_id,
        filter_area_id=filter_area_id,
        last_date=last_date,
        blocker_map=blocker_map,
        UpdatePostAck=UpdatePostAck,
        UpdatePostReaction=UpdatePostReaction,
        reactions_map=reactions_map,
        ack_map=ack_map,
        feed_task_map=feed_task_map,
        feed_project_map=feed_project_map,
        blocker_names_map=blocker_names_map,
        members=blocker_members,
        projects=blocker_projects,
        github_connected=gh_connected,
        github_repo=gh_repo,
    )


# ── Channel List (mobile landing for Channels tab) ───────────────────────

@updates_bp.route("/channels/")
@login_required
def channels_index() -> ResponseReturnValue:
    """List all workspace channels — mobile Channels tab landing page.

    On desktop, redirects to the main feed (channels are in the sidebar).
    On mobile, renders a dedicated channel list page.
    """
    from sqlalchemy.orm import joinedload

    from modules.base.projects.models.project import Project
    from ..models.channel import UpdateChannel
    from ..models.channel_read_state import UpdateChannelReadState

    if not is_mobile():
        return redirect(url_for("updates_bp.updates_index"))

    channels = UpdateChannel.get_all()
    all_project_channel_ids = Project.get_all_channel_ids()
    active_projects = (
        Project.scoped()
        .filter(Project.status != Project.STATUS_ARCHIVED, Project._visible_filter())
        .options(joinedload(Project.channel))
        .order_by(Project._activity_order().desc())
        .all()
    )
    project_channels = [p for p in active_projects if p.channel_id]

    return render_template(
        "updates/mobile/channels/index.html",
        nav_channels=channels,
        nav_project_channels=project_channels,
        nav_project_channel_ids=all_project_channel_ids,
        UpdateChannelReadState=UpdateChannelReadState,
        active_page="channels",
        module_home="updates_bp.index",
    )


# ── Channel Feed (Forum Index) ────────────────────────────────────────────

@updates_bp.route("/channels/<slug>/")
@login_required
def channel_feed(slug):
    """Forum-style thread index for a workspace channel."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.channel_read_state import UpdateChannelReadState
    from ..models.post import UpdatePost

    channel = UpdateChannel.get_by_name(slug)
    if not channel:
        return redirect(url_for("updates_bp.index"))

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if member:
        UpdateChannelReadState.mark_channel_read(member.id, channel.id)

    LIMIT = 20
    offset = request.args.get("offset", 0, type=int)
    posts, has_more = UpdatePost.get_channel_feed(channel.id, limit=LIMIT, offset=offset)

    # Historical messages for archive link
    message_count = UpdatePost.scoped().filter(UpdatePost.channel_id == channel.id).count()

    return render_device_template(
        "updates/desktop/channel_feed.html",
        channel=channel,
        posts=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        message_count=message_count,
        active_page="updates",
        module_home="updates_bp.index",
    )


@updates_bp.route("/organization/channels/<slug>/")
@login_required
def organization_channel_feed(slug):
    """Forum-style thread index for an org-wide channel.

    Org-wide channels are UpdateChannel rows with workspace_id IS NULL.
    Posts live in update_post like any other channel.
    """
    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost

    if not getattr(g, "organization_id", None):
        return redirect(url_for("dashboard_bp.index"))

    channel = UpdateChannel.get_org_wide_by_name(slug)
    if not channel:
        return redirect(url_for("updates_bp.wins_organization"))

    LIMIT = 20
    offset = request.args.get("offset", 0, type=int)
    posts, has_more = UpdatePost.get_channel_feed(
        channel.id, limit=LIMIT, offset=offset
    )

    message_count = (
        UpdatePost.scoped().filter(UpdatePost.channel_id == channel.id).count()
    )

    return render_device_template(
        "updates/desktop/channel_feed.html",
        channel=channel,
        posts=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        message_count=message_count,
        active_page="updates",
        is_organization_channel=True,
        module_home="updates_bp.index",
    )


# ── Thread Detail ─────────────────────────────────────────────────────────

@updates_bp.route("/channels/<slug>/<int:post_id>/")
@login_required
def channel_thread(slug, post_id):
    """Forum thread detail — original post + flat replies + reply composer."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    from sqlalchemy.orm import joinedload as _jl_ct

    from ..models.channel import UpdateChannel
    from ..models.channel_read_state import UpdateChannelReadState
    from ..models.post import UpdatePost
    from ..models.post_reaction import UpdatePostReaction

    channel = UpdateChannel.get_by_name(slug)
    if not channel:
        return redirect(url_for("updates_bp.index"))

    post = (
        UpdatePost.scoped()
        .options(_jl_ct(UpdatePost.member).joinedload(WorkspaceUser.user))
        .filter_by(id=post_id, channel_id=channel.id)
        .first()
    )
    if not post:
        return redirect(url_for("updates_bp.channel_feed", slug=slug))

    # If this is a reply, redirect to the root thread
    if post.parent_id:
        root = post.get_root_post()
        return redirect(url_for("updates_bp.channel_thread", slug=slug, post_id=root.id))

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if member:
        UpdateChannelReadState.mark_channel_read(member.id, channel.id)

    threaded_replies = post.get_threaded_replies()

    return render_device_template(
        "updates/desktop/channel_thread.html",
        channel=channel,
        post=post,
        threaded_replies=threaded_replies,
        UpdatePostReaction=UpdatePostReaction,
        active_page="updates",
        module_home="updates_bp.index",
    )


# ── New Thread ────────────────────────────────────────────────────────────

@updates_bp.route("/channels/<slug>/new", methods=["GET", "POST"])
@login_required
def channel_new_thread(slug):
    """Create a new forum thread (subject + body)."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost

    channel = UpdateChannel.get_by_name(slug)
    if not channel:
        abort(404)

    if request.method == "GET":
        return render_device_template(
            "updates/desktop/channel_new_thread.html",
            channel=channel,
            active_page="updates",
            module_home="updates_bp.index",
        )

    # POST — create the thread
    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    _form_return_to = (request.form.get("return_to") or request.args.get("return_to") or "").strip()
    _new_thread_url = url_for("updates_bp.channel_new_thread", slug=slug)
    if _form_return_to.startswith("/") and not _form_return_to.startswith("//"):
        from urllib.parse import quote
        _new_thread_url = f"{_new_thread_url}?return_to={quote(_form_return_to, safe='/?&=')}"

    if not subject or len(subject) < 3:
        flash(_("Please add a subject for your post."), "warning")
        return redirect(_new_thread_url)
    if not body or len(body) < 3:
        flash(_("Please write something before posting."), "warning")
        return redirect(_new_thread_url)

    if UpdatePost.is_recent_duplicate(member.id, channel_id=channel.id):
        return redirect(url_for("updates_bp.channel_feed", slug=slug))

    try:
        post = UpdatePost.create_channel_post(
            member_id=member.id,
            channel_id=channel.id,
            body=body,
            subject=subject,
        )
    except PermissionError:
        flash(_("This project is closed. Reopen it to post."), "warning")
        return redirect(url_for("updates_bp.channel_feed", slug=slug))

    # In-app notifications for project followers
    if channel.project_id:
        try:
            from modules.base.projects.models.project import Project
            project = Project.get_by_id(channel.project_id)
            if project:
                project.notify_followers_new_post(post, member)
        except Exception as e:
            from flask import current_app
            current_app.logger.error("notify_followers_new_post failed: %s", e, exc_info=True)

    return_to = (request.form.get("return_to") or request.args.get("return_to") or "").strip()
    if return_to.startswith("/") and not return_to.startswith("//"):
        return redirect(return_to)
    return redirect(url_for("updates_bp.channel_thread", slug=slug, post_id=post.id))


@updates_bp.route("/organization/channels/<slug>/<int:post_id>/")
@login_required
def organization_channel_thread(slug, post_id):
    """Org-wide channel thread detail — OP + flat replies."""
    from sqlalchemy.orm import joinedload as _jl_oct

    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost
    from ..models.post_reaction import UpdatePostReaction

    if not getattr(g, "organization_id", None):
        return redirect(url_for("dashboard_bp.index"))

    channel = UpdateChannel.get_org_wide_by_name(slug)
    if not channel:
        return redirect(url_for("updates_bp.wins_organization"))

    post = (
        UpdatePost.scoped()
        .options(_jl_oct(UpdatePost.member).joinedload(WorkspaceUser.user))
        .filter_by(id=post_id, channel_id=channel.id)
        .first()
    )
    if not post:
        return redirect(url_for("updates_bp.organization_channel_feed", slug=slug))

    # If this is a reply, redirect to the root thread.
    if post.parent_id:
        root = post.get_root_post()
        return redirect(
            url_for("updates_bp.organization_channel_thread", slug=slug, post_id=root.id)
        )

    threaded_replies = post.get_threaded_replies()

    return render_device_template(
        "updates/desktop/channel_thread.html",
        channel=channel,
        post=post,
        threaded_replies=threaded_replies,
        UpdatePostReaction=UpdatePostReaction,
        is_organization_channel=True,
        active_page="updates",
        module_home="updates_bp.index",
    )


@updates_bp.route("/organization/channels/<slug>/new", methods=["GET", "POST"])
@login_required
def organization_channel_new_thread(slug):
    """Create a new forum thread in an org-wide channel.

    Any organization member can post. Posts live in update_post with
    channel_id pointing at the org-wide UpdateChannel row (workspace_id NULL).
    """
    from flask import abort
    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost

    if not getattr(g, "organization_id", None):
        abort(404)

    channel = UpdateChannel.get_org_wide_by_name(slug)
    if not channel:
        abort(404)

    if request.method == "GET":
        return render_device_template(
            "updates/desktop/channel_new_thread.html",
            channel=channel,
            is_organization_channel=True,
            active_page="updates",
            module_home="updates_bp.index",
        )

    # POST — resolve any org-member WorkspaceUser for authorship.
    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        from modules.base.core.models.workspace import Workspace
        member = (
            WorkspaceUser.query
            .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
            .filter(WorkspaceUser.user_id == current_user.id)
            .filter(Workspace.organization_id == g.organization_id)
            .filter(WorkspaceUser.deleted_at.is_(None))
            .order_by(WorkspaceUser.id.asc())
            .first()
        )
    if not member:
        flash(_("Join a workspace before posting to organization channels."), "warning")
        return redirect(url_for("updates_bp.organization_channel_feed", slug=slug))

    subject = request.form.get("subject", "").strip()
    body = request.form.get("body", "").strip()

    if not subject or len(subject) < 3:
        flash(_("Please add a subject for your post."), "warning")
        return redirect(url_for("updates_bp.organization_channel_new_thread", slug=slug))
    if not body or len(body) < 3:
        flash(_("Please write something before posting."), "warning")
        return redirect(url_for("updates_bp.organization_channel_new_thread", slug=slug))

    if UpdatePost.is_recent_duplicate(member.id, channel_id=channel.id, org_wide=True):
        return redirect(url_for("updates_bp.organization_channel_feed", slug=slug))

    post = UpdatePost(
        member_id=member.id,
        post_type="update",
        channel_id=channel.id,
        subject=subject,
        payload={"content": body},
    )
    post.workspace_id = None
    from system.db.database import db as _db
    _db.session.add(post)
    _db.session.commit()

    return redirect(
        url_for("updates_bp.organization_channel_thread", slug=slug, post_id=post.id)
    )


# ── Reply to Thread ───────────────────────────────────────────────────────

@updates_bp.route("/channels/<slug>/<int:post_id>/reply", methods=["POST"])
@login_required
def channel_reply(slug, post_id):
    """Create a reply in a forum thread."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost

    channel = UpdateChannel.get_by_name(slug)
    if not channel:
        abort(404)

    # post_id in the URL is the root thread post
    root_post = UpdatePost.scoped().filter_by(id=post_id, channel_id=channel.id).first()
    if not root_post:
        abort(404)

    root_id = root_post.id

    # Determine actual parent: if reply_to_id is provided, reply to that post
    reply_to_id = request.form.get("reply_to_id", "").strip()
    if reply_to_id:
        actual_parent = UpdatePost.scoped().filter_by(id=int(reply_to_id)).first()
        # Cap nesting at 2 levels: if replying to a depth-1 reply, parent is that reply's parent
        if actual_parent and actual_parent.parent_id and actual_parent.parent_id != root_id:
            actual_parent_id = actual_parent.parent_id
        elif actual_parent:
            actual_parent_id = actual_parent.id
        else:
            actual_parent_id = root_id
    else:
        actual_parent_id = root_id

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    body = request.form.get("body", "").strip()
    if len(body) < 1:
        return redirect(url_for("updates_bp.channel_thread", slug=slug, post_id=root_id))

    try:
        reply = UpdatePost.create_channel_reply(
            member_id=member.id,
            channel_id=channel.id,
            parent_id=actual_parent_id,
            body=body,
        )
    except PermissionError:
        flash(_("Channel is locked because its project is closed."), "warning")
        return redirect(url_for("updates_bp.channel_thread", slug=slug, post_id=root_id))

    # In-app notifications for project followers
    if channel.project_id:
        try:
            from modules.base.projects.models.project import Project
            project = Project.get_by_id(channel.project_id)
            if project:
                project.notify_followers_new_post(reply, member)
        except Exception as e:
            from flask import current_app
            current_app.logger.error("notify_followers_new_post failed: %s", e, exc_info=True)

    return_to = (request.form.get("return_to") or "").strip()
    if return_to.startswith("/") and not return_to.startswith("//"):
        # Honor project-scoped return — keep the user in project chrome.
        thread_url = return_to
        if "?" in return_to:
            thread_url = return_to  # caller controls the destination
    else:
        thread_url = url_for("updates_bp.channel_thread", slug=slug, post_id=root_id)

    # HTMX: full page reload to re-render the threaded tree correctly
    if request.headers.get("HX-Request"):
        from flask import make_response

        resp = make_response("", 204)
        resp.headers["HX-Redirect"] = thread_url
        return resp

    return redirect(thread_url)


@updates_bp.route("/organization/channels/<slug>/<int:post_id>/reply", methods=["POST"])
@login_required
def organization_channel_reply(slug, post_id):
    """Reply to a thread in an org-wide channel."""
    from flask import abort
    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.channel import UpdateChannel
    from ..models.post import UpdatePost

    if not getattr(g, "organization_id", None):
        abort(404)

    channel = UpdateChannel.get_org_wide_by_name(slug)
    if not channel:
        abort(404)

    root_post = UpdatePost.scoped().filter_by(id=post_id, channel_id=channel.id).first()
    if not root_post:
        abort(404)

    root_id = root_post.id

    # Mirror workspace reply nesting cap (2 levels).
    reply_to_id = request.form.get("reply_to_id", "").strip()
    if reply_to_id:
        actual_parent = UpdatePost.query.filter_by(id=int(reply_to_id)).first()
        if actual_parent and actual_parent.parent_id and actual_parent.parent_id != root_id:
            actual_parent_id = actual_parent.parent_id
        elif actual_parent:
            actual_parent_id = actual_parent.id
        else:
            actual_parent_id = root_id
    else:
        actual_parent_id = root_id

    # Resolve any active WorkspaceUser for this user within the org.
    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        from modules.base.core.models.workspace import Workspace
        member = (
            WorkspaceUser.query
            .join(Workspace, Workspace.id == WorkspaceUser.workspace_id)
            .filter(WorkspaceUser.user_id == current_user.id)
            .filter(Workspace.organization_id == g.organization_id)
            .filter(WorkspaceUser.deleted_at.is_(None))
            .order_by(WorkspaceUser.id.asc())
            .first()
        )
    if not member:
        abort(403)

    body = request.form.get("body", "").strip()
    if len(body) < 1:
        return redirect(
            url_for("updates_bp.organization_channel_thread", slug=slug, post_id=root_id)
        )

    reply = UpdatePost(
        member_id=member.id,
        post_type="update",
        channel_id=channel.id,
        parent_id=actual_parent_id,
        payload={"content": body},
    )
    reply.workspace_id = None
    from system.db.database import db as _db
    _db.session.add(reply)
    _db.session.commit()

    # Bump root's denormalized reply metadata.
    root_post.reply_count_col = (root_post.reply_count_col or 0) + 1
    root_post.last_reply_at = reply.created_at
    root_post.last_reply_member_id = member.id
    _db.session.commit()

    if request.headers.get("HX-Request"):
        from flask import make_response
        resp = make_response("", 204)
        resp.headers["HX-Redirect"] = url_for(
            "updates_bp.organization_channel_thread", slug=slug, post_id=root_id
        )
        return resp

    return redirect(
        url_for("updates_bp.organization_channel_thread", slug=slug, post_id=root_id)
    )


@updates_bp.route("/channels/<slug>/archive")
@login_required
def channel_archive(slug):
    """Read-only historical chat messages for a channel."""
    from ..models.channel import UpdateChannel

    channel = UpdateChannel.get_by_name(slug)
    if not channel:
        return redirect(url_for("updates_bp.index"))

    from sqlalchemy.orm import joinedload as _jl_ca

    from modules.base.core.models.workspace_user import WorkspaceUser

    from ..models.post import UpdatePost

    LIMIT = 50
    offset = request.args.get("offset", 0, type=int)

    # Show all posts in this channel (including migrated chat messages)
    posts = (
        UpdatePost.scoped()
        .options(_jl_ca(UpdatePost.member).joinedload(WorkspaceUser.user))
        .filter(UpdatePost.channel_id == channel.id)
        .order_by(UpdatePost.created_at.desc())
        .offset(offset)
        .limit(LIMIT + 1)
        .all()
    )
    has_more = len(posts) > LIMIT
    posts = posts[:LIMIT]

    return render_device_template(
        "updates/desktop/channel_archive.html",
        channel=channel,
        messages=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        active_page="updates",
        module_home="updates_bp.index",
    )


# ── Status (filtered by template slug) ────────────────────────────────────

@updates_bp.route("/status/")
@updates_bp.route("/status/<template_slug>/")
@login_required
def status(template_slug=None):
    """Status filtered view — proxies to updates feed with template filter."""
    if template_slug:
        from ..models.template import UpdateTemplate

        tmpl = UpdateTemplate.query.filter(
            UpdateTemplate.name == template_slug.replace("-", " ").title(),
            db.or_(
                UpdateTemplate.workspace_id == g.workspace_id,
                UpdateTemplate.workspace_id.is_(None),
            ),
        ).first()
        if tmpl:
            return redirect(url_for("updates_bp.updates_index", template=tmpl.id))
    return redirect(url_for("updates_bp.updates_index"))


# ── Wins ───────────────────────────────────────────────────────────────────

@updates_bp.route("/wins/")
@login_required
def wins():
    """Read-only wins aggregation — workspace scope."""
    return _render_wins_feed()


@updates_bp.route("/organization/wins/")
@login_required
def wins_organization():
    """Wins feed for the active organization (org-wide posts only)."""
    return _render_wins_feed()


def _render_wins_feed():
    from ..models.post import UpdatePost

    LIMIT = 20
    offset = request.args.get("offset", 0, type=int)
    posts, has_more = UpdatePost.wins_feed_for_scope(limit=LIMIT, offset=offset)

    return render_device_template(
        "updates/desktop/wins_aggregation.html",
        posts=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        active_page="updates",
        workspace_path=url_for("updates_bp.wins"),
        organization_path=url_for("updates_bp.wins_organization"),
        module_home="updates_bp.index",
    )


# ── Activity (webhook posts) ──────────────────────────────────────────────

@updates_bp.route("/activity/")
@login_required
def activity():
    """Activity feed — webhook-originated posts."""
    from ..models.post import UpdatePost

    LIMIT = 20
    offset = request.args.get("offset", 0, type=int)
    posts, has_more = UpdatePost.get_activity_feed(limit=LIMIT, offset=offset)

    return render_device_template(
        "updates/desktop/activity.html",
        posts=posts,
        has_more=has_more,
        next_offset=offset + LIMIT,
        active_page="updates",
        module_home="updates_bp.index",
    )


# ── Board (proxy) ─────────────────────────────────────────────────────────

@updates_bp.route("/board/")
@updates_bp.route("/board/<path:rest>")
@login_required
def board(rest=""):
    """Board — proxy to existing sync board routes."""
    return redirect(url_for("sync_bp.board_index"))


# ── Weekly Plans (proxy) ──────────────────────────────────────────────────

@updates_bp.route("/weekly-plans/")
@updates_bp.route("/weekly-plans/<path:rest>")
@login_required
def weekly_plans(rest=""):
    """Weekly plans — proxy to action items plans routes."""
    return redirect(url_for("tasks_bp.plans_index"))


# Import sub-modules that register routes on updates_bp
from . import pulse  # noqa: E402, F401
