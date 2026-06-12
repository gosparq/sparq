# Copyright (c) 2025-2026 remarQable LLC

"""GitHub ↔ sparQ bidirectional sync service.

Two public functions intended to run in background threads via submit_task:

  sync_github_to_sparq(ref_id, github_action, **kwargs)
      Applies a GitHub event to the linked Task (close, reopen, assigned, relabeled).

  sync_sparq_to_github(task_id, changed_fields)
      Pushes Task field changes (workflow_status, urgency_tier, assignee_id) to GitHub.

Loop suppression:
  _SYNC_IN_PROGRESS is a module-level dict keyed by task_id. The after_update
  listener in task.py checks this flag before enqueuing sync_sparq_to_github so a
  GitHub-triggered change does not echo back.
"""

from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Thread-safe for short-lived reads/writes per the CPython GIL; each sync call
# sets the flag, does its work, then clears it within the same call.
_SYNC_IN_PROGRESS: dict[int, bool] = {}

# Mapping from urgency tier to sparq:* label name
_TIER_LABEL = {1: "sparq:now", 2: "sparq:later", 3: "sparq:whenever"}
# Label colors (hex without #) per the MRD
_LABEL_COLORS = {"sparq:now": "dc2626", "sparq:later": "d97706", "sparq:whenever": "16a34a"}


def sync_github_to_sparq(
    ref_id: int,
    github_action: str,
    new_assignee_id: int | None = None,
    new_tier: int | None = None,
) -> None:
    """Apply a GitHub issue event to the linked sparQ Task.

    Designed to run in a background thread (no Flask request context on entry;
    app context is pushed by submit_task). Sets g.workspace_id from the ref row
    so WorkspaceMixin.scoped() works correctly.

    Args:
        ref_id: IntegrationRef.id to act on.
        github_action: "closed", "reopened", "assigned", or "relabeled".
        new_assignee_id: WorkspaceUser.id for "assigned" action (optional).
        new_tier: urgency_tier int for "relabeled" action (optional).
    """
    from flask import g

    from modules.integrations.models.integration_ref import IntegrationRef
    from modules.base.tasks.models.task import Task
    from system.db.database import db

    try:
        print(f"[sync] sync_github_to_sparq: ref_id={ref_id} action={github_action}")
        # Unscoped lookup by PK — g.workspace_id is not yet set at this point.
        ref = IntegrationRef.query.filter_by(id=ref_id).first()
        if not ref:
            print(f"[sync] sync_github_to_sparq: ref {ref_id} not found")
            return

        # Restore workspace context so scoped() works for subsequent queries.
        g.workspace_id = ref.workspace_id
        g.organization_id = ref.organization_id

        # Resolve the linked task. linked_task_id is authoritative; fall back to
        # object_id for refs created before migration 086.
        task_id = ref.linked_task_id or (ref.object_id if ref.object_type == "task" else None)
        if not task_id:
            return
        task = Task.query.filter_by(id=task_id).first()
        if not task:
            return

        _SYNC_IN_PROGRESS[task.id] = True
        try:
            if github_action == "closed":
                if task.status == "open":
                    # Use Task.resolve() so TaskLog, ActivityLog, and notifications
                    # all fire. resolver_id=None marks it as system/GitHub action.
                    # _SYNC_IN_PROGRESS is set above, so the after_update listener
                    # suppresses the echo-back to GitHub.
                    Task.resolve(task.id, resolver_id=None, note="Closed via GitHub")
                    print(f"[sync] sync_github_to_sparq: resolved task={task.id} via ref={ref_id}")
                    logger.info("sync_github_to_sparq: closed task=%s via ref=%s", task.id, ref_id)

            elif github_action == "reopened":
                if task.status != "open":
                    task.status = "open"
                    task.workflow_status = "todo"
                    task.resolved_at = None
                    task.resolved_by_id = None
                    db.session.commit()
                    # Log the reopen so the task timeline reflects it.
                    try:
                        from modules.base.tasks.models.task_log import TaskLog
                        from modules.base.dashboard.models.activity_log import ActivityLog
                        TaskLog.log(task.id, "reopened", None, "Reopened via GitHub")
                        ActivityLog.log(
                            action="tasks.reopened",
                            model_type="Task",
                            record_id=task.id,
                            member_id=None,
                            title="Task reopened",
                            description=task.title[:100],
                            icon="fa-rotate-left",
                            color="warning",
                            url=f"/tasks/{task.id}",
                        )
                    except Exception:
                        pass
                    print(f"[sync] sync_github_to_sparq: reopened task={task.id} via ref={ref_id}")
                    logger.info("sync_github_to_sparq: reopened task=%s via ref=%s", task.id, ref_id)

            elif github_action == "assigned" and new_assignee_id is not None:
                task.assignee_id = new_assignee_id
                db.session.commit()
                logger.info(
                    "sync_github_to_sparq: assignee task=%s → member=%s via ref=%s",
                    task.id, new_assignee_id, ref_id,
                )

            elif github_action == "relabeled" and new_tier is not None:
                task.urgency_tier = max(1, min(3, new_tier))
                db.session.commit()
                logger.info(
                    "sync_github_to_sparq: urgency task=%s → tier=%s via ref=%s",
                    task.id, new_tier, ref_id,
                )
        finally:
            _SYNC_IN_PROGRESS.pop(task.id, None)

    except Exception:
        logger.exception("sync_github_to_sparq failed for ref_id=%s action=%s", ref_id, github_action)


def sync_sparq_to_github(task_id: int, changed_fields: set[str], snapshot: dict | None = None) -> None:
    """Push sparQ Task field changes to GitHub.

    Designed to run in a background thread. Each GitHub API call is wrapped
    in try/except so one failure does not abort syncing other refs.

    Args:
        task_id: Task.id that was updated.
        changed_fields: Set of field names that changed (e.g. {"workflow_status"}).
        snapshot: In-memory field values captured at flush time, before the DB
            transaction commits. Used to avoid reading stale state when the
            background thread starts before the COMMIT lands.
    """
    from flask import g

    from modules.integrations.models.integration_connection import IntegrationConnection
    from modules.integrations.models.integration_ref import IntegrationRef
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from modules.base.tasks.models.task import Task

    try:
        print(f"[sync] sync_sparq_to_github: task_id={task_id} changed={changed_fields} snapshot={snapshot}")
        # Unscoped lookup by PK — g.workspace_id is not yet set at this point.
        task = Task.query.filter_by(id=task_id).first()
        if not task:
            print(f"[sync] sync_sparq_to_github: task {task_id} not found")
            return

        # Restore workspace context.
        g.workspace_id = task.workspace_id
        g.organization_id = task.organization_id

        # Find all GitHub refs for this task: explicitly paired (linked_task_id)
        # or tagged via the # autocomplete trigger (object_type=task, object_id).
        from sqlalchemy import or_
        all_refs = IntegrationRef.query.filter(
            IntegrationRef.provider == "github",
            IntegrationRef.workspace_id == task.workspace_id,
            or_(
                IntegrationRef.linked_task_id == task_id,
                (IntegrationRef.object_type == "task") & (IntegrationRef.object_id == task_id),
            ),
        ).all()
        # Deduplicate by external_id so the same issue isn't updated twice.
        seen: set[str] = set()
        refs = [r for r in all_refs if not (r.external_id in seen or seen.add(r.external_id))]
        print(f"[sync] sync_sparq_to_github: task={task_id} status={task.status} workflow={task.workflow_status} refs={[r.external_id for r in refs]}")
        if not refs:
            return

        connection = IntegrationConnection.get_active("github")
        if not connection:
            print("[sync] sync_sparq_to_github: no active GitHub connection")
            return

        client = GitHubClient(connection)
        repo = connection.external_repo

        for ref in refs:
            issue_number = int(ref.external_id)

            if "workflow_status" in changed_fields:
                try:
                    # Prefer snapshot values (captured before commit) over the
                    # re-queried task to avoid the pre-commit race condition.
                    eff_status = (snapshot or {}).get("status") or task.status
                    eff_wf = (snapshot or {}).get("workflow_status") or task.workflow_status
                    print(f"[sync] sync_sparq_to_github: issue #{issue_number} eff_status={eff_status} eff_wf={eff_wf}")
                    if eff_status != "open" or eff_wf == "done":
                        client.close_issue(repo, issue_number)
                        logger.info(
                            "sync_sparq_to_github: closed GH issue #%s for task=%s",
                            issue_number, task_id,
                        )
                    else:
                        client.reopen_issue(repo, issue_number)
                        logger.info(
                            "sync_sparq_to_github: reopened GH issue #%s for task=%s",
                            issue_number, task_id,
                        )
                except (GitHubAPIError, Exception) as exc:
                    logger.error(
                        "sync_sparq_to_github: failed to update state for issue #%s: %s",
                        issue_number, exc,
                    )

            if "urgency_tier" in changed_fields:
                label_name = _TIER_LABEL.get((snapshot or {}).get("urgency_tier") or task.urgency_tier)
                if label_name:
                    try:
                        _ensure_sparq_labels(client, repo)
                        client.set_issue_labels(repo, issue_number, [label_name])
                        logger.info(
                            "sync_sparq_to_github: set label %s on issue #%s for task=%s",
                            label_name, issue_number, task_id,
                        )
                    except (GitHubAPIError, Exception) as exc:
                        logger.error(
                            "sync_sparq_to_github: failed to update labels for issue #%s: %s",
                            issue_number, exc,
                        )

            if "assignee_id" in changed_fields:
                login = _resolve_github_login(task.assignee_id)
                if login:
                    try:
                        client.set_issue_assignee(repo, issue_number, login)
                        logger.info(
                            "sync_sparq_to_github: set assignee %s on issue #%s for task=%s",
                            login, issue_number, task_id,
                        )
                    except (GitHubAPIError, Exception) as exc:
                        logger.error(
                            "sync_sparq_to_github: failed to set assignee for issue #%s: %s",
                            issue_number, exc,
                        )

    except Exception:
        logger.exception("sync_sparq_to_github failed for task_id=%s", task_id)


def _ensure_sparq_labels(client: "GitHubClient", repo: str) -> None:  # noqa: F821
    """Create sparq:* labels on the repo if they don't exist.

    Idempotent — skips labels that already exist.

    Args:
        client: Authenticated GitHubClient.
        repo: Owner/repo string.
    """
    for name, color in _LABEL_COLORS.items():
        try:
            client.ensure_label(repo, name, color)
        except Exception as exc:
            logger.warning("_ensure_sparq_labels: failed to ensure %s: %s", name, exc)


def _resolve_github_login(assignee_id: int | None) -> str | None:
    """Look up the GitHub login for a WorkspaceUser via their OAuthConnection.

    OAuthConnection stores provider_user_id (numeric) and email but not the
    GitHub username (login). We use the email as a best-effort identifier;
    GitHub REST API PATCH /issues requires a login, so sync is skipped when
    the email-based lookup can't be confirmed.

    # TODO(human): Add a provider_username column to OAuthConnection so we can
    # reliably resolve GitHub logins without an extra API call.

    Args:
        assignee_id: WorkspaceUser.id, or None.

    Returns:
        GitHub login string, or None if not found.
    """
    if not assignee_id:
        return None
    try:
        from modules.base.core.models.workspace_user import WorkspaceUser
        from modules.base.core.models.oauth_connection import OAuthConnection

        member = WorkspaceUser.query.get(assignee_id)
        if not member:
            return None
        # OAuthConnection.email stores the GitHub-verified email when the user
        # connected via GitHub OAuth. Use it as a proxy for the login until we
        # store the username directly.
        _oauth = OAuthConnection.query.filter_by(
            user_id=member.user_id, provider="github"
        ).first()
        # email-based login fallback: skip if not found
        return None
    except Exception as exc:
        logger.warning("_resolve_github_login failed for assignee_id=%s: %s", assignee_id, exc)
        return None


_BACKLINK_START = "<!-- sparq-backlink-start -->"
_BACKLINK_END = "<!-- sparq-backlink-end -->"


def inject_backlink(body: str, task_title: str, task_url: str) -> str:
    """Insert or replace the sparQ backlink section in a GitHub issue body.

    Uses HTML comment markers to detect an existing section so re-linking
    updates the text rather than appending a duplicate.

    Args:
        body: Current issue body (may be empty).
        task_title: sparQ task title for the link label.
        task_url: Absolute URL to the sparQ task detail page.

    Returns:
        New body with the backlink section added or updated.
    """
    section = (
        f"\n\n{_BACKLINK_START}\n"
        f"---\n"
        f"**sparQ Task:** [{task_title}]({task_url})\n"
        f"{_BACKLINK_END}"
    )
    if _BACKLINK_START in body:
        # Existing section — replace everything from the start marker onward
        # (handles both well-formed and truncated end-marker cases).
        start = body.index(_BACKLINK_START)
        body = body[:start].rstrip() + section
    else:
        body = body.rstrip() + section
    return body


def sync_all_cached_refs(connection) -> int:
    """Refresh cached_state for every IntegrationRef in the workspace from GitHub.

    Fetches the current issue state for each ref in batches. Returns the number
    of refs successfully updated. Intended to run in a background thread.

    Args:
        connection: Active IntegrationConnection for the workspace.

    Returns:
        Count of refs whose cached_state was refreshed.
    """
    from datetime import timezone

    from flask import g

    from modules.integrations.models.integration_ref import IntegrationRef
    from modules.integrations.github.client import GitHubClient, GitHubAPIError
    from system.db.database import db

    g.workspace_id = connection.workspace_id
    g.organization_id = connection.organization_id

    refs = (
        IntegrationRef.scoped()
        .filter_by(provider="github")
        .all()
    )
    if not refs:
        return 0

    from modules.base.tasks.models.task import Task

    client = GitHubClient(connection)
    updated = 0
    now = datetime.now(timezone.utc)

    # Collect (task_id, github_action) pairs to apply after the cached_state commit.
    pending_task_syncs: list[tuple[int, str]] = []

    for ref in refs:
        if not ref.external_id or not ref.external_repo:
            continue
        try:
            raw = client.get_issue(ref.external_repo, int(ref.external_id))
            labels = [lbl.get("name", "") for lbl in raw.get("labels", [])]
            user = raw.get("user") or {}
            assignee = raw.get("assignee") or {}
            new_state = raw.get("state", "open")
            ref.cached_state = {
                "title": raw.get("title", ""),
                "state": new_state,
                "html_url": raw.get("html_url", ""),
                "opened_by": user.get("login", ""),
                "opened_at": raw.get("created_at", ""),
                "labels": labels,
                "assignee_login": assignee.get("login", ""),
            }
            ref.cached_at = now
            updated += 1

            # Queue a task status update if there is a linked task whose
            # current status doesn't match the GitHub issue state.
            task_id = ref.linked_task_id or (
                ref.object_id if ref.object_type == "task" else None
            )
            if task_id:
                if new_state == "closed":
                    pending_task_syncs.append((task_id, "closed"))
                elif new_state == "open":
                    pending_task_syncs.append((task_id, "reopened"))

        except GitHubAPIError as exc:
            logger.warning("sync_all_cached_refs: failed for ref %s (#%s): %s", ref.id, ref.external_id, exc)
        except Exception as exc:
            logger.error("sync_all_cached_refs: unexpected error for ref %s: %s", ref.id, exc, exc_info=True)

    try:
        db.session.commit()
    except Exception as exc:
        logger.error("sync_all_cached_refs: commit failed: %s", exc, exc_info=True)

    # Apply task status changes based on current GitHub state. Only updates
    # tasks whose sparQ status actually disagrees (sync_github_to_sparq is
    # a no-op when the task is already in the right state).
    for task_id, action in pending_task_syncs:
        try:
            task = Task.query.filter_by(id=task_id).first()
            if not task:
                continue
            _SYNC_IN_PROGRESS[task_id] = True
            try:
                if action == "closed" and task.status == "open":
                    task.workflow_status = "done"
                    task.status = "resolved"
                    task.resolved_at = datetime.now(timezone.utc)
                    db.session.commit()
                    logger.info("sync_all_cached_refs: closed task=%s (GH issue closed)", task_id)
                elif action == "reopened" and task.status != "open":
                    task.status = "open"
                    task.workflow_status = "todo"
                    task.resolved_at = None
                    task.resolved_by_id = None
                    db.session.commit()
                    logger.info("sync_all_cached_refs: reopened task=%s (GH issue reopened)", task_id)
            finally:
                _SYNC_IN_PROGRESS.pop(task_id, None)
        except Exception as exc:
            logger.error("sync_all_cached_refs: task sync failed for task_id=%s: %s", task_id, exc, exc_info=True)

    logger.info("sync_all_cached_refs: refreshed %d/%d refs for workspace %s", updated, len(refs), connection.workspace_id)
    return updated
