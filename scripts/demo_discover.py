"""Demo: scan a folder recursively and print all detected Delft3D models."""

from __future__ import annotations

import sys
from pathlib import Path

from deltasuite.core import discover_projects

DEFAULT_ROOT = Path.home() / "Downloads" / "Delft3D-main" / "Delft3D-main" / "examples"


def main(root: Path = DEFAULT_ROOT) -> int:
    if not root.is_dir():
        print(f"ERROR: not a directory: {root}", file=sys.stderr)
        return 1

    projects = discover_projects(root, max_depth=6)
    print(f"Scanned: {root}")
    print(f"Models found: {len(projects)}")
    print()
    print(f"{'#':>3}  {'TYPE':<9}  {'ENTRY POINT':<22}  LOCATION")
    print("-" * 100)
    for i, p in enumerate(projects, 1):
        rel = p.root.relative_to(root)
        entry = p.main_input.name if p.main_input else "-"
        print(f"{i:>3}  {p.project_type.value:<9}  {entry:<22}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
