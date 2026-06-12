# -----------------------------------------------------------------------------
# sparQ - Resources Controllers
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from .docs import docs_blueprint
from .forms import forms_blueprint
from .kb_public import kb_blueprint
from .kb_staff import kb_staff_blueprint
from .knowledge import knowledge_blueprint
from .drive import drive_blueprint
from .notes import notes_blueprint

__all__ = [
    "docs_blueprint",
    "forms_blueprint",
    "kb_blueprint",
    "kb_staff_blueprint",
    "knowledge_blueprint",
    "drive_blueprint",
    "notes_blueprint",
]
