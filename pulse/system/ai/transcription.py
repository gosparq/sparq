# -----------------------------------------------------------------------------
# sparQ - Audio Transcription
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Server-side audio transcription using OpenAI gpt-4o-mini-transcribe."""

import logging
import os
from typing import BinaryIO

logger = logging.getLogger(__name__)


def transcribe_audio(file: BinaryIO, filename: str = "audio.webm") -> str | None:
    """Transcribe an audio file using OpenAI gpt-4o-mini-transcribe.

    Args:
        file: File-like object containing audio data.
        filename: Original filename (used for format detection by the API).

    Returns:
        Transcript text with proper punctuation, or None on failure.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not configured — skipping transcription")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        result = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
            file=(filename, file),
        )
        return result.text
    except Exception:
        logger.exception("Audio transcription failed")
        return None
