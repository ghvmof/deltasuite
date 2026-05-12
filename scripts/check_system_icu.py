"""Check whether C:\\Windows\\System32\\icuuc.dll has the symbols Qt6Core needs."""

from __future__ import annotations

import os
from pathlib import Path

import pefile

SYSTEM_ICU = Path(r"C:\Windows\System32\icuuc.dll")


def main() -> None:
    if not SYSTEM_ICU.exists():
        print(f"{SYSTEM_ICU} does not exist!")
        return
    icu = pefile.PE(str(SYSTEM_ICU))
    exports = {e.name.decode() for e in icu.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
    needed = [
        "UCNV_TO_U_CALLBACK_SUBSTITUTE",
        "UCNV_FROM_U_CALLBACK_SUBSTITUTE",
        "ucnv_open",
        "ucnv_close",
        "ucnv_reset",
        "ucnv_fromUnicode",
        "ucnv_toUnicode",
    ]
    print(f"System32 icuuc.dll: {os.path.getsize(SYSTEM_ICU)} bytes, {len(exports)} exports")
    print()
    for sym in needed:
        marker = "yes" if sym in exports else "NO"
        print(f"  {marker:3s}  {sym}")
    print()
    print("First 5 export names (alphabetical):")
    for e in sorted(exports)[:5]:
        print(f"  {e}")


if __name__ == "__main__":
    main()
