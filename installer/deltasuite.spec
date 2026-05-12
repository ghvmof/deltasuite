# PyInstaller spec for DeltaSuite (Windows / macOS / Linux).
#
# Usage::
#
#     pip install -e .[build]
#     pyinstaller installer/deltasuite.spec --noconfirm
#
# Output: ``installer/dist/DeltaSuite/DeltaSuite[.exe]``.
# The Inno Setup script (``installer/deltasuite.iss``) consumes that
# folder verbatim.
#
# Design notes
# ------------
# We let PyInstaller's bundled hooks do the heavy lifting for PySide6
# and matplotlib (they are remarkably good in PyInstaller 6.x). For
# scientific stacks (xarray, netCDF4, scipy) we still ask for explicit
# data and dynamic-libs collection because they ship resources outside
# their `__init__` reach.

# pyright: reportUndefinedVariable=false
# ruff: noqa
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH).resolve().parent
BRANDING = PROJECT_ROOT / "installer" / "branding"

datas = []
binaries = []
hiddenimports: list[str] = []

# --- Branding ---------------------------------------------------------------
if (BRANDING / "icon.png").exists():
    datas.append((str(BRANDING / "icon.png"), "deltasuite/branding"))

# --- Bundle the documentation user guide for offline access -----------------
docs_user = PROJECT_ROOT / "docs" / "user_guide"
if docs_user.is_dir():
    datas.append((str(docs_user), "deltasuite/docs/user_guide"))

# --- Scientific stacks ------------------------------------------------------
# scipy and netCDF4 ship a non-trivial amount of native libraries that
# their hooks miss because they are loaded via ctypes at runtime.
for pkg in ("xarray", "netCDF4", "scipy"):
    datas += collect_data_files(pkg)
    binaries += collect_dynamic_libs(pkg)

# matplotlib's Qt backend is the one we rely on at runtime; pull in the
# full set of submodules so dynamic dispatch (`get_backend('qtagg')`)
# works inside the frozen bundle.
hiddenimports += collect_submodules("matplotlib.backends")
hiddenimports += [
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_agg",
]

# pydantic v2 lazily resolves model_validators per type; help PyInstaller.
hiddenimports += ["pydantic.deprecated.decorator", "pydantic_core"]


a = Analysis(
    [str(PROJECT_ROOT / "installer" / "entry.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "installer" / "runtime_hook.py")],
    excludes=[
        "tkinter",
        "pytest",
        "_pytest",
        "pytestqt",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

icon = None
if sys.platform == "win32" and (BRANDING / "icon.ico").exists():
    icon = str(BRANDING / "icon.ico")
elif sys.platform == "darwin" and (BRANDING / "icon.icns").exists():
    icon = str(BRANDING / "icon.icns")

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DeltaSuite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DeltaSuite",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="DeltaSuite.app",
        icon=icon,
        bundle_identifier="org.deltasuite.app",
        info_plist={
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "0.1.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
        },
    )
