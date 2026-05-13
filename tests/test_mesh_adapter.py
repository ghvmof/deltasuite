"""Tests for the optional ``xugrid`` / ``meshkernel`` integration."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from deltasuite.core import (
    MeshGeometry,
    MeshLoadResult,
    is_meshkernel_available,
    is_xugrid_available,
    load_mesh_from_dataset,
    load_mesh_from_path,
    meshkernel_version,
    xugrid_version,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ugrid_dataset() -> xr.Dataset:
    """Two-triangle UGRID dataset:

    Nodes:           Edges:
        2 ---- 3        2-3
        | \\    |        2-0  3-1  0-1
        |  \\   |        0-3
        0 ---- 1
    """
    node_x = np.array([0.0, 1.0, 0.0, 1.0])
    node_y = np.array([0.0, 0.0, 1.0, 1.0])
    edge_nodes = np.array(
        [[0, 1], [1, 3], [3, 2], [2, 0], [0, 3]],
        dtype=np.int64,
    )
    face_nodes = np.array(
        [[0, 1, 3], [0, 3, 2]],
        dtype=np.int64,
    )
    # The "mesh2d" dummy variable is the canonical UGRID-1.0 mesh topology
    # marker; xugrid uses its attributes to discover the rest.
    mesh_topology = xr.DataArray(
        np.int32(0),
        attrs={
            "cf_role": "mesh_topology",
            "topology_dimension": 2,
            "node_coordinates": "mesh2d_node_x mesh2d_node_y",
            "edge_node_connectivity": "mesh2d_edge_nodes",
            "face_node_connectivity": "mesh2d_face_nodes",
        },
    )
    ds = xr.Dataset(
        data_vars={
            "mesh2d": mesh_topology,
            "mesh2d_edge_nodes": (("nEdges", "two"), edge_nodes),
            "mesh2d_face_nodes": (
                ("nFaces", "max_nodes"),
                face_nodes,
                {"_FillValue": -1, "start_index": 0},
            ),
        },
        coords={
            "mesh2d_node_x": (
                "nNodes",
                node_x,
                {"standard_name": "projection_x_coordinate"},
            ),
            "mesh2d_node_y": (
                "nNodes",
                node_y,
                {"standard_name": "projection_y_coordinate"},
            ),
        },
        attrs={"Conventions": "CF-1.8 UGRID-1.0"},
    )
    # xugrid wants the mesh topology variable to have start_index=0 for
    # 0-based connectivity and a _FillValue.
    ds["mesh2d_edge_nodes"].attrs["start_index"] = 0
    return ds


# ---------------------------------------------------------------------------
# Always-on tests
# ---------------------------------------------------------------------------


def test_xugrid_availability_returns_bool() -> None:
    assert isinstance(is_xugrid_available(), bool)


def test_meshkernel_availability_returns_bool() -> None:
    assert isinstance(is_meshkernel_available(), bool)


def test_xugrid_version_matches_availability() -> None:
    if is_xugrid_available():
        v = xugrid_version()
        assert isinstance(v, str)
        assert v
    else:
        assert xugrid_version() is None


def test_meshkernel_version_matches_availability() -> None:
    if is_meshkernel_available():
        v = meshkernel_version()
        assert isinstance(v, str)
        assert v
    else:
        assert meshkernel_version() is None


def test_load_mesh_from_path_missing_file(tmp_path: Path) -> None:
    res = load_mesh_from_path(tmp_path / "no_such.nc")
    assert isinstance(res, MeshLoadResult)
    assert not res.ok
    assert res.error is not None


def test_load_mesh_from_dataset_returns_geometry() -> None:
    ds = _ugrid_dataset()
    res = load_mesh_from_dataset(ds)
    assert res.ok
    mesh = res.mesh
    assert isinstance(mesh, MeshGeometry)
    assert mesh.n_nodes == 4
    assert mesh.n_edges >= 4
    assert mesh.n_faces == 2


def test_load_mesh_from_dataset_no_ugrid_returns_error() -> None:
    ds = xr.Dataset({"foo": (("x",), np.zeros(3))})
    res = load_mesh_from_dataset(ds)
    assert not res.ok
    assert res.error is not None


def test_meshgeometry_count_properties() -> None:
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0]),
        node_y=np.array([0.0, 1.0]),
        edge_nodes=np.array([[0, 1]], dtype=np.int64),
        face_nodes=None,
    )
    assert mesh.n_nodes == 2
    assert mesh.n_edges == 1
    assert mesh.n_faces == 0


def test_load_mesh_from_path_with_real_file(tmp_path: Path) -> None:
    """Round-trip via NetCDF on disk."""
    ds = _ugrid_dataset()
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)
    ds.close()
    res = load_mesh_from_path(p)
    assert res.ok
    assert res.path == p
    mesh = res.mesh
    assert mesh is not None
    assert mesh.n_nodes == 4
