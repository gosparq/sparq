# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module controllers.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from typing import Any

from flask import Blueprint

from ..utils.filters import init_filters

# Create blueprint
blueprint = Blueprint(
    "people_bp",
    __name__,
    template_folder="../views/templates",
    static_folder="../views/assets",
    static_url_path="/assets",
)

# Initialize filters with blueprint
init_filters(blueprint)


@blueprint.context_processor
def inject_presence_settings() -> dict[str, Any]:
    """Inject time tracking settings into People templates for mobile nav tabs."""
    from modules.base.presence.controllers import presence_context

    return presence_context()

# Import routes after blueprint creation
from . import people  # noqa: E402, F401
from . import onboarding  # noqa: E402, F401
from . import invite  # noqa: E402, F401
from . import hiring  # noqa: E402, F401 (merged from hiring module)
from . import taxforms  # noqa: E402, F401 (1099-NEC tax forms)
from . import one_on_one  # noqa: E402, F401 (1:1 tracker)
from . import calendar_proxy  # noqa: E402, F401 (calendar + timesheets under People)
