# -----------------------------------------------------------------------------
# sparQ - OAuth System
#
# Description:
#     OAuth 2.0 / OpenID Connect authentication system supporting multiple
#     identity providers (Google, Microsoft, GitHub, LinkedIn).
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from .service import oauth, init_oauth
from .token_manager import TokenManager

__all__ = ["oauth", "init_oauth", "TokenManager"]
