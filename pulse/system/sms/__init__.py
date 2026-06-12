# -----------------------------------------------------------------------------
# sparQ - SMS Service
#
# Description:
#     SMS sending service for passwordless authentication via phone.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from .service import send_sms, is_configured

__all__ = ["send_sms", "is_configured"]
