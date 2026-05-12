"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

# Ensure Qt runs headless in CI and on machines without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture()
def tmp_project_root(tmp_path: Path) -> Iterator[Path]:
    """Provide a temporary, empty directory for project tests."""
    root = tmp_path / "my_project"
    root.mkdir()
    return root


@pytest.fixture()
def fake_kernel_dir(tmp_path: Path) -> Path:
    """Create a directory pretending to host compiled Delft3D kernels.

    Each fake binary is a small executable file so the detector picks it up
    without actually being able to run it.
    """
    bin_dir = tmp_path / "install_all" / "bin"
    bin_dir.mkdir(parents=True)
    fake_files = [
        ("d_hydro.exe", "run_dflow2d3d.bat"),
        ("dflowfm-cli.exe", "run_dflowfm.bat"),
        ("dimr.exe", "run_dimr.bat"),
        ("wave.exe", "run_dwaves.bat"),
        ("delwaq.exe", "run_delwaq.bat"),
        ("delpar.exe", "run_delpar.bat"),
    ]
    for exe, launcher in fake_files:
        exe_path = bin_dir / exe
        exe_path.write_bytes(b"MZ\x90\x00fake-binary")
        exe_path.chmod(0o755)
        (bin_dir / launcher).write_text("@echo off\nrem fake launcher\n")
    return bin_dir
