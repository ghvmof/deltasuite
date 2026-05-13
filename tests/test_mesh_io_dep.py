"""Tests for ``deltasuite.mesh.io_dep``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import (
    DepthField,
    load_dep_samples,
    load_grd_mesh,
    save_dep_samples,
)


def _tiny_mesh_3x2() -> MeshGeometry:
    """3 cols x 2 rows = 6 nodes, structured."""
    return MeshGeometry(
        node_x=np.array([0.0, 1.0, 2.0, 0.0, 1.0, 2.0]),
        node_y=np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0]),
        edge_nodes=np.array(
            [[0, 1], [1, 2], [3, 4], [4, 5], [0, 3], [1, 4], [2, 5]],
            dtype=np.int64,
        ),
        structured_shape=(2, 3),
    )


def _dep_text_corners_extra() -> str:
    """3x2 mesh -> (N+1)x(M+1) = 3x4 = 12 values, last row/col = -999."""
    return (
        "   1.0   1.5   2.0  -999.0\n   1.5   2.0   2.5  -999.0\n  -999.0  -999.0  -999.0  -999.0\n"
    )


def _dep_text_nodes() -> str:
    """3x2 mesh, exactly 6 values aligned with nodes."""
    return "10.0 11.0 12.0 13.0 14.0 15.0\n"


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def test_load_dep_missing_file_returns_error(tmp_path: Path) -> None:
    res = load_dep_samples(tmp_path / "nope.dep", _tiny_mesh_3x2())
    assert not res.ok
    assert res.error is not None
    assert "not found" in res.error


def test_load_dep_rejects_unstructured_mesh(tmp_path: Path) -> None:
    target = tmp_path / "x.dep"
    target.write_text("1.0\n", encoding="utf-8")
    unstructured = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.5]),
        node_y=np.array([0.0, 0.0, 1.0]),
        edge_nodes=np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64),
    )
    res = load_dep_samples(target, unstructured)
    assert not res.ok
    assert "structured" in (res.error or "")


def test_load_dep_corners_extra_layout(tmp_path: Path) -> None:
    target = tmp_path / "ce.dep"
    target.write_text(_dep_text_corners_extra(), encoding="utf-8")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    field = res.field
    assert field is not None
    assert field.layout == "corners_extra"
    assert field.n_nodes == 6
    assert field.n_valid == 6
    np.testing.assert_allclose(
        field.node_values,
        [1.0, 1.5, 2.0, 1.5, 2.0, 2.5],
    )
    assert field.value_range == (1.0, 2.5)


def test_load_dep_nodes_layout(tmp_path: Path) -> None:
    target = tmp_path / "n.dep"
    target.write_text(_dep_text_nodes(), encoding="utf-8")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    field = res.field
    assert field is not None
    assert field.layout == "nodes"
    np.testing.assert_allclose(
        field.node_values,
        [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
    )


def test_load_dep_marks_missing_as_nan(tmp_path: Path) -> None:
    target = tmp_path / "mv.dep"
    text = (
        "   1.0   2.0   3.0  -999.0\n"
        "   1.5  -999.0   2.5  -999.0\n"
        "  -999.0  -999.0  -999.0  -999.0\n"
    )
    target.write_text(text, encoding="utf-8")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    field = res.field
    assert field is not None
    assert field.n_valid == 5
    assert field.n_missing == 1
    assert np.isnan(field.node_values[4])


def test_load_dep_recognises_scientific_missing(tmp_path: Path) -> None:
    target = tmp_path / "sci.dep"
    text = (
        "   1.0   2.0   3.0  -9.99000E+02\n"
        "   1.5   2.0   2.5  -9.99000E+02\n"
        "  -9.99000E+02  -9.99000E+02  -9.99000E+02  -9.99000E+02\n"
    )
    target.write_text(text, encoding="utf-8")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    field = res.field
    assert field is not None
    assert field.n_valid == 6


def test_load_dep_rejects_wrong_size(tmp_path: Path) -> None:
    target = tmp_path / "bad.dep"
    target.write_text("1.0 2.0 3.0\n", encoding="utf-8")  # only 3 samples
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert not res.ok
    assert "does not match" in (res.error or "")


def test_load_dep_rejects_centers_layout(tmp_path: Path) -> None:
    """For a 3x2 mesh, a (M-1)x(N-1) = 2x1 = 2-value file is centres."""
    target = tmp_path / "ctr.dep"
    target.write_text("1.5 1.7\n", encoding="utf-8")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert not res.ok
    assert "cell-centre" in (res.error or "")


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def test_save_dep_writes_corners_extra(tmp_path: Path) -> None:
    field = DepthField(
        node_values=np.array([1.0, 1.5, 2.0, 1.5, 2.0, 2.5]),
        missing_value=-999.0,
        layout="nodes",  # writer always emits corners_extra
    )
    target = tmp_path / "out.dep"
    res = save_dep_samples(field, target, _tiny_mesh_3x2())
    assert res.ok, res.error
    assert target.is_file()
    # Re-read what was written and check the round-trip value layout.
    raw = target.read_text(encoding="utf-8")
    tokens = [float(t) for t in raw.split()]
    assert len(tokens) == (2 + 1) * (3 + 1)  # corners_extra
    # First row first 3 values = original first row
    assert tokens[:3] == [1.0, 1.5, 2.0]
    # Last column / last row are sentinels
    assert tokens[3] == -999.0
    assert tokens[-4:] == [-999.0, -999.0, -999.0, -999.0]


def test_save_dep_does_not_overwrite_when_disabled(tmp_path: Path) -> None:
    target = tmp_path / "exists.dep"
    target.write_bytes(b"placeholder")
    field = DepthField(
        node_values=np.zeros(6),
        missing_value=-999.0,
        layout="nodes",
    )
    res = save_dep_samples(field, target, _tiny_mesh_3x2(), overwrite=False)
    assert not res.ok
    assert "already exists" in (res.error or "")


def test_save_dep_rejects_size_mismatch(tmp_path: Path) -> None:
    field = DepthField(
        node_values=np.zeros(7),  # mesh has 6
        missing_value=-999.0,
        layout="nodes",
    )
    res = save_dep_samples(field, tmp_path / "x.dep", _tiny_mesh_3x2())
    assert not res.ok
    assert "does not match" in (res.error or "")


def test_save_dep_round_trip_preserves_values(tmp_path: Path) -> None:
    original = DepthField(
        node_values=np.array([1.0, 1.5, 2.0, 1.5, 2.0, 2.5]),
        missing_value=-999.0,
        layout="nodes",
    )
    target = tmp_path / "rt.dep"
    save_dep_samples(original, target, _tiny_mesh_3x2())
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    field = res.field
    assert field is not None
    assert field.layout == "corners_extra"  # writer normalises
    np.testing.assert_allclose(field.node_values, original.node_values)


def test_save_dep_serialises_nan_as_missing(tmp_path: Path) -> None:
    field = DepthField(
        node_values=np.array([1.0, np.nan, 2.0, 1.5, 2.0, 2.5]),
        missing_value=-999.0,
        layout="nodes",
    )
    target = tmp_path / "nan.dep"
    save_dep_samples(field, target, _tiny_mesh_3x2())
    raw = target.read_text(encoding="utf-8")
    assert "-999" in raw or "-9.99" in raw.replace(" ", "")
    res = load_dep_samples(target, _tiny_mesh_3x2())
    assert res.ok, res.error
    reloaded = res.field
    assert reloaded is not None
    assert np.isnan(reloaded.node_values[1])
    assert reloaded.n_valid == 5


# ---------------------------------------------------------------------------
# Real-file smoke tests
# ---------------------------------------------------------------------------


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


@pytest.mark.parametrize(
    ("grd_rel", "dep_rel"),
    [
        (
            "examples/delft3d4/01_standard/f34.grd",
            "examples/delft3d4/01_standard/f34.dep",
        ),
        (
            "examples/dflowfm/10_dflowfm_sequential_drtc_dwaves/wave/weir.grd",
            "examples/dflowfm/10_dflowfm_sequential_drtc_dwaves/wave/weir.dep",
        ),
        (
            "examples/delft3d4/07_wave/coastw.grd",
            "examples/delft3d4/07_wave/coastw20.dep",
        ),
    ],
)
def test_load_real_dep_with_real_grd(grd_rel: str, dep_rel: str) -> None:
    grd_path = _find_sample(grd_rel)
    dep_path = _find_sample(dep_rel)
    if grd_path is None or dep_path is None:
        pytest.skip(f"sample files missing: {grd_rel} / {dep_rel}")
    grd = load_grd_mesh(grd_path)
    assert grd.ok, grd.error
    mesh = grd.mesh
    assert mesh is not None
    res = load_dep_samples(dep_path, mesh)
    assert res.ok, f"{dep_path.name}: {res.error}"
    field = res.field
    assert field is not None
    assert field.n_nodes == mesh.n_nodes
    # Real bathymetry must contain *some* finite samples.
    assert field.n_valid > 0
