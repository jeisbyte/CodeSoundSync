from pathlib import Path

from codesound_sync.config import APP_NAME, PROJECT_ROOT
from codesound_sync.utils.paths import ensure_dir, human_size, safe_stem


def test_app_config_paths_resolve_from_package() -> None:
    assert APP_NAME == "CodeSound Sync"
    assert PROJECT_ROOT == Path(__file__).resolve().parents[1]


def test_path_utilities(tmp_path: Path) -> None:
    assert safe_stem(Path("Tutorial: Part 1.mp4")) == "Tutorial__Part_1"
    assert ensure_dir(tmp_path / "nested" / "output").is_dir()
    assert human_size(1024) == "1.0 KB"
