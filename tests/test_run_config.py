"""Tests for ``build_run_config``."""

from __future__ import annotations

from pathlib import Path

import pytest

from deltasuite.core.kernels import KernelKind, detect_kernels
from deltasuite.core.project_detector import detect_project
from deltasuite.core.run_config import RunConfigError, build_run_config


def _make_dummy_dir(tmp_path: Path, *, kind: str) -> Path:
    project = tmp_path / kind
    project.mkdir()
    if kind == "d3d4":
        (project / "f34.mdf").write_text("")
        (project / "config_d_hydro.xml").write_text("<xml/>")
    elif kind == "fm":
        (project / "model.mdu").write_text("")
    elif kind == "dimr":
        (project / "dimr_config.xml").write_text("<dimr/>")
    return project


def test_unknown_project_raises(tmp_path: Path) -> None:
    detected = detect_project(tmp_path)
    with pytest.raises(RunConfigError, match="Could not identify"):
        build_run_config(detected, kernel_sets=[])


def test_no_matching_kernel_raises(tmp_path: Path) -> None:
    detected = detect_project(_make_dummy_dir(tmp_path, kind="d3d4"))
    with pytest.raises(RunConfigError, match="No 'd_hydro' kernel"):
        build_run_config(detected, kernel_sets=[])


def test_d3d4_uses_run_dflow2d3d_with_xml_arg(tmp_path: Path, fake_kernel_dir: Path) -> None:
    detected = detect_project(_make_dummy_dir(tmp_path, kind="d3d4"))
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    config = build_run_config(detected, sets)
    assert config.kernel_kind is KernelKind.D_HYDRO
    assert config.program.name == "run_dflow2d3d.bat"
    assert config.args == ["config_d_hydro.xml"]
    assert config.working_dir == detected.root


def test_dflowfm_passes_mdu_argument(tmp_path: Path, fake_kernel_dir: Path) -> None:
    detected = detect_project(_make_dummy_dir(tmp_path, kind="fm"))
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    config = build_run_config(detected, sets)
    assert config.kernel_kind is KernelKind.DFLOWFM
    assert config.program.name == "run_dflowfm.bat"
    assert config.args == ["model.mdu"]


def test_dimr_passes_xml_argument(tmp_path: Path, fake_kernel_dir: Path) -> None:
    detected = detect_project(_make_dummy_dir(tmp_path, kind="dimr"))
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    config = build_run_config(detected, sets)
    assert config.kernel_kind is KernelKind.DIMR
    assert config.program.name == "run_dimr.bat"
    assert config.args == ["dimr_config.xml"]


def test_description_contains_kernel_and_input(tmp_path: Path, fake_kernel_dir: Path) -> None:
    detected = detect_project(_make_dummy_dir(tmp_path, kind="d3d4"))
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    config = build_run_config(detected, sets)
    assert "Delft3D" in config.description
    assert "config_d_hydro.xml" in config.description
