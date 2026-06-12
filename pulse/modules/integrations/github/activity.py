# Copyright (c) 2025-2026 remarQable LLC

"""Plain-text summaries of GitHub push/PR events for the "Current" status feed.

The updates module's github_formatter produces HTML for chat channels; the
"Current" status template stores structured-list items with a plain ``text``
field, so these helpers emit concise one-liners instead. Each returns ``None``
when the event should not produce a status post (e.g. an empty push, or a noisy
PR action like ``synchronize``).
"""

from __future__ import annotations


def _branch(ref: str) -> str:
    """Return the short branch name from a git ref (``refs/heads/main`` → ``main``)."""
    return ref.rsplit("/", 1)[-1] if ref else ""


def _first_line(message: str, limit: int = 100) -> str:
    """Return the first line of a commit message, truncated to ``limit`` chars."""
    line = (message or "").split("\n", 1)[0].strip()
    return (line[:limit] + "…") if len(line) > limit else line


def summarize_push(payload: dict) -> str | None:
    """Summarize a ``push`` event as one line for a Current status post.

    Args:
        payload: The push webhook payload.

    Returns:
        A summary like ``"Pushed 2 commits to main: fix login bug"``, or None
        when there are no commits (branch delete / tag push) or the push is a
        PR merge commit — that's already reported by the pull_request event, so
        reporting the push too would double-post the same action.
    """
    commits = payload.get("commits") or []
    if not commits:
        return None

    branch = _branch(payload.get("ref", ""))
    count = len(commits)
    head = payload.get("head_commit") or commits[-1]
    head_msg = head.get("message", "")

    # GitHub's default-merge strategy creates a "Merge pull request #N from …"
    # commit and pushes it. The pull_request (merged) event already covers this,
    # so skip the duplicate push.
    if head_msg.startswith("Merge pull request "):
        return None

    msg = _first_line(head_msg)

    plural = "s" if count != 1 else ""
    base = f"Pushed {count} commit{plural}"
    if branch:
        base += f" to {branch}"
    return f"{base}: {msg}" if msg else base


def summarize_pull_request(payload: dict) -> str | None:
    """Summarize a ``pull_request`` event as one line for a Current status post.

    Only meaningful actions produce a line; noisy ones (``synchronize``,
    ``edited``, ``labeled``, etc.) return None so the feed stays signal.

    Args:
        payload: The pull_request webhook payload.

    Returns:
        A summary line, or None when the action should not post.
    """
    action = payload.get("action", "")
    pr = payload.get("pull_request") or {}
    number = pr.get("number")
    title = _first_line(pr.get("title", ""), limit=120)
    if number is None:
        return None

    suffix = f" #{number}: {title}" if title else f" #{number}"

    if action == "opened":
        return f"Opened PR{suffix}"
    if action == "reopened":
        return f"Reopened PR{suffix}"
    if action == "ready_for_review":
        return f"Marked PR ready for review{suffix}"
    if action == "closed":
        return f"Merged PR{suffix}" if pr.get("merged") else f"Closed PR{suffix} without merging"
    return None
