"""Tests for :mod:`deltasuite.core.timeseries`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from deltasuite.core.timeseries import (
    TimeSeriesDataset,
    find_history_files,
)


def _make_fm_his(path: Path, *, n_time: int = 24, n_stations: int = 4) -> None:
    """Write a synthetic D-Flow FM ``*_his.nc`` file."""
    times = np.arange(
        np.datetime64("2024-01-01T00:00", "ns"),
        np.datetime64("2024-01-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    station_names = np.array([f"obs_{i + 1}" for i in range(n_stations)], dtype=object)
    waterlevel = np.zeros((n_time, n_stations), dtype=np.float64)
    for i in range(n_stations):
        waterlevel[:, i] = 0.5 * np.sin(np.linspace(0, 4 * np.pi, n_time)) + i * 0.1

    ds = xr.Dataset(
        data_vars={
            "waterlevel": (
                ("time", "stations"),
                waterlevel,
                {"long_name": "Water level", "units": "m"},
            ),
            "station_name": (("stations",), station_names),
        },
        coords={"time": times},
    )
    ds.to_netcdf(path)


def _make_d3d4_trih(path: Path, *, n_time: int = 12, n_stations: int = 3) -> None:
    """Write a synthetic Delft3D 4 ``trih-*.nc`` file with NAMST char arrays."""
    times = np.arange(
        np.datetime64("2024-06-01T00:00", "ns"),
        np.datetime64("2024-06-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    name_len = 20
    raw = np.zeros((n_stations, name_len), dtype="S1")
    for i in range(n_stations):
        text = f"STATION_{i + 1:02d}".ljust(name_len)
        for j, ch in enumerate(text):
            raw[i, j] = ch.encode("ascii")
    zwl = 0.3 * np.sin(np.linspace(0, 2 * np.pi, n_time))[:, None] * np.ones((1, n_stations))
    ds = xr.Dataset(
        data_vars={
            "ZWL": (
                ("time", "NOSTAT"),
                zwl,
                {"long_name": "Water level at station", "units": "m"},
            ),
            "NAMST": (("NOSTAT", "name_len"), raw),
        },
        coords={"time": times},
    )
    ds.to_netcdf(path)


# ---------------------------------------------------------------------------
# FM (his)
# ---------------------------------------------------------------------------


def test_open_fm_his_detects_stations(tmp_path: Path) -> None:
    target = tmp_path / "case_his.nc"
    _make_fm_his(target, n_stations=5)
    with TimeSeriesDataset.open(target) as ds:
        assert ds.n_stations == 5
        assert ds.stations[0] == "obs_1"
        assert "waterlevel" in ds.variables
        assert ds.variables["waterlevel"].n_time == 24
        assert ds.time_dim == "time"


def test_fm_his_read_series(tmp_path: Path) -> None:
    target = tmp_path / "case_his.nc"
    _make_fm_his(target)
    with TimeSeriesDataset.open(target) as ds:
        s = ds.read_series("waterlevel", "obs_2")
        assert s.station == "obs_2"
        assert s.values.shape == (24,)
        assert s.times.shape == (24,)
        assert s.units == "m"


def test_fm_his_read_many(tmp_path: Path) -> None:
    target = tmp_path / "case_his.nc"
    _make_fm_his(target, n_stations=3)
    with TimeSeriesDataset.open(target) as ds:
        out = ds.read_many("waterlevel", ["obs_1", "obs_3"])
        assert len(out) == 2
        assert out[0].station == "obs_1"
        assert out[1].station == "obs_3"


def test_unknown_variable_raises(tmp_path: Path) -> None:
    target = tmp_path / "case_his.nc"
    _make_fm_his(target)
    with TimeSeriesDataset.open(target) as ds, pytest.raises(KeyError):
        ds.read_series("nonexistent", "obs_1")


def test_unknown_station_raises(tmp_path: Path) -> None:
    target = tmp_path / "case_his.nc"
    _make_fm_his(target)
    with TimeSeriesDataset.open(target) as ds, pytest.raises(KeyError):
        ds.read_series("waterlevel", "ghost_station")


# ---------------------------------------------------------------------------
# Delft3D 4 (trih)
# ---------------------------------------------------------------------------


def test_open_d3d4_trih_decodes_namst(tmp_path: Path) -> None:
    target = tmp_path / "trih-mycase.nc"
    _make_d3d4_trih(target, n_stations=3)
    with TimeSeriesDataset.open(target) as ds:
        assert ds.n_stations == 3
        assert ds.stations == ["STATION_01", "STATION_02", "STATION_03"]
        assert "ZWL" in ds.variables


def test_trih_read_series(tmp_path: Path) -> None:
    target = tmp_path / "trih-foo.nc"
    _make_d3d4_trih(target)
    with TimeSeriesDataset.open(target) as ds:
        s = ds.read_series("ZWL", "STATION_02")
        assert s.values.shape == (12,)
        assert s.units == "m"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def test_find_history_files(tmp_path: Path) -> None:
    (tmp_path / "case_his.nc").write_bytes(b"")
    (tmp_path / "trih-foo.nc").write_bytes(b"")
    (tmp_path / "trim-foo.nc").write_bytes(b"")  # not a history file
    files = find_history_files(tmp_path)
    roles = {f.role for f in files}
    assert roles == {"his", "trih"}
    assert len(files) == 2
