"""Tests for ``deltasuite.mesh.io_enc``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import (
    Enclosure,
    load_enc,
    save_enc,
)


def _coastw_like_enc_text() -> str:
    return (
        "     1     1   *** begin external enclosure\n"
        "    67     1\n"
        "    67    76\n"
        "     1    76\n"
        "     1     1   *** end external grid enclosure\n"
    )


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def test_load_enc_missing_file_returns_error(tmp_path: Path) -> None:
    res = load_enc(tmp_path / "no.enc")
    assert not res.ok
    assert "not found" in (res.error or "")


def test_load_enc_parses_canonical_sample(tmp_path: Path) -> None:
    target = tmp_path / "sample.enc"
    target.write_text(_coastw_like_enc_text(), encoding="utf-8")
    res = load_enc(target)
    assert res.ok, res.error
    enc = res.enclosure
    assert enc is not None
    assert enc.n_vertices == 5
    np.testing.assert_array_equal(enc.m_indices, [1, 67, 67, 1, 1])
    np.testing.assert_array_equal(enc.n_indices, [1, 1, 76, 76, 1])
    assert enc.x is None
    assert enc.y is None


def test_load_enc_auto_closes_open_polygon(tmp_path: Path) -> None:
    text = "  1  1\n  3  1\n  3  3\n  1  3\n"
    target = tmp_path / "open.enc"
    target.write_text(text, encoding="utf-8")
    res = load_enc(target)
    assert res.ok, res.error
    enc = res.enclosure
    assert enc is not None
    assert enc.n_vertices == 5
    assert (enc.m_indices[0], enc.n_indices[0]) == (
        int(enc.m_indices[-1]),
        int(enc.n_indices[-1]),
    )


def test_load_enc_too_few_vertices_returns_error(tmp_path: Path) -> None:
    target = tmp_path / "two.enc"
    target.write_text("1 1\n3 1\n", encoding="utf-8")
    res = load_enc(target)
    assert not res.ok


def test_load_enc_with_mesh_attaches_xy(tmp_path: Path) -> None:
    # 3x3 nodes, unit-spaced; M=3 (cols), N=3 (rows)
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 2.0, 0.0, 1.0, 2.0, 0.0, 1.0, 2.0]),
        node_y=np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0]),
        edge_nodes=np.empty((0, 2), dtype=np.int64),
        structured_shape=(3, 3),
    )
    target = tmp_path / "with_mesh.enc"
    target.write_text("1 1\n3 1\n3 3\n1 3\n1 1\n", encoding="utf-8")
    res = load_enc(target, mesh=mesh)
    assert res.ok, res.error
    enc = res.enclosure
    assert enc is not None
    assert enc.x is not None
    assert enc.y is not None
    np.testing.assert_allclose(enc.x, [0.0, 2.0, 2.0, 0.0, 0.0])
    np.testing.assert_allclose(enc.y, [0.0, 0.0, 2.0, 2.0, 0.0])


def test_load_enc_with_out_of_range_index_returns_error(tmp_path: Path) -> None:
    mesh = MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.0, 1.0]),
        node_y=np.array([0.0, 0.0, 1.0, 1.0]),
        edge_nodes=np.empty((0, 2), dtype=np.int64),
        structured_shape=(2, 2),
    )
    target = tmp_path / "bad.enc"
    target.write_text("1 1\n9 1\n9 9\n1 9\n1 1\n", encoding="utf-8")
    res = load_enc(target, mesh=mesh)
    assert not res.ok
    assert "outside" in (res.error or "") or "out of range" in (res.error or "")


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def test_save_enc_rejects_size_mismatch(tmp_path: Path) -> None:
    res = save_enc(tmp_path / "bad.enc", [1, 2, 3], [1, 2])
    assert not res.ok


def test_save_enc_rejects_too_few_vertices(tmp_path: Path) -> None:
    res = save_enc(tmp_path / "bad.enc", [1, 2], [1, 2])
    assert not res.ok


def test_save_enc_does_not_overwrite_when_disabled(tmp_path: Path) -> None:
    target = tmp_path / "exists.enc"
    target.write_bytes(b"placeholder")
    res = save_enc(target, [1, 3, 3, 1], [1, 1, 3, 3], overwrite=False)
    assert not res.ok


def test_save_enc_writes_canonical_format(tmp_path: Path) -> None:
    target = tmp_path / "out.enc"
    res = save_enc(target, [1, 67, 67, 1], [1, 1, 76, 76])
    assert res.ok, res.error
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert "begin external enclosure" in text
    assert "end external grid enclosure" in text


# ---------------------------------------------------------------------------
# Round-trip
# ---------------------------------------------------------------------------


def test_round_trip_enclosure(tmp_path: Path) -> None:
    target = tmp_path / "rt.enc"
    saved = save_enc(target, [1, 5, 5, 1], [1, 1, 4, 4])
    assert saved.ok
    loaded = load_enc(target)
    assert loaded.ok, loaded.error
    enc = loaded.enclosure
    assert enc is not None
    assert isinstance(enc, Enclosure)
    np.testing.assert_array_equal(enc.m_indices, [1, 5, 5, 1, 1])
    np.testing.assert_array_equal(enc.n_indices, [1, 1, 4, 4, 1])


# ---------------------------------------------------------------------------
# Real samples from the workspace examples
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


def test_load_real_coastw_enc() -> None:
    """The .enc that ships with examples/delft3d4/07_wave."""
    full = _find_sample("examples/delft3d4/07_wave/coastw.enc")
    if full is None:
        pytest.skip("sample coastw.enc not present in workspace")
    res = load_enc(full)
    assert res.ok, res.error
    enc = res.enclosure
    assert enc is not None
    assert enc.n_vertices >= 4
