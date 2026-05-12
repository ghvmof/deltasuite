"""Detection and validation of compiled Delft3D kernels.

DeltaSuite invokes the official Delft3D engines (``d_hydro``, ``dflowfm-cli``,
``wave``, ``delwaq``, etc.) as subprocesses to run simulations. This module
locates those binaries on the user's system using a layered strategy:

1. **Explicit override:** path provided through application settings.
2. **Environment variable:** ``DELTASUITE_KERNEL_DIR``.
3. **Common installation patterns:** Deltares Service Pack, source-built
   ``install_*`` folders, system PATH.

The result is a :class:`KernelSet` describing which engines are available,
their version (when introspectable) and the path to the recommended ``run_*.bat``
launcher script if present.

.. important::
   Detection is **purely passive**: it never launches the kernel binaries.
   Running them outside their carefully prepared environment (DLL search
   path, Intel runtime, MPI, ...) can pop up modal Windows dialogs about
   missing DLLs, which would freeze the application. Version metadata is
   instead read from the PE file headers when possible.
"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from enum import StrEnum, unique
from pathlib import Path

from loguru import logger


@unique
class KernelKind(StrEnum):
    """Identifiers for the supported Delft3D simulation engines."""

    D_HYDRO = "d_hydro"
    """Delft3D 4 launcher (orchestrates flow2d3d, wave, rtc)."""

    DFLOWFM = "dflowfm"
    """D-Flow Flexible Mesh hydrodynamics (unstructured)."""

    DIMR = "dimr"
    """Deltares Integrated Model Runner (D-Flow FM coupling)."""

    WAVE = "wave"
    """SWAN-based wave model."""

    DELWAQ = "delwaq"
    """D-Water Quality (WAQ)."""

    DELPAR = "delpar"
    """Particle tracking (PART)."""

    RTC = "rtc"
    """Real-Time Control."""


_EXECUTABLE_NAMES: dict[KernelKind, tuple[str, ...]] = {
    KernelKind.D_HYDRO: ("d_hydro.exe", "d_hydro"),
    KernelKind.DFLOWFM: ("dflowfm-cli.exe", "dflowfm-cli", "dflowfm"),
    KernelKind.DIMR: ("dimr.exe", "dimr"),
    KernelKind.WAVE: ("wave.exe", "wave_exe.exe", "wave"),
    KernelKind.DELWAQ: ("delwaq.exe", "delwaq"),
    KernelKind.DELPAR: ("delpar.exe", "delpar"),
    KernelKind.RTC: ("rtc.exe", "rtc"),
}


_LAUNCHER_NAMES: dict[KernelKind, tuple[str, ...]] = {
    KernelKind.D_HYDRO: ("run_dflow2d3d.bat", "run_dflow2d3d.sh"),
    KernelKind.DFLOWFM: ("run_dflowfm.bat", "run_dflowfm.sh"),
    KernelKind.DIMR: ("run_dimr.bat", "run_dimr.sh"),
    KernelKind.WAVE: ("run_dwaves.bat", "run_dwaves.sh"),
    KernelKind.DELWAQ: ("run_delwaq.bat", "run_delwaq.sh"),
    KernelKind.DELPAR: ("run_delpar.bat", "run_delpar.sh"),
    KernelKind.RTC: ("run_rtc.bat", "run_rtc.sh"),
}


_REQUIRED_RUNTIME_DLLS: dict[KernelKind, tuple[str, ...]] = {
    KernelKind.D_HYDRO: ("flow2d3d.dll", "pthreadVC2.dll"),
    KernelKind.DFLOWFM: ("dflowfm.dll",),
    KernelKind.DIMR: ("dimr.dll",),
    KernelKind.WAVE: ("wave.dll",),
    KernelKind.DELWAQ: ("delwaq.dll",),
    KernelKind.DELPAR: (),
    KernelKind.RTC: ("FBCTools_BMI.dll",),
}


@dataclass(frozen=True, slots=True)
class KernelInfo:
    """Description of one discovered Delft3D simulation engine.

    :param kind: Type of kernel.
    :param executable: Absolute path to the engine binary.
    :param launcher: Optional ``run_*.bat`` script that pre-configures the
        DLL search path before invoking the binary. When present this is
        the recommended way to run the engine.
    :param version: Version string when introspectable, extracted from the
        PE file headers without executing the binary.
    :param size_mb: File size in megabytes, useful for sanity checks.
    """

    kind: KernelKind
    executable: Path
    launcher: Path | None = None
    version: str | None = None
    size_mb: float = 0.0

    @property
    def name(self) -> str:
        """Short kernel name (``"d_hydro"``, ``"dflowfm"``, ...)."""
        return self.kind.value

    @property
    def display_name(self) -> str:
        """Human-readable kernel name."""
        return _DISPLAY_NAMES[self.kind]

    @property
    def has_launcher(self) -> bool:
        """``True`` if a ``run_*`` launcher script was located."""
        return self.launcher is not None and self.launcher.exists()

    def best_command(self) -> Path:
        """Return the launcher when available, otherwise the raw executable.

        DeltaSuite always prefers the ``run_*.bat`` launcher because it
        configures the DLL search path (Intel runtime, PETSc, pthreads,
        NetCDF) before invoking the engine. Calling the ``.exe`` directly
        usually fails with a "missing DLL" Windows dialog.
        """
        if self.launcher is not None and self.launcher.exists():
            return self.launcher
        return self.executable

    def missing_runtime_dlls(self, search_dirs: list[Path] | None = None) -> list[str]:
        """Return the list of required runtime DLLs that are not findable.

        :param search_dirs: Extra directories to look in. By default the
            executable's own directory plus the sibling ``..\\lib`` and
            ``..\\share`` folders (the layout produced by Delft3D's CMake
            install) are scanned, mirroring what the launcher script does.
        """
        required = _REQUIRED_RUNTIME_DLLS.get(self.kind, ())
        if not required:
            return []

        bin_dir = self.executable.parent
        roots: list[Path] = [bin_dir, bin_dir.parent / "lib", bin_dir.parent / "share"]
        if search_dirs:
            roots.extend(search_dirs)

        missing: list[str] = []
        for dll in required:
            if not any((root / dll).is_file() for root in roots if root.exists()):
                missing.append(dll)
        return missing


_DISPLAY_NAMES: dict[KernelKind, str] = {
    KernelKind.D_HYDRO: "Delft3D-FLOW (d_hydro)",
    KernelKind.DFLOWFM: "D-Flow Flexible Mesh",
    KernelKind.DIMR: "Deltares Integrated Model Runner",
    KernelKind.WAVE: "D-Waves / SWAN",
    KernelKind.DELWAQ: "D-Water Quality",
    KernelKind.DELPAR: "D-Particle tracking",
    KernelKind.RTC: "Real-Time Control",
}


@dataclass(frozen=True, slots=True)
class KernelSet:
    """Collection of detected kernels rooted in a single ``bin`` directory.

    A typical compiled Delft3D installation places all engines under one
    ``install_<config>/bin`` folder. ``KernelSet`` represents that grouping.
    """

    bin_dir: Path
    kernels: dict[KernelKind, KernelInfo] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.kernels)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.kernels.values())

    def __contains__(self, kind: KernelKind) -> bool:
        return kind in self.kernels

    def __getitem__(self, kind: KernelKind) -> KernelInfo:
        return self.kernels[kind]

    def get(self, kind: KernelKind) -> KernelInfo | None:
        """Return the :class:`KernelInfo` for ``kind`` if present."""
        return self.kernels.get(kind)

    @property
    def is_complete(self) -> bool:
        """``True`` when all known kernel kinds were found in this set."""
        return set(self.kernels) == set(KernelKind)

    @property
    def is_empty(self) -> bool:
        """``True`` when no kernels were found."""
        return not self.kernels

    def summary(self) -> str:
        """Return a short multi-line summary suitable for the status bar."""
        if self.is_empty:
            return f"No Delft3D kernels found at {self.bin_dir}"
        kernels = ", ".join(sorted(k.name for k in self))
        return f"{len(self)} kernel(s) at {self.bin_dir}: {kernels}"


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------


def _candidate_directories(extra: list[Path] | None = None) -> list[Path]:
    """Build an ordered list of directories where kernels may live.

    The order matters: earlier entries take precedence when the same kernel
    is found in multiple places.
    """
    candidates: list[Path] = []

    if extra:
        candidates.extend(p for p in extra if p)

    env_dir = os.environ.get("DELTASUITE_KERNEL_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    candidates.extend(_search_source_builds())
    candidates.extend(_search_deltares_service_pack())

    seen: set[Path] = set()
    unique_candidates: list[Path] = []
    for path in candidates:
        try:
            resolved = path.expanduser().resolve()
        except (OSError, RuntimeError):
            continue
        if resolved in seen or not resolved.is_dir():
            continue
        seen.add(resolved)
        unique_candidates.append(resolved)
    return unique_candidates


def _search_source_builds() -> list[Path]:
    """Look for ``install_*/bin`` folders under common development roots."""
    patterns = ("install_all/bin", "install_d3d4-suite/bin", "install_fm-suite/bin")
    roots = [
        Path.home() / "Downloads" / "Delft3D-main" / "Delft3D-main",
        Path.home() / "Downloads" / "Delft3D",
        Path.home() / "Dev" / "Delft3D",
        Path("C:/Dev/Delft3D"),
        Path("C:/checkouts"),
        Path("/opt/delft3d"),
    ]
    found: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for sub in patterns:
            candidate = root / sub
            if candidate.is_dir():
                found.append(candidate)
    return found


def _search_deltares_service_pack() -> list[Path]:
    """Detect Delft3D 4 GUI installations bundled with binaries."""
    if platform.system() != "Windows":
        return []
    program_files = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")),
    ]
    found: list[Path] = []
    for pf in program_files:
        if not pf.exists():
            continue
        try:
            for entry in pf.iterdir():
                if not entry.is_dir() or "Delft3D" not in entry.name:
                    continue
                for sub in ("x64/flow2d3d/bin", "x64/dflowfm/bin", "x64/bin"):
                    candidate = entry / sub
                    if candidate.is_dir():
                        found.append(candidate)
        except OSError:  # pragma: no cover - permission issues
            continue
    return found


def _executable_in(directory: Path, names: tuple[str, ...]) -> Path | None:
    """Return the first file in ``directory`` matching one of ``names``."""
    for name in names:
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK | os.R_OK):
            return candidate
    return None


def _launcher_in(directory: Path, names: tuple[str, ...]) -> Path | None:
    """Return the first launcher script matching ``names``."""
    for name in names:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _scan_directory(directory: Path) -> KernelSet:
    """Scan a single directory and return all kernels found inside it."""
    found: dict[KernelKind, KernelInfo] = {}
    for kind in KernelKind:
        executable = _executable_in(directory, _EXECUTABLE_NAMES[kind])
        if executable is None:
            continue
        launcher = _launcher_in(directory, _LAUNCHER_NAMES[kind])
        try:
            size_mb = executable.stat().st_size / (1024 * 1024)
        except OSError:
            size_mb = 0.0
        found[kind] = KernelInfo(
            kind=kind,
            executable=executable,
            launcher=launcher,
            version=_introspect_version(executable),
            size_mb=round(size_mb, 2),
        )
    return KernelSet(bin_dir=directory, kernels=found)


def _introspect_version(executable: Path) -> str | None:
    """Read the embedded ``FileVersion`` / ``ProductVersion`` from a PE file.

    On Windows the version is read from the executable's resource section
    using the Win32 API. This is **passive**: the binary is never executed,
    which avoids triggering modal "missing DLL" dialogs that can freeze the
    application. On other platforms, ``None`` is returned.
    """
    if platform.system() != "Windows":
        return None
    try:
        return _read_pe_version(executable)
    except (OSError, ValueError):
        return None


def _read_pe_version(executable: Path) -> str | None:
    """Extract version metadata from a Windows PE file via ``ctypes``.

    Returns the most descriptive string available, falling back through
    ``FileVersion`` → ``ProductVersion`` → fixed numeric version → ``None``.
    """
    import ctypes
    from ctypes import wintypes

    version_dll = ctypes.WinDLL("version", use_last_error=True)

    GetFileVersionInfoSizeW = version_dll.GetFileVersionInfoSizeW
    GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    GetFileVersionInfoSizeW.restype = wintypes.DWORD

    GetFileVersionInfoW = version_dll.GetFileVersionInfoW
    GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    GetFileVersionInfoW.restype = wintypes.BOOL

    VerQueryValueW = version_dll.VerQueryValueW
    VerQueryValueW.argtypes = [
        wintypes.LPCVOID,
        wintypes.LPCWSTR,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.UINT),
    ]
    VerQueryValueW.restype = wintypes.BOOL

    handle = wintypes.DWORD(0)
    size = GetFileVersionInfoSizeW(str(executable), ctypes.byref(handle))
    if not size:
        return None

    buffer = ctypes.create_string_buffer(size)
    if not GetFileVersionInfoW(str(executable), 0, size, buffer):
        return None

    # Discover available translations (language + code page combinations).
    translate_ptr = wintypes.LPVOID()
    translate_len = wintypes.UINT()
    if VerQueryValueW(
        buffer,
        r"\VarFileInfo\Translation",
        ctypes.byref(translate_ptr),
        ctypes.byref(translate_len),
    ):
        translations = ctypes.cast(
            translate_ptr, ctypes.POINTER(ctypes.c_uint16 * (translate_len.value // 2))
        ).contents
        for i in range(0, len(translations), 2):
            lang = translations[i]
            codepage = translations[i + 1]
            for field_name in ("FileVersion", "ProductVersion"):
                sub_block = rf"\StringFileInfo\{lang:04x}{codepage:04x}\{field_name}"
                value_ptr = wintypes.LPVOID()
                value_len = wintypes.UINT()
                if VerQueryValueW(
                    buffer, sub_block, ctypes.byref(value_ptr), ctypes.byref(value_len)
                ):
                    string_value = ctypes.wstring_at(value_ptr, value_len.value).strip("\x00 ")
                    if string_value:
                        return string_value[:120]
    return None


def detect_kernels(
    extra_paths: list[Path] | None = None,
    *,
    include_path: bool = True,
) -> list[KernelSet]:
    """Discover all Delft3D kernel installations on the system.

    :param extra_paths: Additional directories to scan first. These take
        precedence over auto-detected locations.
    :param include_path: When ``True`` also search the system ``PATH`` for
        loose kernel binaries.
    :returns: A list of :class:`KernelSet`, one per directory containing at
        least one recognized kernel. May be empty.
    """
    sets: list[KernelSet] = []
    seen_dirs: set[Path] = set()

    for directory in _candidate_directories(extra_paths):
        if directory in seen_dirs:
            continue
        seen_dirs.add(directory)
        ks = _scan_directory(directory)
        if not ks.is_empty:
            logger.debug("Found {} kernel(s) at {}", len(ks), directory)
            sets.append(ks)

    if include_path:
        path_kernels = _scan_path()
        if not path_kernels.is_empty and path_kernels.bin_dir not in seen_dirs:
            sets.append(path_kernels)

    return sets


def _scan_path() -> KernelSet:
    """Look for kernels available on the system ``PATH``.

    All kernels found this way are reported as belonging to a synthetic
    ``$PATH`` directory because they may live in different folders.
    """
    found: dict[KernelKind, KernelInfo] = {}
    for kind in KernelKind:
        for name in _EXECUTABLE_NAMES[kind]:
            located = shutil.which(name)
            if located:
                executable = Path(located)
                try:
                    size_mb = executable.stat().st_size / (1024 * 1024)
                except OSError:
                    size_mb = 0.0
                found[kind] = KernelInfo(
                    kind=kind,
                    executable=executable,
                    launcher=None,
                    version=_introspect_version(executable),
                    size_mb=round(size_mb, 2),
                )
                break
    return KernelSet(bin_dir=Path("$PATH"), kernels=found)
