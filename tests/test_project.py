from pathlib import Path

from codesound_sync.models.project import Project
from codesound_sync.services.project_service import ProjectService


def test_project_service_persists_project(tmp_path: Path) -> None:
    service = ProjectService(tmp_path / "projects")
    project = Project(
        name="Lesson",
        source_video=Path("lesson.mp4"),
        output_dir=tmp_path / "output",
    )

    saved = service.save(project)
    loaded = service.load(project.project_id)

    assert saved.is_file()
    assert loaded.name == "Lesson"
    assert loaded.source_video == Path("lesson.mp4")
    assert loaded.output_dir == tmp_path / "output"
    assert service.list_projects()[0].project_id == project.project_id

    service.delete(project)
    assert not saved.exists()
