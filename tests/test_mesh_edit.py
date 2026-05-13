"""Tests for ``deltasuite.mesh.edit``."""

from __future__ import annotations

import numpy as np
import pytest

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import (
    delete_node,
    hanging_edges,
    make_rectangular_mesh,
    merge_nearby_nodes,
    move_node,
    orthogonalize_mesh,
)

# ---------------------------------------------------------------------------
# Input validation (no meshkernel needed)
# ---------------------------------------------------------------------------


def _trivial_mesh() -> MeshGeometry:
    return MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
        face_nodes=np.array([[0, 1, 2]], dtype=np.int64),
    )


def test_delete_node_index_out_of_range_returns_error() -> None:
    res = delete_node(_trivial_mesh(), 99)
    assert not res.ok
    assert "out of range" in (res.error or "")


def test_move_node_index_out_of_range_returns_error() -> None:
    res = move_node(_trivial_mesh(), -1, 0.0, 0.0)
    assert not res.ok


def test_merge_nearby_nodes_invalid_distance_returns_error() -> None:
    res = merge_nearby_nodes(_trivial_mesh(), merging_distance=0.0)
    assert not res.ok


def test_orthogonalize_mesh_invalid_outer_returns_error() -> None:
    res = orthogonalize_mesh(_trivial_mesh(), outer_iterations=0)
    assert not res.ok


def test_hanging_edges_on_closed_triangle_returns_empty_list() -> None:
    edges = hanging_edges(_trivial_mesh())
    assert edges == []


def test_hanging_edges_on_dangling_edge_detects_it() -> None:
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5, 2.0]),
        node_y=np.array([0.0, 0.0, 1.0, 0.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0], [1, 3]], dtype=np.int64),
        face_nodes=np.array([[0, 1, 2]], dtype=np.int64),
    )
    edges = hanging_edges(mesh)
    assert 3 in edges


# ---------------------------------------------------------------------------
# Integration tests with meshkernel
# ---------------------------------------------------------------------------


def test_orthogonalize_returns_mesh_of_same_size() -> None:
    pytest.importorskip("meshkernel")
    base = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=3,
        n_rows=3,
        cell_size=1.0,
    )
    assert base.ok
    base_mesh = base.mesh
    assert base_mesh is not None

    res = orthogonalize_mesh(base_mesh, outer_iterations=1)
    assert res.ok, f"unexpected error: {res.error}"
    out_mesh = res.mesh
    assert out_mesh is not None
    assert out_mesh.n_nodes == base_mesh.n_nodes


def test_move_node_changes_coordinate() -> None:
    pytest.importorskip("meshkernel")
    base = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=2,
        n_rows=2,
        cell_size=1.0,
    )
    assert base.ok
    base_mesh = base.mesh
    assert base_mesh is not None

    res = move_node(base_mesh, 0, -10.0, -10.0)
    assert res.ok, f"unexpected error: {res.error}"
    moved = res.mesh
    assert moved is not None
    assert moved.node_x.min() <= -10.0 + 1e-6
