"""Refinement operations for 2-D meshes (wrappers around ``meshkernel``).

Two strategies are exposed:

* :func:`refine_mesh_inside_polygon` -- uniform refinement of every
  face whose centroid falls inside a user-supplied polygon. Useful for
  quickly thickening the mesh in a region of interest (port, estuary,
  shoreline) without sample data.
* :func:`refine_mesh_based_on_samples` -- adaptive refinement driven
  by scattered ``(x, y, value)`` samples: cells with a higher local
  sample density (or magnitude, depending on ``refinement_type``) are
  refined more aggressively. This is what one normally uses to drive
  bathymetry-aware refinement.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

from deltasuite.mesh.generate import (
    MeshOpResult,
    _geometry_to_mesh2d,
    _mesh2d_to_geometry,
    _sanitise,
)

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    from numpy.typing import ArrayLike

    from deltasuite.core.mesh_adapter import MeshGeometry


# ---------------------------------------------------------------------------
# Public refinement operations
# ---------------------------------------------------------------------------


def refine_mesh_inside_polygon(
    mesh: MeshGeometry,
    polygon_x: ArrayLike,
    polygon_y: ArrayLike,
    *,
    n_iterations: int = 1,
) -> MeshOpResult:
    """Refine every face inside ``polygon_x/polygon_y`` ``n_iterations`` times.

    Each iteration roughly halves the cell size inside the polygon
    (Casulli refinement), so 2 iterations ≈ ¼ original cell area.
    """
    if n_iterations < 1:
        return MeshOpResult(error=f"n_iterations must be >= 1, got {n_iterations}")
    px = np.asarray(polygon_x, dtype=float).ravel()
    py = np.asarray(polygon_y, dtype=float).ravel()
    if px.size != py.size:
        return MeshOpResult(error="polygon_x and polygon_y differ in size")
    if px.size < 3:
        return MeshOpResult(error=f"polygon must have at least 3 vertices (got {px.size})")
    if px[0] != px[-1] or py[0] != py[-1]:
        px = np.append(px, px[0])
        py = np.append(py, py[0])

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        polygon = mk.GeometryList(x_coordinates=px, y_coordinates=py)
        for _ in range(int(n_iterations)):
            mk_obj.mesh2d_casulli_refinement_on_polygon(polygon)
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel polygon refinement failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


def refine_mesh_based_on_samples(
    mesh: MeshGeometry,
    sample_x: ArrayLike,
    sample_y: ArrayLike,
    sample_values: ArrayLike,
    *,
    min_edge_size: float = 0.0,
    max_refinement_iterations: int = 5,
) -> MeshOpResult:
    """Adaptive refinement driven by a point cloud of ``(x, y, value)`` samples.

    The values are interpreted by ``meshkernel``'s default refinement
    type (wave-courant): bigger absolute values yield smaller cells,
    bounded below by ``min_edge_size``.
    """
    sx = np.asarray(sample_x, dtype=float).ravel()
    sy = np.asarray(sample_y, dtype=float).ravel()
    sv = np.asarray(sample_values, dtype=float).ravel()
    if not (sx.size == sy.size == sv.size):
        return MeshOpResult(error=f"sample arrays differ in size ({sx.size}, {sy.size}, {sv.size})")
    if sx.size == 0:
        return MeshOpResult(error="no samples provided")
    if max_refinement_iterations < 1:
        return MeshOpResult(
            error=f"max_refinement_iterations must be >= 1, got {max_refinement_iterations}"
        )

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        samples = mk.GeometryList(x_coordinates=sx, y_coordinates=sy, values=sv)
        params = mk.MeshRefinementParameters(
            min_edge_size=float(min_edge_size),
            max_refinement_iterations=int(max_refinement_iterations),
        )
        mk_obj.mesh2d_refine_based_on_samples(samples, 1.0, 1, params)
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel sample-based refinement failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


__all__ = (
    "refine_mesh_based_on_samples",
    "refine_mesh_inside_polygon",
)
