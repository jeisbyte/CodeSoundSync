"""Main CodeSound Sync desktop window."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from codesound_sync.config import (
    PROJECT_ROOT,
    WINDOW_DEFAULT_TITLE,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
)
from codesound_sync.models.media_info import MediaInfo
from codesound_sync.models.project import Project
from codesound_sync.services.project_service import ProjectService
from codesound_sync.ui.panels.media_info_panel import MediaInfoPanel
from codesound_sync.ui.panels.status_panel import StatusPanel
from codesound_sync.ui.panels.workspace_panel import WorkspacePanel
from codesound_sync.ui.workers.ffprobe_worker import FFprobeWorker

log = logging.getLogger(__name__)

VIDEO_FILTER = (
    "Video files (*.mp4 *.mov *.mkv *.avi *.m4v *.webm);;"
    "All files (*)"
)


class MainWindow(QMainWindow):
    """Stage 1 window for importing and inspecting local video files."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_DEFAULT_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        self._project_service = ProjectService()
        self._project: Project | None = None
        self._probe_worker: FFprobeWorker | None = None

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

    def load_video(self, path: Path) -> None:
        """Load and probe a selected path. Kept public for reliable UI tests."""
        path = Path(path)
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
        worker.finished.connect(lambda: self._on_worker_finished(worker))
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.analyze_button.setEnabled(
            not busy
            and self._project is not None
            and self._project.media_info is not None
        )
        if busy:
            self.statusBar().showMessage("Inspecting media…")

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
            saved_path = self._project_service.save(self._project)
        except OSError as exc:
            log.exception("Could not save project")
            self.status_panel.error(f"Could not save project: {exc}")
            return
        self.status_panel.success(f"Project saved locally: {saved_path.name}")
        self.statusBar().showMessage(f"Project saved: {saved_path.name}")

    def _analyze_video(self) -> None:
        if self._project is None or self._project.media_info is None:
            return
        self.status_panel.info(
            "Stage 1 analysis complete: video metadata is available. "
            "Frame-level activity analysis will be added in a later stage."
        )
        self.statusBar().showMessage("Stage 1 media inspection complete")

    def closeEvent(self, event) -> None:  # noqa: N802
        worker = self._probe_worker
        if worker is not None and worker.isRunning():
            worker.wait()
        event.accept()
