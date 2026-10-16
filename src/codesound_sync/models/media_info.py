"""
MediaInfo – immutable dataclass holding video metadata returned by ffprobe.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MediaInfo:
    """Parsed metadata for a single video file."""

    path: Path
    duration_seconds: float | None   # total duration in seconds
    width: int | None                # frame width in pixels
    height: int | None               # frame height in pixels
    frame_rate: float | None         # frames per second (may be fractional)
    video_codec: str | None          # e.g. "h264"
    audio_codec: str | None          # None when no audio stream
    bit_rate_kbps: int | None        # overall container bit-rate (kbps)
    size_bytes: int                  # file size in bytes
    audio_streams: tuple[str, ...] = ()

    # -----------------------------------------------------------------------
    # Convenience properties
    # -----------------------------------------------------------------------

    @property
    def resolution(self) -> str:
        """Human-readable resolution string, e.g. '1920×1080'."""
        if self.width is None or self.height is None:
            return "—"
        return f"{self.width}\u00d7{self.height}"

    @property
    def duration_str(self) -> str:
        """Duration formatted as HH:MM:SS."""
        if self.duration_seconds is None:
            return "—"
        total = int(self.duration_seconds)
        h, remainder = divmod(total, 3600)
        m, s = divmod(remainder, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def frame_rate_str(self) -> str:
        """Frame-rate rounded to two decimal places, e.g. '29.97 fps'."""
        if self.frame_rate is None:
            return "—"
        return f"{self.frame_rate:.2f} fps"

    @property
    def size_mb(self) -> float:
        """File size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    # -----------------------------------------------------------------------
    # Serialisation helpers (for project JSON)
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "path": str(self.path),
            "duration_seconds": self.duration_seconds,
            "width": self.width,
            "height": self.height,
            "frame_rate": self.frame_rate,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "audio_streams": list(self.audio_streams),
            "bit_rate_kbps": self.bit_rate_kbps,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MediaInfo":
        audio_codec = data.get("audio_codec")
        return cls(
            path=Path(data["path"]),
            duration_seconds=(
                float(data["duration_seconds"])
                if data.get("duration_seconds") is not None
                else None
            ),
            width=int(data["width"]) if data.get("width") is not None else None,
            height=int(data["height"]) if data.get("height") is not None else None,
            frame_rate=(
                float(data["frame_rate"]) if data.get("frame_rate") is not None else None
            ),
            video_codec=data.get("video_codec"),
            audio_codec=audio_codec,
            bit_rate_kbps=(
                int(data["bit_rate_kbps"])
                if data.get("bit_rate_kbps") is not None
                else None
            ),
            size_bytes=int(data["size_bytes"]),
            audio_streams=(
                tuple(str(codec) for codec in data["audio_streams"])
                if "audio_streams" in data
                else ((str(audio_codec),) if audio_codec else ())
            ),
        )
