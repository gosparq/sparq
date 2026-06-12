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

"""Internationalization (i18n) system for multi-language support.

This package provides translation, date/number formatting, and
industry-specific terminology support for sparQ applications.

Functions:
    translate: Translate a string with industry term support.
    preload_translations: Load all translations into memory at startup.
    format_date: Format a date according to locale patterns.
    format_datetime: Format a datetime with timezone conversion.
    format_number: Format a number with locale-specific separators.

The translation system supports:
- Module-specific translations in lang/ folders
- Language packs from data/lang_packs/
- App-specific translations from data/modules/apps/*/lang/
- Industry terminology overrides (e.g., "Jobs" -> "Projects")

Example:
    Using the translate function in templates::

        {{ _("Hello") }}
        {{ _("Save") }}

    Using in Python code::

        from system.i18n import translate as _

        message = _("Welcome back!")

    Formatting dates and numbers::

        from system.i18n.translation import format_date, format_number

        date_str = format_date(order.created_at, "long")
        price_str = format_number(order.total, decimal_places=2)
"""

from .translation import preload_translations, translate, format_date, format_datetime, format_number

__all__ = ["translate", "preload_translations", "format_date", "format_datetime", "format_number"]
