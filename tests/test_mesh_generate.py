"""Tests for ``deltasuite.mesh.generate``."""

from __future__ import annotations

import numpy as np
import pytest

from deltasuite.mesh import (
    MeshOpResult,
    make_rectangular_mesh,
    make_triangular_mesh_from_polygon,
)

# ---------------------------------------------------------------------------
# Always-on tests (validate input handling without meshkernel)
# ---------------------------------------------------------------------------


def test_triangular_polygon_too_small_returns_error() -> None:
    res = make_triangular_mesh_from_polygon([0.0, 1.0], [0.0, 1.0])
    assert isinstance(res, MeshOpResult)
    assert not res.ok
    assert res.error is not None
    assert "at least 3" in res.error


def test_triangular_polygon_size_mismatch_returns_error() -> None:
    res = make_triangular_mesh_from_polygon([0.0, 1.0, 0.5], [0.0, 1.0])
    assert not res.ok
    assert res.error is not None
    assert "differ in size" in res.error


def test_rectangular_invalid_dimensions_returns_error() -> None:
    res = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=0,
        n_rows=5,
        cell_size=1.0,
    )
    assert not res.ok
    assert res.error is not None


def test_rectangular_invalid_cell_size_returns_error() -> None:
    res = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=5,
        n_rows=5,
        cell_size=0.0,
    )
    assert not res.ok
    assert res.error is not None


# ---------------------------------------------------------------------------
# Tests that require meshkernel
# ---------------------------------------------------------------------------


def test_triangular_mesh_from_polygon_returns_geometry() -> None:
    pytest.importorskip("meshkernel")
    px = np.array([0.0, 10.0, 10.0, 0.0])
    py = np.array([0.0, 0.0, 10.0, 10.0])
    res = make_triangular_mesh_from_polygon(px, py)
    assert res.ok, f"unexpected error: {res.error}"
    mesh = res.mesh
    assert mesh is not None
    assert mesh.n_nodes >= 4
    assert mesh.n_edges >= 4


def test_rectangular_mesh_returns_expected_node_count() -> None:
    pytest.importorskip("meshkernel")
    res = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=4,
        n_rows=3,
        cell_size=2.0,
    )
    assert res.ok, f"unexpected error: {res.error}"
    mesh = res.mesh
    assert mesh is not None
    assert mesh.n_nodes == (4 + 1) * (3 + 1)


def test_rectangular_mesh_with_rotation_runs() -> None:
    pytest.importorskip("meshkernel")
    res = make_rectangular_mesh(
        origin_x=100.0,
        origin_y=200.0,
        n_columns=3,
        n_rows=2,
        cell_size=5.0,
        angle_deg=30.0,
    )
    assert res.ok, f"unexpected error: {res.error}"
    mesh = res.mesh
    assert mesh is not None
    assert mesh.n_nodes == (3 + 1) * (2 + 1)
    # Origin of the rotation is the (100, 200) corner: at least one node
    # must coincide with it (the (0, 0) cell of the unrotated grid).
    distances = np.hypot(mesh.node_x - 100.0, mesh.node_y - 200.0)
    assert distances.min() < 1e-6
