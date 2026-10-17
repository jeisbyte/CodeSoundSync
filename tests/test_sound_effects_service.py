from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest

from codesound_sync.config import AUDIO_SAMPLE_RATE
from codesound_sync.models.sound_event import SoundEvent, SoundEventType
from codesound_sync.services.sound_effects_service import (
    SoundEffectsService,
    SoundRenderError,
)
from codesound_sync.services.sound_generator import SoundGenerator


def _read_samples(path: Path) -> tuple[object, tuple[int, ...]]:
    with wave.open(str(path), "rb") as wav_file:
        params = wav_file.getparams()
        raw = wav_file.readframes(params.nframes)
    samples = struct.unpack(f"<{len(raw) // 2}h", raw) if raw else ()
    return params, samples


@pytest.mark.parametrize("event_type", list(SoundEventType))
def test_each_sound_type_generates_distinguishable_samples(
    event_type: SoundEventType,
) -> None:
    generator = SoundGenerator()

    samples = generator.generate(event_type)

    assert samples
    assert max(abs(sample) for sample in samples) == pytest.approx(0.28)
    assert all(math.isfinite(sample) for sample in samples)


def test_synthesized_sound_types_are_distinguishable() -> None:
    generator = SoundGenerator()
    keyboard = generator.generate(SoundEventType.KEYBOARD_TAP)
    left_click = generator.generate(SoundEventType.MOUSE_LEFT_CLICK)
    right_click = generator.generate(SoundEventType.MOUSE_RIGHT_CLICK)

    assert keyboard != left_click
    assert left_click != right_click


@pytest.mark.parametrize("event_type", list(SoundEventType))
def test_each_sound_type_renders_valid_pcm_wav(
    tmp_path: Path, event_type: SoundEventType
) -> None:
    output = SoundEffectsService().render(
        [SoundEvent(0.0, event_type)],
        tmp_path / f"{event_type.value}.wav",
        variation=False,
    )

    params, samples = _read_samples(output)
    assert params.nchannels == 1
    assert params.sampwidth == 2
    assert params.framerate == AUDIO_SAMPLE_RATE
    assert samples
    assert max(map(abs, samples)) > 0


def test_renderer_creates_pcm_wav_with_silence_and_timestamped_event(
    tmp_path: Path,
) -> None:
    service = SoundEffectsService()
    output = service.render(
        [SoundEvent(0.5, SoundEventType.KEYBOARD_TAP)],
        tmp_path / "timed.wav",
        variation=False,
    )

    params, samples = _read_samples(output)
    start = round(0.5 * AUDIO_SAMPLE_RATE)
    assert params.nchannels == 1
    assert params.sampwidth == 2
    assert params.framerate == AUDIO_SAMPLE_RATE
    assert params.comptype == "NONE"
    assert len(samples) == start + len(
        service._generator.generate(SoundEventType.KEYBOARD_TAP)
    )
    assert not any(samples[:start])
    assert any(samples[start : start + 20])


def test_overlapping_events_are_mixed_not_overwritten(tmp_path: Path) -> None:
    service = SoundEffectsService()
    single = service.render(
        [SoundEvent(0, SoundEventType.KEYBOARD_TAP)],
        tmp_path / "single.wav",
        variation=False,
    )
    overlapping = service.render(
        [
            SoundEvent(0, SoundEventType.KEYBOARD_TAP),
            SoundEvent(0, SoundEventType.KEYBOARD_TAP),
        ],
        tmp_path / "overlap.wav",
        variation=False,
    )

    _, single_samples = _read_samples(single)
    _, overlapping_samples = _read_samples(overlapping)
    assert max(map(abs, overlapping_samples)) > max(map(abs, single_samples)) * 1.9


def test_dense_overlaps_are_limited_below_pcm_clipping(tmp_path: Path) -> None:
    output = SoundEffectsService().render(
        [SoundEvent(0, SoundEventType.MOUSE_LEFT_CLICK) for _ in range(20)],
        tmp_path / "limited.wav",
        variation=False,
    )
    _, samples = _read_samples(output)
    assert max(map(abs, samples)) <= round(0.95 * 32767) + 1


def test_duration_is_at_least_requested_and_includes_final_event(
    tmp_path: Path,
) -> None:
    service = SoundEffectsService()
    output = service.render(
        [SoundEvent(1.0, SoundEventType.MOUSE_RIGHT_CLICK)],
        tmp_path / "duration.wav",
        duration_seconds=3.0,
        variation=False,
    )
    params, _ = _read_samples(output)
    assert params.nframes == 3 * AUDIO_SAMPLE_RATE

    longer_event = service.render(
        [SoundEvent(3.0, SoundEventType.MOUSE_RIGHT_CLICK)],
        tmp_path / "event-duration.wav",
        duration_seconds=1.0,
        variation=False,
    )
    longer_params, _ = _read_samples(longer_event)
    expected = round(3.0 * AUDIO_SAMPLE_RATE) + len(
        service._generator.generate(SoundEventType.MOUSE_RIGHT_CLICK)
    )
    assert longer_params.nframes == expected


def test_empty_events_create_valid_silent_wav(tmp_path: Path) -> None:
    service = SoundEffectsService()
    zero_length = service.render([], tmp_path / "empty.wav")
    params, samples = _read_samples(zero_length)
    assert params.nframes == 0
    assert samples == ()

    silence = service.render(
        [], tmp_path / "silence.wav", duration_seconds=0.25
    )
    silence_params, silence_samples = _read_samples(silence)
    assert silence_params.nframes == round(0.25 * AUDIO_SAMPLE_RATE)
    assert not any(silence_samples)


def test_repeated_render_is_deterministic_when_variation_is_disabled(
    tmp_path: Path,
) -> None:
    service = SoundEffectsService()
    events = [
        SoundEvent(0.1, SoundEventType.KEYBOARD_TAP),
        SoundEvent(0.3, SoundEventType.MOUSE_LEFT_CLICK),
    ]
    first = service.render(events, tmp_path / "first.wav", variation=False)
    second = service.render(events, tmp_path / "second.wav", variation=False)

    assert first.read_bytes() == second.read_bytes()


def test_random_variation_can_be_reproduced_with_a_seed(tmp_path: Path) -> None:
    service = SoundEffectsService()
    events = [
        SoundEvent(0.1, SoundEventType.KEYBOARD_TAP),
        SoundEvent(0.2, SoundEventType.KEYBOARD_TAP),
    ]
    first = service.render(
        events, tmp_path / "seeded-first.wav", random_seed=17
    )
    second = service.render(
        events, tmp_path / "seeded-second.wav", random_seed=17
    )
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize(
    ("timestamp", "event_type", "intensity", "variation"),
    [
        (-0.1, SoundEventType.KEYBOARD_TAP, 1.0, 0.0),
        (float("nan"), SoundEventType.KEYBOARD_TAP, 1.0, 0.0),
        (0.0, "unsupported", 1.0, 0.0),
        (0.0, SoundEventType.KEYBOARD_TAP, 1.1, 0.0),
        (0.0, SoundEventType.KEYBOARD_TAP, 1.0, -1.1),
    ],
)
def test_invalid_events_are_rejected(
    timestamp: float, event_type: object, intensity: float, variation: float
) -> None:
    with pytest.raises(ValueError):
        SoundEvent(timestamp, event_type, intensity, variation)


@pytest.mark.parametrize("duration", [-1, float("inf"), float("nan")])
def test_invalid_render_duration_is_rejected(
    tmp_path: Path, duration: float
) -> None:
    with pytest.raises(ValueError, match="Duration"):
        SoundEffectsService().render([], tmp_path / "invalid.wav", duration)


def test_invalid_sample_rate_and_output_format_are_rejected(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="Sample rate"):
        SoundEffectsService(sample_rate=0)
    with pytest.raises(ValueError, match=".wav"):
        SoundEffectsService().render([], tmp_path / "not-a-wave.mp3")
    with pytest.raises(ValueError, match="too large"):
        SoundEffectsService().render(
            [SoundEvent(1e308, SoundEventType.KEYBOARD_TAP)],
            tmp_path / "too-large.wav",
        )


def test_render_creates_output_directories_and_never_overwrites(
    tmp_path: Path,
) -> None:
    service = SoundEffectsService()
    output = tmp_path / "nested" / "folder" / "result.wav"
    service.render([], output)
    assert output.is_file()

    output.write_bytes(b"keep me")
    with pytest.raises(SoundRenderError, match="Could not write WAV"):
        service.render([], output)
    assert output.read_bytes() == b"keep me"


def test_output_directory_errors_are_reported_clearly(tmp_path: Path) -> None:
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("file", encoding="utf-8")

    with pytest.raises(SoundRenderError, match="Could not write WAV"):
        SoundEffectsService().render([], blocked_parent / "failure.wav")


def test_demo_keyboard_variations_produce_slightly_different_taps() -> None:
    generator = SoundGenerator()
    events = [
        event
        for event in SoundEffectsService.demo_events()
        if event.event_type is SoundEventType.KEYBOARD_TAP
    ]

    sounds = [
        generator.generate(event.event_type, event.intensity, event.variation)
        for event in events
    ]
    assert len(sounds) > 1
    assert any(sound != sounds[0] for sound in sounds[1:])
