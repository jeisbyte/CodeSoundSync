# CodeSound Sync

CodeSound Sync is a local-first Windows desktop application for preparing programming tutorial videos for synchronized typing and mouse sounds. Stage 1 provides the dark-themed desktop foundation, local project settings, asynchronous media metadata inspection, and reopening saved projects. Stage 2 adds a local synthetic sound-effects renderer; Stage 3 adds heuristic video-frame activity candidates for review. Neither stage monitors real keyboard or mouse input.

## Requirements

- Python 3.11 or newer
- FFmpeg and FFprobe available on `PATH` for video inspection
- Windows 10 or newer

Install FFmpeg from a trusted Windows build provider, extract it, and add its `bin` directory (containing both `ffmpeg.exe` and `ffprobe.exe`) to `PATH`. Open a new PowerShell window and confirm both commands are available:

```powershell
ffmpeg -version
ffprobe -version
```

The application can open without FFmpeg, but it will report an actionable error when a video is imported if FFprobe is unavailable.

## Setup and launch (PowerShell)

From the project directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

The project-local virtual environment keeps Python packages isolated from the system installation. If PowerShell blocks virtual-environment activation, run the venv interpreter directly instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
```

Tests cover FFprobe JSON parsing (including missing metadata and audio streams), safe subprocess invocation and missing-tool errors, project persistence, path utilities, sound-effect WAV rendering, local visual-activity analysis, and Qt import/open/generation/review workflows.

## Stage 2 sound-effects demo

Click **Generate Test Sounds** in Project Settings to create a short WAV containing synthetic keyboard taps and left/right mouse clicks. It is saved in the currently configured output directory under a unique `codesound-test-<id>.wav` filename; existing files are never overwritten. The renderer uses only Python's standard-library math, array, and WAV support to synthesize local effects and writes mono, 16-bit PCM at 44,100 Hz. No third-party sound assets are bundled or used. Test events describe sound effects only; the app does not capture typed characters or monitor global input.

## Stage 3 video activity review

Import or open a video, then choose **Analyze Video Activity** in Project Settings. FFmpeg samples 160×90 grayscale frames locally at 0.5-second intervals by default, and a background worker compares consecutive samples. Nearby repeated changes are labeled as possible typing-like activity; isolated changes remain uncertain. The heuristics do not identify mouse buttons and cannot prove that a key was pressed. Scrolling, cursor blinking, scene changes, animations, and window movement can produce candidates. Review the timestamp, confidence, and evidence in the table; uncertain events are excluded from sound rendering by default. Check or uncheck renderable candidates and choose **Generate Sound Effects Track** to create a unique `codesound-activity-<id>.wav` in the configured output directory. This is a sound-effects-only track on source-video timestamps, not aligned to edited or speed-changed footage. Analysis is transient and is not added to saved project JSON.

## Project layout

```text
main.py
requirements.txt
src/codesound_sync/
  app.py
  config.py
  models/       # Project, media metadata, and sound events
  services/     # FFprobe, frame activity analysis, project persistence, sound synthesis, and WAV rendering
  ui/           # Main window, review dialogs, panels, and background workers
  utils/
tests/
assets/sounds/  # Reserved for replaceable local effects in a future stage
projects/       # Local saved project files (ignored by Git)
```

## Roadmap

1. Foundation: desktop UI, local project settings, media metadata inspection, and tests
2. Local synthetic keyboard/mouse sound-effects engine
3. Heuristic visual-activity candidates with human review
4. Improved activity classification and timeline handling
5. Packaging and installer
