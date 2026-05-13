"""Optional integration with ``xugrid`` / ``meshkernel`` for mesh handling.

This is the third (and last for now) Deltares-stack adapter. It exposes
just enough functionality to render a UGRID 2-D mesh as a wireframe over
the existing map view; finer-grained editing (mesh refinement, snapping,
boundary conditions) lives in future PRs.

Why both ``xugrid`` and ``meshkernel``?

* ``xugrid`` (https://github.com/Deltares/xugrid) is the high-level
  xarray extension for UGRID files. It gives us a typed ``Ugrid2d``
  object with face-node connectivity, edge tables and node coordinates.
* ``meshkernel`` (https://github.com/Deltares/MeshKernelPy) is the
  lower-level C++ engine that we'll need later for mesh generation /
  editing. We import it lazily here so we get the cheap availability
  signal without paying the binary load cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:  # pragma: no cover -- import only for type checking
    import numpy as np
    import xarray as xr
    from numpy.typing import NDArray


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def is_xugrid_available() -> bool:
    try:
        import xugrid  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def xugrid_version() -> str | None:
    if not is_xugrid_available():
        return None
    try:
        import xugrid as xu

        return str(getattr(xu, "__version__", "unknown"))
    except Exception:  # pragma: no cover
        return None


@lru_cache(maxsize=1)
def is_meshkernel_available() -> bool:
    try:
        import meshkernel  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def meshkernel_version() -> str | None:
    if not is_meshkernel_available():
        return None
    try:
        import meshkernel as mk

        return str(getattr(mk, "__version__", "unknown"))
    except Exception:  # pragma: no cover
        return None


# ---------------------------------------------------------------------------
# Mesh data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MeshGeometry:
    """Light-weight, library-agnostic representation of a 2-D UGRID mesh.

    * ``node_x`` / ``node_y`` -- 1-D arrays, one entry per mesh node.
    * ``edge_nodes`` -- 2-D ``(n_edges, 2)`` array of node-index pairs;
      this is what we draw with ``LineCollection``.
    * ``face_nodes`` -- ``(n_faces, max_vertices_per_face)`` array padded
      with ``-1`` (UGRID convention). Optional; ``None`` if the source
      did not expose face connectivity.
    """

    node_x: NDArray[np.floating]
    node_y: NDArray[np.floating]
    edge_nodes: NDArray[np.integer]
    face_nodes: NDArray[np.integer] | None = None

    @property
    def n_nodes(self) -> int:
        return int(self.node_x.size)

    @property
    def n_edges(self) -> int:
        return int(self.edge_nodes.shape[0])

    @property
    def n_faces(self) -> int:
        return 0 if self.face_nodes is None else int(self.face_nodes.shape[0])


@dataclass(frozen=True, slots=True)
class MeshLoadResult:
    """Outcome of an attempt to load a mesh from a NetCDF / xarray source."""

    path: Path | None
    mesh: MeshGeometry | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.mesh is not None


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_mesh_from_dataset(dataset: xr.Dataset) -> MeshLoadResult:
    """Build a :class:`MeshGeometry` from a UGRID-tagged xarray Dataset.

    Uses ``xugrid`` when installed (it knows the official UGRID conventions
    and handles the connectivity arrays robustly). Falls back to a
    bare-numpy heuristic that looks for the canonical ``mesh2d_*`` names
    when xugrid is missing.
    """
    if is_xugrid_available():
        return _load_with_xugrid(dataset)
    return _load_with_heuristic(dataset)


def load_mesh_from_path(path: Path) -> MeshLoadResult:
    """Open ``path`` (a NetCDF mesh file) and extract its mesh geometry."""
    path = Path(path).expanduser()
    if not path.is_file():
        return MeshLoadResult(path=path, error=f"file not found: {path}")
    try:
        import xarray as xr

        ds = xr.open_dataset(path)
    except Exception as exc:
        return MeshLoadResult(path=path, error=_sanitise_error(exc))
    try:
        result = load_mesh_from_dataset(ds)
    finally:
        ds.close()
    # Re-attach the source path to the result.
    return MeshLoadResult(path=path, mesh=result.mesh, error=result.error)


# ---------------------------------------------------------------------------
# Internal loaders
# ---------------------------------------------------------------------------


def _load_with_xugrid(dataset: xr.Dataset) -> MeshLoadResult:
    """Use xugrid's Ugrid2d to build the mesh geometry."""
    import numpy as np

    try:
        import xugrid as xu

        uds = xu.UgridDataset(dataset)
    except Exception as exc:
        logger.debug("xugrid could not interpret dataset: {}", exc)
        return MeshLoadResult(path=None, error=_sanitise_error(exc))

    grids = list(uds.grids)
    if not grids:
        return MeshLoadResult(path=None, error="no UGRID 2-D grids found")
    grid = grids[0]
    if not hasattr(grid, "node_x"):
        return MeshLoadResult(path=None, error=f"unsupported grid kind: {type(grid).__name__}")

    node_x = np.asarray(grid.node_x, dtype=float)
    node_y = np.asarray(grid.node_y, dtype=float)
    edge_nodes = np.asarray(grid.edge_node_connectivity, dtype=np.int64)
    face_nodes = (
        np.asarray(grid.face_node_connectivity, dtype=np.int64)
        if hasattr(grid, "face_node_connectivity")
        else None
    )
    return MeshLoadResult(
        path=None,
        mesh=MeshGeometry(
            node_x=node_x,
            node_y=node_y,
            edge_nodes=edge_nodes,
            face_nodes=face_nodes,
        ),
    )


def _load_with_heuristic(dataset: xr.Dataset) -> MeshLoadResult:
    """Best-effort heuristic for when xugrid is not installed."""
    import numpy as np

    # Canonical D-Flow FM UGRID variable names.
    nx_name = next(
        (n for n in ("mesh2d_node_x", "node_x", "x") if n in dataset.variables),
        None,
    )
    ny_name = next(
        (n for n in ("mesh2d_node_y", "node_y", "y") if n in dataset.variables),
        None,
    )
    en_name = next(
        (n for n in ("mesh2d_edge_nodes", "edge_node_connectivity") if n in dataset.variables),
        None,
    )
    if nx_name is None or ny_name is None or en_name is None:
        return MeshLoadResult(
            path=None,
            error="dataset does not expose UGRID node/edge variables (install xugrid for richer parsing)",
        )

    node_x = np.asarray(dataset[nx_name].values, dtype=float)
    node_y = np.asarray(dataset[ny_name].values, dtype=float)
    edge_nodes = np.asarray(dataset[en_name].values, dtype=np.int64)
    # UGRID is normally 1-based; some files are 0-based. Normalise to 0-based.
    if edge_nodes.min() >= 1 and edge_nodes.max() <= node_x.size:
        edge_nodes = edge_nodes - 1
    fn_name = next(
        (n for n in ("mesh2d_face_nodes", "face_node_connectivity") if n in dataset.variables),
        None,
    )
    face_nodes = np.asarray(dataset[fn_name].values, dtype=np.int64) if fn_name else None
    if face_nodes is not None and face_nodes.min() >= 1:
        # Same 1-based -> 0-based normalisation, but preserve the -1 sentinel
        # for ragged faces.
        mask = face_nodes >= 1
        face_nodes = np.where(mask, face_nodes - 1, -1)

    return MeshLoadResult(
        path=None,
        mesh=MeshGeometry(
            node_x=node_x,
            node_y=node_y,
            edge_nodes=edge_nodes,
            face_nodes=face_nodes,
        ),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _sanitise_error(exc: BaseException) -> str:
    msg = str(exc).strip().splitlines()[0]
    if len(msg) > 240:
        msg = msg[:237] + "…"
    return f"{type(exc).__name__}: {msg}"


__all__ = (
    "MeshGeometry",
    "MeshLoadResult",
    "is_meshkernel_available",
    "is_xugrid_available",
    "load_mesh_from_dataset",
    "load_mesh_from_path",
    "meshkernel_version",
    "xugrid_version",
)
