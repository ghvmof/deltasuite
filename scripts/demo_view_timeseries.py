"""Generate a synthetic FM-like ``*_his.nc`` and open it in DeltaSuite.

Run from the project root with the venv active::

    python scripts/demo_view_timeseries.py

The synthetic file contains 6 monitoring stations with two variables
(`waterlevel` and `discharge`) sampled hourly for 5 days.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import xarray as xr
from PySide6.QtWidgets import QApplication

from deltasuite.app.main_window import MainWindow
from deltasuite.core import configure_logging


def make_synthetic_his(target: Path, *, n_stations: int = 6, n_time: int = 120) -> None:
    """Write a curvilinear-style synthetic FM history file."""
    times = np.arange(
        np.datetime64("2024-09-01T00:00", "ns"),
        np.datetime64("2024-09-01T00:00", "ns")
        + np.timedelta64(n_time, "h").astype("timedelta64[ns]"),
        np.timedelta64(1, "h").astype("timedelta64[ns]"),
    )
    names = np.array([f"observation_{i + 1:02d}" for i in range(n_stations)], dtype=object)

    waterlevel = np.zeros((n_time, n_stations), dtype=np.float64)
    discharge = np.zeros_like(waterlevel)
    for i in range(n_stations):
        phase = i * np.pi / n_stations
        waterlevel[:, i] = (
            0.6 * np.sin(2 * np.pi * np.arange(n_time) / 24 + phase)
            + 0.1 * np.cos(2 * np.pi * np.arange(n_time) / 12.42)
            + 0.05 * i
        )
        discharge[:, i] = (
            120.0 + 35.0 * np.cos(2 * np.pi * np.arange(n_time) / 24 + phase) + 8.0 * i
        )

    ds = xr.Dataset(
        data_vars={
            "waterlevel": (
                ("time", "stations"),
                waterlevel,
                {"long_name": "Water level", "units": "m"},
            ),
            "discharge": (
                ("time", "stations"),
                discharge,
                {"long_name": "Discharge", "units": "m3 s-1"},
            ),
            "station_name": (("stations",), names),
        },
        coords={"time": times},
        attrs={"title": "DeltaSuite synthetic history demo"},
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(target)


def main() -> int:
    configure_logging()
    workdir = Path(tempfile.mkdtemp(prefix="deltasuite-demo-his-"))
    target = workdir / "demo_his.nc"
    print(f"[demo] generating {target}")
    make_synthetic_his(target)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.open_history_file(target)
    window.statusBar().showMessage(f"Demo: {target.name}", 0)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
