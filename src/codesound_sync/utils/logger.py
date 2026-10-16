"""
Logging setup for CodeSound Sync.

Call ``setup_logging()`` once at application start.  Every module then does:

    import logging
    log = logging.getLogger(__name__)
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path


_FMT = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: Path, level: int = logging.DEBUG) -> None:
    """Initialise root logger with a rotating file handler + a console handler."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "codesound_sync.log"

    root = logging.getLogger()
    root.setLevel(level)

    if root.handlers:
        # Already configured (e.g. during tests) – don't add duplicates.
        return

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # Rotating file – 5 MB × 3 backups
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)

    # Console (WARNING+ only to avoid noise)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(formatter)

    root.addHandler(fh)
    root.addHandler(ch)
