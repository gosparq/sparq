# -----------------------------------------------------------------------------
# sparQ - Resources Module
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

from system.module.hooks import hookimpl


class ResourcesModule:
    def get_routes(self):
        from .controllers.docs import docs_blueprint
        from .controllers.forms import forms_blueprint
        from .controllers.kb_public import kb_blueprint
        from .controllers.kb_staff import kb_staff_blueprint
        from .controllers.knowledge import knowledge_blueprint
        from .controllers.esign import esign_blueprint
        from .controllers.sign import sign_blueprint
        from .controllers.settings import settings_blueprint
        from .controllers.drive import drive_blueprint
        from .controllers.notes import notes_blueprint
        from .controllers.working_agreement import working_agreement_bp

        return [
            (docs_blueprint, "/resources/docs"),
            (forms_blueprint, "/resources/forms"),
            (knowledge_blueprint, "/resources/knowledge"),
            (kb_staff_blueprint, "/resources/knowledge/browse"),
            (kb_blueprint, "/kb"),
            (esign_blueprint, "/resources/esign"),
            (sign_blueprint, "/sign"),  # Public signing routes (no /resources prefix)
            (settings_blueprint, "/resources/settings"),
            (drive_blueprint, "/resources/drive"),
            (notes_blueprint, "/resources/notes"),
            (working_agreement_bp, "/resources/working-agreement"),
        ]

    @hookimpl
    def init_database(self) -> None:
        # Schema creation is handled centrally by app.py
        from .services.storage import ensure_directories

        ensure_directories()
