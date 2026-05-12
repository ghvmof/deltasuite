"""Tests for the bundled sample projects."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core import samples as samples_mod
from deltasuite.core.samples import open_bundled_sample


def _patch_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _FakePaths:
        data_dir = tmp_path

    monkeypatch.setattr(samples_mod, "get_app_paths", lambda: _FakePaths())  # noqa: PLW0108


def test_open_bundled_sample_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    project = open_bundled_sample("f34")
    assert project.root.is_dir()
    assert (project.root / "f34.mdf").exists()
    assert (project.root / "README.txt").exists()
    assert project.meta.main_input_file == "f34.mdf"


def test_open_bundled_sample_unknown_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="Unknown sample"):
        open_bundled_sample("does-not-exist")


def test_open_bundled_sample_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_data_dir(monkeypatch, tmp_path)
    a = open_bundled_sample("f34")
    b = open_bundled_sample("f34")
    assert a.root == b.root
