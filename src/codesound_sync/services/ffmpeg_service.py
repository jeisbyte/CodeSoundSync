"""
FFmpeg / FFprobe service.

All subprocess calls use explicit argument *lists* (never shell=True) and
validated Path objects so that untrusted filenames cannot inject extra
arguments or shell metacharacters.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from codesound_sync.config import FFMPEG_TIMEOUT_SECONDS, FFPROBE_TIMEOUT_SECONDS
from codesound_sync.models.media_info import MediaInfo

log = logging.getLogger(__name__)


class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg or ffprobe cannot be located on PATH."""


class MediaProbeError(RuntimeError):
    """Raised when ffprobe fails or returns unexpected output."""


def _find_executable(name: str) -> Path:
    """
    Locate *name* on PATH and return its resolved Path.

    Raises FFmpegNotFoundError with an actionable message when not found.
    """
    found = shutil.which(name)
    if found is None:
        raise FFmpegNotFoundError(
            f"'{name}' was not found on PATH.\n"
            "Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/ and add "
            "the bin/ folder to your system PATH, then restart the application."
        )
    return Path(found).resolve()


def get_ffmpeg_path() -> Path:
    return _find_executable("ffmpeg")


def get_ffprobe_path() -> Path:
    return _find_executable("ffprobe")


def check_ffmpeg_available() -> tuple[bool, str]:
    """
    Return (True, version_string) if both ffmpeg and ffprobe are available,
    or (False, error_message) otherwise.
    """
    try:
        ffmpeg = get_ffmpeg_path()
        ffprobe = get_ffprobe_path()
    except FFmpegNotFoundError as exc:
        return False, str(exc)

    try:
        result = subprocess.run(
            [str(ffmpeg), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else "unknown"
        log.debug("FFmpeg located at %s: %s", ffmpeg, first_line)
        log.debug("FFprobe located at %s", ffprobe)
        return True, first_line
    except Exception as exc:  # noqa: BLE001
        return False, f"FFmpeg found but failed to run: {exc}"


def probe_media(video_path: Path) -> MediaInfo:
    """
    Run ffprobe on *video_path* and return a :class:`MediaInfo` instance.

    Raises
    ------
    FFmpegNotFoundError
        When ffprobe is not on PATH.
    MediaProbeError
        When the file cannot be probed or required fields are missing.
    FileNotFoundError
        When *video_path* does not exist.
    """
    if not video_path.is_file():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    ffprobe = get_ffprobe_path()

    cmd = [
        str(ffprobe),
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-i",
        str(video_path),  # validated Path – no shell expansion
    ]

    log.info("Probing media: %s", video_path.name)  # log name only, not full path
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise MediaProbeError(f"ffprobe timed out after {FFPROBE_TIMEOUT_SECONDS}s")
    except OSError as exc:
        raise MediaProbeError(f"Failed to launch ffprobe: {exc}") from exc

    if result.returncode != 0:
        details = result.stderr.strip()[:500]
        if not details:
            details = "The file may be invalid, unsupported, or unreadable."
        raise MediaProbeError(
            f"ffprobe could not inspect this media file (exit code "
            f"{result.returncode}):\n{details}"
        )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError(f"Could not parse ffprobe JSON output: {exc}") from exc

    return _parse_probe_output(video_path, data)


def _parse_probe_output(video_path: Path, data: dict) -> MediaInfo:
    """Convert raw ffprobe JSON into a :class:`MediaInfo`."""
    if not isinstance(data, dict):
        raise MediaProbeError("ffprobe returned invalid media metadata.")
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    if not isinstance(fmt, dict) or not isinstance(streams, list):
        raise MediaProbeError("ffprobe returned invalid media metadata.")

    # Pick video and audio streams
    video_stream: Optional[dict] = None
    audio_streams: list[dict] = []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type", "")
        if codec_type == "video" and video_stream is None:
            video_stream = stream
        elif codec_type == "audio":
            audio_streams.append(stream)

    if video_stream is None:
        raise MediaProbeError("No video stream found in the file.")

    # Duration: prefer stream-level, fall back to format-level
    duration = _parse_optional_float(video_stream.get("duration"))
    if duration is None:
        duration = _parse_optional_float(fmt.get("duration"))

    # Prefer the nominal rate, but use the average when it is missing or invalid.
    frame_rate = _parse_frame_rate(video_stream.get("r_frame_rate"))
    if frame_rate is None:
        frame_rate = _parse_frame_rate(video_stream.get("avg_frame_rate"))

    width = _parse_optional_int(video_stream.get("width"))
    height = _parse_optional_int(video_stream.get("height"))
    width = width or None
    height = height or None

    bit_rate_raw = fmt.get("bit_rate")
    parsed_bit_rate = _parse_optional_int(bit_rate_raw)
    bit_rate_kbps = parsed_bit_rate // 1000 if parsed_bit_rate is not None else None

    size_bytes = _parse_optional_int(fmt.get("size"))
    if size_bytes is None:
        size_bytes = video_path.stat().st_size

    audio_codecs = tuple(
        str(stream.get("codec_name") or "unknown") for stream in audio_streams
    )
    return MediaInfo(
        path=video_path,
        duration_seconds=duration,
        width=width,
        height=height,
        frame_rate=frame_rate,
        video_codec=video_stream.get("codec_name"),
        audio_codec=audio_codecs[0] if audio_codecs else None,
        bit_rate_kbps=bit_rate_kbps,
        size_bytes=size_bytes,
        audio_streams=audio_codecs,
    )


def _parse_optional_float(value: object) -> float | None:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) and parsed >= 0 else None
    except (ValueError, TypeError):
        return None


def _parse_optional_int(value: object) -> int | None:
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else None
    except (ValueError, TypeError):
        return None


def _parse_frame_rate(rate_str: object) -> float | None:
    """Parse a fractional frame-rate string like '30000/1001' → 29.97."""
    if rate_str is None:
        return None
    try:
        rate_str = str(rate_str)
        if "/" in rate_str:
            num, den = rate_str.split("/", 1)
            den_int = int(den)
            rate = round(int(num) / den_int, 6) if den_int else None
        else:
            rate = _parse_optional_float(rate_str)
        return rate if rate and rate > 0 else None
    except (ValueError, TypeError, ZeroDivisionError):
        return None
