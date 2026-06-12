# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Sync module controllers.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from flask import Blueprint

# Create blueprint
blueprint = Blueprint(
    "sync_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)

# Import routes after blueprint creation
from . import routes  # noqa: E402, F401
from . import chat  # noqa: E402, F401
from . import dm  # noqa: E402, F401
from . import calendar  # noqa: E402, F401
from . import websocket  # noqa: E402, F401
from . import webhook_admin  # noqa: E402, F401
from . import posts  # noqa: E402, F401
from . import follow  # noqa: E402, F401
from . import areas  # noqa: E402, F401
from . import blockers  # noqa: E402, F401
from . import week_review  # noqa: E402, F401
