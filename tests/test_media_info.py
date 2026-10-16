from pathlib import Path

from codesound_sync.models.media_info import MediaInfo
from codesound_sync.services.ffmpeg_service import (
    MediaProbeError,
    _parse_probe_output,
)


def test_parse_probe_output_extracts_media_metadata(tmp_path: Path) -> None:
    path = tmp_path / "lesson video.mp4"
    path.write_bytes(b"video")
    info = _parse_probe_output(
        path,
        {
            "format": {
                "duration": "65.5",
                "size": "123456",
                "bit_rate": "1500000",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30000/1001",
                },
                {"codec_type": "audio", "codec_name": "aac"},
                {"codec_type": "audio", "codec_name": "opus"},
            ],
        },
    )

    assert info.duration_seconds == 65.5
    assert info.duration_str == "00:01:05"
    assert info.resolution == "1920×1080"
    assert info.frame_rate == 29.97003
    assert info.audio_streams == ("aac", "opus")
    assert info.audio_codec == "aac"
    assert info.bit_rate_kbps == 1500
    assert info.size_bytes == 123456


def test_parse_probe_output_handles_missing_metadata_and_audio(tmp_path: Path) -> None:
    video_path = tmp_path / "video.mkv"
    video_path.write_bytes(b"")
    info = _parse_probe_output(
        video_path,
        {"format": {}, "streams": [{"codec_type": "video"}]},
    )

    assert info.duration_seconds is None
    assert info.resolution == "—"
    assert info.frame_rate is None
    assert info.video_codec is None
    assert info.audio_streams == ()
    assert info.size_bytes == 0


def test_parse_probe_output_falls_back_to_average_frame_rate(tmp_path: Path) -> None:
    path = tmp_path / "video.mp4"
    path.write_bytes(b"")
    info = _parse_probe_output(
        path,
        {
            "format": {"duration": "12.0"},
            "streams": [
                {
                    "codec_type": "video",
                    "r_frame_rate": "0/0",
                    "avg_frame_rate": "24000/1001",
                }
            ],
        },
    )

    assert info.duration_seconds == 12.0
    assert info.frame_rate == 23.976024


def test_parse_probe_output_rejects_files_without_video(tmp_path: Path) -> None:
    try:
        _parse_probe_output(
            tmp_path / "audio.mp3",
            {"format": {}, "streams": [{"codec_type": "audio"}]},
        )
    except MediaProbeError as exc:
        assert "No video stream" in str(exc)
    else:
        raise AssertionError("Expected a file without video to be rejected")


def test_media_info_round_trips_optional_fields_and_old_audio_codec() -> None:
    info = MediaInfo(
        path=Path("video.mp4"),
        duration_seconds=None,
        width=None,
        height=None,
        frame_rate=None,
        video_codec=None,
        audio_codec="aac",
        bit_rate_kbps=None,
        size_bytes=15,
    )

    restored = MediaInfo.from_dict(info.to_dict())
    assert restored == info

    legacy = info.to_dict()
    legacy.pop("audio_streams")
    assert MediaInfo.from_dict(legacy).audio_streams == ("aac",)
