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
        if not isinstance(data, dict):
            raise ValueError("Project data must be a JSON object.")

        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Project name must be a non-empty string.")

        for key in ("source_video", "output_dir"):
            value = data.get(key)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"Project {key} must be a path string or null.")

        project_id = data.get("project_id", str(uuid.uuid4()))
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError("Project ID must be a non-empty string.")

        for key in ("created_at", "modified_at"):
            if key in data and not isinstance(data[key], str):
                raise ValueError(f"Project {key} must be a string.")

        media_raw = data.get("media_info")
        if media_raw is not None and not isinstance(media_raw, dict):
            raise ValueError("Project media information must be an object or null.")
        media_info = MediaInfo.from_dict(media_raw) if media_raw is not None else None

        return cls(
            name=name,
            source_video=Path(data["source_video"]) if data.get("source_video") else None,
            output_dir=Path(data["output_dir"]) if data.get("output_dir") else None,
            media_info=media_info,
            project_id=project_id,
            created_at=data.get("created_at", _utcnow_iso()),
            modified_at=data.get("modified_at", _utcnow_iso()),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "Project":
        return cls.from_dict(json.loads(raw))
