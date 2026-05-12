"""Generate a synthetic Delft3D-like NetCDF and open it in the DeltaSuite viewer.

Run from the project root with the venv active::

    python scripts/demo_view_results.py

This is the preferred way to *visually* validate the Phase 2 viewer when no
real Delft3D run is available (or its output is in NEFIS).
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


def make_synthetic_trim(target: Path, *, n_time: int = 24) -> None:
    """Write a curvilinear trim-style NetCDF with three plottable variables."""
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
    u1 = np.zeros_like(s1)
    v1 = np.zeros_like(s1)
    for t in range(n_time):
        phase = 2 * np.pi * t / n_time
        s1[t] = 0.5 * np.sin(2 * np.pi * xx / 4000 + phase) * np.cos(2 * np.pi * yy / 3000)
        u1[t] = 0.3 * np.cos(2 * np.pi * xx / 4000 + phase)
        v1[t] = 0.3 * np.sin(2 * np.pi * yy / 3000 + phase)

    ds = xr.Dataset(
        data_vars={
            "S1": (("time", "M", "N"), s1, {"long_name": "Water level", "units": "m"}),
            "U1": (
                ("time", "M", "N"),
                u1,
                {"long_name": "Velocity (X)", "units": "m s-1"},
            ),
            "V1": (
                ("time", "M", "N"),
                v1,
                {"long_name": "Velocity (Y)", "units": "m s-1"},
            ),
        },
        coords={
            "XCOR": (("M", "N"), xx),
            "YCOR": (("M", "N"), yy),
            "time": times,
        },
        attrs={"title": "DeltaSuite synthetic curvilinear demo"},
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(target)


def main() -> int:
    configure_logging()
    workdir = Path(tempfile.mkdtemp(prefix="deltasuite-demo-"))
    target = workdir / "trim-demo.nc"
    print(f"[demo] generating {target}")
    make_synthetic_trim(target)

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    window.open_result_file(target)
    window.statusBar().showMessage(f"Demo: {target.name}", 0)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
