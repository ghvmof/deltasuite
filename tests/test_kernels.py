"""Tests for the Delft3D kernel detection logic."""

from __future__ import annotations

from pathlib import Path

from deltasuite.core.kernels import (
    KernelInfo,
    KernelKind,
    KernelSet,
    detect_kernels,
)


def test_kernelset_is_empty_when_no_kernels() -> None:
    ks = KernelSet(bin_dir=Path("/nowhere"))
    assert ks.is_empty
    assert not ks.is_complete
    assert len(ks) == 0
    assert "No Delft3D kernels found" in ks.summary()


def test_detect_finds_fake_install(fake_kernel_dir: Path) -> None:
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    assert sets, "expected to detect at least one KernelSet"

    target = next((s for s in sets if s.bin_dir == fake_kernel_dir.resolve()), None)
    assert target is not None
    assert KernelKind.D_HYDRO in target
    assert KernelKind.DFLOWFM in target
    assert KernelKind.DIMR in target


def test_kernelinfo_uses_launcher_when_available(fake_kernel_dir: Path) -> None:
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    target = next(s for s in sets if s.bin_dir == fake_kernel_dir.resolve())
    info: KernelInfo = target[KernelKind.D_HYDRO]
    assert info.has_launcher
    assert info.best_command() == info.launcher
    assert info.display_name.startswith("Delft3D")


def test_kernelset_iteration_returns_kernelinfo(fake_kernel_dir: Path) -> None:
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    target = next(s for s in sets if s.bin_dir == fake_kernel_dir.resolve())
    for kernel in target:
        assert isinstance(kernel, KernelInfo)
        assert kernel.executable.exists()


def test_missing_runtime_dlls_reported(fake_kernel_dir: Path) -> None:
    """The fake install only provides the executables, so DLLs are missing."""
    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    target = next(s for s in sets if s.bin_dir == fake_kernel_dir.resolve())
    info = target[KernelKind.D_HYDRO]
    missing = info.missing_runtime_dlls()
    assert "flow2d3d.dll" in missing
    assert "pthreadVC2.dll" in missing


def test_missing_runtime_dlls_resolved_via_lib_dir(fake_kernel_dir: Path) -> None:
    """When DLLs live in the sibling ``lib`` directory they are considered present."""
    lib_dir = fake_kernel_dir.parent / "lib"
    lib_dir.mkdir()
    (lib_dir / "pthreadVC2.dll").write_bytes(b"MZ")
    (fake_kernel_dir / "flow2d3d.dll").write_bytes(b"MZ")

    sets = detect_kernels(extra_paths=[fake_kernel_dir], include_path=False)
    target = next(s for s in sets if s.bin_dir == fake_kernel_dir.resolve())
    info = target[KernelKind.D_HYDRO]
    assert info.missing_runtime_dlls() == []
