from __future__ import annotations

import io
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from codesound_sync.models.activity_candidate import (
    ActivityAnalysisResult,
    ActivityCandidate,
    ActivityType,
    candidates_to_sound_events,
)
from codesound_sync.models.media_info import MediaInfo
from codesound_sync.models.sound_event import SoundEventType
from codesound_sync.services import activity_analysis_service
from codesound_sync.services.activity_analysis_service import (
    ActivityAnalysisCancelled,
    ActivityAnalysisError,
    FrameActivityAnalyzer,
)


def _frame(*changed_pixels: int, size: int = 100) -> bytes:
    pixels = bytearray(size)
    for pixel in changed_pixels:
        pixels[pixel] = 255
    return bytes(pixels)


def _analyzer() -> FrameActivityAnalyzer:
    return FrameActivityAnalyzer(
        sample_interval_seconds=0.5,
        pixel_delta_threshold=20,
        changed_pixel_fraction=0.02,
        typing_cluster_gap_seconds=0.75,
    )


def test_frame_samples_use_configured_interval_and_cluster_nearby_changes() -> None:
    analyzer = _analyzer()
    frames = [
        _frame(),
        _frame(*range(10)),
        _frame(*range(20)),
        _frame(*range(30)),
    ]

    result = analyzer.analyze_frames(
        frames,
        frame_width=10,
        frame_height=10,
        video_duration_seconds=2.0,
    )

    assert result.sampled_frame_count == 4
    assert result.sample_interval_seconds == 0.5
    assert result.video_duration_seconds == 2.0
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.timestamp_seconds == 0.5
    assert candidate.candidate_type is ActivityType.TYPING
    assert candidate.change_count == 3
    assert 0.0 <= candidate.confidence <= 1.0
    assert "Not proof" in candidate.evidence


def test_isolated_visual_change_stays_uncertain_and_unchanged_frames_are_ignored() -> None:
    analyzer = _analyzer()
    unchanged = _frame()
    stable = analyzer.analyze_frames(
        [unchanged, unchanged, unchanged],
        frame_width=10,
        frame_height=10,
    )
    isolated = analyzer.analyze_frames(
        [unchanged, _frame(*range(10)), _frame(*range(10))],
        frame_width=10,
        frame_height=10,
    )

    assert stable.candidates == ()
    assert len(isolated.candidates) == 1
    assert isolated.candidates[0].timestamp_seconds == 0.5
    assert isolated.candidates[0].candidate_type is ActivityType.UNCERTAIN
    assert isolated.candidates[0].confidence < 0.5


def test_empty_frames_report_no_events_and_keep_known_duration() -> None:
    result = _analyzer().analyze_frames(
        [],
        frame_width=10,
        frame_height=10,
        video_duration_seconds=7.25,
    )
    assert result.candidates == ()
    assert result.sampled_frame_count == 0
    assert result.video_duration_seconds == 7.25


def test_long_gaps_are_deduplicated_into_separate_bursts() -> None:
    analyzer = _analyzer()
    changed = _frame(*range(30))
    frames = [
        _frame(),
        _frame(*range(10)),
        _frame(*range(20)),
        _frame(*range(30)),
        changed,
        changed,
        changed,
        changed,
        _frame(*range(40)),
    ]
    result = analyzer.analyze_frames(frames, frame_width=10, frame_height=10)
    assert [candidate.timestamp_seconds for candidate in result.candidates] == [0.5, 4.0]


def test_invalid_analysis_configuration_and_frame_shape_are_rejected() -> None:
    with pytest.raises(ValueError, match="Sample interval"):
        FrameActivityAnalyzer(sample_interval_seconds=0)
    with pytest.raises(ValueError, match="Pixel threshold"):
        FrameActivityAnalyzer(pixel_delta_threshold=300)
    with pytest.raises(ValueError, match="Changed-pixel"):
        FrameActivityAnalyzer(changed_pixel_fraction=0)
    with pytest.raises(ActivityAnalysisError, match="grayscale frame"):
        _analyzer().analyze_frames([b"short"], frame_width=10, frame_height=10)


@pytest.mark.parametrize(
    "candidate_kwargs",
    [
        {"timestamp_seconds": -1},
        {"timestamp_seconds": float("inf")},
        {"confidence": -0.1},
        {"confidence": 1.1},
        {"candidate_type": "keystroke"},
        {"evidence": ""},
    ],
)
def test_activity_candidate_rejects_invalid_fields(candidate_kwargs: dict) -> None:
    values = {
        "timestamp_seconds": 1.0,
        "candidate_type": ActivityType.TYPING,
        "confidence": 0.5,
        "evidence": "Repeated visual changes.",
    }
    values.update(candidate_kwargs)
    with pytest.raises(ValueError):
        ActivityCandidate(**values)


def test_selected_candidate_conversion_maps_supported_and_skips_uncertain() -> None:
    candidates = (
        ActivityCandidate(1.0, ActivityType.TYPING, 0.6, "Typing-like."),
        ActivityCandidate(2.0, ActivityType.LEFT_CLICK, 0.8, "Click evidence."),
        ActivityCandidate(3.0, ActivityType.RIGHT_CLICK, 0.7, "Click evidence."),
        ActivityCandidate(4.0, ActivityType.UNCERTAIN, 0.3, "Visual change."),
    )

    events = candidates_to_sound_events(candidates[:3])

    assert [event.event_type for event in events] == [
        SoundEventType.KEYBOARD_TAP,
        SoundEventType.MOUSE_LEFT_CLICK,
        SoundEventType.MOUSE_RIGHT_CLICK,
    ]
    assert candidates_to_sound_events((candidates[-1],)) == ()


def test_video_sampling_command_uses_ffmpeg_and_preserves_sample_timestamps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "synthetic.mp4"
    video.write_bytes(b"synthetic")
    raw_frames = _frame(size=160 * 90) + _frame(
        *range(300), size=160 * 90
    )
    calls: list[tuple[list[str], dict]] = []

    class FakeProcess:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            calls.append((command, kwargs))
            self.stdout = io.BytesIO(raw_frames)

        def wait(self) -> int:
            return 0

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(
        activity_analysis_service,
        "probe_media",
        lambda path: MediaInfo(
            path=path,
            duration_seconds=1.0,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec=None,
            bit_rate_kbps=100,
            size_bytes=10,
        ),
    )
    monkeypatch.setattr(
        activity_analysis_service, "get_ffmpeg_path", lambda: Path("ffmpeg.exe")
    )
    monkeypatch.setattr(activity_analysis_service.subprocess, "Popen", FakeProcess)

    result = _analyzer().analyze_video(video)

    command, kwargs = calls[0]
    assert str(video) in command
    assert "fps=2.00000000" in command[command.index("-vf") + 1]
    assert kwargs["stderr"] == activity_analysis_service.subprocess.DEVNULL
    assert result.sampled_frame_count == 2
    assert len(result.candidates) == 1
    assert result.candidates[0].timestamp_seconds == 0.5
    assert result.video_duration_seconds == 1.0


def test_empty_video_frame_stream_returns_no_candidates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    video = tmp_path / "empty.mp4"
    video.write_bytes(b"synthetic empty")

    class EmptyProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.stdout = io.BytesIO()

        def wait(self) -> int:
            return 0

        def poll(self) -> int:
            return 0

    monkeypatch.setattr(
        activity_analysis_service,
        "probe_media",
        lambda path: SimpleNamespace(duration_seconds=0.0),
    )
    monkeypatch.setattr(
        activity_analysis_service, "get_ffmpeg_path", lambda: Path("ffmpeg.exe")
    )
    monkeypatch.setattr(activity_analysis_service.subprocess, "Popen", EmptyProcess)

    result = _analyzer().analyze_video(video)
    assert result.candidates == ()
    assert result.sampled_frame_count == 0


def test_cancellation_and_ffmpeg_errors_are_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(ActivityAnalysisCancelled):
        _analyzer().analyze_frames(
            [_frame()],
            frame_width=10,
            frame_height=10,
            cancel_event=cancellation,
        )

    video = tmp_path / "bad.mp4"
    video.write_bytes(b"bad")
    monkeypatch.setattr(
        activity_analysis_service,
        "probe_media",
        lambda path: SimpleNamespace(duration_seconds=1.0),
    )
    monkeypatch.setattr(
        activity_analysis_service, "get_ffmpeg_path", lambda: Path("ffmpeg.exe")
    )

    class FailedProcess:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self.stdout = io.BytesIO()

        def wait(self) -> int:
            return 1

        def poll(self) -> int:
            return 1

    monkeypatch.setattr(activity_analysis_service.subprocess, "Popen", FailedProcess)
    with pytest.raises(ActivityAnalysisError, match="could not decode"):
        _analyzer().analyze_video(video)


def test_older_stage_one_project_json_still_loads(tmp_path: Path) -> None:
    from codesound_sync.services.project_service import ProjectService

    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(
        '{"project_id":"old-id","name":"Old Lesson",'
        '"source_video":"lesson.mp4","output_dir":"rendered",'
        '"media_info":null,"created_at":"2025-01-01T00:00:00+00:00",'
        '"modified_at":"2025-01-01T00:00:00+00:00"}',
        encoding="utf-8",
    )

    loaded = ProjectService(tmp_path / "projects").load_file(legacy_path)

    assert loaded.project_id == "old-id"
    assert loaded.name == "Old Lesson"
    assert loaded.source_video == Path("lesson.mp4")
    assert loaded.output_dir == Path("rendered")
