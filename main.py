"""
CodeSound Sync – application entry point.

Usage (PowerShell, venv active):
    python main.py
"""

import sys
from pathlib import Path

# Ensure the src/ tree is importable regardless of how the script is launched.
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    try:
        from codesound_sync.app import run  # noqa: E402
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "PySide6 is not installed. Activate the project virtual "
                "environment and run: python -m pip install -r requirements.txt",
                file=sys.stderr,
            )
            sys.exit(1)
        raise
    sys.exit(run())
