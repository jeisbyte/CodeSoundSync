"""Reviewable visual-activity candidates, separate from renderable sound events."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from codesound_sync.models.sound_event import SoundEvent, SoundEventType


class ActivityType(str, Enum):
    """Candidate interpretations of visual changes; not confirmed user input."""

    TYPING = "typing-like activity"
    LEFT_CLICK = "possible left click"
    RIGHT_CLICK = "possible right click"
    UNCERTAIN = "uncertain visual activity"


@dataclass(frozen=True)
class ActivityCandidate:
    """An estimated visual event and the evidence behind its classification."""

    timestamp_seconds: float
    candidate_type: ActivityType
    confidence: float
    evidence: str
    change_count: int = 1

    def __post_init__(self) -> None:
        if (
            isinstance(self.timestamp_seconds, bool)
            or not isinstance(self.timestamp_seconds, (int, float))
            or not math.isfinite(self.timestamp_seconds)
            or self.timestamp_seconds < 0
        ):
            raise ValueError("Candidate timestamp must be finite and non-negative.")

        try:
            candidate_type = ActivityType(self.candidate_type)
        except (ValueError, TypeError) as exc:
            raise ValueError(
                f"Unsupported activity candidate type: {self.candidate_type!r}."
            ) from exc
        object.__setattr__(self, "candidate_type", candidate_type)

        if (
            isinstance(self.confidence, bool)
            or not isinstance(self.confidence, (int, float))
            or not math.isfinite(self.confidence)
            or not 0.0 <= self.confidence <= 1.0
        ):
            raise ValueError("Candidate confidence must be between 0 and 1.")
        if not isinstance(self.evidence, str) or not self.evidence.strip():
            raise ValueError("Candidate evidence must be a non-empty string.")
        if (
            isinstance(self.change_count, bool)
            or not isinstance(self.change_count, int)
            or self.change_count < 1
        ):
            raise ValueError("Candidate change count must be a positive integer.")

    def to_sound_event(self) -> SoundEvent | None:
        """Convert supported reviewed candidates; uncertain activity is ignored."""
        event_type = {
            ActivityType.TYPING: SoundEventType.KEYBOARD_TAP,
            ActivityType.LEFT_CLICK: SoundEventType.MOUSE_LEFT_CLICK,
            ActivityType.RIGHT_CLICK: SoundEventType.MOUSE_RIGHT_CLICK,
        }.get(self.candidate_type)
        if event_type is None:
            return None
        return SoundEvent(
            timestamp_seconds=self.timestamp_seconds,
            event_type=event_type,
            intensity=min(0.7, max(0.25, float(self.confidence))),
        )


@dataclass(frozen=True)
class ActivityAnalysisResult:
    """Transient analysis output; not serialized into existing project files."""

    candidates: tuple[ActivityCandidate, ...]
    sample_interval_seconds: float
    sampled_frame_count: int
    video_duration_seconds: float

    def __post_init__(self) -> None:
        if (
            isinstance(self.sample_interval_seconds, bool)
            or not isinstance(self.sample_interval_seconds, (int, float))
            or not math.isfinite(self.sample_interval_seconds)
            or self.sample_interval_seconds <= 0
        ):
            raise ValueError("Sample interval must be finite and greater than zero.")
        if (
            isinstance(self.sampled_frame_count, bool)
            or not isinstance(self.sampled_frame_count, int)
            or self.sampled_frame_count < 0
        ):
            raise ValueError("Sampled frame count must be a non-negative integer.")
        if (
            isinstance(self.video_duration_seconds, bool)
            or not isinstance(self.video_duration_seconds, (int, float))
            or not math.isfinite(self.video_duration_seconds)
            or self.video_duration_seconds < 0
        ):
            raise ValueError("Video duration must be finite and non-negative.")
        if not all(isinstance(candidate, ActivityCandidate) for candidate in self.candidates):
            raise ValueError("Analysis results must contain ActivityCandidate objects.")
        object.__setattr__(self, "candidates", tuple(self.candidates))


def candidates_to_sound_events(
    candidates: tuple[ActivityCandidate, ...] | list[ActivityCandidate],
) -> tuple[SoundEvent, ...]:
    """Convert reviewed candidates that the sound engine can render.

    Uncertain activity remains reviewable but is deliberately not converted into
    invented key or mouse sounds.
    """
    events = []
    for candidate in candidates:
        event = candidate.to_sound_event()
        if event is not None:
            events.append(event)
    return tuple(events)
