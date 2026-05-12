"""One-shot diagnostic: locate ICU DLLs and check Qt6Core's expectations."""

from __future__ import annotations

from pathlib import Path

import pefile
import PySide6


def main() -> None:  # noqa: PLR0912
    pyside_root = Path(PySide6.__file__).parent
    print(f"PySide6 location: {pyside_root}")

    # 1) Look for ICU DLLs everywhere reasonable.
    search_roots = [
        pyside_root,
        pyside_root.parent / "PySide6_Essentials",
        pyside_root.parent / "PySide6_Addons",
        pyside_root.parent / "shiboken6",
    ]
    print("\n=== ICU DLLs found in venv site-packages ===")
    for root in search_roots:
        if not root.exists():
            continue
        for dll in root.rglob("icu*.dll"):
            print(f"  {dll}  ({dll.stat().st_size // 1024} KB)")

    # 2) Inspect what the venv's Qt6Core.dll imports (no bundle yet).
    venv_qtcore = pyside_root / "Qt6Core.dll"
    print(f"\n=== Imports of venv {venv_qtcore.name} ===")
    pe = pefile.PE(str(venv_qtcore))
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        name = entry.dll.decode()
        if "icu" in name.lower():
            print(f"  {name}")
            for imp in entry.imports[:5]:
                sym = imp.name.decode() if imp.name else f"ord{imp.ordinal}"
                print(f"    sample sym: {sym}")

    # 3) Show what icuuc.dll (if any) exports inside venv.
    candidates = list(pyside_root.glob("icuuc*.dll"))
    print(f"\n=== icuuc*.dll inside PySide6 venv: {len(candidates)} ===")
    for cand in candidates:
        print(f"  {cand.name}")
        pe = pefile.PE(str(cand))
        if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
            samples = [
                e.name.decode()
                for e in pe.DIRECTORY_ENTRY_EXPORT.symbols
                if e.name and b"ucnv_open" in e.name
            ][:5]
            for s in samples:
                print(f"    export: {s}")

    # 4) Search system-wide for ICU 73 with un-suffixed symbols.
    print("\n=== Searching system for canonical icuuc.dll (un-suffixed exports) ===")
    candidates_paths = [
        Path(r"C:\Qt"),
        Path(r"C:\Program Files\Qt"),
        Path(r"C:\Users") / "gherrerav" / "AppData" / "Local" / "Qt",
    ]
    for base in candidates_paths:
        if not base.exists():
            continue
        for icu in base.rglob("icuuc*.dll"):
            if icu.stat().st_size < 1_000_000:
                continue
            try:
                pe = pefile.PE(str(icu))
                if not hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
                    continue
                exports = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
                if "ucnv_open" in exports:  # un-suffixed → official Qt-style
                    print(f"  CANDIDATE: {icu}  ({icu.stat().st_size // 1024} KB)")
            except Exception as exc:
                print(f"  {icu}: skipped ({exc})")


if __name__ == "__main__":
    main()
