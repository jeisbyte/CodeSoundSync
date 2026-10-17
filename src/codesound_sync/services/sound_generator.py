"""Small deterministic synthetic sound effects for keyboard and mouse events."""

from __future__ import annotations

import math

from codesound_sync.config import AUDIO_SAMPLE_RATE
from codesound_sync.models.sound_event import SoundEventType


class SoundGenerator:
    """Generate short, local effects without third-party audio assets."""

    def __init__(self, sample_rate: int = AUDIO_SAMPLE_RATE) -> None:
        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, int)
            or not 8_000 <= sample_rate <= 192_000
        ):
            raise ValueError("Sample rate must be an integer from 8000 to 192000 Hz.")
        self.sample_rate = sample_rate

    def generate(
        self,
        event_type: SoundEventType,
        intensity: float = 1.0,
        variation: float = 0.0,
    ) -> list[float]:
        """Synthesize one event as normalized floating-point mono samples."""
        try:
            event_type = SoundEventType(event_type)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Unsupported sound event type: {event_type!r}.") from exc

        if (
            isinstance(intensity, bool)
            or not isinstance(intensity, (int, float))
            or not math.isfinite(intensity)
            or not 0.0 <= intensity <= 1.0
        ):
            raise ValueError("Event intensity must be a finite number from 0 to 1.")
        if (
            isinstance(variation, bool)
            or not isinstance(variation, (int, float))
            or not math.isfinite(variation)
            or not -1.0 <= variation <= 1.0
        ):
            raise ValueError("Event variation must be a finite number from -1 to 1.")

        if event_type is SoundEventType.KEYBOARD_TAP:
            duration = 0.043 * (1.0 + 0.14 * variation)
            frequency = 1_650.0 * (1.0 + 0.10 * variation)
            decay = 0.0105
            harmonics = ((1.0, 1.0), (2.15, 0.24), (0.53, 0.12))
        elif event_type is SoundEventType.MOUSE_LEFT_CLICK:
            duration = 0.058
            frequency = 1_150.0
            decay = 0.015
            harmonics = ((1.0, 1.0), (1.82, 0.32), (0.48, 0.14))
        else:
            duration = 0.073
            frequency = 760.0
            decay = 0.023
            harmonics = ((1.0, 1.0), (1.61, 0.28), (2.47, 0.12))

        frame_count = max(1, round(duration * self.sample_rate))
        samples: list[float] = []
        peak = 0.0
        for frame in range(frame_count):
            time_seconds = frame / self.sample_rate
            attack = 1.0 - math.exp(-time_seconds * 900.0)
            envelope = attack * math.exp(-time_seconds / decay)
            tone = sum(
                amplitude
                * math.sin(
                    2.0 * math.pi * frequency * multiplier * time_seconds
                )
                for multiplier, amplitude in harmonics
            )
            sample = tone * envelope
            samples.append(sample)
            peak = max(peak, abs(sample))

        if peak == 0.0:
            return samples
        output_gain = 0.28 * float(intensity) / peak
        return [sample * output_gain for sample in samples]
