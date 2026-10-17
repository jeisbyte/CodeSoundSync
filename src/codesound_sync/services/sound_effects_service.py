"""Render timestamped sound-only events to mono PCM WAV files."""

from __future__ import annotations

import array
import math
import random
import sys
import wave
from contextlib import suppress
from pathlib import Path
from typing import Iterable, Iterator

from codesound_sync.config import AUDIO_SAMPLE_RATE
from codesound_sync.models.sound_event import SoundEvent, SoundEventType
from codesound_sync.services.sound_generator import SoundGenerator

_MAX_WAV_FRAMES = (2**32 - 1 - 36) // 2
_MIX_BLOCK_FRAMES = 16_384


class SoundRenderError(OSError):
    """Raised when the rendered WAV cannot be written."""


class SoundEffectsService:
    """Mix synthetic effects into mono, 16-bit PCM WAV (44.1 kHz by default)."""

    def __init__(
        self,
        sample_rate: int = AUDIO_SAMPLE_RATE,
        generator: SoundGenerator | None = None,
    ) -> None:
        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, int)
            or not 8_000 <= sample_rate <= 192_000
        ):
            raise ValueError("Sample rate must be an integer from 8000 to 192000 Hz.")
        self._generator = generator or SoundGenerator(sample_rate)
        if self._generator.sample_rate != sample_rate:
            raise ValueError("Generator sample rate must match renderer sample rate.")
        self.sample_rate = sample_rate

    def render(
        self,
        events: Iterable[SoundEvent],
        output_path: Path,
        duration_seconds: float | None = None,
        *,
        variation: bool = True,
        random_seed: int | None = None,
    ) -> Path:
        """Render events; the final duration includes the full last sound.

        Adjacent keyboard taps vary slightly by default. Pass ``variation=False``
        for identical repeats, or a seed for reproducible generated variation.
        Existing files are never overwritten.
        """
        if duration_seconds is not None and (
            isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or not math.isfinite(duration_seconds)
            or duration_seconds < 0
        ):
            raise ValueError("Duration must be a finite, non-negative number.")
        if not isinstance(variation, bool):
            raise ValueError("Variation must be True or False.")
        if random_seed is not None and (
            isinstance(random_seed, bool) or not isinstance(random_seed, int)
        ):
            raise ValueError("Random seed must be an integer or None.")

        try:
            scheduled_events = tuple(events)
        except TypeError as exc:
            raise ValueError("Events must be an iterable of SoundEvent objects.") from exc
        if any(not isinstance(event, SoundEvent) for event in scheduled_events):
            raise ValueError("Events must contain only SoundEvent objects.")

        try:
            target = Path(output_path)
        except (TypeError, ValueError) as exc:
            raise ValueError("Output path must be a valid file path.") from exc
        if target.suffix.lower() != ".wav":
            raise ValueError("Output file must use the .wav extension.")

        rng = random.Random(random_seed)
        rendered_events: list[tuple[int, list[float]]] = []
        frame_count = 0
        if duration_seconds is not None:
            requested_frames = duration_seconds * self.sample_rate
            if not math.isfinite(requested_frames):
                raise ValueError("Requested duration is too large to render.")
            frame_count = math.ceil(requested_frames)
            if frame_count > _MAX_WAV_FRAMES:
                raise ValueError("Requested duration exceeds the WAV format limit.")

        for event in scheduled_events:
            event_variation = float(event.variation)
            if variation and event.event_type is SoundEventType.KEYBOARD_TAP:
                event_variation = max(
                    -1.0,
                    min(1.0, event_variation + rng.uniform(-0.12, 0.12)),
                )
            samples = self._generator.generate(
                event.event_type,
                intensity=event.intensity,
                variation=event_variation,
            )
            position_frames = event.timestamp_seconds * self.sample_rate
            if not math.isfinite(position_frames):
                raise ValueError("Event timestamp is too large to render.")
            start_frame = round(position_frames)
            rendered_events.append((start_frame, samples))
            frame_count = max(frame_count, start_frame + len(samples))
            if frame_count > _MAX_WAV_FRAMES:
                raise ValueError("Event duration exceeds the WAV format limit.")

        rendered_events.sort(key=lambda item: item[0])
        peak = max(
            (
                abs(sample)
                for chunk in self._iter_mixed_chunks(rendered_events, frame_count)
                for sample in chunk
            ),
            default=0.0,
        )
        gain = 0.95 / peak if peak > 0.95 else 1.0

        created = False
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output_file:
                created = True
                with wave.open(output_file, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(self.sample_rate)
                    for chunk in self._iter_mixed_chunks(
                        rendered_events, frame_count
                    ):
                        pcm = array.array(
                            "h",
                            (
                                max(
                                    -32768,
                                    min(32767, round(sample * gain * 32767)),
                                )
                                for sample in chunk
                            ),
                        )
                        if sys.byteorder != "little":
                            pcm.byteswap()
                        wav_file.writeframesraw(pcm.tobytes())
        except (OSError, wave.Error) as exc:
            if created:
                with suppress(OSError):
                    target.unlink(missing_ok=True)
            raise SoundRenderError(f"Could not write WAV file '{target}': {exc}") from exc
        return target

    def _iter_mixed_chunks(
        self,
        rendered_events: list[tuple[int, list[float]]],
        frame_count: int,
    ) -> Iterator[array.array]:
        """Mix a bounded block at a time so longer renders use modest memory."""
        next_event = 0
        active_events: list[tuple[int, list[float]]] = []
        for block_start in range(0, frame_count, _MIX_BLOCK_FRAMES):
            block_end = min(block_start + _MIX_BLOCK_FRAMES, frame_count)
            while (
                next_event < len(rendered_events)
                and rendered_events[next_event][0] < block_end
            ):
                active_events.append(rendered_events[next_event])
                next_event += 1
            active_events = [
                (start, samples)
                for start, samples in active_events
                if start + len(samples) > block_start
            ]

            mixed = array.array("f", [0.0]) * (block_end - block_start)
            for start, samples in active_events:
                first_frame = max(start, block_start)
                last_frame = min(start + len(samples), block_end)
                for frame in range(first_frame, last_frame):
                    mixed[frame - block_start] += samples[frame - start]
            yield mixed

    @staticmethod
    def demo_events() -> tuple[SoundEvent, ...]:
        """A fixed sound-only sequence for the UI demo (no keys or text captured)."""
        return (
            SoundEvent(0.20, SoundEventType.KEYBOARD_TAP, variation=-0.6),
            SoundEvent(0.34, SoundEventType.KEYBOARD_TAP, variation=0.25),
            SoundEvent(0.50, SoundEventType.KEYBOARD_TAP, variation=0.75),
            SoundEvent(0.78, SoundEventType.MOUSE_LEFT_CLICK),
            SoundEvent(1.10, SoundEventType.KEYBOARD_TAP, variation=-0.2),
            SoundEvent(1.12, SoundEventType.MOUSE_RIGHT_CLICK),
            SoundEvent(1.55, SoundEventType.KEYBOARD_TAP, variation=0.45),
        )
