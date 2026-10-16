"""
MediaInfoPanel – displays duration, resolution, frame rate, codec,
and file size for the currently loaded video.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from codesound_sync.models.media_info import MediaInfo
from codesound_sync.utils.paths import human_size

_PLACEHOLDER = "—"


class _InfoRow(QWidget):
    """A single label / value pair."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setColumnStretch(1, 1)

        self._label = QLabel(label)
        self._label.setObjectName("infoLabel")
        self._label.setFixedWidth(110)

        self._value = QLabel(_PLACEHOLDER)
        self._value.setObjectName("infoValue")
        self._value.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout.addWidget(self._label, 0, 0)
        layout.addWidget(self._value, 0, 1)

    @property
    def value_label(self) -> QLabel:
        return self._value

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def clear(self) -> None:
        self._value.setText(_PLACEHOLDER)


class MediaInfoPanel(QWidget):
    """Side panel showing parsed video metadata."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("mediaInfoPanel")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        title = QLabel("Media Information")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setObjectName("separator")
        layout.addWidget(sep)

        self._duration = _InfoRow("Duration")
        self._resolution = _InfoRow("Resolution")
        self._fps = _InfoRow("Frame Rate")
        self._video_codec = _InfoRow("Video Codec")
        self._audio_streams = _InfoRow("Audio Streams")
        self._bitrate = _InfoRow("Bit Rate")
        self._size = _InfoRow("File Size")

        for row in (
            self._duration,
            self._resolution,
            self._fps,
            self._video_codec,
            self._audio_streams,
            self._bitrate,
            self._size,
        ):
            layout.addWidget(row)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_info(self, info: MediaInfo) -> None:
        """Populate all rows from a :class:`MediaInfo` instance."""
        self._duration.set_value(info.duration_str)
        self._resolution.set_value(info.resolution)
        self._fps.set_value(info.frame_rate_str)
        self._video_codec.set_value(info.video_codec or _PLACEHOLDER)
        self._audio_streams.set_value(
            "None"
            if not info.audio_streams
            else f"{len(info.audio_streams)} ({', '.join(info.audio_streams)})"
        )
        self._bitrate.set_value(
            f"{info.bit_rate_kbps} kbps" if info.bit_rate_kbps else _PLACEHOLDER
        )
        self._size.set_value(human_size(info.size_bytes))

    def clear_info(self) -> None:
        """Reset all rows to placeholder dashes."""
        for row in (
            self._duration,
            self._resolution,
            self._fps,
            self._video_codec,
            self._audio_streams,
            self._bitrate,
            self._size,
        ):
            row.clear()
