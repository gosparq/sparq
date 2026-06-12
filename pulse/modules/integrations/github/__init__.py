# Copyright (c) 2025-2026 remarQable LLC

from .module import GitHubModule
from . import provider  # noqa: F401 — triggers GitHubProvider self-registration

module_instance = GitHubModule()

__all__ = ["module_instance"]
