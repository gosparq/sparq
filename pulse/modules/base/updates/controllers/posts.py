# -----------------------------------------------------------------------------
# sparQ - Sync Module: Posts Controller
#
# Routes for template-driven posts (status, wins, board).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import os

from flask import abort, flash, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue
from flask_login import current_user, login_required

from system.db.database import db
from system.device.template import render_device_template
from system.i18n.translation import translate as _

from flask import jsonify

from . import blueprint
from ..models.acknowledgment import UpdatePostAck
from ..models.post import UpdatePost
from ..models.post_reaction import UpdatePostReaction
from ..models.template import UpdateTemplate

# Templates that record completed work or simple notifications — never generate action items.
_INFORMATIONAL_TEMPLATES = {"Async - End of Day (EOD)", "End of Day (EOD)", "Standup", "Win", "Heads up"}


def _process_text_audio_field(key: str, payload: dict) -> None:
    """Extract text, audio attachment, and duration from a text_audio form field into *payload*."""
    from modules.base.resources.models.attachment import Attachment

    payload[key] = request.form.get(f"field_{key}", "").strip()
    audio_file = request.files.get(f"field_{key}_audio")
    att = Attachment.create_from_audio_upload(audio_file)
    if att:
        payload[f"{key}_audio_uuid"] = att.uuid
        dur = request.form.get(f"field_{key}_audio_duration", type=int)
        if dur and dur > 0:
            payload[f"{key}_audio_duration"] = dur
    elif request.form.get(f"field_{key}_existing_audio"):
        payload[f"{key}_audio_uuid"] = request.form.get(f"field_{key}_existing_audio")


def _bind_pending_post_refs(post_id: int) -> None:
    """Rebind IntegrationRef rows with object_id=0 to the newly created post."""
    try:
        from datetime import datetime, timedelta
        from modules.integrations.models.integration_ref import IntegrationRef

        cutoff = datetime.utcnow() - timedelta(minutes=30)
        pending = (
            IntegrationRef.scoped()
            .filter_by(object_type="post", object_id=0)
            .filter(IntegrationRef.created_at >= cutoff)
            .all()
        )
        for ref in pending:
            ref.object_id = post_id
        if pending:
            db.session.commit()
    except Exception:
        pass


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


@blueprint.route("/audio/transcribe", methods=["POST"])
@login_required
def audio_transcribe() -> ResponseReturnValue:
    """Transcribe an uploaded audio clip via OpenAI."""
    audio_file = request.files.get("audio")
    if not audio_file or not audio_file.filename:
        return jsonify({"error": "No audio file provided"}), 400

    from system.ai.transcription import transcribe_audio

    transcript = transcribe_audio(audio_file, audio_file.filename)
    if transcript is None:
        return jsonify({"error": "Transcription unavailable"}), 500

    return jsonify({"transcript": transcript})


@blueprint.route("/updates/")
@login_required
def updates_index():
    """Legacy URL — redirect to /updates/."""
    return redirect(url_for("updates_bp.updates_index", **request.args), code=302)


@blueprint.route("/updates/feed")
@login_required
def updates_feed_page():
    """Legacy URL — redirect to /updates/feed."""
    return redirect(url_for("updates_bp.updates_feed_page", **request.args), code=302)


@blueprint.route("/wins/")
@login_required
def wins_index():
    """Redirect old wins URL to status feed."""
    return redirect(url_for("sync_bp.updates_index"), code=301)


@blueprint.route("/board/")
@login_required
def board_index():
    """List all active board posts, optionally filtered by template."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    filter_template_id = request.args.get("template", type=int)
    view = request.args.get("view", "grid")
    posts = UpdatePost.get_board_feed(template_id=filter_template_id)
    templates = UpdateTemplate.get_for_workspace(post_type="board")

    member = WorkspaceUser.get_by_user_id(current_user.id)
    current_member_id = member.id if member else None
    ack_map = UpdatePostAck.get_for_posts(posts, current_member_id)

    return render_device_template(
        "updates/desktop/board/index.html",
        posts=posts,
        templates=templates,
        filter_template_id=filter_template_id,
        view=view,
        ack_map=ack_map,
        active_page="board",
        module_home="sync_bp.index",
    )


@blueprint.route("/board/<int:post_id>/refresh", methods=["POST"])
@login_required
def board_refresh(post_id: int):
    """Refresh a board post's expiry (author or admin)."""
    post = UpdatePost.scoped().filter_by(id=post_id, post_type="board").first()
    if not post:
        abort(404)

    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not (current_user.is_admin or (member and post.member_id == member.id)):
        abort(403)

    post.refresh_expiry()
    return redirect(url_for("sync_bp.board_index"))


@blueprint.route("/board/<int:post_id>/archive", methods=["POST"])
@login_required
def board_archive(post_id: int):
    """Archive a board post by setting expires_at to now (author or admin)."""
    from datetime import datetime

    post = UpdatePost.scoped().filter_by(id=post_id, post_type="board").first()
    if not post:
        abort(404)

    from modules.base.core.models.workspace_user import WorkspaceUser
    from system.db.database import db

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not (current_user.is_admin or (member and post.member_id == member.id)):
        abort(403)

    post.expires_at = datetime.utcnow()
    db.session.commit()
    return redirect(url_for("sync_bp.board_index"))


@blueprint.route("/posts/<int:post_id>")
@login_required
def post_permalink(post_id: int):
    """Redirect to the post's canonical URL.

    Channel posts (and their replies) route to the channel thread view.
    Board and update posts route to their respective feeds.
    """
    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    # Walk to root if this is a reply (replies share the channel_id of the root)
    root = post.get_root_post() if post.parent_id else post

    # Channel posts → deep-link to the thread view
    if root.channel_id:
        from ..models.channel import UpdateChannel
        channel = UpdateChannel.scoped().filter_by(id=root.channel_id).first()
        if channel:
            if channel.project_id:
                return redirect(url_for(
                    "projects_bp.channel_thread",
                    project_id=channel.project_id,
                    post_id=root.id,
                ))
            return redirect(url_for(
                "updates_bp.channel_thread",
                slug=channel.name,
                post_id=root.id,
            ))

    if post.post_type == "board":
        params = {"template": post.template_id} if post.template_id else {}
        return redirect(url_for("sync_bp.board_index", **params) + f"#post-{post_id}")
    params = {"template": post.template_id} if post.template_id else {}
    return redirect(url_for("sync_bp.updates_index", **params) + f"#post-{post_id}")


@blueprint.route("/posts/<int:post_id>/edit")
@login_required
def post_edit(post_id: int):
    """Show edit form for an existing post (owner only)."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member or post.member_id != member.id:
        abort(403)

    template = UpdateTemplate.get_by_id(post.template_id)
    if not template:
        abort(404)

    # "I'm blocked" posts are the feed-side representation of a blocker
    # Task. The generic template form would only show `body`/title —
    # forward to the Task editor so urgency, assignee, project, etc.
    # are editable too.
    if template.name == "I'm blocked":
        from modules.base.tasks.models.task import Task

        ai_id = post.payload.get("action_item_id") if post.payload else None
        task = None
        if ai_id:
            task = Task.scoped().filter_by(id=ai_id).first()
        if not task:
            # Legacy posts created before the link existed — heuristic match
            # on same author + same title + is_blocker.
            body = (post.payload or {}).get("body", "") or ""
            if body:
                task = (
                    Task.scoped()
                    .filter_by(
                        is_blocker=True,
                        raised_by_id=post.member_id,
                        title=body[:200],
                    )
                    .order_by(Task.created_at.desc())
                    .first()
                )
        if task:
            # Open → editor; resolved/dismissed/canceled → detail (editor 403s).
            if task.status == "open":
                return redirect(url_for("tasks_bp.edit", item_id=task.id))
            return redirect(url_for("tasks_bp.detail", item_id=task.id))
        return redirect(url_for("updates_bp.updates_index"))

    # Active projects for dropdown
    projects = []
    try:
        from modules.base.projects.models.project import Project
        projects = Project.get_active_for_workspace()
    except Exception:
        pass

    # Active members for blocker assignee picker
    active_members = []
    try:
        from modules.base.core.models.workspace_user import WorkspaceUser as TSU
        from sqlalchemy.orm import joinedload
        active_members = TSU.scoped().options(joinedload(TSU.user)).filter_by(status="ACTIVE").order_by(TSU.id).all()
    except Exception:
        pass

    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "updates/desktop/post_form.html",
        template=template,
        post=post,
        is_edit=True,
        is_informational=(template.name in _INFORMATIONAL_TEMPLATES),
        projects=projects,
        active_members=active_members,
        github_connected=github_connected,
        github_repo=github_repo,
        ai_available=bool(os.environ.get("OPENAI_API_KEY")),
        active_page=template.post_type,
        module_home="sync_bp.index",
    )


@blueprint.route("/posts/<int:post_id>/update", methods=["POST"])
@login_required
def post_update(post_id: int):
    """Update an existing post's payload (owner only)."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member or post.member_id != member.id:
        abort(403)

    template = UpdateTemplate.get_by_id(post.template_id)
    if not template:
        abort(400)

    # Build payload from field keys (same logic as post_create)
    payload = {}
    for field in template.fields or []:
        key = field.get("key")
        if not key:
            continue
        if field.get("type") == "bullets":
            raw = request.form.getlist(f"field_{key}[]")
            payload[key] = [v.strip() for v in raw if v.strip()]
        elif field.get("type") == "structured_list":
            texts = request.form.getlist(f"field_{key}_text[]")
            projects = request.form.getlist(f"field_{key}_project[]")
            tasks_list = request.form.getlist(f"field_{key}_action_item[]")
            assignees = request.form.getlist(f"field_{key}_assignee[]") if field.get("blocker") else []
            items = []
            for i, text in enumerate(texts):
                text = text.strip()
                if not text:
                    continue
                item = {"text": text}
                proj_id = int(projects[i]) if i < len(projects) and projects[i] else None
                ai_id = int(tasks_list[i]) if i < len(tasks_list) and tasks_list[i] else None
                item["project_id"] = proj_id
                item["action_item_id"] = ai_id
                if field.get("blocker"):
                    assignee_id = int(assignees[i]) if i < len(assignees) and assignees[i] else None
                    item["assignee_id"] = assignee_id
                items.append(item)
            payload[key] = items
        elif field.get("type") == "text_audio":
            _process_text_audio_field(key, payload)
        else:
            value = request.form.get(f"field_{key}", "").strip()
            payload[key] = value

    post.update_payload(payload)

    # Update promote-to-dashboard flag (admin-only, board posts only)
    if template.post_type == "board" and current_user.is_admin:
        post.set_promoted(bool(request.form.get("promoted_to_dashboard")))

    params = {"template": post.template_id} if post.template_id else {}
    return redirect(url_for("sync_bp.updates_index", **params))


@blueprint.route("/posts/<int:post_id>/delete", methods=["POST"])
@login_required
def post_delete(post_id: int):
    """Soft-delete a post (owner only)."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member or post.member_id != member.id:
        abort(403)

    post.soft_delete()

    # Redirect back to where the user was (preserves "All" vs filtered view)
    referrer = request.referrer
    if referrer and "/sync/" in referrer:
        return redirect(referrer)
    return redirect(url_for("sync_bp.updates_index"))


@blueprint.route("/posts/<int:post_id>/bump", methods=["POST"])
@login_required
def post_bump(post_id: int):
    """Bump (repost) an existing post for the current interval (owner only)."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member or post.member_id != member.id:
        abort(403)

    if post.post_type not in ("update", "win"):
        abort(400)

    template = UpdateTemplate.get_by_id(post.template_id)
    if not template or template.schedule_type != "periodic":
        abort(400)

    bumped_post = UpdatePost.bump(original_post=post, member_id=member.id)

    # Dismiss template nudge notification (same as post_create)
    from modules.base.core.models.notification import SystemNotification

    SystemNotification.dismiss_by_title(
        f"Reminder: {template.name}", user_id=current_user.id
    )

    # Mark the outstanding nudge as completed
    from modules.base.updates.models.nudge_log import UpdateNudgeLog
    UpdateNudgeLog.mark_completed(template.id, current_user.id)

    # Resolve missed check-in action items
    try:
        from modules.base.tasks.models.task import Task

        Task.resolve_missed_checkins(template.name, member.id)
    except Exception:
        pass

    # Notify followers
    from system.email.sync_notifications import notify_followers

    if template.post_type in ("update", "win"):
        notify_followers("status_template", template.id, bumped_post, member)

    params = {"template": post.template_id} if post.template_id else {}
    return redirect(url_for("sync_bp.updates_index", **params))


@blueprint.route("/posts/new/<int:template_id>")
@login_required
def post_new(template_id: int):
    """Show form for creating a post using a template."""
    template = UpdateTemplate.get_by_id(template_id)
    if not template:
        abort(404)

    # "I'm blocked" uses the dedicated blocker modal on the board, not this
    # generic template-driven form. Mobile/desktop templates open the modal
    # directly via HTMX; this redirect is a fallback for direct URL access.
    if template.name == "I'm blocked":
        return redirect(url_for("updates_bp.updates_index"))

    # Active projects for dropdown
    projects = []
    preselected_project_id = None
    last_project_id = None
    try:
        from modules.base.projects.models.project import Project

        projects = Project.get_active_for_workspace()
        last_project_id = request.args.get("project_id", type=int) or None
        if not last_project_id:
            from flask import session
            last_project_id = session.get("last_project_id")
        if last_project_id:
            preselected_project_id = last_project_id
        elif len(projects) == 1:
            preselected_project_id = projects[0].id
    except Exception:
        pass

    # Active members for blocker assignee picker
    active_members = []
    try:
        from modules.base.core.models.workspace_user import WorkspaceUser as TSU
        from sqlalchemy.orm import joinedload
        active_members = TSU.scoped().options(joinedload(TSU.user)).filter_by(status="ACTIVE").order_by(TSU.id).all()
    except Exception:
        pass

    # Channel context — when composing from a channel feed page
    channel_id = request.args.get("channel_id", type=int)

    # Previous posts for the bump picker (periodic templates only)
    previous_posts = []
    prefill_post = None
    if template.schedule_type == "periodic":
        try:
            from modules.base.core.models.workspace_user import WorkspaceUser as _TSU2

            _member = _TSU2.get_by_user_id(current_user.id)
            if _member:
                previous_posts = UpdatePost.get_recent_for_member_template(
                    _member.id, template.id
                )
                bump_from_id = request.args.get("bump_from", type=int)
                if bump_from_id:
                    _candidate = UpdatePost.scoped().filter_by(
                        id=bump_from_id,
                        member_id=_member.id,
                        template_id=template.id,
                    ).first()
                    if _candidate:
                        prefill_post = _candidate
        except Exception:
            pass

    github_connected, github_repo = _get_github_context()
    return render_device_template(
        "updates/desktop/post_form.html",
        template=template,
        is_informational=(template.name in _INFORMATIONAL_TEMPLATES),
        projects=projects,
        preselected_project_id=preselected_project_id,
        last_project_id=last_project_id,
        active_members=active_members,
        channel_id=channel_id,
        previous_posts=previous_posts,
        prefill_post=prefill_post,
        github_connected=github_connected,
        github_repo=github_repo,
        ai_available=bool(os.environ.get("OPENAI_API_KEY")),
        active_page=template.post_type,
        module_home="sync_bp.index",
    )


@blueprint.route("/posts/create", methods=["POST"])
@login_required
def post_create():
    """Create a new UpdatePost from a submitted form."""
    template_id = request.form.get("template_id", type=int)
    template = UpdateTemplate.get_by_id(template_id) if template_id else None
    if not template:
        abort(400)

    from modules.base.core.models.workspace_user import WorkspaceUser

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    if UpdatePost.is_recent_duplicate(member.id, template.id):
        if template.post_type in ("update", "win"):
            return redirect(url_for("sync_bp.updates_index", template=template.id))
        elif template.post_type == "board":
            return redirect(url_for("sync_bp.board_index"))
        elif template.post_type == "pulse":
            return redirect(url_for("presence_flow_bp.pulse_index"))
        return redirect(url_for("sync_bp.index"))

    # Build payload from field keys defined in the template
    payload = {}
    for field in template.fields or []:
        key = field.get("key")
        if not key:
            continue
        if field.get("type") == "bullets":
            # bullets: collect all non-empty items
            raw = request.form.getlist(f"field_{key}[]")
            payload[key] = [v.strip() for v in raw if v.strip()]
        elif field.get("type") == "structured_list":
            # Collect parallel arrays for structured list items
            texts = request.form.getlist(f"field_{key}_text[]")
            projects = request.form.getlist(f"field_{key}_project[]")
            tasks_list = request.form.getlist(f"field_{key}_action_item[]")
            assignees = request.form.getlist(f"field_{key}_assignee[]") if field.get("blocker") else []

            items = []
            for i, text in enumerate(texts):
                text = text.strip()
                if not text:
                    continue
                item = {"text": text}
                proj_id = int(projects[i]) if i < len(projects) and projects[i] else None
                ai_id = int(tasks_list[i]) if i < len(tasks_list) and tasks_list[i] else None
                item["project_id"] = proj_id
                item["action_item_id"] = ai_id
                if field.get("blocker"):
                    assignee_id = int(assignees[i]) if i < len(assignees) and assignees[i] else None
                    item["assignee_id"] = assignee_id
                items.append(item)
            payload[key] = items
        elif field.get("type") == "text_audio":
            _process_text_audio_field(key, payload)
        else:
            value = request.form.get(f"field_{key}", "").strip()
            payload[key] = value

    # Validate: require at least one text/title/bullets field to have content
    has_text = False
    for field in template.fields or []:
        key = field.get("key", "")
        val = payload.get(key)
        if field.get("type") in ("text", "title", "text_audio") and val and len(val) >= 3:
            has_text = True
            break
        if field.get("type") == "bullets" and val and any(len(v) >= 3 for v in val):
            has_text = True
            break
        if field.get("type") == "structured_list" and val and isinstance(val, list) and any(isinstance(v, dict) and len(v.get("text", "")) >= 3 for v in val):
            has_text = True
            break
    if not has_text and template.post_type in ("update", "win"):
        flash(_("Please write something before posting."), "warning")
        return redirect(url_for("sync_bp.post_new", template_id=template.id))

    # Preserve bump lineage when created from the prefill flow
    bump_from_id = request.form.get("bump_from", type=int)
    if bump_from_id:
        payload["_bumped_from"] = bump_from_id

    # Optional channel and win flag from form
    form_channel_id = request.form.get("channel_id", type=int)
    form_is_win = bool(request.form.get("is_win"))

    post = UpdatePost.create(
        template=template,
        member_id=member.id,
        payload=payload,
        channel_id=form_channel_id,
        is_win=form_is_win,
    )

    # Auto-create action items from structured list fields
    try:
        from modules.base.tasks.models.task import Task
        if template.name not in _INFORMATIONAL_TEMPLATES:
            for field in template.fields or []:
                key = field.get("key")
                if field.get("type") != "structured_list" or not key:
                    continue
                if field.get("no_tasks"):
                    continue
                is_blocker = bool(field.get("blocker"))
                items = payload.get(key, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    proj_id = item.get("project_id")
                    ai_id = item.get("action_item_id")
                    text = item.get("text", "")
                    if is_blocker:
                        # Blocker fields: original behavior unchanged (project required)
                        if proj_id and not ai_id and text:
                            assignee_id_val = item.get("assignee_id")
                            new_ai = Task.create(
                                title=text[:200],
                                urgency_tier=2,
                                assignee_id=assignee_id_val or member.id,
                                raised_by_id=member.id,
                                source_type="sync_post",
                                source_id=post.id,
                                is_blocker=True,
                                project_id=proj_id,
                            )
                            if new_ai:
                                item["action_item_id"] = new_ai.id
                    elif template.post_type == "update":
                        # Update posts: create without requiring a project
                        if not ai_id and text:
                            new_ai = Task.create(
                                title=text[:200],
                                urgency_tier=3,
                                assignee_id=member.id,
                                raised_by_id=member.id,
                                source_type="sync_post",
                                source_id=post.id,
                                project_id=proj_id or None,
                                workflow_status="in_progress",
                            )
                            if new_ai:
                                item["action_item_id"] = new_ai.id
                        elif ai_id:
                            Task.set_workflow_status(ai_id, "in_progress")
                    else:
                        # Other post types (board, win): original project-required behavior
                        if proj_id and not ai_id and text:
                            new_ai = Task.create(
                                title=text[:200],
                                urgency_tier=3,
                                assignee_id=member.id,
                                raised_by_id=member.id,
                                source_type="sync_post",
                                source_id=post.id,
                                project_id=proj_id,
                                workflow_status="in_progress",
                            )
                            if new_ai:
                                item["action_item_id"] = new_ai.id
                # Re-save payload with filled action_item_ids
                post.update_payload(payload)
    except Exception:
        pass  # Don't block post creation

    # Tag with area if provided
    area_id = request.form.get("area_id", type=int)
    if area_id:
        post.tag_area(area_id)

    # Promote to dashboard (admin-only, board posts only)
    if template.post_type == "board" and current_user.is_admin:
        post.set_promoted(bool(request.form.get("promoted_to_dashboard")))

    # Auto-dismiss template reminder notification now that user has posted
    from modules.base.core.models.notification import SystemNotification
    SystemNotification.dismiss_by_title(f"Reminder: {template.name}", user_id=current_user.id)

    # Mark the outstanding nudge as completed
    from modules.base.updates.models.nudge_log import UpdateNudgeLog
    if template.nudge_enabled and template.schedule_type == "daily":
        UpdateNudgeLog.record_daily_completion(template.id, current_user.id)
    else:
        UpdateNudgeLog.mark_completed(template.id, current_user.id)

    # Auto-resolve any "missed check-in" action items for this template
    try:
        from modules.base.tasks.models.task import Task
        Task.resolve_missed_checkins(template.name, member.id)
    except Exception:
        pass  # Don't block post creation

    # Update focus status from inline payload field
    if template.post_type in ("update", "win"):
        focus_value = payload.get("focus", "")
        if focus_value:
            from modules.base.core.models.user_setting import UserSetting
            UserSetting.set(current_user.id, "flow_status", "flow" if focus_value == "focus" else "free")

    # Mark AI pulse nudge as responded if nudge_id was submitted
    nudge_id = request.form.get("nudge_id", type=int)
    if nudge_id:
        from ..models.nudge_log import UpdateNudgeLog

        nudge = UpdateNudgeLog.scoped().filter_by(id=nudge_id, user_id=current_user.id).first()
        if nudge:
            # Use first non-empty payload value as response
            response_val = ""
            for field in template.fields or []:
                val = payload.get(field.get("key", ""), "")
                if isinstance(val, str) and val:
                    response_val = val
                    break
            nudge.respond(response_val)
            SystemNotification.dismiss_by_url(f"nudge_id={nudge_id}", user_id=current_user.id)

    # Auto-create blocker action item for "I'm blocked" posts
    if template.name == "I'm blocked":
        title = ""
        for field in template.fields or []:
            val = payload.get(field.get("key", ""), "")
            if isinstance(val, str) and val:
                title = val[:200]
                break
        if title:
            try:
                from modules.base.tasks.models.task import Task as AI
                blocker_ai = AI.create(
                    title=title,
                    urgency_tier=2,
                    assignee_id=member.id,
                    raised_by_id=member.id,
                    source_type="sync_post",
                    source_id=post.id,
                )
                if blocker_ai:
                    blocker_ai.is_blocker = True
                    db.session.commit()
            except Exception:
                pass

    # Follow notifications — email followers of this template
    from system.email.sync_notifications import notify_followers, notify_mention

    if template.post_type in ("update", "win"):
        notify_followers("status_template", template.id, post, member)
    elif template.post_type == "board":
        notify_followers("board_template", template.id, post, member)

    # Parse @mentions from payload text fields and notify
    import re

    for val in (payload or {}).values():
        if isinstance(val, str):
            for mid in re.findall(r"@\[(\d+)\]", val):
                notify_mention(int(mid), post, member)

    # Bind any [GH-N] refs created during this form session to the new post.
    _bind_pending_post_refs(post.id)

    # Redirect back to the appropriate feed (filtered by template)
    if template.post_type in ("update", "win"):
        return redirect(url_for("sync_bp.updates_index", template=template.id))
    elif template.post_type == "board":
        return redirect(url_for("sync_bp.board_index"))
    elif template.post_type == "pulse":
        return redirect(url_for("presence_flow_bp.pulse_index"))
    else:
        return redirect(url_for("sync_bp.index"))


@blueprint.route("/posts/<int:post_id>/acknowledge", methods=["POST"])
@login_required
def acknowledge_post(post_id: int) -> ResponseReturnValue:
    """Acknowledge a sync post (10-4). Returns HTMX partial or redirects."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    try:
        ack_data = UpdatePostAck.acknowledge(post.id, member.id)
    except PermissionError:
        if request.headers.get("HX-Request") == "true":
            return _("Channel is locked because its project is closed."), 403
        flash(_("Channel is locked because its project is closed."), "warning")
        return redirect(request.referrer or url_for("sync_bp.updates_index"))

    if request.headers.get("HX-Request") == "true":
        return render_template(
            "updates/desktop/partials/_post_ten_four.html",
            post=post,
            ack_data=ack_data,
            current_member_id=member.id,
        )

    referrer = request.referrer
    if referrer and "/sync/" in referrer:
        return redirect(referrer)
    return redirect(url_for("sync_bp.updates_index"))


@blueprint.route("/posts/ten-four-status")
@login_required
def ten_four_status() -> ResponseReturnValue:
    """HTMX polling endpoint: return OOB-swapped 10-4 grids for visible posts."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post_ids_raw = request.args.get("posts", "")
    if not post_ids_raw:
        return ""

    try:
        post_ids = [int(pid) for pid in post_ids_raw.split(",") if pid.strip()]
    except (ValueError, TypeError):
        return ""

    member = WorkspaceUser.get_by_user_id(current_user.id)
    current_member_id = member.id if member else None

    post_map = UpdatePost.get_ackable_by_ids(post_ids)
    ackable_posts = [p for p in post_map.values()]
    ack_map = UpdatePostAck.get_for_posts(ackable_posts, current_member_id)

    fragments = []
    for pid in post_ids:
        post = post_map.get(pid)
        if not post:
            continue
        ack_data = ack_map.get(pid, {})
        html = render_template(
            "updates/desktop/partials/_post_ten_four.html",
            post=post,
            ack_data=ack_data,
            current_member_id=current_member_id,
        )
        html = html.replace(
            f'id="post-ten4-{pid}"',
            f'id="post-ten4-{pid}" hx-swap-oob="outerHTML:#post-ten4-{pid}"',
            1,
        )
        fragments.append(html)

    return "\n".join(fragments)


@blueprint.route("/posts/<int:post_id>/react", methods=["POST"])
@login_required
def toggle_post_reaction(post_id: int) -> ResponseReturnValue:
    """Toggle an emoji reaction on a status update post."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    emoji = request.form.get("emoji")
    if not emoji:
        return jsonify({"error": "Emoji is required"}), 400

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        return jsonify({"error": "Post not found"}), 404

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        added, count = UpdatePostReaction.toggle(post_id, member.id, emoji)
    except PermissionError:
        return jsonify({"error": "Channel is locked because its project is closed."}), 403
    reactions = UpdatePostReaction.get_for_message(post_id)

    return jsonify({"added": added, "count": count, "reactions": reactions})


@blueprint.route("/posts/<int:post_id>/reply", methods=["POST"])
@login_required
def post_reply(post_id: int) -> ResponseReturnValue:
    """Create a reply to a status update post."""
    from modules.base.core.models.workspace_user import WorkspaceUser

    post = UpdatePost.scoped().filter_by(id=post_id).first()
    if not post:
        abort(404)

    member = WorkspaceUser.get_by_user_id(current_user.id)
    if not member:
        abort(403)

    content = request.form.get("content", "").strip()
    if not content:
        if request.headers.get("HX-Request") == "true":
            return "", 204
        return redirect(url_for("updates_bp.updates_index"))

    # Find root post (replies always attach to root)
    root_id = post.parent_id or post.id

    try:
        reply = UpdatePost.create_channel_reply(
            channel_id=post.channel_id,
            member_id=member.id,
            content=content,
            parent_id=root_id,
        )
    except PermissionError:
        if request.headers.get("HX-Request") == "true":
            return _("Channel is locked because its project is closed."), 403
        flash(_("Channel is locked because its project is closed."), "warning")
        return redirect(request.referrer or url_for("updates_bp.updates_index"))

    if request.headers.get("HX-Request") == "true":
        return render_template(
            "updates/desktop/partials/_post_reply.html",
            reply=reply,
            UpdatePostReaction=UpdatePostReaction,
        )

    return redirect(url_for("updates_bp.updates_index"))
