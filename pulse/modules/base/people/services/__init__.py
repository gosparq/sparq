# -----------------------------------------------------------------------------
# sparQ
#
# Description:
#     Team module services initialization.
#
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
#
# -----------------------------------------------------------------------------

from .resume_parser import parse_resume, is_supported_file, ParsedResume, ParsedField

__all__ = [
    "parse_resume",
    "is_supported_file",
    "ParsedResume",
    "ParsedField",
]
