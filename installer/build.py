"""End-to-end local build of the DeltaSuite Windows installer.

Steps performed by this script:

1. Regenerate the application icons (``installer/branding/``).
2. Run PyInstaller against ``installer/deltasuite.spec``.
3. Optionally invoke Inno Setup if ``ISCC.exe`` is on ``PATH`` or in
   the standard install location.

CI does the same thing in three explicit YAML steps; on a developer's
machine this single script is more convenient.

Usage::

    python installer/build.py [--skip-iscc] [--skip-icons]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = ROOT / "installer"
BRANDING_DIR = INSTALLER_DIR / "branding"
SPEC_FILE = INSTALLER_DIR / "deltasuite.spec"
ISS_FILE = INSTALLER_DIR / "deltasuite.iss"

ISCC_DEFAULT_PATHS = (
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
)


def _detect_version() -> str:
    try:
        return version("deltasuite")
    except PackageNotFoundError:
        return "0.0.0"


def _find_iscc() -> Path | None:
    found = shutil.which("ISCC")
    if found:
        return Path(found)
    return next((p for p in ISCC_DEFAULT_PATHS if p.is_file()), None)


def _run(cmd: list[str], cwd: Path) -> None:
    print(f"\n>>> {' '.join(cmd)}\n")
    completed = subprocess.run(cmd, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"Command failed (exit {completed.returncode}): {' '.join(cmd)}")


def _step_icons() -> None:
    script = ROOT / "scripts" / "make_icons.py"
    _run([sys.executable, str(script)], cwd=ROOT)
    if not (BRANDING_DIR / "icon.ico").is_file():
        raise SystemExit(f"Icon generation failed: {BRANDING_DIR / 'icon.ico'} missing")


def _step_pyinstaller() -> None:
    dist = INSTALLER_DIR / "dist"
    work = INSTALLER_DIR / "build"
    _run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            str(SPEC_FILE),
            "--noconfirm",
            "--clean",
            f"--distpath={dist}",
            f"--workpath={work}",
        ],
        cwd=INSTALLER_DIR,
    )
    bundle = dist / "DeltaSuite"
    exe_name = "DeltaSuite.exe" if os.name == "nt" else "DeltaSuite"
    exe = bundle / exe_name
    if not exe.is_file():
        raise SystemExit(f"PyInstaller did not produce {exe}.")
    if os.name == "nt":
        _fix_icu_naming(bundle)


def _fix_icu_naming(bundle_dir: Path) -> None:
    """Quarantine bundled ``icuuc.dll`` / ``icuin.dll`` with renamed exports.

    PyInstaller eagerly bundles the ``icuuc.dll`` shipped by Anaconda's
    ``netCDF4`` (because ``netCDF4`` is in our import graph). That copy
    re-exports every ICU symbol with a version suffix
    (``ucnv_open_73``) so multiple ICU runtimes can coexist. PySide6's
    Qt6Core.dll, in contrast, links against the canonical names
    (``ucnv_open``) which are exported by the forwarder
    ``C:\\Windows\\System32\\icuuc.dll`` that ships with Windows 10/11.

    If we leave the Anaconda copy in the bundle, the loader resolves
    ``icuuc.dll`` to it, the canonical exports are missing and Qt6Core
    fails to load with ``WinError 127``. We rename the offending DLL
    out of the way so the loader transparently falls back to System32,
    which is exactly what PySide6 does in development.
    """
    internal = bundle_dir / "_internal"
    pyside_dir = internal / "PySide6"
    if not internal.is_dir():
        return

    # Anaconda's ``netCDF4`` ships an ``icuuc.dll`` with renamed
    # exports (``ucnv_open_73``) so multiple ICU versions can coexist
    # in one process. PyInstaller eagerly bundles that copy because
    # ``netCDF4`` is in our import graph -- but Qt6Core.dll expects
    # the *canonical* exports (``ucnv_open``) that ship with the
    # forwarder ``C:\\Windows\\System32\\icuuc.dll`` on Windows
    # 10/11. If we leave the Anaconda copy in the bundle root, the
    # Windows DLL loader picks it up first and Qt6Core fails to
    # resolve every single ICU symbol -> ``WinError 127``.
    #
    # Solution: rename any unsuffixed bundled ICU DLL out of the way
    # so the loader falls back to System32. The runtime hook does the
    # same on already-frozen bundles for defence in depth.
    repaired: list[str] = []
    for unversioned in ("icuuc.dll", "icuin.dll"):
        for directory in (internal, pyside_dir):
            target = directory / unversioned
            if not target.is_file():
                continue
            try:
                blob = target.read_bytes()
            except OSError:
                continue
            if b"ucnv_open_" not in blob:
                continue  # canonical exports -> safe to keep
            shadow = target.with_suffix(".dll.disabled")
            target.replace(shadow)
            repaired.append(f"renamed {target.name} -> {shadow.name} ({directory.name})")

    if repaired:
        print("ICU DLL clean-up:")
        for line in repaired:
            print(f"  {line}")


def _step_iscc(version_str: str) -> None:
    iscc = _find_iscc()
    if iscc is None:
        print(
            "\n[skip] Inno Setup compiler (ISCC) not found. "
            "Install https://jrsoftware.org/isinfo.php and re-run this script "
            "to produce DeltaSuite-<version>-Setup.exe."
        )
        return
    _run(
        [
            str(iscc),
            f"/DMyAppVersion={version_str}",
            str(ISS_FILE),
        ],
        cwd=INSTALLER_DIR,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-icons",
        action="store_true",
        help="Reuse the icons already in installer/branding.",
    )
    parser.add_argument(
        "--skip-iscc",
        action="store_true",
        help="Skip the Inno Setup compilation (CI uses a separate step).",
    )
    parser.add_argument(
        "--skip-pyinstaller",
        action="store_true",
        help="Reuse the PyInstaller dist/ from a previous build.",
    )
    args = parser.parse_args()

    if os.name != "nt" and not args.skip_iscc:
        # ISCC only runs on Windows; auto-skip on Linux/macOS so this
        # script is friendly for cross-platform contributors.
        args.skip_iscc = True

    version_str = _detect_version()
    print(f"DeltaSuite version: {version_str}")

    if not args.skip_icons:
        _step_icons()
    if not args.skip_pyinstaller:
        _step_pyinstaller()
    if not args.skip_iscc:
        _step_iscc(version_str)

    print("\n>>> All requested build steps completed successfully.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
