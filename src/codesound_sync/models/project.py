"""
Project – data model for a CodeSound Sync project.

A project ties together:
  • the source video path
  • optional MediaInfo (populated after analysis)
  • output directory
  • creation / modification timestamps
  • a stable UUID for persistence
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from codesound_sync.models.media_info import MediaInfo


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Project:
    """Mutable project state."""

    name: str
    source_video: Optional[Path] = None
    output_dir: Optional[Path] = None
    media_info: Optional[MediaInfo] = None

    # Automatically assigned
    project_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=_utcnow_iso)
    modified_at: str = field(default_factory=_utcnow_iso)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def touch(self) -> None:
        """Update the modified timestamp (call after mutating the project)."""
        self.modified_at = _utcnow_iso()

    # -----------------------------------------------------------------------
    # Serialisation
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "source_video": str(self.source_video) if self.source_video else None,
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "media_info": self.media_info.to_dict() if self.media_info else None,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        media_raw = data.get("media_info")
        return cls(
            name=data["name"],
            source_video=Path(data["source_video"]) if data.get("source_video") else None,
            output_dir=Path(data["output_dir"]) if data.get("output_dir") else None,
            media_info=MediaInfo.from_dict(media_raw) if media_raw else None,
            project_id=data.get("project_id", str(uuid.uuid4())),
            created_at=data.get("created_at", _utcnow_iso()),
            modified_at=data.get("modified_at", _utcnow_iso()),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "Project":
        return cls.from_dict(json.loads(raw))
