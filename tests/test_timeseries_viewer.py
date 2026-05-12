"""Smoke tests for the time-series viewer and panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.core.timeseries import TimeSeriesDataset, TimeSeriesFile
from deltasuite.views.timeseries_panel import TimeSeriesPanel
from deltasuite.views.timeseries_viewer import TimeSeriesViewerWidget


def _make_his(path: Path, n_stations: int = 3) -> None:
    n_time = 12
    times = np.arange(
        np.datetime64("2024-01-01T00:00", "ns"),
        np.datetime64("2024-01-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    waterlevel = np.zeros((n_time, n_stations), dtype=np.float64)
    for i in range(n_stations):
        waterlevel[:, i] = np.sin(np.linspace(0, 2 * np.pi, n_time)) + i
    names = np.array([f"obs_{i + 1}" for i in range(n_stations)], dtype=object)
    ds = xr.Dataset(
        data_vars={
            "waterlevel": (
                ("time", "stations"),
                waterlevel,
                {"long_name": "Water level", "units": "m"},
            ),
            "station_name": (("stations",), names),
        },
        coords={"time": times},
    )
    ds.to_netcdf(path)


def test_viewer_renders_series(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "case_his.nc"
    _make_his(target)
    viewer = TimeSeriesViewerWidget()
    qtbot.addWidget(viewer)

    with TimeSeriesDataset.open(target) as ds:
        series = ds.read_many("waterlevel", ["obs_1", "obs_2"])
        viewer.set_series(series, ylabel="waterlevel")
        assert len(viewer.current_series()) == 2
        viewer.clear()
        assert viewer.current_series() == []


def test_viewer_csv_export(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "case_his.nc"
    _make_his(target)
    viewer = TimeSeriesViewerWidget()
    qtbot.addWidget(viewer)

    with TimeSeriesDataset.open(target) as ds:
        series = ds.read_many("waterlevel", ["obs_1", "obs_2"])
        csv = viewer.to_csv(series)
        lines = csv.strip().splitlines()
        assert lines[0] == "time,obs_1,obs_2"
        assert len(lines) == 13  # header + 12 timestamps


def test_panel_loads_files(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    a = tmp_path / "case_his.nc"
    _make_his(a)
    panel = TimeSeriesPanel()
    qtbot.addWidget(panel)
    panel.set_files([TimeSeriesFile(path=a, role="his")])
    qtbot.wait(50)
    # First station auto-selected → at least one curve.
    assert len(panel.viewer.current_series()) >= 1
    panel.shutdown()
