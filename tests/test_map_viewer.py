"""Smoke tests for the matplotlib map viewer and result panel."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.core.results import ResultDataset, ResultFile
from deltasuite.views.map_viewer import MapViewerWidget
from deltasuite.views.result_panel import ResultPanel


def _make_curvilinear(path: Path) -> None:
    m, n, t = 6, 5, 2
    x = np.linspace(0, 100, m)
    y = np.linspace(0, 80, n)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    times = np.arange(
        np.datetime64("2024-01-01T00:00", "ns"),
        np.datetime64("2024-01-01T00:00", "ns") + np.timedelta64(t, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    data = np.stack([np.sin(0.05 * xx + 0.05 * yy + i) for i in range(t)])
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


def test_map_viewer_renders_curvilinear(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "trim-test.nc"
    _make_curvilinear(target)

    viewer = MapViewerWidget()
    qtbot.addWidget(viewer)

    with ResultDataset.open(target) as ds:
        field = ds.read_field("S1", time_index=0)
        viewer.set_field(field)
        assert viewer.current_field() is field
        viewer.set_colormap("plasma")
        viewer.set_value_range(-1.0, 1.0)
        viewer.set_value_range(None, None)
        viewer.clear()
        assert viewer.current_field() is None


def test_result_panel_loads_files(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    a = tmp_path / "trim-a.nc"
    _make_curvilinear(a)

    panel = ResultPanel()
    qtbot.addWidget(panel)
    panel.set_files([ResultFile(path=a, role="trim")])

    qtbot.wait(50)
    assert panel.viewer.current_field() is not None
    panel.shutdown()
