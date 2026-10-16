"""
Path utility helpers.
"""

from __future__ import annotations

from pathlib import Path


def safe_stem(path: Path) -> str:
    """Return a filesystem-safe version of the file stem (no special chars)."""
    import re
    stem = path.stem
    return re.sub(r"[^\w\-]", "_", stem)


def ensure_dir(path: Path) -> Path:
    """Create *path* as a directory if it does not exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def human_size(size_bytes: int) -> str:
    """Return a human-readable file size string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f} TB"
