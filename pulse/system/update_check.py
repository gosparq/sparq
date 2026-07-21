# -----------------------------------------------------------------------------
# sparQ - Update Check
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Anonymous update check.

Once a day, sparQ asks the sparQ website for the latest released version and
logs a notice if the running instance is behind. The request transmits **nothing**
about the instance — no version, no identifier, no usage, no content. It is a
plain ``GET`` to a public endpoint that returns ``{"latest_version": "x.y.z"}``.

It is enabled by default and can be disabled with ``SPARQ_UPDATE_CHECK=false``.
The check runs off the request path in a background daemon thread, never blocks
startup, and silently does nothing on any error.

Example:
    Started once during app boot (production only)::

        from system.update_check import start_update_check_scheduler
        start_update_check_scheduler(app)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import date
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)

DEFAULT_UPDATE_URL = "https://www.gosparq.com/api/latest-version"
_STATE_FILENAME = ".sparq-last-update-check"
_REQUEST_TIMEOUT_SECONDS = 2
_CHECK_INTERVAL_HOURS = 6
_POLL_SECONDS = 300

_scheduler_running = False


def is_enabled() -> bool:
    """Return True unless disabled via ``SPARQ_UPDATE_CHECK`` (enabled by default)."""
    return os.environ.get("SPARQ_UPDATE_CHECK", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _update_url() -> str:
    """Return the version endpoint URL (overridable via ``SPARQ_UPDATE_URL``)."""
    return os.environ.get("SPARQ_UPDATE_URL", DEFAULT_UPDATE_URL)


def _data_dir() -> str:
    """Return the data directory (``SPARQ_DATA_DIR`` or ``<pulse>/data``)."""
    if "SPARQ_DATA_DIR" in os.environ:
        return os.environ["SPARQ_DATA_DIR"]
    pulse_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(pulse_root, "data")


def _state_file() -> str:
    return os.path.join(_data_dir(), _STATE_FILENAME)


def _checked_today() -> bool:
    """Return True if a successful check was already recorded today."""
    try:
        with open(_state_file(), encoding="utf-8") as fh:
            return fh.read().strip() == date.today().isoformat()
    except OSError:
        return False


def _record_check() -> None:
    """Persist today's date so restarts don't re-check the same day."""
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(_state_file(), "w", encoding="utf-8") as fh:
            fh.write(date.today().isoformat())
    except OSError as exc:
        logger.debug("Could not persist update-check date: %s", exc)


def _parse_version(value: str) -> tuple[int, ...] | None:
    """Parse a ``major.minor.patch`` string into a comparable tuple, or None."""
    core = value.strip().lstrip("vV").split("+")[0].split("-")[0]
    try:
        return tuple(int(part) for part in core.split("."))
    except (ValueError, AttributeError):
        return None


def is_newer(remote: str, local: str) -> bool:
    """Return True if ``remote`` is a strictly newer version than ``local``."""
    remote_parts = _parse_version(remote)
    local_parts = _parse_version(local)
    if remote_parts is None or local_parts is None:
        return False
    width = max(len(remote_parts), len(local_parts))
    remote_parts += (0,) * (width - len(remote_parts))
    local_parts += (0,) * (width - len(local_parts))
    return remote_parts > local_parts


def _fetch_latest(url: str) -> str | None:
    """GET the version endpoint and return its ``latest_version``, or None."""
    try:
        import requests

        response = requests.get(url, timeout=_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        latest = response.json().get("latest_version")
        return latest if isinstance(latest, str) else None
    except Exception as exc:  # network, timeout, bad JSON — all non-fatal
        logger.debug("Update check request failed: %s", exc)
        return None


def run_check(force: bool = False) -> None:
    """Perform one update check: fetch the latest version and log if behind.

    No-ops when disabled or already checked today (unless ``force``). Records the
    check date only on a successful fetch, so a transient failure retries later
    rather than burning the day's slot. Never raises.

    Args:
        force: Skip the once-per-day guard (used for tests / manual runs).
    """
    if not is_enabled():
        return
    if not force and _checked_today():
        return

    latest = _fetch_latest(_update_url())
    if latest is None:
        return

    _record_check()

    from system.version import get_version

    current = get_version()
    if is_newer(latest, current):
        # WARNING, not INFO: the `system` logger is set to WARNING in non-verbose
        # (production) mode, and this once-a-day notice must reach the operator.
        logger.warning(
            "A newer sparQ version is available: %s (installed: %s). "
            "Release notes: https://gosparq.com",
            latest,
            current,
        )
    else:
        logger.debug("sparQ is up to date (installed: %s, latest: %s)", current, latest)


def _run_in_context(app: Flask) -> None:
    """Run a single check inside an app context, swallowing any error."""
    with app.app_context():
        try:
            run_check()
        except Exception as exc:  # defensive: a background check must never crash
            logger.debug("Update check failed: %s", exc)


def start_update_check_scheduler(app: Flask) -> None:
    """Start the daily update-check daemon thread (production use).

    Runs one check shortly after startup, then re-evaluates on an interval. The
    once-per-day guard in :func:`run_check` keeps restarts from re-pinging.

    Args:
        app: Flask application instance.
    """
    global _scheduler_running

    if _scheduler_running:
        return
    if not is_enabled():
        logger.info("Update check disabled via SPARQ_UPDATE_CHECK")
        return

    import schedule

    scheduler = schedule.Scheduler()
    scheduler.every(_CHECK_INTERVAL_HOURS).hours.do(_run_in_context, app)
    _scheduler_running = True

    def _run() -> None:
        logger.info("Update check thread started")
        _run_in_context(app)  # initial check on boot (deduped by date)
        while _scheduler_running:
            scheduler.run_pending()
            time.sleep(_POLL_SECONDS)

    thread = threading.Thread(target=_run, daemon=True, name="update-check")
    thread.start()

    logger.info(
        "Update check enabled (anonymous daily version ping to %s; "
        "disable with SPARQ_UPDATE_CHECK=false)",
        _update_url(),
    )
