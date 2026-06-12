# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Translation module that provides core translation functionality including
#     preloading translations, custom translation function, and formatting functions.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

"""Core translation functionality for sparQ internationalization.

This module handles loading translations from JSON files and providing
the translation function used throughout the application.

Translation Loading:
    Translations are loaded from three sources in order:
    1. Module lang/ folders (en.json for English base)
    2. Language packs from data/lang_packs/ (community translations)
    3. App translations from data/modules/apps/*/lang/

Translation Lookup:
    When translating, the system checks:
    1. Industry-specific terminology overrides
    2. Current module's translations
    3. Core module translations as fallback
    4. Original text if no translation found

Functions:
    preload_translations: Load all JSON translation files into memory.
    translate: Translate a string with industry term and i18n support.
    format_date: Format a date using locale patterns.
    format_datetime: Format a datetime with timezone conversion.
    format_number: Format numbers with locale separators.
    get_format_patterns: Get formatting patterns for current language.

Example:
    Preload translations at app startup::

        @app.before_first_request
        def load_i18n():
            preload_translations()

    Use the translate function::

        from system.i18n.translation import translate

        greeting = translate("Hello")  # Returns translated string
"""

import json
import os
from datetime import datetime, date
from typing import Any

from flask import current_app
from flask import g

_TZ_UNSET = object()


def _resolve_user_timezone() -> str:
    """Per-request cached lookup for the active user's timezone.

    The chain is: UserSetting('timezone') → company_settings → default. This
    runs once per ``format_datetime`` call from templates; without caching, a
    feed page issues 10+ duplicate ``user_setting`` queries.
    """
    cached = getattr(g, "_user_tz_name_cache", _TZ_UNSET)
    if cached is not _TZ_UNSET:
        return cached

    tz_name = None
    try:
        from flask_login import current_user

        from modules.base.core.models.user_setting import UserSetting

        if getattr(current_user, "is_authenticated", False):
            tz_name = UserSetting.get(current_user.id, "timezone")
    except Exception:
        tz_name = None

    if not tz_name:
        company_settings = g.get("company_settings") if hasattr(g, "get") else None
        tz_name = company_settings.timezone if company_settings else "America/Chicago"

    try:
        g._user_tz_name_cache = tz_name
    except Exception:
        pass  # outside request/app context — caller will just re-resolve
    return tz_name

# Store translations in memory
TRANSLATIONS: dict[str, dict[str, dict[str, Any]]] = {}


def _get_data_dir() -> str:
    """Get the data directory path."""
    return os.environ.get("SPARQ_DATA_DIR", os.path.join(current_app.root_path, "data"))


def preload_translations() -> None:
    """Load all translations into memory at startup.

    Translation sources (in order):
    1. Module lang/ folders (English overrides only - en.json)
    2. Language packs from data/lang_packs/ (all non-English languages)
    3. App translations from data/modules/apps/*/lang/ (app-specific)
    """
    global TRANSLATIONS
    TRANSLATIONS = {}

    modules_path = os.path.join(current_app.root_path, "modules")

    # 1. Load all translations from module lang/ folders
    # Each module can have en.json, es.json, etc. in its lang/ folder
    for folder in ["base"]:
        folder_path = os.path.join(modules_path, folder)
        if not os.path.isdir(folder_path):
            continue

        for module_name in os.listdir(folder_path):
            module_path = os.path.join(folder_path, module_name)
            if not os.path.isdir(module_path):
                continue

            module_lang_path = os.path.join(module_path, "lang")
            if not os.path.isdir(module_lang_path):
                continue

            # Load all language files from module's lang folder
            for lang_file in os.listdir(module_lang_path):
                if lang_file.endswith(".json"):
                    lang_code = lang_file.replace(".json", "")
                    file_path = os.path.join(module_lang_path, lang_file)

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            TRANSLATIONS.setdefault(lang_code, {}).setdefault(module_name, {}).update(
                                json.load(f)
                            )
                    except (json.JSONDecodeError, IOError) as e:
                        current_app.logger.warning(f"Failed to load module translation {file_path}: {e}")

    # 2. Load language packs from data/lang_packs/
    lang_packs_path = os.path.join(_get_data_dir(), "lang_packs")
    if os.path.isdir(lang_packs_path):
        for lang_code in os.listdir(lang_packs_path):
            pack_path = os.path.join(lang_packs_path, lang_code)
            if not os.path.isdir(pack_path):
                continue

            for module_file in os.listdir(pack_path):
                if module_file.endswith(".json") and module_file != "manifest.json":
                    module_name = module_file.replace(".json", "")
                    file_path = os.path.join(pack_path, module_file)

                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            TRANSLATIONS.setdefault(lang_code, {}).setdefault(module_name, {}).update(
                                json.load(f)
                            )
                    except (json.JSONDecodeError, IOError) as e:
                        current_app.logger.warning(f"Failed to load translation {file_path}: {e}")

    # 3. Load app translations from data/modules/apps/*/lang/
    # Apps manage their own translations (all languages)
    data_apps_path = os.path.join(_get_data_dir(), "modules", "apps")
    if os.path.isdir(data_apps_path):
        for app_name in os.listdir(data_apps_path):
            app_path = os.path.join(data_apps_path, app_name)
            if not os.path.isdir(app_path):
                continue

            app_lang_path = os.path.join(app_path, "lang")
            if os.path.isdir(app_lang_path):
                for lang_file in os.listdir(app_lang_path):
                    if lang_file.endswith(".json"):
                        lang_code = lang_file.replace(".json", "")
                        file_path = os.path.join(app_lang_path, lang_file)

                        try:
                            with open(file_path, "r", encoding="utf-8") as f:
                                TRANSLATIONS.setdefault(lang_code, {}).setdefault(app_name, {}).update(
                                    json.load(f)
                                )
                        except (json.JSONDecodeError, IOError) as e:
                            current_app.logger.warning(f"Failed to load app translation {file_path}: {e}")


def translate(text: str) -> str:
    """Custom translation function with industry terminology support.

    This function first checks for industry-specific terminology overrides
    (e.g., "Jobs" -> "Projects" for Professional Services), then applies
    standard i18n translation.
    """
    from system.terminology import get_industry_term

    # 1. Check for industry-specific term first
    text = get_industry_term(text)

    # 2. Proceed with normal i18n translation
    lang = g.get("lang", current_app.config.get("DEFAULT_LANGUAGE", "en"))
    current_module = g.get("current_module", {}).get("module_dir", "core")

    # If we're not in the core module, try the module-specific translation
    if current_module != "core":
        module_trans = TRANSLATIONS.get(lang, {}).get(current_module, {}).get(text)
        # Only use module translation if it's nonempty
        if module_trans is not None and module_trans != "":
            return module_trans

    # Fallback to core translation
    core_trans = TRANSLATIONS.get(lang, {}).get("core", {}).get(text)
    if core_trans is not None and core_trans != "":
        return core_trans

    # Finally, return the text (possibly industry-modified) if no translation found
    return text


# Create alias for translate function
_ = translate

# Export both names
__all__ = [
    "translate",
    "_",
    "preload_translations",
    "format_date",
    "format_day_name",
    "format_datetime",
    "format_number",
    "get_format_patterns",
]


def get_format_patterns(lang: str | None = None) -> dict[str, Any]:
    """Get formatting patterns for the current language"""
    if not lang:
        lang = g.get("lang", current_app.config.get("DEFAULT_LANGUAGE", "en"))

    # Get patterns from core module first (defaults)
    patterns = TRANSLATIONS.get(lang, {}).get("core", {}).get("_meta", {}).copy()

    # Override with current module patterns if they exist, but only if the value is nonempty.
    current_module = g.get("current_module", {}).get("module_dir", "core")
    module_patterns = TRANSLATIONS.get(lang, {}).get(current_module, {}).get("_meta", {})

    for key, value in module_patterns.items():
        # Only override if the module value is not empty
        if value:
            patterns[key] = value

    return patterns


def format_day_name(date: datetime | date, style: str = "full") -> str:
    """Return locale-aware day name for a date."""
    patterns = get_format_patterns()
    day_names = patterns.get("day_names", {})
    names = day_names.get(style, [])
    weekday = date.weekday()  # 0=Monday, 6=Sunday
    if weekday < len(names):
        return names[weekday]
    return date.strftime("%A" if style == "full" else "%a")


def format_date(date: datetime | date | str | None, format_type: str = "medium") -> str:
    """Format a date according to the current language patterns."""
    if not date:
        return ""

    patterns = get_format_patterns()
    date_formats = patterns.get("date_formats", {})
    pattern = date_formats.get(format_type, "%Y-%m-%d")  # Default pattern in strftime format

    # Track which month tokens are used before converting
    has_full_month = "MMMM" in pattern
    has_short_month = not has_full_month and "MMM" in pattern

    # Convert pattern from our format to strftime format
    pattern = (
        pattern.replace("YYYY", "%Y")
        .replace("MMMM", "%B")  # Full month name (before MM)
        .replace("MMM", "%b")   # Abbreviated month name (before MM)
        .replace("MM", "%m")
        .replace("DD", "%d")
        .replace("HH", "%H")
        .replace("mm", "%M")
    )

    try:
        if isinstance(date, str):
            date = datetime.strptime(date, "%Y-%m-%d")

        result = date.strftime(pattern)

        # Replace English month names with locale-specific names
        month_names = patterns.get("month_names")
        if month_names and (has_full_month or has_short_month):
            month_idx = date.month - 1  # 0-based
            if has_full_month:
                full_names = month_names.get("full", [])
                if month_idx < len(full_names):
                    en_full = date.strftime("%B")
                    result = result.replace(en_full, full_names[month_idx])
            elif has_short_month:
                short_names = month_names.get("short", [])
                if month_idx < len(short_names):
                    en_short = date.strftime("%b")
                    result = result.replace(en_short, short_names[month_idx])

        return result
    except (ValueError, AttributeError) as e:
        current_app.logger.error(f"Error formatting date: {e}")
        return str(date)


def format_datetime(
    dt: datetime | None,
    format_str: str = "%b %d, %Y %H:%M",
    show_date_only: bool = False,
) -> str:
    """Format a datetime, converting from UTC to the configured timezone.

    Args:
        dt: A datetime object (assumed to be in UTC if naive)
        format_str: strftime format string
        show_date_only: If True, uses '%b %d, %Y' format

    Returns:
        Formatted datetime string in the configured timezone
    """
    if not dt:
        return "-"

    try:
        import pytz  # type: ignore[import-untyped]

        # Resolve timezone: user preference → workspace setting → default.
        # Matches the canonical chain used by nudges and action items
        # (see system/tasks/system_triggers.py, system/sync/nudge_scheduler.py).
        tz_name = _resolve_user_timezone()
        local_tz = pytz.timezone(tz_name)

        # Assume naive datetimes are UTC
        if dt.tzinfo is None:
            dt = pytz.UTC.localize(dt)

        # Convert to local timezone
        local_dt = dt.astimezone(local_tz)

        if show_date_only:
            return local_dt.strftime("%b %d, %Y")
        return local_dt.strftime(format_str)
    except Exception as e:
        current_app.logger.error(f"Error formatting datetime: {e}")
        # Fallback to original formatting
        if show_date_only:
            return dt.strftime("%b %d, %Y")
        return dt.strftime(format_str)


def format_number(number: float | int, decimal_places: int = 2) -> str:
    """Format a number according to the current language patterns"""
    patterns = get_format_patterns()
    formats = patterns.get("number_formats", {})
    decimal_sep = formats.get("decimal_separator", ".")
    thousand_sep = formats.get("thousand_separator", ",")

    # Format number with proper separators
    number_str = f"{number:,.{decimal_places}f}"
    if thousand_sep != ",":
        number_str = number_str.replace(",", thousand_sep)
    if decimal_sep != ".":
        number_str = number_str.replace(".", decimal_sep)

    return number_str
