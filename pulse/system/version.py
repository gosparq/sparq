# -----------------------------------------------------------------------------
# sparQ - Version Management
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Version utilities for production mode detection and build info."""

import subprocess
from datetime import datetime
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
VERSION_FILE = PROJECT_ROOT / "VERSION"
BUILD_FILE = PROJECT_ROOT / "BUILD"


def _get_base_version() -> str:
    """Read major.minor from VERSION file, or 'dev' if not present."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return "dev"


def _get_patch_from_git(base_version: str) -> int | None:
    """Count commits since tag v{base_version}.0, or None if unavailable."""
    if base_version == "dev":
        return None
    tag = f"v{base_version}.0"
    try:
        result = subprocess.run(
            ["git", "rev-list", f"{tag}..HEAD", "--count"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    return None


def _get_version_from_build_file() -> str | None:
    """Extract version from BUILD file (format: VERSION+HASH.TIMESTAMP)."""
    if BUILD_FILE.exists():
        content = BUILD_FILE.read_text().strip()
        # Format: 0.5.23+abc1234.241214-1530
        if "+" in content:
            return content.split("+")[0]
    return None


def get_version() -> str:
    """Get version with computed patch number."""
    # Try BUILD file first (Docker deployment)
    baked = _get_version_from_build_file()
    if baked:
        return baked

    # Read VERSION file
    base = _get_base_version()
    if base == "dev":
        return "dev"

    # If VERSION has full version (3 parts), use it directly (public repo)
    if base.count(".") >= 2:
        return base

    # Compute patch from git (monorepo)
    patch = _get_patch_from_git(base)
    if patch is not None:
        return f"{base}.{patch}"

    # No git, no BUILD file - return base.0
    return f"{base}.0"


def is_production() -> bool:
    """Check if running in production mode (debug mode is off)."""
    from flask import current_app
    try:
        return not current_app.debug
    except RuntimeError:
        # Outside application context — assume production
        return True


def get_build_info() -> tuple[str, str]:
    """
    Get build hash and timestamp.

    Returns (hash, timestamp) where:
    - hash: git commit hash (7 chars) or "dev"
    - timestamp: YYMMDD-HHMM format

    Priority:
    1. BUILD file (Docker container)
    2. Git (local dev)
    3. Fallback to "dev" with current timestamp
    """
    # Try BUILD file first (Docker) - handles both formats
    if BUILD_FILE.exists():
        content = BUILD_FILE.read_text().strip()
        if "+" in content:
            # New format: 0.5.23+abc1234.241214-1530
            after_plus = content.split("+", 1)[1]  # abc1234.241214-1530
            parts = after_plus.split(".", 1)
            if len(parts) == 2:
                return parts[0], parts[1]
        else:
            # Legacy format: abc1234.241214-1530
            parts = content.split(".", 1)
            if len(parts) == 2:
                return parts[0], parts[1]

    # Try git (local dev)
    try:
        git_hash = (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                cwd=PROJECT_ROOT,
            )
            .decode()
            .strip()
        )
        # Get the commit timestamp instead of current time
        commit_timestamp = (
            subprocess.check_output(
                ["git", "log", "-1", "--format=%cd", "--date=format:%y%m%d-%H%M"],
                stderr=subprocess.DEVNULL,
                cwd=PROJECT_ROOT,
            )
            .decode()
            .strip()
        )
        return git_hash, commit_timestamp
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Fallback
    return "dev", datetime.now().strftime("%y%m%d-%H%M")


def get_full_version() -> str:
    """
    Get full version string with build info.

    Format: 0.5.23+abc1234.241214-1530
    - 0.5.23 = version with computed patch
    - abc1234 = git commit hash
    - 241214-1530 = build timestamp (YYMMDD-HHMM)
    """
    version = get_version()
    git_hash, timestamp = get_build_info()
    return f"{version}+{git_hash}.{timestamp}"


def get_display_version() -> str:
    """
    Get user-friendly version display string.

    Format: v0.5.199 (Mar 04, 8:44PM)
    - v0.5.199 = version with 'v' prefix
    - (Mar 04, 8:44PM) = build date in parentheses
    """
    version = get_version()
    build_date = get_build_date_display()
    return f"v{version} ({build_date})"


def get_version_info() -> dict:
    """Get version information dict."""
    git_hash, timestamp = get_build_info()
    return {
        "version": get_version(),
        "full_version": get_full_version(),
        "display_version": get_display_version(),
        "build_date_display": get_build_date_display(),
        "git_hash": git_hash,
        "build_time": timestamp,
        "mode": "production" if is_production() else "development",
    }


def get_build_date_display() -> str:
    """
    Get user-friendly build date string.

    Converts YYMMDD-HHMM format to "Jan 21, 8:44PM"
    """
    _, timestamp = get_build_info()
    try:
        # Parse YYMMDD-HHMM format
        dt = datetime.strptime(timestamp, "%y%m%d-%H%M")
        # Format as "Jan 21, 8:44PM"
        hour = dt.hour
        am_pm = "AM" if hour < 12 else "PM"
        hour_12 = hour % 12 or 12
        return dt.strftime(f"%b %d, {hour_12}:%M{am_pm}")
    except ValueError:
        return timestamp
