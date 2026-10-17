from pathlib import Path

import pytest

from codesound_sync.models.media_info import MediaInfo
from codesound_sync.models.project import Project
from codesound_sync.services.project_service import ProjectFileError, ProjectService


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


def test_project_service_loads_selected_project_file_with_media_info(
    tmp_path: Path,
) -> None:
    service = ProjectService(tmp_path / "projects")
    source = tmp_path / "lesson.mp4"
    project = Project(
        name="Lesson",
        source_video=source,
        output_dir=tmp_path / "output",
        media_info=MediaInfo(
            path=source,
            duration_seconds=65.5,
            width=1920,
            height=1080,
            frame_rate=30.0,
            video_codec="h264",
            audio_codec="aac",
            bit_rate_kbps=1500,
            size_bytes=123456,
            audio_streams=("aac",),
        ),
    )
    saved_path = service.save(project)

    loaded = service.load_file(saved_path)

    assert loaded.name == project.name
    assert loaded.source_video == source
    assert loaded.output_dir == tmp_path / "output"
    assert loaded.media_info == project.media_info
    assert loaded.project_id == project.project_id


def test_project_service_rejects_malformed_and_incompatible_files(
    tmp_path: Path,
) -> None:
    service = ProjectService(tmp_path / "projects")
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{not json", encoding="utf-8")
    incompatible = tmp_path / "incompatible.json"
    incompatible.write_text('{"unexpected": "data"}', encoding="utf-8")
    invalid_metadata = tmp_path / "invalid-metadata.json"
    invalid_metadata.write_text(
        '{"name": "Lesson", "media_info": {}}', encoding="utf-8"
    )

    with pytest.raises(ProjectFileError, match="not valid JSON"):
        service.load_file(malformed)
    with pytest.raises(ProjectFileError, match="not a valid CodeSound Sync project"):
        service.load_file(incompatible)
    with pytest.raises(ProjectFileError, match="not a valid CodeSound Sync project"):
        service.load_file(invalid_metadata)
