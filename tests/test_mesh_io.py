"""Tests for ``deltasuite.mesh.io`` (UGRID NetCDF round-trip)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import (
    UGRID_CONVENTIONS,
    round_trip_mesh,
    save_mesh_to_ugrid_netcdf,
)


def _square_mesh() -> MeshGeometry:
    """Two-triangle square mesh (4 nodes, 5 edges, 2 faces)."""
    return MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.0, 1.0]),
        node_y=np.array([0.0, 0.0, 1.0, 1.0]),
        edge_nodes=np.array(
            [[0, 1], [1, 3], [3, 2], [2, 0], [0, 3]],
            dtype=np.int64,
        ),
        face_nodes=np.array([[0, 1, 3], [0, 3, 2]], dtype=np.int64),
    )


def test_constants_exposed() -> None:
    assert UGRID_CONVENTIONS == "CF-1.8 UGRID-1.0"


def test_save_too_small_mesh_returns_error(tmp_path: Path) -> None:
    tiny = MeshGeometry(
        node_x=np.array([0.0]),
        node_y=np.array([0.0]),
        edge_nodes=np.empty((0, 2), dtype=np.int64),
    )
    res = save_mesh_to_ugrid_netcdf(tiny, tmp_path / "tiny.nc")
    assert not res.ok
    assert "too small" in (res.error or "")


def test_save_writes_netcdf_file(tmp_path: Path) -> None:
    mesh = _square_mesh()
    target = tmp_path / "square.nc"
    res = save_mesh_to_ugrid_netcdf(mesh, target)
    assert res.ok, f"unexpected error: {res.error}"
    assert res.path == target
    assert target.is_file()
    assert target.stat().st_size > 0


def test_save_does_not_overwrite_when_disabled(tmp_path: Path) -> None:
    mesh = _square_mesh()
    target = tmp_path / "square.nc"
    target.write_bytes(b"placeholder")
    res = save_mesh_to_ugrid_netcdf(mesh, target, overwrite=False)
    assert not res.ok
    assert "already exists" in (res.error or "")


def test_round_trip_preserves_node_count(tmp_path: Path) -> None:
    mesh = _square_mesh()
    target = tmp_path / "rt.nc"
    res = round_trip_mesh(mesh, target)
    assert res.ok, f"unexpected error: {res.error}"
    loaded = res.mesh
    assert loaded is not None
    assert loaded.n_nodes == mesh.n_nodes
    assert loaded.n_edges == mesh.n_edges


def test_round_trip_preserves_node_coordinates(tmp_path: Path) -> None:
    mesh = _square_mesh()
    target = tmp_path / "coords.nc"
    res = round_trip_mesh(mesh, target)
    assert res.ok, f"unexpected error: {res.error}"
    loaded = res.mesh
    assert loaded is not None
    np.testing.assert_allclose(np.sort(loaded.node_x), np.sort(mesh.node_x))
    np.testing.assert_allclose(np.sort(loaded.node_y), np.sort(mesh.node_y))
