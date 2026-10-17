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


class ProjectFileError(ValueError):
    """Raised when a project file cannot be read as a CodeSound Sync project."""


class ProjectService:
    """Manages project JSON files stored in PROJECTS_DIR."""

    def __init__(self, projects_dir: Path = PROJECTS_DIR) -> None:
        self._dir = projects_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def _project_path(self, project: Project) -> Path:
        return self._dir / f"{project.project_id}.json"

    def save(self, project: Project, path: Path | None = None) -> Path:
        """Persist *project* to disk; returns the file path written.

        When *path* is supplied, update that previously opened project file.
        Otherwise save under the project's UUID in the standard projects folder.
        """
        project.touch()
        target = Path(path) if path is not None else self._project_path(project)
        target.write_text(project.to_json(), encoding="utf-8")
        log.info("Project saved: %s", target.name)
        return target

    def load(self, project_id: str) -> Project:
        """Load and return the project with *project_id*."""
        target = self._dir / f"{project_id}.json"
        if not target.exists():
            raise FileNotFoundError(f"Project file not found: {target.name}")
        return self.load_file(target)

    def load_file(self, path: Path) -> Project:
        """Load a project from an explicitly selected JSON file."""
        target = Path(path)
        try:
            raw = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ProjectFileError(
                f"Could not read project file '{target.name}': {exc}"
            ) from exc

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProjectFileError(
                f"'{target.name}' is not valid JSON."
            ) from exc

        try:
            project = Project.from_dict(data)
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ProjectFileError(
                f"'{target.name}' is not a valid CodeSound Sync project "
                f"(missing or invalid project data)."
            ) from exc

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
