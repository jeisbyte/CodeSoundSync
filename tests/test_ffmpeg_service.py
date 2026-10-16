from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from codesound_sync.services import ffmpeg_service


def test_probe_media_uses_argument_list_and_parses_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "lesson; & sample.mp4"
    video.write_bytes(b"not a real video")
    calls: list[tuple[list[str], dict]] = []

    monkeypatch.setattr(ffmpeg_service, "get_ffprobe_path", lambda: Path("ffprobe.exe"))

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"format":{"duration":"12","size":"5"},'
                '"streams":[{"codec_type":"video","width":640,"height":360,'
                '"r_frame_rate":"25/1","codec_name":"h264"}]}'
            ),
            stderr="",
        )

    monkeypatch.setattr(ffmpeg_service.subprocess, "run", fake_run)
    info = ffmpeg_service.probe_media(video)

    command, kwargs = calls[0]
    assert command[-2:] == ["-i", str(video)]
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert "shell" not in kwargs
    assert info.resolution == "640×360"
    assert info.frame_rate == 25.0


def test_probe_media_reports_missing_ffprobe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")

    def missing_probe() -> Path:
        raise ffmpeg_service.FFmpegNotFoundError(
            "'ffprobe' was not found on PATH. Install FFmpeg and restart the application."
        )

    monkeypatch.setattr(ffmpeg_service, "get_ffprobe_path", missing_probe)
    with pytest.raises(ffmpeg_service.FFmpegNotFoundError, match="ffprobe.*PATH"):
        ffmpeg_service.probe_media(video)


def test_probe_media_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Video file not found"):
        ffmpeg_service.probe_media(tmp_path / "absent.mp4")


def test_probe_media_reports_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "video.mp4"
    video.write_bytes(b"video")
    monkeypatch.setattr(ffmpeg_service, "get_ffprobe_path", lambda: Path("ffprobe.exe"))

    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("ffprobe", 1)

    monkeypatch.setattr(ffmpeg_service.subprocess, "run", timeout)
    with pytest.raises(ffmpeg_service.MediaProbeError, match="timed out"):
        ffmpeg_service.probe_media(video)


def test_probe_media_explains_unreadable_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "invalid.mp4"
    video.write_bytes(b"not a video")
    monkeypatch.setattr(ffmpeg_service, "get_ffprobe_path", lambda: Path("ffprobe.exe"))
    monkeypatch.setattr(
        ffmpeg_service.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr=""
        ),
    )

    with pytest.raises(
        ffmpeg_service.MediaProbeError, match="invalid, unsupported, or unreadable"
    ):
        ffmpeg_service.probe_media(video)
