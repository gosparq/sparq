# -----------------------------------------------------------------------------
# sparQ - Sync Module: Blockers Controller
#
# Routes for the persistent blockers board.
# Backed by Task with is_blocker=True.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from flask import abort, g, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.auth.current_member import current_member as _current_member
from system.db.database import db

from . import blueprint


def _get_github_context() -> tuple[bool, str]:
    """Return (github_connected, github_repo) for _new_blocker_modal.html trigger.

    Required because _new_blocker_modal.html embeds the issue_trigger macro
    which needs github_connected and github_repo from its render context.

    Returns:
        Tuple of (bool, str). False/"" when integrations module unavailable.
    """
    try:
        from modules.integrations.models.integration_connection import IntegrationConnection
        conn = IntegrationConnection.get_active("github")
        return conn is not None, (conn.external_repo if conn else "")
    except Exception:
        return False, ""


@blueprint.route("/blockers/create", methods=["POST"])
@login_required
def blockers_create() -> ResponseReturnValue:
    """Create a new blocker as an Task with is_blocker=True.

    Supports multi-assignment via assign_mode (single, multi, all, unassigned),
    reusing the Task broadcast group pattern.
    """
    from modules.base.tasks.models.task import Task
    from modules.base.core.models.workspace_user import EmployeeStatus, WorkspaceUser

    member = _current_member()
    if not member:
        abort(403)

    title = request.form.get("title", "").strip()
    if not title:
        abort(400)

    description = request.form.get("description", "").strip() or None
    project_id = request.form.get("project_id", type=int) or None
    try:
        action_tier = max(1, min(3, int(request.form.get("action_tier", "2"))))
    except (ValueError, TypeError):
        action_tier = 2

    # Multi-assignment handling (matches action items controller pattern)
    assign_mode = request.form.get("assign_mode", "single")
    assignee_ids = request.form.getlist("assignee_ids", type=int)
    single_assignee_id = request.form.get("assignee_id", type=int)

    if assign_mode == "unassigned":
        assignee_ids = [None]
    elif assign_mode == "all":
        all_members = (
            WorkspaceUser.scoped()
            .filter_by(status=EmployeeStatus.ACTIVE)
            .all()
        )
        assignee_ids = [m.id for m in all_members if m.id != member.id]
    elif assign_mode == "multi":
        if len(assignee_ids) == 1:
            single_assignee_id = assignee_ids[0]
            assignee_ids = [single_assignee_id]
        elif not assignee_ids:
            abort(400)
    else:
        assignee_ids = [single_assignee_id] if single_assignee_id else [member.id]

    context_note = description[:500] if description else None
    created_items = []

    if len(assignee_ids) == 1:
        task = Task.create(
            title=title[:200],
            urgency_tier=action_tier,
            assignee_id=assignee_ids[0],
            raised_by_id=member.id,
            context_note=context_note,
        )
        if task:
            task.is_blocker = True
            if project_id:
                task.project_id = project_id
            db.session.commit()
            created_items.append(task)
    else:
        items = Task.create_broadcast(
            title=title[:200],
            urgency_tier=action_tier,
            assignee_ids=assignee_ids,
            raised_by_id=member.id,
            context_note=context_note,
        )
        for item in items:
            item.is_blocker = True
            if project_id:
                item.project_id = project_id
        db.session.commit()
        created_items.extend(items)

    # Also create an "I'm blocked" post for the feed (one post regardless of
    # how many assignees). Link to the first item for the edit button.
    first_item = created_items[0] if created_items else None
    try:
        from ..models.post import UpdatePost
        from ..models.template import UpdateTemplate

        blocked_template = UpdateTemplate.get_by_name("I'm blocked", post_type="update")
        if blocked_template:
            UpdatePost.create(
                template=blocked_template,
                member_id=member.id,
                payload={
                    "body": title,
                    "action_item_id": first_item.id if first_item else None,
                },
            )
    except Exception:
        pass

    next_url = request.form.get("next") or url_for("updates_bp.updates_index")
    if not next_url.startswith("/"):
        next_url = url_for("updates_bp.updates_index")
    return redirect(next_url)


@blueprint.route("/blockers/<int:task_id>/update", methods=["POST"])
@login_required
def blockers_update(task_id: int) -> ResponseReturnValue:
    """Update a blocker Task using the same fields the create modal exposes.

    Handles the fields in `_new_blocker_modal.html`: title, description
    (→ context_note), project, assignee, urgency tier. Due date, workflow
    status, and watchers stay editable via the tasks detail page.
    """
    from modules.base.tasks.models.task import Task

    member = _current_member()
    if not member:
        abort(403)

    item = Task.scoped().filter_by(id=task_id, is_blocker=True).first()
    if not item:
        abort(404)

    is_raiser = item.raised_by_id == member.id
    is_admin = getattr(current_user, "is_admin", False)
    if not (is_raiser or is_admin):
        abort(403)
    if item.status != "open":
        abort(403)

    title = request.form.get("title", "").strip()
    if not title:
        abort(400)
    description = request.form.get("description", "").strip() or None
    assignee_id = request.form.get("assignee_id", type=int) or item.assignee_id
    project_id = request.form.get("project_id", type=int) or None
    try:
        action_tier = max(1, min(3, int(request.form.get("action_tier", item.urgency_tier))))
    except (ValueError, TypeError):
        action_tier = item.urgency_tier

    item.title = title[:200]
    item.urgency_tier = action_tier
    item.assignee_id = assignee_id
    item.project_id = project_id
    item.context_note = description[:500] if description else None
    db.session.commit()

    try:
        from modules.base.tasks.models.task_log import TaskLog
        TaskLog.log(item.id, "edited", member.id)
    except Exception:
        pass

    # Return to wherever the user came from (feed or board).
    next_url = request.form.get("next") or url_for("updates_bp.updates_index")
    return redirect(next_url)


@blueprint.route("/blockers/modal/new")
@login_required
def blockers_modal_new() -> ResponseReturnValue:
    """Return the shared create-blocker modal fragment for HTMX swap into #modal-container.

    Used by the mobile Blockers page — the mobile main content is position:fixed,
    which traps Bootstrap modals in a stacking context where the backdrop covers
    them. HTMX loads the modal directly into #modal-container (which sits outside
    .mobile-main-content in core/mobile/base.html), avoiding the stacking issue.
    """
    from ..queries.feed import get_active_members

    member = _current_member()

    members = get_active_members(g.organization_id, g.workspace_id)

    projects = []
    try:
        from modules.base.projects.models.project import Project
        projects = Project.get_active_for_workspace()
    except Exception:
        pass

    next_url = request.args.get("next")

    github_connected, github_repo = _get_github_context()
    return render_template(
        "updates/desktop/partials/_new_blocker_modal.html",
        members=members,
        projects=projects,
        current_member=member,
        modal_id="newBlockerModal",
        task=None,
        htmx_auto_show=True,
        next_url=next_url,
        github_connected=github_connected,
        github_repo=github_repo,
    )


@blueprint.route("/blockers/<int:task_id>/modal/edit")
@login_required
def blockers_modal_edit(task_id: int) -> ResponseReturnValue:
    """Return the shared blocker modal fragment in edit mode for HTMX swap into #modal-container."""
    from modules.base.tasks.models.task import Task

    from ..queries.feed import get_active_members

    member = _current_member()
    if not member:
        abort(403)

    item = Task.scoped().filter_by(id=task_id, is_blocker=True).first()
    if not item:
        abort(404)

    # Same auth rule as blockers_update — raiser or admin, and only while open.
    is_raiser = item.raised_by_id == member.id
    is_admin = getattr(current_user, "is_admin", False)
    if not (is_raiser or is_admin):
        abort(403)
    if item.status != "open":
        abort(403)

    members = get_active_members(g.organization_id, g.workspace_id)

    projects = []
    try:
        from modules.base.projects.models.project import Project
        projects = Project.get_active_for_workspace()
    except Exception:
        pass

    github_connected, github_repo = _get_github_context()
    return render_template(
        "updates/desktop/partials/_new_blocker_modal.html",
        members=members,
        projects=projects,
        current_member=member,
        modal_id="editBlockerModal",
        task=item,
        htmx_auto_show=True,
        github_connected=github_connected,
        github_repo=github_repo,
    )


@blueprint.route("/blockers/<int:blocker_id>/resolve", methods=["POST"])
@login_required
def blockers_resolve(blocker_id: int) -> ResponseReturnValue:
    """Mark a blocker action item as resolved."""
    from modules.base.tasks.models.task import Task

    member = _current_member()
    if not member:
        abort(403)

    result = Task.resolve(blocker_id, member.id)
    if not result:
        abort(404)

    return redirect(url_for("updates_bp.updates_index"))
