"""High-level widget combining a :class:`MapViewerWidget` and its controls.

This is what the main window embeds as the *Map* tab. It owns the open
:class:`~deltasuite.core.results.ResultDataset` lifecycle: opening,
switching files / variables / time steps, and closing on shutdown.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from deltasuite.core.results import ResultDataset
from deltasuite.views.map_viewer import MapViewerWidget
from deltasuite.widgets.result_controls import ResultControls

if TYPE_CHECKING:
    from deltasuite.core.results import ResultFile


class ResultPanel(QWidget):
    """Coordinator widget that pairs the map viewer with its controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = MapViewerWidget()
        self._controls = ResultControls()
        self._dataset: ResultDataset | None = None
        self._files: list[Path] = []

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(self._viewer)
        self._splitter.addWidget(self._controls)
        self._splitter.setStretchFactor(0, 4)
        self._splitter.setStretchFactor(1, 1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._splitter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._controls.file_selected.connect(self._on_file_selected)
        self._controls.variable_changed.connect(self._on_variable_changed)
        self._controls.time_changed.connect(self._on_time_changed)
        self._controls.colormap_changed.connect(self._viewer.set_colormap)
        self._controls.range_changed.connect(self._viewer.set_value_range)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_files(self, files: list[ResultFile]) -> None:
        """Populate the file selector with discovered result files."""
        paths = [f.path for f in files if f.is_spatial_field] or [f.path for f in files]
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
    def viewer(self) -> MapViewerWidget:
        """The underlying matplotlib viewer (for tests / advanced uses)."""
        return self._viewer

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_file_selected(self, index: int) -> None:
        if not 0 <= index < len(self._files):
            return
        path = self._files[index]
        self._close_dataset()
        try:
            ds = ResultDataset.open(path)
        except (OSError, RuntimeError) as exc:
            logger.error("Failed to open {}: {}", path, exc)
            QMessageBox.critical(
                self,
                "Could not open result file",
                f"DeltaSuite could not read {path.name}:\n\n{exc}",
            )
            return
        self._dataset = ds
        self._controls.set_dataset(ds)
        self._refresh_field()

    def _on_variable_changed(self, _name: str) -> None:
        self._refresh_field()

    def _on_time_changed(self, _index: int) -> None:
        self._refresh_field()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _refresh_field(self) -> None:
        if self._dataset is None:
            return
        var = self._controls.current_variable()
        if var is None:
            return
        time_index = self._controls.current_time_index()
        try:
            field = self._dataset.read_field(var, time_index=time_index)
        except (KeyError, IndexError, ValueError) as exc:
            logger.warning("read_field({}, t={}) failed: {}", var, time_index, exc)
            return
        self._viewer.set_field(field)

    def _close_dataset(self) -> None:
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None
