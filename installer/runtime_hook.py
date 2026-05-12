"""PyInstaller runtime hook for DeltaSuite.

Runs *before* any application code (including the main entry point).

Goal
----
Make the bundled Qt load cleanly even when the user's shell inherits
configuration from a different Python (Anaconda, MSYS2, system Python,
etc.).

What we explicitly do NOT do
----------------------------
We must **not** mess with ``icuuc.dll`` resolution. PySide6's official
Qt6Core.dll is built against the canonical ICU API (un-suffixed
exports such as ``ucnv_open``). Modern Windows 10/11 ships an
``icuuc.dll`` forwarder in ``System32`` that exports exactly those
canonical names, and that is what the dev wheel uses too.

Anaconda's ``netCDF4`` package, in contrast, ships its own
``icuuc.dll`` with **renamed** exports (``ucnv_open_73``) so multiple
ICU versions can coexist in one process. PyInstaller eagerly bundles
that copy because ``netCDF4`` is in our import graph. If we then force
that DLL to win the search, Qt6Core fails to resolve every single ICU
symbol -> ``WinError 127``.

So: we let ``icuuc.dll`` resolve from System32 (the OS supplies it),
and we only intervene to make sure Qt6 itself, shiboken and MSVC load
from the bundled directory.
"""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Scrub environment.
# ---------------------------------------------------------------------------
for var in (
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",
    "CONDA_PYTHON_EXE",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONSTARTUP",
    "PYTHONUSERBASE",
    "PYTHONNOUSERSITE",
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_QPA_PLATFORMTHEME",
    "QML2_IMPORT_PATH",
    "QML_IMPORT_PATH",
):
    os.environ.pop(var, None)


# ---------------------------------------------------------------------------
# 2. Steer Windows away from any *bundled* icuuc.dll (which would have
#    the wrong, suffixed exports). We delete those copies from the
#    bundle root so System32's icuuc.dll wins by default.
# ---------------------------------------------------------------------------
def _remove_bad_icu() -> dict[str, str]:
    """Remove ``icuuc.dll`` / ``icuin.dll`` from the bundle if their
    exports are suffixed (Anaconda ICU build). Qt6Core needs the
    *canonical* exports that ship with Windows' System32 ICU."""
    report: dict[str, str] = {}
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return report
    base = Path(meipass)
    pyside_dir = base / "PySide6"

    targets = [
        base / "icuuc.dll",
        base / "icuin.dll",
        pyside_dir / "icuuc.dll",
        pyside_dir / "icuin.dll",
    ]
    for target in targets:
        if not target.is_file():
            continue
        # Heuristic: bytes ``ucnv_open_`` only appear in the suffixed
        # Anaconda build. The canonical Microsoft / Qt builds use
        # ``ucnv_open\0`` (no suffix). Reading the file directly avoids
        # parsing the export table at startup.
        try:
            blob = target.read_bytes()
            if b"ucnv_open_" in blob:
                # rename out of the way; we cannot delete because the
                # bootloader holds an open handle to the bundle dir on
                # some Windows versions.
                shadow = target.with_suffix(".dll.disabled")
                target.replace(shadow)
                report[str(target.name)] = f"renamed -> {shadow.name}"
        except OSError as exc:
            report[str(target.name)] = f"could not inspect: {exc}"
    return report


_ICU_FIX = _remove_bad_icu()


# ---------------------------------------------------------------------------
# 3. Pre-load Qt + shiboken + MSVC from the bundled dirs so they win
#    over any system-wide copy.
# ---------------------------------------------------------------------------
def _pin_bundled_qt() -> dict[str, str]:  # noqa: PLR0912
    report: dict[str, str] = {}
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return {"_meipass": "missing"}
    base = Path(meipass)
    pyside_dir = base / "PySide6"
    shiboken_dir = base / "shiboken6"
    if not pyside_dir.is_dir():
        return {"PySide6_dir": f"missing at {pyside_dir}"}

    try:
        import ctypes
        from ctypes import wintypes
    except ImportError as exc:
        return {"ctypes": str(exc)}

    kernel32 = ctypes.windll.kernel32
    kernel32.SetDllDirectoryW.argtypes = (wintypes.LPCWSTR,)
    kernel32.SetDllDirectoryW.restype = wintypes.BOOL
    kernel32.LoadLibraryW.argtypes = (wintypes.LPCWSTR,)
    kernel32.LoadLibraryW.restype = wintypes.HMODULE
    kernel32.GetLastError.restype = wintypes.DWORD

    if not kernel32.SetDllDirectoryW(str(pyside_dir)):
        report["SetDllDirectoryW"] = f"WinError {kernel32.GetLastError()}"
    else:
        report["SetDllDirectoryW"] = f"ok ({pyside_dir.name})"

    if hasattr(os, "add_dll_directory"):
        for directory in (pyside_dir, shiboken_dir, base):
            if directory.is_dir():
                try:
                    os.add_dll_directory(str(directory))
                except OSError as exc:
                    report[f"add_dll_directory({directory.name})"] = str(exc)

    existing_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{pyside_dir};{shiboken_dir};{base};{existing_path}"

    def _winerror_message(code: int) -> str:
        try:
            return ctypes.WinError(code).strerror or f"WinError {code}"
        except OSError:
            return f"WinError {code}"

    # Pre-load order: low-level dependencies first so higher-level
    # ones reuse them by handle.  We deliberately do NOT pre-load
    # ``icuuc.dll`` -- that has to come from System32 (see comment at
    # the top of this file).
    candidates = (
        "VCRUNTIME140.dll",
        "VCRUNTIME140_1.dll",
        "MSVCP140.dll",
        "MSVCP140_1.dll",
        "MSVCP140_2.dll",
        "shiboken6.abi3.dll",
        "Qt6Core.dll",
        "Qt6Gui.dll",
        "Qt6Widgets.dll",
        "Qt6Network.dll",
        "Qt6OpenGL.dll",
        "Qt6Svg.dll",
    )
    for name in candidates:
        present_in: Path | None = None
        for directory in (pyside_dir, shiboken_dir, base):
            if (directory / name).is_file():
                present_in = directory
                break
        if present_in is None:
            report[name] = "not bundled"
            continue
        handle = kernel32.LoadLibraryW(name)
        if handle:
            report[name] = f"ok (from {present_in.name})"
        else:
            err = kernel32.GetLastError()
            report[name] = f"WinError {err}: {_winerror_message(err)}"
    return report


_PRELOADED = _pin_bundled_qt()


# ---------------------------------------------------------------------------
# 4. Surface bootstrap errors instead of swallowing them.
# ---------------------------------------------------------------------------
def _show_message_box(title: str, body: str) -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, body, title, 0x00000010)  # MB_ICONERROR
    except Exception:
        sys.stderr.write(f"{title}\n{body}\n")


def _excepthook(exc_type, exc_value, exc_tb):  # type: ignore[no-untyped-def]
    body = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    body += "\n\nRuntime-hook diagnostic\n"
    body += "-----------------------\n"
    if _ICU_FIX:
        body += "ICU clean-up:\n"
        for key, value in _ICU_FIX.items():
            body += f"  {key:30s} -> {value}\n"
    if _PRELOADED:
        body += "DLL pre-load:\n"
        for key, value in _PRELOADED.items():
            body += f"  {key:30s} -> {value}\n"
    body += (
        "\nIf this is a 'DLL load failed while importing QtCore' message,\n"
        "please install the Microsoft Visual C++ Redistributable 2015-2022:\n"
        "https://aka.ms/vs/17/release/vc_redist.x64.exe\n"
    )
    _show_message_box("DeltaSuite - startup error", body)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook
