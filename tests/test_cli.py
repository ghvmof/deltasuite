"""Tests for the Typer-based command-line interface."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from deltasuite.cli.main import app

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "DeltaSuite" in result.output


def test_detect_no_kernels_returns_nonzero(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        "deltasuite.cli.detect.detect_kernels",
        lambda extra_paths=None, include_path=True: [],
    )
    result = runner.invoke(app, ["detect", "--no-path"])
    assert result.exit_code == 1
    assert "No Delft3D kernels detected" in result.output


def test_detect_lists_fake_kernels(fake_kernel_dir: Path) -> None:
    result = runner.invoke(app, ["detect", "--no-path", "--path", str(fake_kernel_dir)])
    assert result.exit_code == 0
    assert "d_hydro" in result.output or "Delft3D" in result.output


def test_detect_json_output(fake_kernel_dir: Path) -> None:
    result = runner.invoke(app, ["detect", "--no-path", "--path", str(fake_kernel_dir), "--json"])
    assert result.exit_code == 0
    assert '"d_hydro"' in result.output
