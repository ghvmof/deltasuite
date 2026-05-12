"""Tests for the project model and its TOML serialization."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core.project import PROJECT_FILE_NAME, Project, ProjectType


def test_create_project_writes_metadata_file(tmp_project_root: Path) -> None:
    project = Project.create(tmp_project_root, name="Estuary 2026")
    assert project.project_file.is_file()
    assert project.output_dir.is_dir()
    assert project.meta.name == "Estuary 2026"
    assert project.meta.project_type == ProjectType.UNKNOWN


def test_create_project_refuses_non_empty_directory(tmp_project_root: Path) -> None:
    (tmp_project_root / "old.txt").write_text("hello")
    with pytest.raises(FileExistsError):
        Project.create(tmp_project_root, name="should fail")


def test_open_project_round_trips(tmp_project_root: Path) -> None:
    created = Project.create(
        tmp_project_root,
        name="Coastal Bay",
        project_type=ProjectType.DELFT3D4,
        description="Tidal study",
        author="J. Doe",
        main_input_file="bay.mdf",
    )
    opened = Project.open(tmp_project_root)
    assert opened.meta.name == created.meta.name
    assert opened.meta.project_type == ProjectType.DELFT3D4
    assert opened.meta.author == "J. Doe"
    assert opened.meta.main_input_file == "bay.mdf"


def test_open_project_accepts_either_dir_or_file(tmp_project_root: Path) -> None:
    Project.create(tmp_project_root, name="Lake")
    by_dir = Project.open(tmp_project_root)
    by_file = Project.open(tmp_project_root / PROJECT_FILE_NAME)
    assert by_dir.meta.uuid == by_file.meta.uuid


def test_open_project_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        Project.open(tmp_path)


def test_list_input_files(tmp_project_root: Path) -> None:
    project = Project.create(tmp_project_root, name="River")
    (tmp_project_root / "case.mdf").write_text("")
    (tmp_project_root / "grid.grd").write_text("")
    (tmp_project_root / "ignore_me.txt").write_text("")

    files = {p.name for p in project.list_input_files()}
    assert "case.mdf" in files
    assert "grid.grd" in files
    assert "ignore_me.txt" not in files
