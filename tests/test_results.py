"""Tests for :mod:`deltasuite.core.results`.

Exercises the dataset reader against synthetic NetCDF files mimicking the
two grid families DeltaSuite supports: Delft3D 4 trim NetCDF (curvilinear)
and D-Flow FM map NetCDF (UGRID).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from deltasuite.core.results import (
    GridKind,
    ResultDataset,
    find_result_files,
)

# ---------------------------------------------------------------------------
# Synthetic file builders
# ---------------------------------------------------------------------------


def _make_curvilinear_trim(path: Path, *, n_time: int = 3) -> None:
    m, n = 8, 6
    x = np.linspace(0, 1000, m)
    y = np.linspace(0, 600, n)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    times = np.arange(
        np.datetime64("2024-01-01T00:00", "ns"),
        np.datetime64("2024-01-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )

    data = np.zeros((n_time, m, n), dtype=np.float64)
    for t in range(n_time):
        data[t] = np.sin(0.01 * xx + 0.02 * yy + 0.1 * t)

    ds = xr.Dataset(
        data_vars={
            "S1": (("time", "M", "N"), data, {"long_name": "Water level", "units": "m"}),
        },
        coords={
            "XCOR": (("M", "N"), xx),
            "YCOR": (("M", "N"), yy),
            "time": times,
        },
    )
    ds.to_netcdf(path)


def _make_ugrid_map(path: Path, *, n_time: int = 2) -> None:
    nodes = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [2.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
            [2.0, 1.0],
        ]
    )
    faces = np.array(
        [
            [1, 2, 5, 4],
            [2, 3, 6, 5],
        ],
        dtype=np.int32,
    )

    times = np.arange(
        np.datetime64("2024-06-01T00:00", "ns"),
        np.datetime64("2024-06-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )

    s1 = np.array([[0.10, 0.20], [0.15, 0.25]])  # (time, face)

    ds = xr.Dataset(
        data_vars={
            "mesh2d_face_nodes": (
                ("nmesh2d_face", "max_nmesh2d_face_nodes"),
                faces,
                {"_FillValue": -1},
            ),
            "mesh2d_s1": (
                ("time", "nmesh2d_face"),
                s1,
                {"long_name": "Water level", "units": "m"},
            ),
        },
        coords={
            "mesh2d_node_x": ("nmesh2d_node", nodes[:, 0]),
            "mesh2d_node_y": ("nmesh2d_node", nodes[:, 1]),
            "time": times,
        },
    )
    ds.to_netcdf(path)


# ---------------------------------------------------------------------------
# Curvilinear
# ---------------------------------------------------------------------------


def test_open_curvilinear_detects_grid_and_variables(tmp_path: Path) -> None:
    target = tmp_path / "trim-mycase.nc"
    _make_curvilinear_trim(target)

    with ResultDataset.open(target) as ds:
        assert ds.grid_kind is GridKind.CURVILINEAR
        assert ds.path == target
        assert ds.n_time == 3
        assert "S1" in ds.variables
        assert ds.variables["S1"].units == "m"
        assert ds.variables["S1"].long_name == "Water level"
        assert ds.variables["S1"].n_time == 3


def test_curvilinear_field_extraction(tmp_path: Path) -> None:
    target = tmp_path / "trim-case.nc"
    _make_curvilinear_trim(target)
    with ResultDataset.open(target) as ds:
        field = ds.read_field("S1", time_index=1)
        assert field.values.shape == (8, 6)
        assert field.units == "m"
        assert field.grid.kind is GridKind.CURVILINEAR
        assert field.time is not None
        assert field.time.year == 2024


def test_curvilinear_time_index_out_of_range(tmp_path: Path) -> None:
    target = tmp_path / "trim-case.nc"
    _make_curvilinear_trim(target, n_time=2)
    with ResultDataset.open(target) as ds, pytest.raises(IndexError):
        ds.read_field("S1", time_index=99)


# ---------------------------------------------------------------------------
# Unstructured (UGRID)
# ---------------------------------------------------------------------------


def test_open_ugrid_detects_grid(tmp_path: Path) -> None:
    target = tmp_path / "case_map.nc"
    _make_ugrid_map(target)

    with ResultDataset.open(target) as ds:
        assert ds.grid_kind is GridKind.UNSTRUCTURED
        grid = ds.grid()
        assert grid.x.shape == (6,)
        assert grid.cells is not None
        assert grid.cells.shape == (2, 4)
        # 1-based indices were converted to 0-based.
        assert grid.cells.min() == 0


def test_ugrid_field_extraction(tmp_path: Path) -> None:
    target = tmp_path / "case_map.nc"
    _make_ugrid_map(target)
    with ResultDataset.open(target) as ds:
        field = ds.read_field("mesh2d_s1", time_index=1)
        assert field.values.shape == (2,)
        assert field.units == "m"
        assert pytest.approx(0.15) == field.values[0]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_find_result_files_classifies_roles(tmp_path: Path) -> None:
    (tmp_path / "trim-foo.nc").write_bytes(b"")
    (tmp_path / "case_map.nc").write_bytes(b"")
    (tmp_path / "case_his.nc").write_bytes(b"")
    (tmp_path / "random.nc").write_bytes(b"")
    files = find_result_files(tmp_path)
    by_role = {f.role for f in files}
    assert "trim" in by_role
    assert "map" in by_role
    assert "his" in by_role
    assert "unknown" in by_role


def test_unknown_grid_kind(tmp_path: Path) -> None:
    target = tmp_path / "weird.nc"
    ds = xr.Dataset(
        data_vars={"A": (("i", "j"), np.zeros((4, 5)))},
        coords={"i": np.arange(4), "j": np.arange(5)},
    )
    ds.to_netcdf(target)
    with ResultDataset.open(target) as result:
        assert result.grid_kind is GridKind.UNKNOWN
        with pytest.raises(RuntimeError):
            result.grid()
