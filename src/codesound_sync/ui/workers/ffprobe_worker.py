"""
FFprobe worker – runs media probing on a background QThread so the UI
never blocks during analysis.

Signals
-------
media_ready(MediaInfo) Emitted on success.
error(str)             Emitted on any failure with a human-readable message.
progress(str)          Emitted with status text suitable for the status panel.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from codesound_sync.models.media_info import MediaInfo
from codesound_sync.services.ffmpeg_service import (
    FFmpegNotFoundError,
    MediaProbeError,
    probe_media,
)

log = logging.getLogger(__name__)


class FFprobeWorker(QThread):
    """Background thread that probes a video file with ffprobe."""

    media_ready = Signal(object)  # MediaInfo
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, video_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._video_path = video_path

    def run(self) -> None:  # noqa: D102
        self.progress.emit(f"Analysing: {self._video_path.name} …")
        log.info("FFprobeWorker started for: %s", self._video_path.name)
        try:
            info = probe_media(self._video_path)
            log.info("FFprobeWorker finished successfully")
            self.media_ready.emit(info)
        except FFmpegNotFoundError as exc:
            log.error("FFmpeg not found: %s", exc)
            self.error.emit(str(exc))
        except MediaProbeError as exc:
            log.error("Media probe error: %s", exc)
            self.error.emit(str(exc))
        except FileNotFoundError as exc:
            log.error("File not found: %s", exc)
            self.error.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected error in FFprobeWorker")
            self.error.emit(f"Unexpected error: {type(exc).__name__}: {exc}")
