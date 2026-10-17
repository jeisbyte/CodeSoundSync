"""Background worker for local video activity analysis."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from codesound_sync.models.activity_candidate import ActivityAnalysisResult
from codesound_sync.services.activity_analysis_service import (
    ActivityAnalysisCancelled,
    FrameActivityAnalyzer,
)

log = logging.getLogger(__name__)


class ActivityAnalysisWorker(QThread):
    """Run FFmpeg frame sampling outside the Qt UI thread."""

    result_ready = Signal(object)  # ActivityAnalysisResult
    error = Signal(str)
    progress = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        video_path: Path,
        analyzer: FrameActivityAnalyzer | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._video_path = Path(video_path)
        self._analyzer = analyzer or FrameActivityAnalyzer()
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:  # noqa: D102
        self.progress.emit(f"Sampling frames from {self._video_path.name}…")
        try:
            result = self._analyzer.analyze_video(
                self._video_path,
                cancel_event=self._cancel_event,
                progress_callback=self.progress.emit,
            )
        except ActivityAnalysisCancelled:
            self.cancelled.emit()
        except Exception as exc:  # noqa: BLE001
            log.exception("Video activity analysis failed")
            self.error.emit(str(exc))
        else:
            self.result_ready.emit(result)

