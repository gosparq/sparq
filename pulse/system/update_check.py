# -----------------------------------------------------------------------------
# sparQ - Update Check
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Update service (WordPress-style).

Once a day, sparQ contacts the sparQ update service to learn whether a newer or
security-related release is available. To let the service return compatible
update information, the request sends a small, **non-identifying** payload
describing the software and its environment:

    product, sparq_version, edition, operating_system, architecture,
    runtime_version, locale, and the installed sparQ modules + versions.

It deliberately sends **no** identifying information — no usernames, emails,
customer/organization names, repository names or contents, source code, commit
or developer activity, hostnames, full IP addresses, credentials, and **no
persistent installation identifier**. See :func:`build_payload` for the exact
contents; the disclosure lives in the README, the first-boot notice, and
``/legal/telemetry`` on gosparq.com.

It is enabled by default and can be disabled with ``SPARQ_UPDATE_CHECK=false``
(air-gapped / restricted environments). The check runs off the request path in
a background daemon thread, uses a short timeout, never blocks startup, and
silently does nothing on any error — a failed request simply retries at the next
scheduled check.

Example:
    Started once during app boot (production only)::

        from system.update_check import start_update_check_scheduler
        start_update_check_scheduler(app)
"""

from __future__ import annotations

import json
import logging
import os
import platform
import threading
import time
from datetime import date
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flask import Flask

logger = logging.getLogger(__name__)

DEFAULT_CHECK_URL = "https://www.gosparq.com/api/v1/check"
EDITION = "community"
_STATE_FILENAME = ".sparq-last-update-check"
_STATUS_FILENAME = ".sparq-update-status.json"
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


def _check_url() -> str:
    """Return the update-service endpoint (overridable via ``SPARQ_CHECK_URL``)."""
    return os.environ.get("SPARQ_CHECK_URL", DEFAULT_CHECK_URL)


def _data_dir() -> str:
    """Return the data directory (``SPARQ_DATA_DIR`` or ``<pulse>/data``)."""
    if "SPARQ_DATA_DIR" in os.environ:
        return os.environ["SPARQ_DATA_DIR"]
    pulse_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(pulse_root, "data")


def _state_file() -> str:
    return os.path.join(_data_dir(), _STATE_FILENAME)


def _status_file() -> str:
    return os.path.join(_data_dir(), _STATUS_FILENAME)


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


def _write_status(status: dict[str, Any]) -> None:
    """Persist the latest check result for the Settings → Updates page."""
    try:
        os.makedirs(_data_dir(), exist_ok=True)
        with open(_status_file(), "w", encoding="utf-8") as fh:
            json.dump(status, fh)
    except OSError as exc:
        logger.debug("Could not persist update status: %s", exc)


def read_status() -> dict[str, Any] | None:
    """Return the last recorded check result, or None if never checked."""
    try:
        with open(_status_file(), encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _locale() -> str:
    """Return a best-effort locale string (``SPARQ_LOCALE`` override, else system)."""
    override = os.environ.get("SPARQ_LOCALE")
    if override:
        return override
    try:
        import locale as _loc

        code = _loc.getlocale()[0]
        if code:
            return code.replace("_", "-")
    except Exception:  # noqa: BLE001 — locale probing is best-effort
        pass
    return "en"


def _installed_modules() -> list[dict[str, str]]:
    """Return the enabled sparQ modules and their versions (no other metadata).

    Reads the manifests the loader stashed in ``INSTALLED_MODULES``; returns an
    empty list if no app context / config is available.
    """
    try:
        from flask import current_app

        manifests = current_app.config.get("INSTALLED_MODULES", {}) or {}
    except Exception:  # noqa: BLE001 — no app context is a non-fatal condition
        return []

    modules: list[dict[str, str]] = []
    for manifest in manifests.values():
        if not manifest.get("enabled", True):
            continue
        name = manifest.get("module_dir") or manifest.get("name")
        version = manifest.get("version")
        if name and version:
            modules.append({"name": str(name), "version": str(version)})
    modules.sort(key=lambda m: m["name"])
    return modules


def build_payload() -> dict[str, Any]:
    """Build the non-identifying update-check payload.

    Contains only software/environment facts needed for update compatibility and
    support planning. Contains **no** PII, workspace content, or persistent
    installation identifier. Any change here must be mirrored in the README, the
    first-boot notice, ``.env.example``, and the ``/legal/telemetry`` disclosure.
    """
    from system.version import get_version

    return {
        "product": "sparq",
        "sparq_version": get_version(),
        "edition": EDITION,
        "operating_system": platform.system().lower(),
        "architecture": platform.machine().lower(),
        "runtime_version": f"python{platform.python_version()}",
        "locale": _locale(),
        "installed_modules": _installed_modules(),
    }


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


def _post_check(url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """POST the payload to the update service and return the parsed response.

    Returns None on any network, timeout, HTTP, or JSON error — all non-fatal.
    """
    try:
        import requests

        version = payload.get("sparq_version", "")
        response = requests.post(
            url,
            json=payload,
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": f"sparQ/{version}"},
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None
    except Exception as exc:  # noqa: BLE001 — network/timeout/bad JSON are non-fatal
        logger.debug("Update check request failed: %s", exc)
        return None


def run_check(force: bool = False) -> dict[str, Any] | None:
    """Perform one update check and return the recorded status (or None).

    No-ops (returns None) when disabled or already checked today (unless
    ``force``). Records the check date and status only on a successful response,
    so a transient failure retries later rather than burning the day's slot.
    Never raises.

    Args:
        force: Skip the once-per-day guard (used for manual checks / tests).

    Returns:
        The status dict written to disk, or None when nothing was checked.
    """
    if not is_enabled():
        return None
    if not force and _checked_today():
        return read_status()

    payload = build_payload()
    data = _post_check(_check_url(), payload)
    if data is None:
        return None

    _record_check()

    current = str(payload["sparq_version"])
    latest = data.get("latest_version")
    latest = latest if isinstance(latest, str) else None
    update_available = bool(data.get("update_available")) or (
        latest is not None and is_newer(latest, current)
    )
    release_url = data.get("release_url")
    status: dict[str, Any] = {
        "checked_on": date.today().isoformat(),
        "current_version": current,
        "latest_version": latest,
        "update_available": update_available,
        "security_update": bool(data.get("security_update")),
        "release_url": release_url if isinstance(release_url, str) else None,
    }
    _write_status(status)

    if update_available:
        # WARNING, not INFO: the `system` logger is set to WARNING in non-verbose
        # (production) mode, and this once-a-day notice must reach the operator.
        logger.warning(
            "A newer sparQ version is available: %s (installed: %s). Release notes: %s",
            latest,
            current,
            status["release_url"] or "https://gosparq.com",
        )
    else:
        logger.debug("sparQ is up to date (installed: %s, latest: %s)", current, latest)

    return status


def _run_in_context(app: Flask) -> None:
    """Run a single check inside an app context, swallowing any error."""
    with app.app_context():
        try:
            run_check()
        except Exception as exc:  # noqa: BLE001 — a background check must never crash
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
        "Update check enabled (daily check to %s reports version/OS/module info; "
        "disable with SPARQ_UPDATE_CHECK=false)",
        _check_url(),
    )
