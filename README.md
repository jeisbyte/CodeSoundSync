# CodeSound Sync

CodeSound Sync is a local-first Windows desktop application for preparing programming tutorial videos for synchronized typing and mouse sounds. **Stage 1** provides the dark-themed desktop foundation, local project settings, and asynchronous media metadata inspection. Sound generation, frame analysis, input capture, and rendering are not part of this stage.

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

Tests cover FFprobe JSON parsing (including missing metadata and audio streams), safe subprocess invocation and missing-tool errors, project persistence, path utilities, and the responsive Qt import workflow.

## Project layout

```text
main.py
requirements.txt
src/codesound_sync/
  app.py
  config.py
  models/       # Project and media metadata
  services/     # FFprobe and local project persistence
  ui/           # Main window, panels, and background worker
  utils/
tests/
assets/sounds/  # Reserved for a future stage
projects/       # Local saved project files (ignored by Git)
```

## Roadmap

1. Foundation: desktop UI, local project settings, media metadata inspection, and tests
2. Audio engine and sound assets
3. Code-activity detection from video frames
4. Timeline mapping and audio/video export
5. Packaging and installer
