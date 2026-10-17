from __future__ import annotations

import time
import threading
import wave
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFileDialog, QPlainTextEdit, QPushButton

from codesound_sync.models.activity_candidate import (
    ActivityAnalysisResult,
    ActivityCandidate,
    ActivityType,
)
from codesound_sync.models.media_info import MediaInfo
from codesound_sync.models.project import Project
from codesound_sync.services.project_service import ProjectService
from codesound_sync.ui.workers import ffprobe_worker
from codesound_sync.ui.main_window import MainWindow, PROJECT_FILTER
from codesound_sync.services.activity_analysis_service import ActivityAnalysisCancelled


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


def test_open_project_restores_fields_and_warns_for_missing_video(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "missing-lesson.mp4"
    project = Project(
        name="Saved Lesson",
        source_video=source,
        output_dir=tmp_path / "rendered",
        media_info=MediaInfo(
            path=source,
            duration_seconds=125,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            bit_rate_kbps=1200,
            size_bytes=2048,
            audio_streams=("aac",),
        ),
    )
    service = ProjectService(tmp_path / "projects")
    project_file = service.save(project)
    window = MainWindow()
    window._project_service = service
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args: (str(project_file), PROJECT_FILTER),
    )

    window.open_project_button.click()

    assert window.open_project_button.isEnabled()
    assert window._project == project
    assert window._project_file == project_file
    assert window.project_name.text() == "Saved Lesson"
    assert window.output_location.text() == str(tmp_path / "rendered")
    assert window.workspace_panel._preview.text().startswith("Source video missing")
    assert window.media_info_panel._duration.value_label.text() == "00:02:05"
    assert window.media_info_panel._resolution.value_label.text() == "1920×1080"
    assert window.analyze_button.isEnabled()
    assert "cannot currently be found" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()


def test_open_project_dialog_cancel_preserves_current_project(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    window = MainWindow()
    current_project = Project(name="Current Project")
    current_project_file = tmp_path / "current.json"
    window._project = current_project
    window._project_file = current_project_file
    window.project_name.setText(current_project.name)
    qtbot.addWidget(window)
    dialog_args: list[tuple] = []

    def cancel_dialog(*args: object) -> tuple[str, str]:
        dialog_args.append(args)
        return "", ""

    monkeypatch.setattr(QFileDialog, "getOpenFileName", cancel_dialog)
    window.open_project_button.click()

    assert window._project is current_project
    assert window._project_file == current_project_file
    assert window.project_name.text() == "Current Project"
    assert len(dialog_args) == 1
    assert dialog_args[0][1] == "Open Project"
    assert dialog_args[0][3] == PROJECT_FILTER


def test_open_project_rejects_malformed_file_without_replacing_state(
    qtbot, tmp_path: Path
) -> None:
    window = MainWindow()
    current_project = Project(name="Current Project")
    window._project = current_project
    window.project_name.setText(current_project.name)
    qtbot.addWidget(window)
    malformed = tmp_path / "broken.json"
    malformed.write_text("{broken", encoding="utf-8")

    assert not window.load_project(malformed)

    assert window._project is current_project
    assert window.project_name.text() == "Current Project"
    assert "not valid JSON" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()


def test_save_loaded_project_updates_selected_file(
    qtbot, tmp_path: Path
) -> None:
    service = ProjectService(tmp_path / "projects")
    original = Project(
        name="Original",
        source_video=tmp_path / "lesson.mp4",
        output_dir=tmp_path / "output",
    )
    project_file = service.save(original)
    window = MainWindow()
    window._project_service = service
    qtbot.addWidget(window)

    assert window.load_project(project_file)
    window.project_name.setText("Renamed")
    window.output_location.setText(str(tmp_path / "new-output"))
    window._save_project()

    loaded = service.load_file(project_file)
    assert loaded.project_id == original.project_id
    assert loaded.name == "Renamed"
    assert loaded.output_dir == tmp_path / "new-output"
    assert list((tmp_path / "projects").glob("*.json")) == [project_file]


def test_generate_test_sounds_button_writes_wav_to_configured_output(
    qtbot, tmp_path: Path
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    output_dir = tmp_path / "generated"
    window.output_location.setText(str(output_dir))

    window.generate_test_sounds_button.click()

    generated = list(output_dir.glob("codesound-test-*.wav"))
    assert len(generated) == 1
    with wave.open(str(generated[0]), "rb") as wav_file:
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2
        assert wav_file.getframerate() == 44_100
        assert wav_file.getnframes() > 0
    log_text = window.status_panel.findChild(QPlainTextEdit).toPlainText()
    assert str(generated[0]) in log_text


def test_generate_test_sounds_reports_output_directory_error(
    qtbot, tmp_path: Path
) -> None:
    blocked_output = tmp_path / "output-file"
    blocked_output.write_text("not a directory", encoding="utf-8")
    window = MainWindow()
    qtbot.addWidget(window)
    window.output_location.setText(str(blocked_output))

    window.generate_test_sounds_button.click()

    log_text = window.status_panel.findChild(QPlainTextEdit).toPlainText()
    assert "Could not generate test sounds" in log_text
    assert "Could not write WAV" in log_text


def test_activity_analysis_runs_in_background_and_review_controls_wav_events(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import codesound_sync.ui.main_window as main_window_module

    source = tmp_path / "tutorial.mp4"
    source.write_bytes(b"synthetic")
    result = ActivityAnalysisResult(
        candidates=(
            ActivityCandidate(
                0.4,
                ActivityType.TYPING,
                0.55,
                "Repeated visual changes; possible typing-like activity.",
                change_count=3,
            ),
            ActivityCandidate(
                0.8,
                ActivityType.UNCERTAIN,
                0.3,
                "One isolated visual change.",
            ),
        ),
        sample_interval_seconds=0.5,
        sampled_frame_count=3,
        video_duration_seconds=1.0,
    )

    class SlowAnalyzer:
        def __init__(self, sample_interval_seconds: float) -> None:
            self.sample_interval_seconds = sample_interval_seconds

        def analyze_video(
            self, path: Path, *, cancel_event, progress_callback
        ) -> ActivityAnalysisResult:
            progress_callback("Synthetic sampling in progress.")
            time.sleep(0.15)
            return result

    monkeypatch.setattr(main_window_module, "FrameActivityAnalyzer", SlowAnalyzer)
    window = MainWindow()
    qtbot.addWidget(window)
    output_dir = tmp_path / "output"
    window.output_location.setText(str(output_dir))
    window._project = Project(name="Tutorial", source_video=source)
    window._update_activity_button()
    window.show()

    timer_ticks: list[bool] = []
    timer = QTimer(window)
    timer.setInterval(10)
    timer.timeout.connect(lambda: timer_ticks.append(True))
    timer.start()
    window.analyze_activity_button.click()
    qtbot.waitUntil(lambda: window._activity_worker is None, timeout=3000)
    timer.stop()

    assert timer_ticks
    assert window._review_dialog is not None
    dialog = window._review_dialog
    assert dialog.table.rowCount() == 2
    assert dialog.table.item(0, 0).checkState() == Qt.Checked
    assert dialog.table.item(1, 0).checkState() == Qt.Unchecked

    dialog.table.item(0, 0).setCheckState(Qt.Unchecked)
    dialog.generate_button.click()
    assert not list(output_dir.glob("codesound-activity-*.wav"))
    assert "No included candidates can be rendered" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()

    dialog.table.item(0, 0).setCheckState(Qt.Checked)
    dialog.generate_button.click()
    generated = list(output_dir.glob("codesound-activity-*.wav"))
    assert len(generated) == 1
    with wave.open(str(generated[0]), "rb") as wav_file:
        assert wav_file.getframerate() == 44_100
        assert wav_file.getnframes() == 44_100
    dialog.generate_button.click()
    assert len(list(output_dir.glob("codesound-activity-*.wav"))) == 2
    assert "not aligned to edited or speed-changed footage" in (
        window.status_panel.findChild(QPlainTextEdit).toPlainText()
    )


def test_activity_analysis_cancel_and_worker_error_are_reported(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    import codesound_sync.ui.main_window as main_window_module

    source = tmp_path / "tutorial.mp4"
    source.write_bytes(b"synthetic")

    class CancellableAnalyzer:
        def __init__(self, sample_interval_seconds: float) -> None:
            pass

        def analyze_video(
            self, path: Path, *, cancel_event, progress_callback
        ) -> ActivityAnalysisResult:
            progress_callback("Waiting for cancellation.")
            cancel_event.wait(2)
            if cancel_event.is_set():
                raise ActivityAnalysisCancelled("Activity analysis was cancelled.")
            return ActivityAnalysisResult((), 0.5, 0, 0.0)

    monkeypatch.setattr(
        main_window_module, "FrameActivityAnalyzer", CancellableAnalyzer
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = Project(name="Tutorial", source_video=source)
    window._update_activity_button()
    window.show()
    window.analyze_activity_button.click()
    qtbot.waitUntil(lambda: window._activity_progress is not None, timeout=1000)
    cancel_button = next(
        button
        for button in window._activity_progress.findChildren(QPushButton)
        if button.text() == "Cancel"
    )
    qtbot.mouseClick(cancel_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: window._activity_worker is None, timeout=3000)
    assert "analysis cancelled" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText().lower()

    class FailingAnalyzer:
        def __init__(self, sample_interval_seconds: float) -> None:
            pass

        def analyze_video(self, path: Path, **kwargs: object) -> ActivityAnalysisResult:
            raise RuntimeError("synthetic FFmpeg decode error")

    monkeypatch.setattr(main_window_module, "FrameActivityAnalyzer", FailingAnalyzer)
    window.analyze_activity_button.click()
    qtbot.waitUntil(lambda: window._activity_worker is None, timeout=3000)
    assert "synthetic FFmpeg decode error" in window.status_panel.findChild(
        QPlainTextEdit
    ).toPlainText()


def test_activity_action_requires_an_existing_video(qtbot, tmp_path: Path) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = Project(
        name="Missing", source_video=tmp_path / "absent.mp4"
    )
    window._update_activity_button()
    assert not window.analyze_activity_button.isEnabled()


def test_activity_action_stays_disabled_during_media_probe(
    qtbot, tmp_path: Path
) -> None:
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"video")
    window = MainWindow()
    qtbot.addWidget(window)
    window._project = Project(name="Lesson", source_video=source)

    window._set_busy(True)
    assert not window.analyze_activity_button.isEnabled()
    window._set_busy(False)
    assert window.analyze_activity_button.isEnabled()
