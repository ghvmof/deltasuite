"""Tests for ``deltasuite.mesh.io_pol``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from deltasuite.mesh import load_polygon_file
from deltasuite.mesh.io_pol import Polygon2D


def test_load_polygon_missing_file_returns_error(tmp_path: Path) -> None:
    res = load_polygon_file(tmp_path / "nope.pol")
    assert not res.ok
    assert res.error is not None
    assert "not found" in res.error


def test_load_polygon_simple_pol_with_header(tmp_path: Path) -> None:
    text = "Obstacle 1\n2 2\n   1.0   2.0\n   3.0   4.0\n"
    target = tmp_path / "simple.pol"
    target.write_text(text, encoding="utf-8")
    res = load_polygon_file(target)
    assert res.ok, res.error
    assert len(res.polygons) == 1
    poly = res.polygons[0]
    assert poly.name == "Obstacle 1"
    assert poly.n_vertices == 2
    np.testing.assert_allclose(poly.x, [1.0, 3.0])
    np.testing.assert_allclose(poly.y, [2.0, 4.0])


def test_load_polygon_xy_no_header(tmp_path: Path) -> None:
    target = tmp_path / "points.xy"
    target.write_text("1.1e+003  1.1e+003\n978       1234\n", encoding="utf-8")
    res = load_polygon_file(target)
    assert res.ok, res.error
    assert len(res.polygons) == 1
    poly = res.polygons[0]
    assert poly.name == "points"
    assert poly.n_vertices == 2


def test_load_polygon_skips_comments(tmp_path: Path) -> None:
    text = "* this is a comment\n# another\n\nring1\n3 2\n0 0\n1 0\n0 1\n"
    target = tmp_path / "comments.pol"
    target.write_text(text, encoding="utf-8")
    res = load_polygon_file(target)
    assert res.ok, res.error
    assert len(res.polygons) == 1
    assert res.polygons[0].name == "ring1"
    assert res.polygons[0].n_vertices == 3


def test_load_polygon_multiple_rings_in_one_file(tmp_path: Path) -> None:
    text = "first\n3 2\n0 0\n1 0\n0 1\nsecond\n4 2\n10 10\n20 10\n20 20\n10 20\n"
    target = tmp_path / "multi.pol"
    target.write_text(text, encoding="utf-8")
    res = load_polygon_file(target)
    assert res.ok, res.error
    assert len(res.polygons) == 2
    assert res.polygons[0].name == "first"
    assert res.polygons[0].n_vertices == 3
    assert res.polygons[1].name == "second"
    assert res.polygons[1].n_vertices == 4
    largest = res.largest()
    assert largest is not None
    assert largest.name == "second"


def test_polygon_closed_property_and_helper() -> None:
    open_p = Polygon2D(
        name="r",
        x=np.array([0.0, 1.0, 1.0, 0.0]),
        y=np.array([0.0, 0.0, 1.0, 1.0]),
    )
    assert not open_p.is_closed
    closed = open_p.closed()
    assert closed.is_closed
    assert closed.n_vertices == 5

    already = Polygon2D(
        name="r",
        x=np.array([0.0, 1.0, 0.0]),
        y=np.array([0.0, 0.0, 0.0]),
    )
    assert already.closed() is already


def test_load_polygon_empty_file_returns_error(tmp_path: Path) -> None:
    target = tmp_path / "empty.pol"
    target.write_text("* only a comment\n\n* and a blank\n", encoding="utf-8")
    res = load_polygon_file(target)
    assert not res.ok
    assert "no polygons" in (res.error or "")


# ---------------------------------------------------------------------------
# Real-file smoke tests
# ---------------------------------------------------------------------------


def _find_sample(rel_path: str) -> Path | None:
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
    "rel_path",
    [
        "examples/delft3d4/07_wave/obw.pol",
        "examples/delft3d4/01_standard/f34.ldb",
        "examples/delft3d4/07_wave/points.xy",
    ],
)
def test_load_real_polygon_files(rel_path: str) -> None:
    sample = _find_sample(rel_path)
    if sample is None:
        pytest.skip(f"sample missing: {rel_path}")
    res = load_polygon_file(sample)
    assert res.ok, res.error
    # The parser must recover at least one polygon with one or more
    # vertices. Whether the polygon is suitable for triangulation
    # (>= 3 vertices) is the caller's concern -- thin-dam .pol files
    # legitimately ship as 2-vertex line segments and points.xy can
    # be a single observation pair.
    largest = res.largest()
    assert largest is not None
    assert largest.n_vertices >= 1
