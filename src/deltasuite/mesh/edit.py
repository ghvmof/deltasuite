"""Local mesh editing operations (orthogonalisation, node ops, merging).

These are the operations the interactive mesh editor will eventually
expose as buttons / mouse handlers in the GUI. Keeping them in a
self-contained, headless module means we can unit-test the geometry
transformations without spinning up a Qt event loop.

The conventions follow the rest of the package:

* every function takes a :class:`~deltasuite.core.mesh_adapter.MeshGeometry`
  and returns a :class:`~deltasuite.mesh.generate.MeshOpResult`;
* nothing raises through the API -- failures travel as
  ``result.error``;
* internal numerical work is delegated to ``meshkernel`` so that we
  benefit from its tested orthogonalisation / merging algorithms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from deltasuite.mesh.generate import (
    MeshOpResult,
    _geometry_to_mesh2d,
    _mesh2d_to_geometry,
    _sanitise,
)

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    from deltasuite.core.mesh_adapter import MeshGeometry


# ---------------------------------------------------------------------------
# Orthogonalisation
# ---------------------------------------------------------------------------


def orthogonalize_mesh(
    mesh: MeshGeometry,
    *,
    outer_iterations: int = 2,
    boundary_iterations: int = 25,
    inner_iterations: int = 25,
    orthogonalization_to_smoothing_factor: float = 0.975,
) -> MeshOpResult:
    """Run ``meshkernel``'s orthogonaliser to improve mesh quality.

    The four parameters are passed straight through to
    :class:`meshkernel.OrthogonalizationParameters`. The defaults
    mirror what D-Flow FM uses for moderately structured meshes;
    adjust them only if the mesh is highly skewed.
    """
    if outer_iterations < 1:
        return MeshOpResult(error=f"outer_iterations must be >= 1, got {outer_iterations}")

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        params = mk.OrthogonalizationParameters(
            outer_iterations=int(outer_iterations),
            boundary_iterations=int(boundary_iterations),
            inner_iterations=int(inner_iterations),
            orthogonalization_to_smoothing_factor=float(orthogonalization_to_smoothing_factor),
        )
        empty_polygon = mk.GeometryList()
        empty_lines = mk.GeometryList()
        mk_obj.mesh2d_compute_orthogonalization(
            mk.ProjectToLandBoundaryOption.DO_NOT_PROJECT_TO_LANDBOUNDARY,
            params,
            empty_polygon,
            empty_lines,
        )
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel orthogonalisation failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


# ---------------------------------------------------------------------------
# Node operations
# ---------------------------------------------------------------------------


def delete_node(mesh: MeshGeometry, node_index: int) -> MeshOpResult:
    """Remove a single node and the edges that referenced it."""
    if node_index < 0 or node_index >= mesh.n_nodes:
        return MeshOpResult(error=f"node_index {node_index} out of range [0, {mesh.n_nodes})")

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        mk_obj.mesh2d_delete_node(int(node_index))
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel delete_node failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


def move_node(
    mesh: MeshGeometry,
    node_index: int,
    new_x: float,
    new_y: float,
) -> MeshOpResult:
    """Move ``node_index`` to ``(new_x, new_y)`` and re-derive edges."""
    if node_index < 0 or node_index >= mesh.n_nodes:
        return MeshOpResult(error=f"node_index {node_index} out of range [0, {mesh.n_nodes})")

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        mk_obj.mesh2d_move_node(float(new_x), float(new_y), int(node_index))
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel move_node failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


def merge_nearby_nodes(
    mesh: MeshGeometry,
    *,
    merging_distance: float,
) -> MeshOpResult:
    """Merge any pair of nodes closer than ``merging_distance``."""
    if merging_distance <= 0:
        return MeshOpResult(error=f"merging_distance must be > 0, got {merging_distance}")

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_set(_geometry_to_mesh2d(mesh))
        mk_obj.mesh2d_merge_nodes_with_merging_distance(float(merging_distance))
        out = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel merge failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(out))


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def hanging_edges(mesh: MeshGeometry) -> list[int]:
    """Return the indices of edges with a *dangling* endpoint.

    A dangling node is one that appears in exactly one edge of the mesh
    (i.e. has no other incident edges). The corresponding edge is what
    UGRID / D-Flow FM call a *hanging edge*: removing it cleans up the
    mesh without affecting any face. Sentinel-padded edges (negative
    node indices) are also reported.

    Pure-Python so the function works whether or not ``meshkernel`` is
    installed -- handy for a quick preview / linting pass in the GUI
    before triggering a heavy refinement.
    """
    edges = mesh.edge_nodes
    if edges.size == 0:
        return []

    # First pass: count how many edges each node participates in.
    incidence: dict[int, int] = {}
    for k in range(edges.shape[0]):
        a, b = int(edges[k, 0]), int(edges[k, 1])
        if a >= 0:
            incidence[a] = incidence.get(a, 0) + 1
        if b >= 0:
            incidence[b] = incidence.get(b, 0) + 1

    # Second pass: an edge is hanging if at least one of its endpoints
    # is dangling (incidence == 1) or invalid (negative).
    out: list[int] = []
    for k in range(edges.shape[0]):
        a, b = int(edges[k, 0]), int(edges[k, 1])
        if a < 0 or b < 0 or incidence.get(a, 0) <= 1 or incidence.get(b, 0) <= 1:
            out.append(k)
    return out


__all__ = (
    "delete_node",
    "hanging_edges",
    "merge_nearby_nodes",
    "move_node",
    "orthogonalize_mesh",
)
