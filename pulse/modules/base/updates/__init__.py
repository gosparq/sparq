# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.

"""Updates module — status updates, channels, chat, and calendar.

Key Features:
    - Channels (real-time messaging via UpdatePost)
    - Template-driven posts (updates, wins)
    - Direct messages with 10-4 acknowledgments
    - Calendar events
    - Webhooks
"""

from .module import UpdatesModule

# Import all models to ensure they're registered with SQLAlchemy
from .models.acknowledgment import DMAck, UpdatePostAck
from .models.channel import UpdateChannel
from .models.channel_read_state import UpdateChannelReadState
from .models.dm import DM, DMThread, DMReaction
from .models.event import Event
from .models.post import UpdatePost
from .models.post_reaction import UpdatePostReaction
from .models.template import UpdateTemplate

module_instance = UpdatesModule()

__all__ = [
    "module_instance",
    "UpdateChannel",
    "UpdateChannelReadState",
    "UpdatePost",
    "UpdatePostAck",
    "UpdatePostReaction",
    "UpdateTemplate",
    "DMAck",
    "DM",
    "DMThread",
    "DMReaction",
    "Event",
]
