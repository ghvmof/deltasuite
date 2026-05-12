"""Embedded matplotlib widget that plots multi-station time series."""

from __future__ import annotations

import contextlib

import numpy as np
from loguru import logger
from matplotlib.backends.backend_qtagg import (  # type: ignore[attr-defined]
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.dates import AutoDateFormatter, AutoDateLocator
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from deltasuite.core.timeseries import StationSeries


class TimeSeriesViewerWidget(QWidget):
    """Plot one or more :class:`StationSeries` on a shared time axis.

    The widget keeps the most recent set of series so toggling stations or
    variables can be done with a single :meth:`set_series` call.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(7, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)  # type: ignore[no-untyped-call]
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)  # type: ignore[no-untyped-call]
        self._axes = self._figure.add_subplot(111)
        self._axes.grid(True, which="both", linestyle=":", alpha=0.5)
        self._series: list[StationSeries] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self._show_placeholder("No series selected")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_series(self, series: list[StationSeries], *, ylabel: str = "") -> None:
        """Render every entry of ``series`` as a labelled line."""
        self._series = list(series)
        if not series:
            self._show_placeholder("No stations selected")
            return
        try:
            self._render(ylabel)
        except (ValueError, RuntimeError) as exc:
            logger.warning("Failed to render time series: {}", exc)
            self._show_placeholder(f"Cannot render: {exc}")

    def clear(self) -> None:
        """Drop all curves and show a placeholder."""
        self._series = []
        self._show_placeholder("No data loaded")

    def current_series(self) -> list[StationSeries]:
        """The series most recently passed to :meth:`set_series`."""
        return list(self._series)

    def figure(self) -> Figure:
        """Underlying matplotlib :class:`Figure` (for tests / screenshots)."""
        return self._figure

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _render(self, ylabel: str) -> None:
        self._axes.clear()
        self._axes.grid(True, which="both", linestyle=":", alpha=0.5)
        for series in self._series:
            x = series.times
            y = series.values
            if y.ndim != 1 or x.shape[0] != y.shape[0]:
                logger.warning(
                    "Skipping {}@{}: shape mismatch (x={}, y={})",
                    series.variable,
                    series.station,
                    x.shape,
                    y.shape,
                )
                continue
            self._axes.plot(
                x.astype("datetime64[ms]").astype("O"),
                y,
                label=series.station,
                linewidth=1.4,
            )

        units = self._series[0].units if self._series else ""
        if not ylabel:
            ylabel = self._series[0].variable if self._series else ""
        if units:
            ylabel = f"{ylabel} [{units}]"
        self._axes.set_ylabel(ylabel)
        self._axes.set_xlabel("Time")

        locator = AutoDateLocator()  # type: ignore[no-untyped-call]
        self._axes.xaxis.set_major_locator(locator)
        self._axes.xaxis.set_major_formatter(AutoDateFormatter(locator))  # type: ignore[no-untyped-call]
        self._figure.autofmt_xdate()

        if len(self._series) <= 12:
            self._axes.legend(loc="best", fontsize=9, framealpha=0.85)
        else:
            self._axes.legend().remove() if self._axes.get_legend() else None

        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def _show_placeholder(self, message: str) -> None:
        self._axes.clear()
        with contextlib.suppress(KeyError, ValueError, AttributeError):
            self._axes.legend().remove() if self._axes.get_legend() else None
        self._axes.set_xticks([])
        self._axes.set_yticks([])
        self._axes.text(
            0.5,
            0.5,
            message,
            transform=self._axes.transAxes,
            ha="center",
            va="center",
            fontsize=14,
            color="#888",
        )
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    @staticmethod
    def to_csv(series: list[StationSeries]) -> str:
        """Serialise ``series`` to CSV (one column per station, time first)."""
        if not series:
            return "time\n"
        times = series[0].times
        for s in series[1:]:
            if s.times.shape != times.shape:
                raise ValueError("Series have inconsistent time axes; cannot export to CSV")
        header = "time," + ",".join(s.station for s in series)
        rows = []
        for i, t in enumerate(times):
            ts = np.datetime_as_string(t, unit="s")
            cols = [ts] + [f"{s.values[i]:.6g}" for s in series]
            rows.append(",".join(cols))
        return header + "\n" + "\n".join(rows) + "\n"
