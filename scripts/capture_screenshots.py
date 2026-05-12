"""Capture PNG screenshots of every workspace tab for the README.

Run from the project root with the venv active::

    python scripts/capture_screenshots.py

Output files land in ``docs/_static/screenshots/``.

Each capture briefly drives the GUI through synthetic data so the user
sees the *same* result a real run would produce, without needing to set
up Delft3D or pick a sample.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import xarray as xr
from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from deltasuite.app.main_window import MainWindow
from deltasuite.core import configure_logging, open_bundled_sample
from deltasuite.core.recent import push_recent

OUTPUT_DIR = Path("docs/_static/screenshots")


# ---------------------------------------------------------------------------
# Synthetic data builders (re-using the same recipes as the demo scripts)
# ---------------------------------------------------------------------------


def _make_trim_nc(target: Path, n_time: int = 24) -> None:
    m, n = 60, 40
    x = np.linspace(0.0, 6000.0, m)
    y = np.linspace(0.0, 4000.0, n)
    xx, yy = np.meshgrid(x, y, indexing="ij")
    times = np.arange(
        np.datetime64("2024-09-01T00:00", "ns"),
        np.datetime64("2024-09-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    s1 = np.zeros((n_time, m, n), dtype=np.float64)
    for t in range(n_time):
        phase = 2 * np.pi * t / n_time
        s1[t] = 0.5 * np.sin(2 * np.pi * xx / 4000 + phase) * np.cos(2 * np.pi * yy / 3000)
    ds = xr.Dataset(
        data_vars={
            "S1": (
                ("time", "M", "N"),
                s1,
                {"long_name": "Water level", "units": "m"},
            ),
        },
        coords={
            "XCOR": (("M", "N"), xx),
            "YCOR": (("M", "N"), yy),
            "time": times,
        },
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(target)


def _make_his_nc(target: Path, n_stations: int = 6, n_time: int = 120) -> None:
    times = np.arange(
        np.datetime64("2024-09-01T00:00", "ns"),
        np.datetime64("2024-09-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    names = np.array([f"observation_{i + 1:02d}" for i in range(n_stations)], dtype=object)
    waterlevel = np.zeros((n_time, n_stations), dtype=np.float64)
    for i in range(n_stations):
        phase = i * np.pi / n_stations
        waterlevel[:, i] = 0.6 * np.sin(2 * np.pi * np.arange(n_time) / 24 + phase) + 0.05 * i
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
    target.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(target)


# ---------------------------------------------------------------------------
# Capture helpers
# ---------------------------------------------------------------------------


def _save_window(window: MainWindow, name: str) -> Path:
    pix = window.grab()
    out = OUTPUT_DIR / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out), "PNG")
    logger.info("Wrote {}", out)
    return out


def _capture_sequence(window: MainWindow, results: Path, history: Path) -> None:
    """Drive ``window`` through every tab and grab a screenshot of each."""
    # 1) Welcome screen (no project loaded yet).
    _save_window(window, "01_welcome")

    # 2) Open the bundled sample → Overview.
    project = open_bundled_sample("f34")
    push_recent(project.root, name=project.meta.name)
    window._set_current_project(project)
    _save_window(window, "02_overview")

    # 3) Setup tab.
    window._workspace_tabs.setCurrentWidget(window._setup_editor)
    _save_window(window, "03_setup")

    # 4) Map tab with synthetic NetCDF.
    window._workspace_tabs.setCurrentWidget(window._result_panel)
    window._result_panel.open_file(results)
    QApplication.processEvents()
    _save_window(window, "04_map")

    # 5) Series tab with synthetic history.
    window._workspace_tabs.setCurrentWidget(window._series_panel)
    window._series_panel.open_file(history)
    QApplication.processEvents()
    _save_window(window, "05_series")


def main() -> int:
    configure_logging()
    workdir = Path(tempfile.mkdtemp(prefix="deltasuite-screens-"))
    results = workdir / "trim-demo.nc"
    history = workdir / "demo_his.nc"
    _make_trim_nc(results)
    _make_his_nc(history)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.resize(1280, 800)
    window.show()

    # Schedule the capture once Qt has finished its initial layout pass.
    timer = QTimer()
    timer.setSingleShot(True)

    def _go() -> None:
        try:
            _capture_sequence(window, results, history)
        finally:
            QApplication.quit()

    timer.timeout.connect(_go)
    timer.start(800)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
