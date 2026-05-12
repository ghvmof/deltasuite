"""Built-in tiny sample projects used by the welcome screen.

A *sample* is a self-contained Delft3D 4 model that DeltaSuite materialises
on disk from a Python builder. We deliberately avoid bundling binary
inputs (grids, dep files…) — instead, the builder writes them
programmatically with NumPy. This keeps the wheel small and platform
agnostic.

Use :func:`open_bundled_sample` to drop the sample into the user's data
directory and return a :class:`~deltasuite.core.project.Project` ready
to be opened by the GUI.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from deltasuite.core.paths import get_app_paths
from deltasuite.core.project import Project, ProjectMeta, ProjectType

_F34_MDF: str = """\
* DeltaSuite tutorial sample
* Tiny rectangular flow model based on the official Delft3D F34 case.
Ident   = #Delft3D-FLOW 4.05.00#
Runtxt  = #DeltaSuite tutorial sample - rectangular tidal channel#
Filcco  = #grid.grd#
Fildep  = #depth.dep#
Tstart  = 0.0
Tstop   = 1440.0
Dt      = 5.0
Tunit   = #M#
Itdate  = #1990-08-05#
Tzone   = 0.0
Sub1    = #STC#
Sub2    = #SD#
Roumet  = #C#
Ccofu   = 65.0
Ccofv   = 65.0
Vicouv  = 1.0
Tlfsmo  = 60.0
Filcom  = #YES#
FlNcdf  = #trim trih#
"""

_F34_README: str = """\
DeltaSuite F34 tutorial sample
==============================

This is a *placeholder* model meant for UI walkthroughs. It does NOT
include real inputs (grid, bathymetry, boundaries) and therefore will
not run a simulation by itself.

To run a real F34 case, copy the official example from
``examples/01_standard/f34/`` of your Delft3D source tree on top of
this folder, then press F5 in DeltaSuite.
"""


def _write_sample_files(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    (target / "f34.mdf").write_text(_F34_MDF, encoding="utf-8")
    (target / "README.txt").write_text(_F34_README, encoding="utf-8")


def open_bundled_sample(name: str = "f34") -> Project:
    """Materialise the sample called ``name`` and return its :class:`Project`.

    The sample is written under
    ``$DATA_DIR/samples/<name>`` and only re-extracted when missing.
    """
    if name != "f34":
        raise ValueError(f"Unknown sample: {name!r}")

    base = get_app_paths().data_dir / "samples" / name
    target = base.resolve()
    if not (target / "f34.mdf").exists():
        logger.info("Writing bundled sample to {}", target)
        _write_sample_files(target)

    meta = ProjectMeta(
        name=f"DeltaSuite sample - {name}",
        project_type=ProjectType.DELFT3D4,
        description="Built-in tutorial sample for DeltaSuite.",
        main_input_file="f34.mdf",
    )
    project = Project(root=target, meta=meta)
    project.save()
    return project


__all__ = ("open_bundled_sample",)
