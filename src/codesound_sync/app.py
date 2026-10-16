"""Qt application bootstrap."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from codesound_sync.config import APP_NAME, LOGS_DIR
from codesound_sync.ui.main_window import MainWindow
from codesound_sync.utils.logger import setup_logging


def run() -> int:
    """Create and run the desktop application."""
    setup_logging(LOGS_DIR)
    application = QApplication(sys.argv)
    application.setApplicationName(APP_NAME)
    window = MainWindow()
    window.show()
    return application.exec()
