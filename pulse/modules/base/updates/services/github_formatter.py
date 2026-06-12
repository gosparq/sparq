# -----------------------------------------------------------------------------
# sparQ - GitHub Webhook Event Formatter
#
# Formats GitHub webhook payloads into Slack-style HTML for chat display.
# Output is trusted HTML (we control generation), rendered with |safe.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

import html


def _esc(value: str) -> str:
    """Escape user-supplied text for safe HTML output."""
    return html.escape(str(value))


def format_github_event(event_type: str, payload: dict) -> str | None:
    """Format a GitHub webhook event into HTML for chat display.

    Returns formatted HTML string, or None if the event should be ignored (e.g. ping).
    """
    formatter = _FORMATTERS.get(event_type)
    if formatter:
        return formatter(payload)

    # Unknown event type - generic fallback
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    action = payload.get("action", "")
    if repo or sender:
        msg = f'{_esc(sender)} triggered <code>{_esc(event_type)}</code>'
        if action:
            msg += f" ({_esc(action)})"
        return msg + (_repo_footer(repo, repo_url) if repo else "")

    return None


def _repo_name(payload: dict) -> str:
    """Extract repository full name."""
    repo = payload.get("repository", {})
    return repo.get("full_name", repo.get("name", ""))


def _repo_url(payload: dict) -> str:
    """Extract repository HTML URL, constructing from full_name if needed."""
    url = payload.get("repository", {}).get("html_url", "")
    if not url:
        name = _repo_name(payload)
        if name:
            url = f"https://github.com/{name}"
    return url


def _sender(payload: dict) -> str:
    """Extract sender username."""
    return payload.get("sender", {}).get("login", "unknown")


def _repo_footer(repo: str, repo_url: str) -> str:
    """Render the repo footer line with small GitHub icon."""
    icon = '<img src="/sync/assets/img/github-mark.svg" style="width: 13px; height: 13px; vertical-align: -1px; opacity: 0.5;">'
    if repo_url:
        return f'<div style="margin-top: 6px;">{icon} <a href="{_esc(repo_url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-gray-500); font-size: 12px; text-decoration: none;">{_esc(repo)}</a></div>'
    return f'<div style="margin-top: 6px;">{icon} <span style="color: var(--color-gray-500); font-size: 12px;">{_esc(repo)}</span></div>'


def _commit_block(commits: list[dict], repo_url: str = "", compare_url: str = "") -> str:
    """Render the indented commit list with left border."""
    if not commits:
        return ""
    lines = []
    for commit in commits[:5]:
        full_sha = commit.get("id", "")
        sha = full_sha[:7]
        msg = commit.get("message", "").split("\n")[0][:100]
        url = commit.get("url", "")
        if not url and repo_url and full_sha:
            url = f"{repo_url}/commit/{full_sha}"
        if url:
            lines.append(f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="font-family: monospace; font-size: 12px; color: var(--color-primary); background: var(--color-gray-100); padding: 1px 5px; border-radius: 3px; text-decoration: none;">{_esc(sha)}</a> - {_esc(msg)}')
        else:
            lines.append(f'<code style="font-size: 12px;">{_esc(sha)}</code> - {_esc(msg)}')
    if len(commits) > 5:
        lines.append(f'... and {len(commits) - 5} more')

    inner = "<br>".join(lines)
    return f'<div style="border-left: 3px solid var(--color-gray-300); padding: 4px 0 4px 12px; margin: 6px 0;">{inner}</div>'


def _format_push(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    ref = payload.get("ref", "")
    branch = ref.rsplit("/", 1)[-1] if "/" in ref else ref
    commits = payload.get("commits", [])
    count = len(commits)
    compare_url = payload.get("compare", "")

    count_text = f'{count} new commit{"s" if count != 1 else ""}'
    if compare_url:
        header = f'<a href="{_esc(compare_url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">{count_text}</a>'
    else:
        header = count_text

    header += f' pushed to <code>{_esc(branch)}</code> by {_esc(sender)}'

    return header + _commit_block(commits, repo_url, compare_url) + _repo_footer(repo, repo_url)


def _format_issues(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    action = payload.get("action", "")
    issue = payload.get("issue", {})
    number = issue.get("number", "?")
    title = issue.get("title", "")
    url = issue.get("html_url", "")

    issue_link = f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">#{_esc(str(number))} {_esc(title)}</a>' if url else f'#{_esc(str(number))} {_esc(title)}'

    return f'{_esc(sender)} {_esc(action)} issue {issue_link}' + _repo_footer(repo, repo_url)


def _format_pull_request(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    number = pr.get("number", "?")
    title = pr.get("title", "")
    url = pr.get("html_url", "")
    merged = pr.get("merged", False)

    if action == "closed" and merged:
        action = "merged"

    pr_link = f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">#{_esc(str(number))} {_esc(title)}</a>' if url else f'#{_esc(str(number))} {_esc(title)}'

    return f'{_esc(sender)} {_esc(action)} PR {pr_link}' + _repo_footer(repo, repo_url)


def _format_issue_comment(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    issue = payload.get("issue", {})
    number = issue.get("number", "?")
    title = issue.get("title", "")
    comment = payload.get("comment", {})
    url = comment.get("html_url", "")

    issue_link = f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">#{_esc(str(number))} {_esc(title)}</a>' if url else f'#{_esc(str(number))} {_esc(title)}'

    return f'{_esc(sender)} commented on {issue_link}' + _repo_footer(repo, repo_url)


def _format_pull_request_review(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    pr = payload.get("pull_request", {})
    number = pr.get("number", "?")
    title = pr.get("title", "")
    url = pr.get("html_url", "")
    review = payload.get("review", {})
    state = review.get("state", "")

    state_text = {
        "approved": "approved",
        "changes_requested": "requested changes on",
        "commented": "reviewed",
    }.get(state, state)

    pr_link = f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">#{_esc(str(number))} {_esc(title)}</a>' if url else f'#{_esc(str(number))} {_esc(title)}'

    return f'{_esc(sender)} {_esc(state_text)} PR {pr_link}' + _repo_footer(repo, repo_url)


def _format_release(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    release = payload.get("release", {})
    tag = release.get("tag_name", "")
    url = release.get("html_url", "")

    tag_link = f'<a href="{_esc(url)}" target="_blank" rel="noopener noreferrer" style="color: var(--color-primary); text-decoration: none;">{_esc(tag)}</a>' if url else _esc(tag)

    return f'{_esc(sender)} published release {tag_link}' + _repo_footer(repo, repo_url)


def _format_create(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    ref_type = payload.get("ref_type", "")
    ref = payload.get("ref", "")

    return f'{_esc(sender)} created {_esc(ref_type)} <code>{_esc(ref)}</code>' + _repo_footer(repo, repo_url)


def _format_delete(payload: dict) -> str:
    repo = _repo_name(payload)
    repo_url = _repo_url(payload)
    sender = _sender(payload)
    ref_type = payload.get("ref_type", "")
    ref = payload.get("ref", "")

    return f'{_esc(sender)} deleted {_esc(ref_type)} <code>{_esc(ref)}</code>' + _repo_footer(repo, repo_url)


def _format_ping(payload: dict) -> None:
    """Ping event - return None to skip message creation."""
    return None


_FORMATTERS = {
    "push": _format_push,
    "issues": _format_issues,
    "pull_request": _format_pull_request,
    "issue_comment": _format_issue_comment,
    "pull_request_review": _format_pull_request_review,
    "release": _format_release,
    "create": _format_create,
    "delete": _format_delete,
    "ping": _format_ping,
}
