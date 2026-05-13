"""High-level wrappers around ``meshkernel`` for 2-D mesh **generation**.

The functions in this module accept and return library-agnostic
:class:`~deltasuite.core.mesh_adapter.MeshGeometry` objects so the rest
of the application never sees a ``meshkernel`` symbol directly. This
keeps the GUI testable without the C++ extension installed and lets us
swap the back end later (e.g. to a pure Python triangulator) without
touching the views.

Two generators are exposed for now:

* :func:`make_triangular_mesh_from_polygon` -- Delaunay triangulation
  inside an arbitrary 2-D polygon. The polygon vertices double as the
  initial set of mesh nodes; ``meshkernel`` then refines the interior.
* :func:`make_rectangular_mesh` -- regular rectangular mesh with a
  configurable cell size, optional rotation and origin. Convenient for
  quick "blank canvas" scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
from loguru import logger

from deltasuite.core.mesh_adapter import MeshGeometry

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    from numpy.typing import ArrayLike


# ---------------------------------------------------------------------------
# Result wrapper
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeshOpResult:
    """Return type for every public mesh operation in this package.

    Carries either a successful :class:`MeshGeometry` or a structured
    error string. Mirrors ``MeshLoadResult`` so the GUI can use a single
    handler shape for *load*, *generate*, *refine* and *edit* outcomes.
    """

    mesh: MeshGeometry | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.mesh is not None


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------


def make_triangular_mesh_from_polygon(
    polygon_x: ArrayLike,
    polygon_y: ArrayLike,
) -> MeshOpResult:
    """Generate a Delaunay triangular mesh inside ``polygon_x/polygon_y``.

    The polygon is treated as a single closed ring; ``meshkernel`` is
    responsible for the triangulation. The first and last vertex do
    *not* need to coincide -- we always close the polygon for the user.
    """
    px = np.asarray(polygon_x, dtype=float).ravel()
    py = np.asarray(polygon_y, dtype=float).ravel()
    if px.size != py.size:
        return MeshOpResult(
            error=f"polygon_x and polygon_y differ in size ({px.size} vs {py.size})"
        )
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
        polygon = mk.GeometryList(x_coordinates=px, y_coordinates=py)
        mk_obj.mesh2d_make_triangular_mesh_from_polygon(polygon)
        mesh2d = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel triangular generation failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(mesh2d))


def make_rectangular_mesh(
    *,
    origin_x: float,
    origin_y: float,
    n_columns: int,
    n_rows: int,
    cell_size: float,
    angle_deg: float = 0.0,
) -> MeshOpResult:
    """Generate a uniform rectangular mesh of ``n_rows`` by ``n_columns`` cells.

    ``angle_deg`` rotates the whole grid counter-clockwise about the
    origin. ``cell_size`` is in the same units as ``origin_x/origin_y``
    (typically metres for a projected CRS).
    """
    if n_columns < 1 or n_rows < 1:
        return MeshOpResult(error=f"need n_rows>=1 and n_columns>=1, got {n_rows}x{n_columns}")
    if cell_size <= 0:
        return MeshOpResult(error=f"cell_size must be > 0, got {cell_size}")

    try:
        import meshkernel as mk
    except ImportError:
        return MeshOpResult(error="meshkernel is not installed")

    try:
        params = mk.MakeGridParameters(
            num_columns=int(n_columns),
            num_rows=int(n_rows),
            angle=float(angle_deg),
            origin_x=float(origin_x),
            origin_y=float(origin_y),
            block_size_x=float(cell_size),
            block_size_y=float(cell_size),
        )
        mk_obj = mk.MeshKernel()
        mk_obj.mesh2d_make_rectangular_mesh(params)
        mesh2d = mk_obj.mesh2d_get()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("meshkernel rectangular generation failed: {}", exc)
        return MeshOpResult(error=_sanitise(exc))

    return MeshOpResult(mesh=_mesh2d_to_geometry(mesh2d))


# ---------------------------------------------------------------------------
# Internal helpers (also reused by ``refine`` and ``edit``)
# ---------------------------------------------------------------------------


def _mesh2d_to_geometry(mesh2d: Any) -> MeshGeometry:
    """Convert a ``meshkernel.Mesh2d`` into our :class:`MeshGeometry`.

    Defined here (rather than as a ``MeshGeometry`` constructor) so that
    ``MeshGeometry`` itself stays dependency-free and importable when
    meshkernel is not installed.
    """
    node_x = np.asarray(mesh2d.node_x, dtype=np.float64)
    node_y = np.asarray(mesh2d.node_y, dtype=np.float64)
    edge_nodes_flat = np.asarray(mesh2d.edge_nodes, dtype=np.int64)
    edge_nodes = edge_nodes_flat.reshape(-1, 2)

    face_nodes: np.ndarray | None
    if hasattr(mesh2d, "face_nodes") and mesh2d.face_nodes is not None:
        face_nodes_flat = np.asarray(mesh2d.face_nodes, dtype=np.int64)
        nodes_per_face = getattr(mesh2d, "nodes_per_face", None)
        if nodes_per_face is not None and len(face_nodes_flat) > 0:
            nodes_per_face_arr = np.asarray(nodes_per_face, dtype=np.int64)
            max_n = int(nodes_per_face_arr.max())
            n_faces = nodes_per_face_arr.size
            face_nodes = np.full((n_faces, max_n), -1, dtype=np.int64)
            offset = 0
            for i, n in enumerate(nodes_per_face_arr):
                n_int = int(n)
                face_nodes[i, :n_int] = face_nodes_flat[offset : offset + n_int]
                offset += n_int
        else:
            face_nodes = None
    else:
        face_nodes = None

    return MeshGeometry(
        node_x=node_x,
        node_y=node_y,
        edge_nodes=edge_nodes,
        face_nodes=face_nodes,
    )


def _geometry_to_mesh2d(geom: MeshGeometry) -> Any:
    """Convert a :class:`MeshGeometry` back into a ``meshkernel.Mesh2d``.

    Imported locally so the function is a no-op cost when meshkernel is
    not installed (it will raise the ``ImportError`` only if called).
    """
    import meshkernel as mk

    edge_nodes_flat = np.asarray(geom.edge_nodes, dtype=np.int32).ravel()

    if geom.face_nodes is not None:
        rows = geom.face_nodes
        valid = rows != -1
        nodes_per_face = valid.sum(axis=1).astype(np.int32)
        face_nodes_flat = rows[valid].astype(np.int32)
    else:
        nodes_per_face = np.empty(0, dtype=np.int32)
        face_nodes_flat = np.empty(0, dtype=np.int32)

    return mk.Mesh2d(
        node_x=np.asarray(geom.node_x, dtype=np.float64),
        node_y=np.asarray(geom.node_y, dtype=np.float64),
        edge_nodes=edge_nodes_flat,
        face_nodes=face_nodes_flat,
        nodes_per_face=nodes_per_face,
    )


def _sanitise(exc: BaseException) -> str:
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    if len(msg) > 240:
        msg = msg[:237] + "…"
    return f"{type(exc).__name__}: {msg}"


__all__ = (
    "MeshOpResult",
    "make_rectangular_mesh",
    "make_triangular_mesh_from_polygon",
)
