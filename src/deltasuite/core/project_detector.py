"""Heuristic detection of Delft3D project layouts on disk.

Given an arbitrary directory, this module tries to identify whether it
contains a Delft3D 4 model (``.mdf`` + ``config_d_hydro.xml``), a D-Flow FM
model (``.mdu``), a DIMR coupling (``dimr_config.xml``), or none of the
above.

The result is a :class:`DetectedProject` describing what was found, used
both by the *Open Folder* flow (to materialise an in-memory project) and
by the run controller (to choose the right launcher).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deltasuite.core.project import ProjectType


@dataclass(frozen=True, slots=True)
class DetectedProject:
    """Summary of what was found in a candidate project directory."""

    root: Path
    project_type: ProjectType
    """Best-effort classification of the model family."""

    main_input: Path | None
    """Entry-point file: ``.mdf``, ``.mdu``, ``config_d_hydro.xml`` or
    ``dimr_config.xml`` depending on the project type."""

    mdf_files: tuple[Path, ...] = ()
    mdu_files: tuple[Path, ...] = ()
    dimr_files: tuple[Path, ...] = ()
    d_hydro_configs: tuple[Path, ...] = ()

    @property
    def is_recognised(self) -> bool:
        """``True`` when the project type was successfully identified."""
        return self.project_type is not ProjectType.UNKNOWN

    @property
    def description(self) -> str:
        """Short human-readable label like ``"Delft3D 4 model: f34.mdf"``."""
        labels = {
            ProjectType.DELFT3D4: "Delft3D 4 model",
            ProjectType.DFLOWFM: "D-Flow FM model",
            ProjectType.DIMR: "DIMR coupling",
            ProjectType.UNKNOWN: "Unknown project type",
        }
        label = labels[self.project_type]
        if self.main_input is not None:
            return f"{label}: {self.main_input.name}"
        return label


_DIMR_NAMES: frozenset[str] = frozenset({"dimr_config.xml", "dimr.xml", "config_dimr.xml"})
_D_HYDRO_NAMES: frozenset[str] = frozenset({"config_d_hydro.xml", "config_flow2d3d.xml"})


def detect_project(directory: Path) -> DetectedProject:
    """Inspect ``directory`` (non-recursively) and return a :class:`DetectedProject`.

    The detection order is:

    1. **DIMR** — wins if a ``dimr_config.xml`` is present (it can drive any
       combination of the other engines).
    2. **D-Flow FM** — any ``.mdu`` file.
    3. **Delft3D 4** — a ``.mdf`` file plus ideally a ``config_d_hydro.xml``.
    4. **Unknown** — none of the above.
    """
    directory = Path(directory).expanduser().resolve()
    if not directory.is_dir():
        raise NotADirectoryError(f"Not a directory: {directory}")

    mdf_files = tuple(sorted(directory.glob("*.mdf")))
    mdu_files = tuple(sorted(directory.glob("*.mdu")))
    dimr_files = tuple(p for p in sorted(directory.glob("*.xml")) if p.name.lower() in _DIMR_NAMES)
    d_hydro_configs = tuple(
        p for p in sorted(directory.glob("*.xml")) if p.name.lower() in _D_HYDRO_NAMES
    )

    if dimr_files:
        project_type = ProjectType.DIMR
        main_input: Path | None = dimr_files[0]
    elif mdu_files:
        project_type = ProjectType.DFLOWFM
        main_input = mdu_files[0]
    elif mdf_files:
        project_type = ProjectType.DELFT3D4
        main_input = d_hydro_configs[0] if d_hydro_configs else mdf_files[0]
    else:
        project_type = ProjectType.UNKNOWN
        main_input = None

    return DetectedProject(
        root=directory,
        project_type=project_type,
        main_input=main_input,
        mdf_files=mdf_files,
        mdu_files=mdu_files,
        dimr_files=dimr_files,
        d_hydro_configs=d_hydro_configs,
    )


_SKIP_DIR_NAMES: frozenset[str] = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "__pycache__",
        ".idea",
        ".vscode",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "build",
        "dist",
        "_build",
        "site-packages",
        "output",
        "outputs",
        "results",
    }
)


def discover_projects(
    root: Path,
    *,
    max_depth: int = 4,
    max_results: int = 200,
) -> list[DetectedProject]:
    """Recursively walk ``root`` looking for Delft3D project directories.

    The recursion is bounded by:

    * ``max_depth`` — how deep to descend (0 = only ``root`` itself).
    * ``max_results`` — abort after this many projects are found.

    Common noise directories (``.git``, ``.venv``, ``__pycache__``, build /
    output folders…) are pruned. When a directory is itself recognised as a
    project, we **stop descending** into it: nested ``output/`` or
    ``results/`` subfolders should not generate spurious hits.
    """
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {root}")

    found: list[DetectedProject] = []

    def _walk(current: Path, depth: int) -> None:
        if len(found) >= max_results:
            return
        try:
            detected = detect_project(current)
        except NotADirectoryError:
            return

        if detected.is_recognised:
            found.append(detected)
            return

        if depth >= max_depth:
            return

        try:
            entries = sorted(p for p in current.iterdir() if p.is_dir())
        except (OSError, PermissionError):
            return
        for sub in entries:
            if sub.name.startswith(".") or sub.name.lower() in _SKIP_DIR_NAMES:
                continue
            _walk(sub, depth + 1)

    _walk(root, 0)
    return found
