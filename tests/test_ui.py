from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QPlainTextEdit

from codesound_sync.models.media_info import MediaInfo
from codesound_sync.services.project_service import ProjectService
from codesound_sync.ui.workers import ffprobe_worker
from codesound_sync.ui.main_window import MainWindow


def test_window_import_runs_probe_in_background(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"local video")
    result = MediaInfo(
        path=video,
        duration_seconds=42.0,
        width=1280,
        height=720,
        frame_rate=30.0,
        video_codec="h264",
        audio_codec="aac",
        bit_rate_kbps=1500,
        size_bytes=1024,
        audio_streams=("aac",),
    )

    def slow_probe(path: Path) -> MediaInfo:
        time.sleep(0.15)
        return result

    monkeypatch.setattr(ffprobe_worker, "probe_media", slow_probe)
    window = MainWindow()
    window._project_service = ProjectService(tmp_path / "projects")
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle() == "CodeSound Sync"
    assert not window.record_button.isEnabled()
    assert not window.analyze_button.isEnabled()

    timer_ticks: list[bool] = []
    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(lambda: timer_ticks.append(True))
    timer.start()
    window.load_video(video)
    assert not window.import_button.isEnabled()
    qtbot.waitUntil(lambda: window._probe_worker is None, timeout=3000)
    timer.stop()

    assert timer_ticks
    assert window.import_button.isEnabled()
    assert window.analyze_button.isEnabled()
    assert window.save_project_button.isEnabled()

    window._analyze_video()
    assert "Stage 1 analysis complete" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()


def test_window_shows_missing_ffprobe_error(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    video = tmp_path / "lesson.mp4"
    video.write_bytes(b"local video")

    def missing_probe(path: Path) -> MediaInfo:
        from codesound_sync.services.ffmpeg_service import FFmpegNotFoundError

        raise FFmpegNotFoundError("ffprobe was not found on PATH.")

    monkeypatch.setattr(ffprobe_worker, "probe_media", missing_probe)
    window = MainWindow()
    qtbot.addWidget(window)
    window.load_video(video)
    qtbot.waitUntil(lambda: window._probe_worker is None, timeout=3000)

    assert not window.analyze_button.isEnabled()
    assert window.save_project_button.isEnabled()
    assert "ffprobe was not found on PATH" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()
