"""Central workspace shown while a video is selected or being inspected."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WorkspacePanel(QWidget):
    """Video preview placeholder and selected media path."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("workspacePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        self._preview = QLabel("Import a video to begin")
        self._preview.setObjectName("previewPlaceholder")
        self._preview.setAlignment(Qt.AlignCenter)
        self._preview.setMinimumHeight(300)
        layout.addWidget(self._preview, 1)

        self._path = QLabel("No video selected")
        self._path.setObjectName("selectedMediaPath")
        self._path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._path.setWordWrap(True)
        layout.addWidget(self._path)

    def set_video(self, path: Path) -> None:
        self._preview.setText(f"Video selected\n\n{path.name}\n\nPreview playback is not part of Stage 1.")
        self._path.setText(str(path))

    def clear(self) -> None:
        self._preview.setText("Import a video to begin")
        self._path.setText("No video selected")
