"""Tests for :mod:`deltasuite.core.recent`."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core import recent as recent_mod
from deltasuite.core.recent import (
    DEFAULT_LIMIT,
    RecentEntry,
    RecentProjects,
    save_recent,
)


@pytest.fixture
def tmp_recent_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``recent_projects.toml`` to a temporary location."""
    target = tmp_path / "recent_projects.toml"

    class _FakePaths:
        recent_projects_file = target

        def __init__(self) -> None: ...

    monkeypatch.setattr(recent_mod, "get_app_paths", lambda: _FakePaths())  # noqa: PLW0108
    recent_mod.get_recent.cache_clear()
    return target


def test_default_limit_constant() -> None:
    assert DEFAULT_LIMIT >= 5


def test_add_moves_to_top(tmp_path: Path) -> None:
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()

    recent = RecentProjects()
    recent.add(project_a, name="A")
    recent.add(project_b, name="B")
    assert recent.entries[0].path == project_b

    recent.add(project_a, name="A again")
    assert recent.entries[0].path == project_a
    assert len(recent.entries) == 2  # no duplicates


def test_remove(tmp_path: Path) -> None:
    project_a = tmp_path / "a"
    project_a.mkdir()
    recent = RecentProjects()
    recent.add(project_a)
    recent.remove(project_a)
    assert recent.entries == []


def test_alive_filters_missing(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    fake = tmp_path / "ghost"
    recent = RecentProjects()
    recent.add(real)
    recent.entries.append(RecentEntry(path=fake, name="ghost"))
    alive = recent.alive()
    assert len(alive) == 1
    assert alive[0].path == real


def test_save_and_reload_roundtrip(tmp_recent_file: Path, tmp_path: Path) -> None:
    project = tmp_path / "p"
    project.mkdir()
    recent = RecentProjects()
    recent.add(project, name="P")
    save_recent(recent, tmp_recent_file)

    reloaded = recent_mod._load_from_disk(tmp_recent_file)
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0].name == "P"


def test_limit_truncates(tmp_path: Path) -> None:
    recent = RecentProjects(limit=3)
    for i in range(5):
        sub = tmp_path / f"p_{i}"
        sub.mkdir()
        recent.add(sub)
    assert len(recent.entries) == 3
