"""Main CodeSound Sync desktop window."""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from codesound_sync.config import (
    ACTIVITY_SAMPLE_INTERVAL_SECONDS,
    PROJECT_ROOT,
    PROJECTS_DIR,
    WINDOW_DEFAULT_TITLE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from codesound_sync.models.media_info import MediaInfo
from codesound_sync.models.activity_candidate import (
    ActivityAnalysisResult,
    ActivityCandidate,
    candidates_to_sound_events,
)
from codesound_sync.models.project import Project
from codesound_sync.services.project_service import ProjectFileError, ProjectService
from codesound_sync.services.activity_analysis_service import FrameActivityAnalyzer
from codesound_sync.services.sound_effects_service import SoundEffectsService
from codesound_sync.ui.dialogs.activity_review_dialog import ActivityReviewDialog
from codesound_sync.ui.panels.media_info_panel import MediaInfoPanel
from codesound_sync.ui.panels.status_panel import StatusPanel
from codesound_sync.ui.panels.workspace_panel import WorkspacePanel
from codesound_sync.ui.workers.activity_analysis_worker import ActivityAnalysisWorker
from codesound_sync.ui.workers.ffprobe_worker import FFprobeWorker

log = logging.getLogger(__name__)

VIDEO_FILTER = (
    "Video files (*.mp4 *.mov *.mkv *.avi *.m4v *.webm);;"
    "All files (*)"
)
PROJECT_FILTER = "CodeSound Sync project files (*.json)"


class MainWindow(QMainWindow):
    """Stage 1 and 2 window for local video projects and sound-effects demos."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_DEFAULT_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self._project_service = ProjectService()
        self._sound_effects_service = SoundEffectsService()
        self._project: Project | None = None
        self._project_file: Path | None = None
        self._probe_worker: FFprobeWorker | None = None
        self._probe_busy = False
        self._activity_worker: ActivityAnalysisWorker | None = None
        self._activity_progress: QProgressDialog | None = None
        self._review_dialog: ActivityReviewDialog | None = None
        self._activity_result: ActivityAnalysisResult | None = None

        self._build_ui()
        self._apply_theme()
        self._set_busy(False)

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("appRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(22, 18, 22, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("CodeSound Sync")
        title.setObjectName("appTitle")
        subtitle = QLabel("Prepare a local video project for sound synchronization")
        subtitle.setObjectName("appSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch()

        self.import_button = QPushButton("Import Video")
        self.import_button.setObjectName("primaryButton")
        self.import_button.clicked.connect(self._choose_video)
        header.addWidget(self.import_button)

        self.open_project_button = QPushButton("Open Project")
        self.open_project_button.setObjectName("secondaryButton")
        self.open_project_button.clicked.connect(self._choose_project)
        header.addWidget(self.open_project_button)

        self.analyze_button = QPushButton("Analyze Video")
        self.analyze_button.setObjectName("secondaryButton")
        self.analyze_button.clicked.connect(self._analyze_video)
        header.addWidget(self.analyze_button)

        self.record_button = QPushButton("Start Recording Session")
        self.record_button.setObjectName("disabledButton")
        self.record_button.setEnabled(False)
        self.record_button.setToolTip("Recording mode will be implemented in a later stage.")
        header.addWidget(self.record_button)
        outer.addLayout(header)

        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)
        self.workspace_panel = WorkspacePanel()
        self.media_info_panel = MediaInfoPanel()
        self.media_info_panel.setMinimumWidth(290)

        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)
        side_layout.addWidget(self.media_info_panel)
        side_layout.addWidget(self._build_project_settings())

        content.addWidget(self.workspace_panel)
        content.addWidget(side)
        content.setStretchFactor(0, 3)
        content.setStretchFactor(1, 2)
        outer.addWidget(content, 1)

        self.status_panel = StatusPanel()
        self.status_panel.setMinimumHeight(150)
        outer.addWidget(self.status_panel)

        self.setCentralWidget(root)
        self.statusBar().showMessage("Ready")
        self.status_panel.info("Ready. Import a local video to inspect its media information.")

    def _build_project_settings(self) -> QGroupBox:
        group = QGroupBox("Project Settings")
        group.setObjectName("projectSettings")
        form = QFormLayout(group)
        form.setContentsMargins(14, 18, 14, 14)
        form.setSpacing(10)

        self.project_name = QLineEdit()
        self.project_name.setPlaceholderText("Project name")
        form.addRow("Project name", self.project_name)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        self.output_location = QLineEdit(str(PROJECT_ROOT / "output"))
        self.output_location.setReadOnly(True)
        self.output_location.setToolTip("Local folder reserved for project output.")
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._choose_output_location)
        output_layout.addWidget(self.output_location, 1)
        output_layout.addWidget(browse_button)
        form.addRow("Output location", output_row)

        self.save_project_button = QPushButton("Save Project")
        self.save_project_button.setEnabled(False)
        self.save_project_button.clicked.connect(self._save_project)
        form.addRow(self.save_project_button)

        self.generate_test_sounds_button = QPushButton("Generate Test Sounds")
        self.generate_test_sounds_button.setObjectName("secondaryButton")
        self.generate_test_sounds_button.setToolTip(
            "Create a short WAV of synthetic keyboard and mouse sound effects."
        )
        self.generate_test_sounds_button.clicked.connect(self._generate_test_sounds)
        form.addRow(self.generate_test_sounds_button)

        self.analyze_activity_button = QPushButton("Analyze Video Activity")
        self.analyze_activity_button.setObjectName("secondaryButton")
        self.analyze_activity_button.setToolTip(
            "Sample the imported video for possible visual activity. "
            "Candidates are estimates, not confirmed input."
        )
        self.analyze_activity_button.clicked.connect(self._analyze_video_activity)
        form.addRow(self.analyze_activity_button)
        return group

    def _apply_theme(self) -> None:
        self.setStyleSheet(
            """
            QWidget#appRoot { background: #171a21; color: #e6e9ef; }
            QLabel#appTitle { color: #f5f7fa; font-size: 24px; font-weight: 700; }
            QLabel#appSubtitle { color: #9ca6b5; font-size: 12px; }
            QGroupBox, QWidget#mediaInfoPanel, QWidget#workspacePanel,
            QWidget#statusPanel {
                background: #202530; border: 1px solid #303846; border-radius: 8px;
            }
            QGroupBox { margin-top: 10px; padding-top: 8px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
            QLabel#panelTitle { color: #f0f3f8; font-size: 14px; font-weight: 600; }
            QLabel#infoLabel, QLabel#appSubtitle { color: #9ca6b5; }
            QLabel#infoValue { color: #e6e9ef; }
            QLabel#previewPlaceholder {
                background: #151922; border: 1px dashed #485365; border-radius: 8px;
                color: #aab3c1; font-size: 15px;
            }
            QLabel#selectedMediaPath { color: #aab3c1; }
            QLineEdit, QPlainTextEdit {
                background: #151922; border: 1px solid #3a4351; border-radius: 5px;
                color: #e6e9ef; padding: 7px;
            }
            QPushButton {
                background: #303846; border: 1px solid #465164; border-radius: 5px;
                color: #f0f3f8; padding: 8px 12px;
            }
            QPushButton:hover:!disabled { background: #3b4657; }
            QPushButton:disabled { color: #727c8a; background: #252b35; }
            QPushButton#primaryButton { background: #2865c7; border-color: #3478e8; }
            QPushButton#primaryButton:hover:!disabled { background: #3478e8; }
            QStatusBar { background: #171a21; color: #b9c2cf; }
            QSplitter::handle { background: #171a21; }
            """
        )

    def _choose_video(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Import Video", "", VIDEO_FILTER
        )
        if selected:
            self.load_video(Path(selected))

    def _choose_project(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self, "Open Project", str(PROJECTS_DIR), PROJECT_FILTER
        )
        if selected:
            self.load_project(Path(selected))

    def load_project(self, path: Path) -> bool:
        """Load a saved project and restore its state in the window."""
        if self._activity_worker is not None and self._activity_worker.isRunning():
            self.status_panel.warning("Wait for activity analysis to finish first.")
            return False
        if self._probe_worker is not None and self._probe_worker.isRunning():
            self.status_panel.warning("Wait for the current media inspection to finish.")
            return False

        path = Path(path)
        try:
            project = self._project_service.load_file(path)
        except ProjectFileError as exc:
            message = f"Could not open project: {exc}"
            log.warning(message)
            self.status_panel.error(message)
            self.statusBar().showMessage("Project could not be opened")
            return False

        self._project = project
        self._project_file = path
        self.project_name.setText(project.name)
        self.output_location.setText(
            str(project.output_dir or PROJECT_ROOT / "output")
        )
        self.save_project_button.setEnabled(True)

        try:
            source_exists = (
                project.source_video is not None and project.source_video.is_file()
            )
        except (OSError, ValueError):
            source_exists = False
        if project.source_video is None:
            self.workspace_panel.clear()
        elif source_exists:
            self.workspace_panel.set_video(project.source_video)
        else:
            self.workspace_panel.set_missing_video(project.source_video)

        if project.media_info is not None:
            self.media_info_panel.update_info(project.media_info)
        else:
            self.media_info_panel.clear_info()

        self.analyze_button.setEnabled(project.media_info is not None)
        self._update_activity_button()
        if project.source_video is not None and not source_exists:
            message = (
                f"Project opened, but the source video cannot currently be found: "
                f"{project.source_video}"
            )
            self.status_panel.warning(message)
            self.statusBar().showMessage("Project opened; source video is missing")
        else:
            self.status_panel.success(f"Project opened: {project.name}")
            self.statusBar().showMessage(f"Project opened: {project.name}")
        return True

    def load_video(self, path: Path) -> None:
        """Load and probe a selected path. Kept public for reliable UI tests."""
        path = Path(path)
        if self._activity_worker is not None and self._activity_worker.isRunning():
            self.status_panel.warning("Wait for activity analysis to finish first.")
            return
        if not path.is_file():
            message = f"Video file not found: {path}"
            self.status_panel.error(message)
            self.statusBar().showMessage(message)
            return
        if self._probe_worker is not None and self._probe_worker.isRunning():
            self.status_panel.warning("Wait for the current media inspection to finish.")
            return

        self._project = Project(
            name=path.stem or "Untitled Project",
            source_video=path,
            output_dir=Path(self.output_location.text()),
        )
        self._project_file = None
        self.project_name.setText(self._project.name)
        self.workspace_panel.set_video(path)
        self.media_info_panel.clear_info()
        self.analyze_button.setEnabled(False)
        self.save_project_button.setEnabled(True)
        self._set_busy(True)

        worker = FFprobeWorker(path, self)
        self._probe_worker = worker
        worker.progress.connect(self._on_probe_progress)
        worker.media_ready.connect(self._on_probe_ready)
        worker.error.connect(self._on_probe_error)
        worker.finished.connect(self._on_probe_worker_finished)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self._probe_busy = busy
        self.import_button.setEnabled(not busy)
        self.open_project_button.setEnabled(not busy)
        self.analyze_button.setEnabled(
            not busy
            and self._project is not None
            and self._project.media_info is not None
        )
        self._update_activity_button()
        if busy:
            self.statusBar().showMessage("Inspecting media…")

    def _update_activity_button(self) -> None:
        project = self._project
        try:
            source_available = (
                project is not None
                and project.source_video is not None
                and project.source_video.is_file()
            )
        except (OSError, ValueError):
            source_available = False
        self.analyze_activity_button.setEnabled(
            source_available
            and not self._probe_busy
            and self._activity_worker is None
        )

    def _on_probe_progress(self, message: str) -> None:
        self.status_panel.info(message)
        self.statusBar().showMessage(message)

    def _on_probe_ready(self, info: MediaInfo) -> None:
        if self._project is None:
            return
        self._project.media_info = info
        self._project.touch()
        self.media_info_panel.update_info(info)
        self.analyze_button.setEnabled(True)
        self.save_project_button.setEnabled(True)
        self.status_panel.success(
            f"Media inspected: {info.path.name} — {info.duration_str}, "
            f"{info.resolution}, {info.frame_rate_str}."
        )
        if not info.audio_streams:
            self.status_panel.warning("No audio streams were found in this video.")
        self.statusBar().showMessage(f"Loaded {info.path.name}")

    def _on_probe_error(self, message: str) -> None:
        self.media_info_panel.clear_info()
        self.analyze_button.setEnabled(False)
        self.status_panel.error(message)
        self.statusBar().showMessage("Media inspection failed")

    def _on_worker_finished(self, worker: FFprobeWorker) -> None:
        if self._probe_worker is worker:
            self._probe_worker = None
        self._set_busy(False)
        worker.deleteLater()

    def _on_probe_worker_finished(self) -> None:
        worker = self._probe_worker
        if worker is not None:
            self._on_worker_finished(worker)

    def _choose_output_location(self) -> None:
        current = self.output_location.text()
        selected = QFileDialog.getExistingDirectory(
            self, "Choose Output Location", current
        )
        if not selected:
            return
        output_path = Path(selected)
        self.output_location.setText(str(output_path))
        if self._project is not None:
            self._project.output_dir = output_path
            self._project.touch()

    def _save_project(self) -> None:
        if self._project is None:
            return
        project_name = self.project_name.text().strip()
        if not project_name:
            self.status_panel.error("Enter a project name before saving.")
            return
        self._project.name = project_name
        self._project.output_dir = Path(self.output_location.text())
        try:
            saved_path = self._project_service.save(
                self._project, path=self._project_file
            )
        except OSError as exc:
            log.exception("Could not save project")
            self.status_panel.error(f"Could not save project: {exc}")
            return
        self._project_file = saved_path
        self.status_panel.success(f"Project saved locally: {saved_path.name}")
        self.statusBar().showMessage(f"Project saved: {saved_path.name}")

    def _generate_test_sounds(self) -> None:
        output_dir = Path(self.output_location.text())
        filename = f"codesound-test-{uuid4().hex}.wav"
        output_path = output_dir / filename
        try:
            generated_path = self._sound_effects_service.render(
                self._sound_effects_service.demo_events(),
                output_path,
                duration_seconds=2.0,
            )
        except (OSError, ValueError) as exc:
            log.exception("Could not generate test sounds")
            self.status_panel.error(f"Could not generate test sounds: {exc}")
            self.statusBar().showMessage("Test sound generation failed")
            return

        message = f"Test sound WAV generated: {generated_path}"
        self.status_panel.success(message)
        self.statusBar().showMessage(message)

    def _analyze_video_activity(self) -> None:
        if self._project is None or self._project.source_video is None:
            self.status_panel.warning("Import a valid video before analyzing activity.")
            return
        if self._activity_worker is not None:
            return
        if not self._project.source_video.is_file():
            self.status_panel.error(
                f"Video file not found: {self._project.source_video}"
            )
            return
        if self._probe_worker is not None and self._probe_worker.isRunning():
            self.status_panel.warning("Wait for media inspection to finish first.")
            return

        if self._review_dialog is not None:
            self._review_dialog.close()
            self._review_dialog.deleteLater()
            self._review_dialog = None

        analyzer = FrameActivityAnalyzer(
            sample_interval_seconds=ACTIVITY_SAMPLE_INTERVAL_SECONDS
        )
        worker = ActivityAnalysisWorker(self._project.source_video, analyzer, self)
        self._activity_worker = worker
        worker.progress.connect(self._on_activity_progress)
        worker.result_ready.connect(self._on_activity_ready)
        worker.error.connect(self._on_activity_error)
        worker.cancelled.connect(self._on_activity_cancelled)
        worker.finished.connect(self._on_activity_worker_finished)

        progress = QProgressDialog(
            "Sampling local video frames…",
            "Cancel",
            0,
            0,
            self,
        )
        progress.setWindowTitle("Analyze Video Activity")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.canceled.connect(worker.cancel)
        self._activity_progress = progress
        self.import_button.setEnabled(False)
        self.open_project_button.setEnabled(False)
        self.analyze_button.setEnabled(False)
        self.analyze_activity_button.setEnabled(False)
        progress.show()
        worker.start()

    def _on_activity_progress(self, message: str) -> None:
        self.status_panel.info(message)
        self.statusBar().showMessage(message)
        if self._activity_progress is not None:
            self._activity_progress.setLabelText(message)

    def _on_activity_ready(self, result: ActivityAnalysisResult) -> None:
        summary = (
            f"Activity analysis complete: {len(result.candidates)} candidate(s) "
            f"from {result.sampled_frame_count} sampled frames."
        )
        self.status_panel.success(summary)
        self.statusBar().showMessage(summary)
        self._activity_result = result
        dialog = ActivityReviewDialog(result, self)
        dialog.generate_requested.connect(self._generate_activity_sounds)
        self._review_dialog = dialog
        dialog.show()

    def _on_activity_error(self, message: str) -> None:
        self.status_panel.error(f"Video activity analysis failed: {message}")
        self.statusBar().showMessage("Video activity analysis failed")

    def _on_activity_cancelled(self) -> None:
        self.status_panel.warning("Video activity analysis cancelled.")
        self.statusBar().showMessage("Video activity analysis cancelled")

    def _on_activity_finished(self, worker: ActivityAnalysisWorker) -> None:
        if self._activity_worker is worker:
            self._activity_worker = None
        if self._activity_progress is not None:
            self._activity_progress.close()
            self._activity_progress.deleteLater()
            self._activity_progress = None
        worker.deleteLater()
        self._set_busy(False)

    def _on_activity_worker_finished(self) -> None:
        worker = self._activity_worker
        if worker is not None:
            self._on_activity_finished(worker)

    def _generate_activity_sounds(
        self, candidates: tuple[ActivityCandidate, ...]
    ) -> None:
        events = candidates_to_sound_events(candidates)
        if not events:
            self.status_panel.warning(
                "No included candidates can be rendered. Uncertain visual activity "
                "is excluded rather than converted into guessed input sounds."
            )
            self.statusBar().showMessage("No renderable activity candidates selected")
            return

        duration_seconds = (
            self._activity_result.video_duration_seconds
            if self._activity_result is not None
            else None
        )
        output_path = (
            Path(self.output_location.text())
            / f"codesound-activity-{uuid4().hex}.wav"
        )
        try:
            generated_path = self._sound_effects_service.render(
                events,
                output_path,
                duration_seconds=duration_seconds,
            )
        except (OSError, ValueError) as exc:
            log.exception("Could not generate activity sound effects")
            self.status_panel.error(f"Could not generate sound-effects track: {exc}")
            self.statusBar().showMessage("Sound-effects track generation failed")
            return

        message = (
            f"Sound-effects-only track generated (source-video timestamps; not "
            f"aligned to edited or speed-changed footage): {generated_path}"
        )
        self.status_panel.success(message)
        self.statusBar().showMessage("Sound-effects-only track generated")

    def _analyze_video(self) -> None:
        if self._project is None or self._project.media_info is None:
            return
        self.status_panel.info(
            "Stage 1 analysis complete: video metadata is available. "
            "Frame-level activity analysis will be added in a later stage."
        )
        self.statusBar().showMessage("Stage 1 media inspection complete")

    def closeEvent(self, event) -> None:  # noqa: N802
        activity_worker = self._activity_worker
        if activity_worker is not None and activity_worker.isRunning():
            activity_worker.cancel()
            activity_worker.wait()
        worker = self._probe_worker
        if worker is not None and worker.isRunning():
            worker.wait()
        event.accept()
