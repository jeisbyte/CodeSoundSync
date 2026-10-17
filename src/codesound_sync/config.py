"""
Application-wide constants and resolved paths.

All path resolution happens at import time so the rest of the package
can do ``from codesound_sync.config import ASSETS_DIR`` without knowing
where the project root is.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Project root (two levels above this file: src/codesound_sync/ → project/)
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
PROJECT_ROOT: Path = _THIS_FILE.parent.parent.parent  # …/CodeSoundSync/

# ---------------------------------------------------------------------------
# Well-known directories
# ---------------------------------------------------------------------------
SRC_DIR: Path = PROJECT_ROOT / "src"
ASSETS_DIR: Path = PROJECT_ROOT / "assets"
SOUNDS_DIR: Path = ASSETS_DIR / "sounds"
PROJECTS_DIR: Path = PROJECT_ROOT / "projects"
LOGS_DIR: Path = PROJECT_ROOT / "logs"

# Create runtime directories on first import.
for _d in (PROJECTS_DIR, LOGS_DIR, SOUNDS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME = "CodeSound Sync"
APP_VERSION = "0.1.0"
APP_ORG = "CodeSoundSync"

# ---------------------------------------------------------------------------
# FFmpeg / FFprobe – resolved at runtime by ffmpeg_service
# ---------------------------------------------------------------------------
FFMPEG_TIMEOUT_SECONDS: int = 60
FFPROBE_TIMEOUT_SECONDS: int = 30
AUDIO_SAMPLE_RATE: int = 44_100
ACTIVITY_SAMPLE_INTERVAL_SECONDS: float = 0.5

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
WINDOW_MIN_WIDTH: int = 1100
WINDOW_MIN_HEIGHT: int = 700
WINDOW_DEFAULT_TITLE: str = APP_NAME
