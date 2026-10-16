"""
Project persistence service – saves and loads Project JSON files.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from codesound_sync.config import PROJECTS_DIR
from codesound_sync.models.project import Project

log = logging.getLogger(__name__)


class ProjectService:
    """Manages project JSON files stored in PROJECTS_DIR."""

    def __init__(self, projects_dir: Path = PROJECTS_DIR) -> None:
        self._dir = projects_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, project: Project) -> Path:
        return self._dir / f"{project.project_id}.json"

    def save(self, project: Project) -> Path:
        """Persist *project* to disk; returns the file path written."""
        project.touch()
        target = self._project_path(project)
        target.write_text(project.to_json(), encoding="utf-8")
        log.info("Project saved: %s", target.name)
        return target

    def load(self, project_id: str) -> Project:
        """Load and return the project with *project_id*."""
        target = self._dir / f"{project_id}.json"
        if not target.exists():
            raise FileNotFoundError(f"Project file not found: {target.name}")
        raw = target.read_text(encoding="utf-8")
        project = Project.from_json(raw)
        log.info("Project loaded: %s", project.name)
        return project

    def list_projects(self) -> List[Project]:
        """Return all saved projects sorted by modification time (newest first)."""
        projects: List[Project] = []
        for path in self._dir.glob("*.json"):
            try:
                raw = path.read_text(encoding="utf-8")
                projects.append(Project.from_dict(json.loads(raw)))
            except Exception as exc:  # noqa: BLE001
                log.warning("Skipping corrupt project file %s: %s", path.name, exc)
        projects.sort(key=lambda p: p.modified_at, reverse=True)
        return projects

    def delete(self, project: Project) -> None:
        """Remove a project file from disk."""
        target = self._project_path(project)
        if target.exists():
            target.unlink()
            log.info("Project deleted: %s", target.name)
