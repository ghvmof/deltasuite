"""High-level widget combining a :class:`TimeSeriesViewerWidget` and its controls."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from deltasuite.core.timeseries import TimeSeriesDataset
from deltasuite.views.timeseries_viewer import TimeSeriesViewerWidget
from deltasuite.widgets.timeseries_controls import TimeSeriesControls

if TYPE_CHECKING:
    from deltasuite.core.timeseries import TimeSeriesFile


class TimeSeriesPanel(QWidget):
    """Coordinator widget that pairs the time-series viewer with its controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = TimeSeriesViewerWidget()
        self._controls = TimeSeriesControls()
        self._dataset: TimeSeriesDataset | None = None
        self._files: list[Path] = []

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._viewer)
        splitter.addWidget(self._controls)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._controls.file_selected.connect(self._on_file_selected)
        self._controls.variable_changed.connect(self._on_variable_changed)
        self._controls.stations_changed.connect(self._on_stations_changed)
        self._controls.select_all_requested.connect(self._controls.select_all_stations)
        self._controls.select_none_requested.connect(self._controls.clear_station_selection)
        self._controls.export_csv_requested.connect(self._on_export_csv)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_files(self, files: list[TimeSeriesFile]) -> None:
        """Populate the file selector with discovered history files."""
        paths = [f.path for f in files]
        self._files = paths
        self._controls.set_files(paths)
        if not paths:
            self._close_dataset()
            self._viewer.clear()

    def open_file(self, path: Path) -> None:
        """Open ``path`` and select it in the file combo (creating the entry)."""
        path = Path(path).resolve()
        if path not in self._files:
            self._files.append(path)
            self._controls.set_files(self._files)
        else:
            index = self._files.index(path)
            self._controls.set_current_file_index(index)
            self._on_file_selected(index)

    def shutdown(self) -> None:
        """Close any open dataset (called when the window is destroyed)."""
        self._close_dataset()

    @property
    def viewer(self) -> TimeSeriesViewerWidget:
        """The underlying matplotlib viewer (for tests / advanced uses)."""
        return self._viewer

    @property
    def controls(self) -> TimeSeriesControls:
        """The control panel (for tests / advanced uses)."""
        return self._controls

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_file_selected(self, index: int) -> None:
        if not 0 <= index < len(self._files):
            return
        path = self._files[index]
        self._close_dataset()
        try:
            ds = TimeSeriesDataset.open(path)
        except (OSError, RuntimeError) as exc:
            logger.error("Failed to open {}: {}", path, exc)
            QMessageBox.critical(
                self,
                "Could not open history file",
                f"DeltaSuite could not read {path.name}:\n\n{exc}",
            )
            return
        self._dataset = ds
        self._controls.set_dataset(ds)
        self._refresh_curves()

    def _on_variable_changed(self, _name: str) -> None:
        self._refresh_curves()

    def _on_stations_changed(self, _stations: list[str]) -> None:
        self._refresh_curves()

    def _on_export_csv(self) -> None:
        series = self._viewer.current_series()
        if not series:
            QMessageBox.information(self, "Export CSV", "No curves to export.")
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export curves as CSV",
            f"{series[0].variable}.csv",
            "CSV files (*.csv);;All files (*)",
        )
        if not path_str:
            return
        try:
            payload = self._viewer.to_csv(series)
            Path(path_str).write_text(payload, encoding="utf-8")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export CSV", f"Could not write {path_str}:\n\n{exc}")
            return
        QMessageBox.information(self, "Export CSV", f"Wrote {len(series)} series to {path_str}.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh_curves(self) -> None:
        if self._dataset is None:
            self._viewer.clear()
            return
        var = self._controls.current_variable()
        stations = self._controls.current_stations()
        if not var or not stations:
            self._viewer.set_series([])
            return
        try:
            series = self._dataset.read_many(var, stations)
        except (KeyError, ValueError) as exc:
            logger.warning("read_many({}) failed: {}", var, exc)
            self._viewer.set_series([])
            return
        self._viewer.set_series(series, ylabel=var)

    def _close_dataset(self) -> None:
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None
