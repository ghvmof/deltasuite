"""PyInstaller entry point.

PyInstaller imports *this file* — not the `deltasuite` console script —
to avoid the entry-point indirection that confuses the Analysis stage
on Windows.
"""

from __future__ import annotations

import sys

from deltasuite.app.entrypoint import run

if __name__ == "__main__":
    sys.exit(run())
