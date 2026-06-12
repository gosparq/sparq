# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Language and localization utility functions.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from typing import Any


def get_user_language(user: Any) -> str:
    """Get user's language, falling back to company default if not set"""
    if user.settings and user.settings.language:
        return user.settings.language
    # TODO: get company default language if user language is not set
    # return get_company_settings().default_language
    return "en"
