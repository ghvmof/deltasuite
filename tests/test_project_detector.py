"""Tests for the heuristic project detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core.project import ProjectType
from deltasuite.core.project_detector import detect_project, discover_projects


def test_empty_dir_is_unknown(tmp_path: Path) -> None:
    result = detect_project(tmp_path)
    assert result.project_type is ProjectType.UNKNOWN
    assert not result.is_recognised
    assert result.main_input is None


def test_mdf_detected_as_delft3d4(tmp_path: Path) -> None:
    (tmp_path / "f34.mdf").write_text("dummy")
    result = detect_project(tmp_path)
    assert result.project_type is ProjectType.DELFT3D4
    assert result.main_input is not None
    assert result.main_input.name == "f34.mdf"


def test_mdf_with_d_hydro_xml_prefers_xml(tmp_path: Path) -> None:
    (tmp_path / "f34.mdf").write_text("")
    (tmp_path / "config_d_hydro.xml").write_text("<xml/>")
    result = detect_project(tmp_path)
    assert result.project_type is ProjectType.DELFT3D4
    assert result.main_input is not None
    assert result.main_input.name == "config_d_hydro.xml"


def test_mdu_detected_as_dflowfm(tmp_path: Path) -> None:
    (tmp_path / "model.mdu").write_text("[General]")
    result = detect_project(tmp_path)
    assert result.project_type is ProjectType.DFLOWFM


def test_dimr_wins_over_mdf_and_mdu(tmp_path: Path) -> None:
    (tmp_path / "model.mdu").write_text("")
    (tmp_path / "f34.mdf").write_text("")
    (tmp_path / "dimr_config.xml").write_text("<dimr/>")
    result = detect_project(tmp_path)
    assert result.project_type is ProjectType.DIMR
    assert result.main_input is not None
    assert result.main_input.name == "dimr_config.xml"


def test_real_f34_example_when_available() -> None:
    """If the user has the Delft3D source repo, validate against the real f34."""
    candidate = (
        Path.home()
        / "Downloads"
        / "Delft3D-main"
        / "Delft3D-main"
        / "examples"
        / "delft3d4"
        / "01_standard"
    )
    if not candidate.is_dir():
        pytest.skip("Delft3D examples not available on this machine")
    result = detect_project(candidate)
    assert result.project_type is ProjectType.DELFT3D4
    assert result.main_input is not None
    assert result.main_input.name == "config_d_hydro.xml"
    assert any(p.name == "f34.mdf" for p in result.mdf_files)


def test_non_directory_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "not_a_dir.txt"
    file_path.write_text("")
    with pytest.raises(NotADirectoryError):
        detect_project(file_path)


# ---------------------------------------------------------------------------
# discover_projects (recursive)
# ---------------------------------------------------------------------------


def _make_d3d4(directory: Path, name: str = "model.mdf") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("")


def _make_fm(directory: Path, name: str = "model.mdu") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("")


def _make_dimr(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "dimr_config.xml").write_text("<dimr/>")


def test_discover_finds_root_when_root_is_a_project(tmp_path: Path) -> None:
    _make_d3d4(tmp_path)
    found = discover_projects(tmp_path)
    assert len(found) == 1
    assert found[0].root == tmp_path.resolve()


def test_discover_finds_models_in_subdirectories(tmp_path: Path) -> None:
    _make_d3d4(tmp_path / "a" / "01_standard")
    _make_fm(tmp_path / "b" / "01_fm")
    _make_dimr(tmp_path / "b" / "02_dimr")
    found = discover_projects(tmp_path, max_depth=4)
    assert len(found) == 3
    types = sorted(p.project_type.value for p in found)
    assert types == ["delft3d4", "dflowfm", "dimr"]


def test_discover_does_not_descend_into_recognised_projects(tmp_path: Path) -> None:
    """Once a project is found, its subfolders should not produce more hits."""
    project_dir = tmp_path / "case"
    _make_d3d4(project_dir)
    _make_d3d4(project_dir / "output", name="restart.mdf")
    found = discover_projects(tmp_path)
    assert len(found) == 1
    assert found[0].root == project_dir.resolve()


def test_discover_respects_max_depth(tmp_path: Path) -> None:
    _make_d3d4(tmp_path / "a" / "b" / "c" / "deep")
    assert discover_projects(tmp_path, max_depth=2) == []
    assert len(discover_projects(tmp_path, max_depth=4)) == 1


def test_discover_skips_noise_dirs(tmp_path: Path) -> None:
    _make_d3d4(tmp_path / ".git" / "hidden")
    _make_d3d4(tmp_path / "__pycache__" / "stuff")
    _make_d3d4(tmp_path / "real_case")
    found = discover_projects(tmp_path)
    assert len(found) == 1
    assert found[0].root.name == "real_case"


def test_discover_real_delft3d_examples_when_available() -> None:
    candidate = Path.home() / "Downloads" / "Delft3D-main" / "Delft3D-main" / "examples"
    if not candidate.is_dir():
        pytest.skip("Delft3D examples not available on this machine")
    found = discover_projects(candidate, max_depth=5)
    # The repo ships ~20 example models; allow some slack but expect plenty.
    assert len(found) >= 15
    types = {p.project_type.value for p in found}
    assert {"delft3d4", "dimr"}.issubset(types)
