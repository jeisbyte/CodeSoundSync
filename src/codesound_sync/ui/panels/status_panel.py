"""
StatusPanel – scrollable log area that shows progress, warnings, and errors
with colour-coded severity badges.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class StatusPanel(QWidget):
    """Appends timestamped messages with INFO / WARNING / ERROR colouring."""

    _COLOURS = {
        "info":    "#a8d8a8",   # soft green
        "warning": "#f5c842",   # amber
        "error":   "#f07070",   # soft red
        "success": "#7ec8e3",   # sky blue
    }

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusPanel")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Header bar ---
        header = QWidget()
        header.setObjectName("statusHeader")
        hlay = QHBoxLayout(header)
        hlay.setContentsMargins(12, 6, 12, 6)

        title = QLabel("Status / Log")
        title.setObjectName("panelTitle")
        hlay.addWidget(title)
        hlay.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("clearBtn")
        clear_btn.setFixedWidth(60)
        hlay.addWidget(clear_btn)
        outer.addWidget(header)

        # --- Log area ---
        self._log = QPlainTextEdit()
        self._log.setObjectName("logArea")
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(2000)
        self._log.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(self._log)

        clear_btn.clicked.connect(self._log.clear)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def info(self, message: str) -> None:
        self._append(message, "info")

    def warning(self, message: str) -> None:
        self._append(message, "warning")

    def error(self, message: str) -> None:
        self._append(message, "error")

    def success(self, message: str) -> None:
        self._append(message, "success")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _append(self, message: str, level: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        colour = self._COLOURS.get(level, "#ffffff")

        cursor = self._log.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#888888"))
        cursor.setCharFormat(fmt)
        cursor.insertText(f"[{ts}] ")

        badge_fmt = QTextCharFormat()
        badge_fmt.setForeground(QColor(colour))
        cursor.setCharFormat(badge_fmt)
        cursor.insertText(f"{level.upper():8s}  ")

        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor("#e0e0e0"))
        cursor.setCharFormat(msg_fmt)
        cursor.insertText(f"{message}\n")

        self._log.setTextCursor(cursor)
        self._log.ensureCursorVisible()
