"""Persistence: read / write a :class:`MeshGeometry` as UGRID NetCDF.

We deliberately keep this module **stand-alone** -- it does not depend
on ``meshkernel``, only on ``xarray`` + ``netCDF4`` (already required
by DeltaSuite). That way users can still save edited meshes when
``meshkernel`` is unavailable (e.g. in a CI smoke-test) and so can our
own test suite.

The output follows UGRID-1.0 with the canonical D-Flow FM names
(``mesh2d``, ``mesh2d_node_x``, ``mesh2d_node_y``,
``mesh2d_edge_nodes``, ``mesh2d_face_nodes``). This is what
``hydrolib-core``, ``dfm-tools`` and ``xugrid`` all expect.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr
from loguru import logger

from deltasuite.core.mesh_adapter import (
    MeshGeometry,
    MeshLoadResult,
    load_mesh_from_path,
)

UGRID_CONVENTIONS = "CF-1.8 UGRID-1.0"


def save_mesh_to_ugrid_netcdf(
    mesh: MeshGeometry,
    path: Path | str,
    *,
    mesh_name: str = "mesh2d",
    overwrite: bool = True,
) -> MeshLoadResult:
    """Serialise ``mesh`` to ``path`` in UGRID-1.0 / D-Flow FM convention.

    Returns a :class:`MeshLoadResult` for symmetry with
    :func:`~deltasuite.core.mesh_adapter.load_mesh_from_path`. The
    result's ``mesh`` field is the same object that was written, so
    callers can chain ``save_mesh_to_ugrid_netcdf(...).ok``.
    """
    target = Path(path).expanduser()
    if target.exists() and not overwrite:
        return MeshLoadResult(path=target, error=f"target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)

    if mesh.n_nodes < 3 or mesh.n_edges < 1:
        return MeshLoadResult(
            path=target,
            error=f"mesh too small to serialise (nodes={mesh.n_nodes}, edges={mesh.n_edges})",
        )

    try:
        ds = _build_ugrid_dataset(mesh, mesh_name=mesh_name)
        ds.to_netcdf(target)
        ds.close()
    except Exception as exc:  # pragma: no cover -- defensive
        logger.warning("UGRID NetCDF write failed: {}", exc)
        return MeshLoadResult(path=target, error=f"{type(exc).__name__}: {exc}")

    return MeshLoadResult(path=target, mesh=mesh)


def round_trip_mesh(mesh: MeshGeometry, path: Path | str) -> MeshLoadResult:
    """Helper: write ``mesh`` to ``path`` and re-read it from disk.

    Useful for tests and for verifying that an in-memory edit can be
    persisted without information loss.
    """
    save_result = save_mesh_to_ugrid_netcdf(mesh, path)
    if not save_result.ok:
        return save_result
    return load_mesh_from_path(Path(path))


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _build_ugrid_dataset(mesh: MeshGeometry, *, mesh_name: str) -> xr.Dataset:
    """Build a UGRID-1.0 :class:`xarray.Dataset` from ``mesh``.

    Centralised so the convention names live in exactly one place.
    """
    node_x_name = f"{mesh_name}_node_x"
    node_y_name = f"{mesh_name}_node_y"
    edge_nodes_name = f"{mesh_name}_edge_nodes"
    face_nodes_name = f"{mesh_name}_face_nodes"

    topology_attrs: dict[str, object] = {
        "cf_role": "mesh_topology",
        "topology_dimension": 2,
        "node_coordinates": f"{node_x_name} {node_y_name}",
        "edge_node_connectivity": edge_nodes_name,
    }
    if mesh.face_nodes is not None and mesh.face_nodes.size > 0:
        topology_attrs["face_node_connectivity"] = face_nodes_name

    data_vars: dict[str, Any] = {
        mesh_name: xr.DataArray(np.int32(0), attrs=topology_attrs),
        edge_nodes_name: (
            ("nEdges", "two"),
            np.asarray(mesh.edge_nodes, dtype=np.int32),
            {"_FillValue": -1, "start_index": 0, "cf_role": "edge_node_connectivity"},
        ),
    }
    if mesh.face_nodes is not None and mesh.face_nodes.size > 0:
        data_vars[face_nodes_name] = (
            ("nFaces", "max_face_nodes"),
            np.asarray(mesh.face_nodes, dtype=np.int32),
            {"_FillValue": -1, "start_index": 0, "cf_role": "face_node_connectivity"},
        )

    coords = {
        node_x_name: (
            "nNodes",
            np.asarray(mesh.node_x, dtype=float),
            {"standard_name": "projection_x_coordinate", "units": "m"},
        ),
        node_y_name: (
            "nNodes",
            np.asarray(mesh.node_y, dtype=float),
            {"standard_name": "projection_y_coordinate", "units": "m"},
        ),
    }

    return xr.Dataset(
        data_vars=data_vars,
        coords=coords,
        attrs={
            "Conventions": UGRID_CONVENTIONS,
            "title": f"{mesh_name} -- DeltaSuite generated mesh",
        },
    )


__all__ = (
    "UGRID_CONVENTIONS",
    "round_trip_mesh",
    "save_mesh_to_ugrid_netcdf",
)
