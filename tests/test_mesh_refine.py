"""Tests for ``deltasuite.mesh.refine``."""

from __future__ import annotations

import numpy as np
import pytest

from deltasuite.mesh import (
    make_rectangular_mesh,
    refine_mesh_based_on_samples,
    refine_mesh_inside_polygon,
)

# ---------------------------------------------------------------------------
# Input validation (no meshkernel needed)
# ---------------------------------------------------------------------------


def test_refine_inside_polygon_invalid_iterations() -> None:
    from deltasuite.core.mesh_adapter import MeshGeometry

    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
    )
    res = refine_mesh_inside_polygon(
        mesh,
        polygon_x=[0.0, 1.0, 0.5],
        polygon_y=[0.0, 0.0, 1.0],
        n_iterations=0,
    )
    assert not res.ok


def test_refine_based_on_samples_empty_returns_error() -> None:
    from deltasuite.core.mesh_adapter import MeshGeometry

    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
    )
    res = refine_mesh_based_on_samples(mesh, [], [], [])
    assert not res.ok
    assert res.error is not None


def test_refine_based_on_samples_size_mismatch_returns_error() -> None:
    from deltasuite.core.mesh_adapter import MeshGeometry

    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
    )
    res = refine_mesh_based_on_samples(mesh, [0.0, 1.0], [0.0], [1.0])
    assert not res.ok


# ---------------------------------------------------------------------------
# Integration tests with meshkernel
# ---------------------------------------------------------------------------


def test_refine_inside_polygon_increases_node_count() -> None:
    pytest.importorskip("meshkernel")
    base = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=4,
        n_rows=4,
        cell_size=2.0,
    )
    assert base.ok
    base_mesh = base.mesh
    assert base_mesh is not None
    base_nodes = base_mesh.n_nodes

    refined = refine_mesh_inside_polygon(
        base_mesh,
        polygon_x=[1.0, 7.0, 7.0, 1.0],
        polygon_y=[1.0, 1.0, 7.0, 7.0],
        n_iterations=1,
    )
    assert refined.ok, f"unexpected error: {refined.error}"
    refined_mesh = refined.mesh
    assert refined_mesh is not None
    assert refined_mesh.n_nodes > base_nodes


def test_refine_inside_polygon_full_extent_regression() -> None:
    """Regression test for the GUI ``Refine`` button.

    Calling ``refine_mesh_inside_polygon`` with a polygon equal to the
    mesh bounding box (which is what ``MeshPanel`` does) used to raise
    ``ConstraintError: Mesh::FindEdge: Invalid node index`` because
    we were passing our padded ``face_nodes`` matrix straight into
    ``meshkernel.Mesh2d``. The fix is to let MeshKernel rebuild the
    face topology from ``edge_nodes``; this test guards against any
    future regression.
    """
    pytest.importorskip("meshkernel")
    base = make_rectangular_mesh(
        origin_x=0.0,
        origin_y=0.0,
        n_columns=4,
        n_rows=4,
        cell_size=1.0,
    )
    assert base.ok
    base_mesh = base.mesh
    assert base_mesh is not None
    bbox_x = [0.0, 4.0, 4.0, 0.0, 0.0]
    bbox_y = [0.0, 0.0, 4.0, 4.0, 0.0]
    refined = refine_mesh_inside_polygon(
        base_mesh,
        polygon_x=bbox_x,
        polygon_y=bbox_y,
        n_iterations=1,
    )
    assert refined.ok, f"unexpected error: {refined.error}"
    refined_mesh = refined.mesh
    assert refined_mesh is not None
    assert refined_mesh.n_nodes > base_mesh.n_nodes
