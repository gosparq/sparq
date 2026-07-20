# -----------------------------------------------------------------------------
# sparQ - Audio Transcoding Service
# Copyright (c) 2025-2026 sparQ Software LLC. Licensed under AGPL-3.0.
# -----------------------------------------------------------------------------

"""Transcode browser-recorded audio into a cross-platform playable format.

Browsers record voice notes with ``MediaRecorder``, which on Chrome/Firefox/
Android produces ``audio/webm; codecs=opus``. iOS Safari/WebKit cannot reliably
decode Opus (or Vorbis) in a WebM/Ogg container in an HTML5 ``<audio>`` element,
so those clips fail to play on many iPhones. AAC audio in an MP4 (``.m4a``)
container plays on every current browser and operating-system version, so this
service transcodes WebM/Ogg uploads to AAC/MP4.

The heavy lifting runs off the HTTP request (see ``system.background``), so the
user never waits for it, and every failure path leaves the original file intact.

Example:
    Transcode a freshly uploaded clip in the background::

        from system.background import submit_task
        from modules.base.resources.services import audio

        submit_task(audio.transcode_attachment_async, attachment.uuid)
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.attachment import Attachment

logger = logging.getLogger(__name__)

# Base MIME types iOS/WebKit cannot reliably decode in <audio> (Opus/Vorbis).
TRANSCODE_SOURCE_TYPES = {"audio/webm", "audio/ogg"}

_TARGET_EXTENSION = ".m4a"
_TARGET_MIME = "audio/mp4"
_TIMEOUT_SECONDS = 120


def _ffmpeg_exe() -> str | None:
    """Locate an ffmpeg binary.

    Prefers the binary bundled with the ``imageio-ffmpeg`` wheel (so no system
    package is required in the container), falling back to an ffmpeg on PATH.

    Returns:
        Absolute path to an ffmpeg executable, or None if none is available.
    """
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg")


def transcode_attachment(attachment: Attachment) -> bool:
    """Transcode a WebM/Ogg audio attachment in place to AAC in an MP4 container.

    On success the stored file is replaced with an ``.m4a`` file and the
    attachment's ``filename``, ``mime_type`` and ``size_bytes`` are updated to
    match; the original file is then removed. On any failure (unsupported type,
    missing file, no ffmpeg, transcode error) the attachment and its original
    file are left completely untouched.

    Args:
        attachment: An Attachment whose stored file is WebM/Ogg audio.

    Returns:
        True if the file was transcoded, False if skipped or on failure.
    """
    from system.db.database import db
    from . import storage

    base_type = (attachment.mime_type or "").split(";")[0].strip()
    if base_type not in TRANSCODE_SOURCE_TYPES:
        return False

    src_path = storage.get_attachment_path(attachment)
    if not os.path.exists(src_path):
        logger.warning("Audio transcode skipped, source file missing: %s", src_path)
        return False

    exe = _ffmpeg_exe()
    if not exe:
        logger.warning("ffmpeg unavailable — leaving audio %s as %s", attachment.uuid, base_type)
        return False

    uuid = attachment.uuid
    original_filename = attachment.filename
    dest_path = os.path.join(storage.get_attachments_dir(), uuid + _TARGET_EXTENSION)

    # Release any open transaction BEFORE the (multi-second) ffmpeg run. Holding a
    # transaction across the subprocess pins a database connection — and on SQLite,
    # whose single writer serializes everything, it blocks concurrent web requests
    # until ffmpeg finishes. Transcode with no lock held; write briefly afterwards.
    db.session.rollback()

    try:
        result = subprocess.run(
            [
                exe, "-nostdin", "-y",
                "-i", src_path,
                "-vn",                        # drop any video track
                "-c:a", "aac", "-b:a", "128k",  # AAC-LC, transparent for voice
                "-movflags", "+faststart",    # moov atom up front for iOS streaming
                dest_path,
            ],
            capture_output=True,
            timeout=_TIMEOUT_SECONDS,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.error("Audio transcode did not run for %s: %s", uuid, exc)
        _cleanup(dest_path)
        return False

    if result.returncode != 0 or not os.path.exists(dest_path):
        logger.error("ffmpeg transcode failed for %s (rc=%s)", uuid, result.returncode)
        _cleanup(dest_path)
        return False

    new_filename = (
        original_filename.rsplit(".", 1)[0] + _TARGET_EXTENSION
        if "." in original_filename
        else original_filename + _TARGET_EXTENSION
    )
    new_size = os.path.getsize(dest_path)

    if not _apply_transcode(attachment, new_filename, new_size):
        _cleanup(dest_path)  # keep the original; drop the orphan output
        return False

    if src_path != dest_path and os.path.exists(src_path):
        try:
            os.remove(src_path)
        except OSError:
            logger.warning("Could not remove original audio file: %s", src_path)

    logger.info("Transcoded audio attachment %s to AAC/MP4", uuid)
    return True


def _apply_transcode(attachment: Attachment, new_filename: str, new_size: int) -> bool:
    """Persist the transcoded file's metadata in a short, retried commit.

    The write window is tiny, but SQLite's single writer can briefly be held by a
    concurrent web request, so retry a couple of times before giving up. On
    PostgreSQL this single-row update won't contend and succeeds first try.

    Args:
        attachment: The attachment to update.
        new_filename: Filename with the ``.m4a`` extension.
        new_size: Size of the transcoded file in bytes.

    Returns:
        True if committed, False if the database stayed locked.
    """
    from sqlalchemy.exc import OperationalError

    from system.db.database import db

    for attempt in range(3):
        try:
            attachment.filename = new_filename
            attachment.mime_type = _TARGET_MIME
            attachment.size_bytes = new_size
            db.session.commit()
            return True
        except OperationalError:
            db.session.rollback()
            if attempt == 2:
                logger.error("Audio transcode commit failed (database locked): %s", attachment.uuid)
                return False
            time.sleep(0.5)
    return False


def transcode_attachment_async(attachment_uuid: str) -> None:
    """Look up an attachment by UUID and transcode it.

    This is the entry point handed to ``system.background.submit_task`` so the
    work runs in a background thread after the HTTP request has returned.

    Args:
        attachment_uuid: UUID of the attachment to transcode.
    """
    from ..models.attachment import Attachment

    attachment = Attachment.get_by_uuid(attachment_uuid)
    if attachment is not None:
        transcode_attachment(attachment)


def _cleanup(path: str) -> None:
    """Remove a partial/failed transcode output if it exists."""
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
