"""Tests for ``deltasuite.mesh.io_grd``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import (
    load_grd_mesh,
    make_rectangular_mesh,
    save_grd_mesh,
)


def _tiny_grd_text() -> str:
    """A 3x2 mesh in canonical RGFGRID style."""
    return (
        "*\n"
        "* tiny test mesh\n"
        "*\n"
        "Coordinate System = Cartesian\n"
        "       3       2\n"
        " 0 0 0\n"
        " ETA=    1   0.000000000000000E+00   1.000000000000000E+00   2.000000000000000E+00\n"
        " ETA=    2   0.000000000000000E+00   1.000000000000000E+00   2.000000000000000E+00\n"
        " ETA=    1   0.000000000000000E+00   0.000000000000000E+00   0.000000000000000E+00\n"
        " ETA=    2   1.000000000000000E+00   1.000000000000000E+00   1.000000000000000E+00\n"
    )


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def test_load_grd_missing_file_returns_error(tmp_path: Path) -> None:
    res = load_grd_mesh(tmp_path / "does_not_exist.grd")
    assert not res.ok
    assert res.error is not None
    assert "not found" in res.error


def test_load_grd_tiny_inline_text(tmp_path: Path) -> None:
    grd = tmp_path / "tiny.grd"
    grd.write_text(_tiny_grd_text(), encoding="utf-8")
    res = load_grd_mesh(grd)
    assert res.ok, res.error
    mesh = res.mesh
    assert mesh is not None
    assert mesh.structured_shape == (2, 3)  # (n_rows, n_cols)
    assert mesh.n_nodes == 6
    assert mesh.n_edges == (3 - 1) * 2 + 3 * (2 - 1)  # 4 horiz + 3 vert = 7
    assert mesh.n_faces == (3 - 1) * (2 - 1)  # 2 quads
    np.testing.assert_allclose(np.sort(mesh.node_x), [0, 0, 1, 1, 2, 2])
    np.testing.assert_allclose(np.sort(mesh.node_y), [0, 0, 0, 1, 1, 1])


def test_load_grd_handles_trailing_blank_and_comments(tmp_path: Path) -> None:
    grd = tmp_path / "tiny.grd"
    grd.write_text(_tiny_grd_text() + "\n\n\n", encoding="utf-8")
    res = load_grd_mesh(grd)
    assert res.ok, res.error


def test_load_grd_supports_missing_value(tmp_path: Path) -> None:
    text = (
        "Coordinate System = Cartesian\n"
        "Missing Value = -9.99000000000000E+02\n"
        "       3       2\n"
        " 0 0 0\n"
        " ETA=    1   0.000000000000000E+00   1.000000000000000E+00  -9.990000000000000E+02\n"
        " ETA=    2   0.000000000000000E+00   1.000000000000000E+00   2.000000000000000E+00\n"
        " ETA=    1   0.000000000000000E+00   0.000000000000000E+00  -9.990000000000000E+02\n"
        " ETA=    2   1.000000000000000E+00   1.000000000000000E+00   1.000000000000000E+00\n"
    )
    grd = tmp_path / "miss.grd"
    grd.write_text(text, encoding="utf-8")
    res = load_grd_mesh(grd)
    assert res.ok, res.error
    mesh = res.mesh
    assert mesh is not None
    # The (3, 1) node is masked, so the face that uses it must be dropped.
    assert mesh.n_faces == 1


def _find_sample(rel_path: str) -> Path | None:
    """Locate a Delft3D example file in any of the common workspace roots."""
    candidates = [
        Path.home() / "Downloads" / "Delft3D-main" / "Delft3D-main" / rel_path,
        Path.home() / "Downloads" / "Delft3D-main" / rel_path,
        Path.cwd().parent / "Delft3D-main" / rel_path,
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def test_load_real_examples_no_crash() -> None:
    """Smoke-load every .grd that ships with the workspace examples."""
    sample_paths = [
        "examples/delft3d4/02_domaindecomposition/bak_1.grd",
        "examples/delft3d4/04_fluidmud/case1.grd",
        "examples/delft3d4/07_wave/coastw.grd",
    ]
    seen = 0
    for rel in sample_paths:
        full = _find_sample(rel)
        if full is None:
            continue
        seen += 1
        res = load_grd_mesh(full)
        assert res.ok, f"{full.name}: {res.error}"
        mesh = res.mesh
        assert mesh is not None
        assert mesh.structured_shape is not None
        assert mesh.n_nodes > 0
    if seen == 0:
        pytest.skip("no example .grd files found in workspace")


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def test_save_grd_rejects_unstructured_mesh(tmp_path: Path) -> None:
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
    )
    res = save_grd_mesh(mesh, tmp_path / "bad.grd")
    assert not res.ok
    assert res.error is not None
    assert "structured" in res.error


def test_save_grd_does_not_overwrite_when_disabled(tmp_path: Path) -> None:
    target = tmp_path / "exists.grd"
    target.write_bytes(b"placeholder")
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.0, 1.0]),
        node_y=np.array([0.0, 0.0, 1.0, 1.0]),
        edge_nodes=np.array([[0, 1], [2, 3], [0, 2], [1, 3]], dtype=np.int64),
        structured_shape=(2, 2),
    )
    res = save_grd_mesh(mesh, target, overwrite=False)
    assert not res.ok
    assert "already exists" in (res.error or "")


def test_save_grd_creates_file(tmp_path: Path) -> None:
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.0, 1.0]),
        node_y=np.array([0.0, 0.0, 1.0, 1.0]),
        edge_nodes=np.array([[0, 1], [2, 3], [0, 2], [1, 3]], dtype=np.int64),
        structured_shape=(2, 2),
    )
    target = tmp_path / "out.grd"
    res = save_grd_mesh(mesh, target)
    assert res.ok, res.error
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "Coordinate System" in text
    assert "ETA=" in text


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_inline_text_preserves_geometry(tmp_path: Path) -> None:
    src = tmp_path / "src.grd"
    src.write_text(_tiny_grd_text(), encoding="utf-8")
    loaded = load_grd_mesh(src)
    assert loaded.ok, loaded.error
    target = tmp_path / "rt.grd"
    saved = save_grd_mesh(loaded.mesh, target)  # type: ignore[arg-type]
    assert saved.ok, saved.error
    reloaded = load_grd_mesh(target)
    assert reloaded.ok, reloaded.error
    a = loaded.mesh
    b = reloaded.mesh
    assert a is not None
    assert b is not None
    assert a.structured_shape == b.structured_shape
    np.testing.assert_allclose(a.node_x, b.node_x)
    np.testing.assert_allclose(a.node_y, b.node_y)


def test_round_trip_generated_rectangular_mesh(tmp_path: Path) -> None:
    pytest.importorskip("meshkernel")
    res = make_rectangular_mesh(
        origin_x=100.0,
        origin_y=200.0,
        n_columns=4,
        n_rows=3,
        cell_size=10.0,
    )
    assert res.ok, res.error
    mesh = res.mesh
    assert mesh is not None
    assert mesh.structured_shape == (4, 5)  # (n_rows + 1, n_cols + 1)

    target = tmp_path / "generated.grd"
    save = save_grd_mesh(mesh, target)
    assert save.ok, save.error
    back = load_grd_mesh(target)
    assert back.ok, back.error
    loaded = back.mesh
    assert loaded is not None
    assert loaded.structured_shape == mesh.structured_shape
    assert loaded.n_nodes == mesh.n_nodes
