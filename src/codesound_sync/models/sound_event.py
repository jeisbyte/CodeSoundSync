"""Sound-only events used to render keyboard and mouse effects."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class SoundEventType(str, Enum):
    """Supported sound effects; these values never represent input content."""

    KEYBOARD_TAP = "keyboard_tap"
    MOUSE_LEFT_CLICK = "mouse_left_click"
    MOUSE_RIGHT_CLICK = "mouse_right_click"


@dataclass(frozen=True)
class SoundEvent:
    """A sound effect scheduled at a timestamp, without any typed input."""

    timestamp_seconds: float
    event_type: SoundEventType
    intensity: float = 1.0
    variation: float = 0.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.timestamp_seconds, bool)
            or not isinstance(self.timestamp_seconds, (int, float))
            or not math.isfinite(self.timestamp_seconds)
            or self.timestamp_seconds < 0
        ):
            raise ValueError("Event timestamp must be a finite, non-negative number.")

        try:
            event_type = SoundEventType(self.event_type)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Unsupported sound event type: {self.event_type!r}."
            ) from exc
        object.__setattr__(self, "event_type", event_type)

        if (
            isinstance(self.intensity, bool)
            or not isinstance(self.intensity, (int, float))
            or not math.isfinite(self.intensity)
            or not 0.0 <= self.intensity <= 1.0
        ):
            raise ValueError("Event intensity must be a finite number from 0 to 1.")

        if (
            isinstance(self.variation, bool)
            or not isinstance(self.variation, (int, float))
            or not math.isfinite(self.variation)
            or not -1.0 <= self.variation <= 1.0
        ):
            raise ValueError("Event variation must be a finite number from -1 to 1.")
