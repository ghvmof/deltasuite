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

from deltasuite.core.dfm_tools_adapter import (
    extract_uv_field,
    find_uv_variables,
)
from deltasuite.core.mesh_adapter import MeshGeometry, load_mesh_from_dataset
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
        self._cached_mesh: MeshGeometry | None = None

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
        self._controls.vector_overlay_toggled.connect(self._on_vector_toggled)
        self._controls.vector_stride_changed.connect(self._on_vector_stride_changed)
        self._controls.mesh_overlay_toggled.connect(self._on_mesh_toggled)

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
        # Inform the controls panel whether U/V components exist in this
        # dataset so it can enable/disable the vector overlay row.
        u_name, v_name = find_uv_variables(ds.raw)
        self._controls.set_vector_overlay_available(u_name is not None and v_name is not None)
        # Same idea for the mesh wireframe overlay: only enable it when the
        # dataset actually contains a mesh we can render.
        mesh_result = load_mesh_from_dataset(ds.raw)
        self._controls.set_mesh_overlay_available(mesh_result.ok)
        self._cached_mesh = mesh_result.mesh
        self._refresh_field()

    def _on_variable_changed(self, _name: str) -> None:
        self._refresh_field()

    def _on_time_changed(self, _index: int) -> None:
        self._refresh_field()

    def _on_vector_toggled(self, enabled: bool) -> None:
        if not enabled:
            self._viewer.set_vector_overlay(None)
            return
        self._refresh_uv_overlay()

    def _on_vector_stride_changed(self, _stride: int) -> None:
        if self._controls.vector_overlay_enabled():
            self._refresh_uv_overlay()

    def _on_mesh_toggled(self, enabled: bool) -> None:
        if enabled and self._cached_mesh is not None:
            self._viewer.set_mesh_overlay(self._cached_mesh)
        else:
            self._viewer.set_mesh_overlay(None)

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
        # Re-draw the vector overlay if the user has it enabled, so it
        # stays synchronised with the current time step.
        if self._controls.vector_overlay_enabled():
            self._refresh_uv_overlay()

    def _refresh_uv_overlay(self) -> None:
        """Re-extract U/V and feed it to the map viewer for the current time."""
        if self._dataset is None:
            return
        time_index = self._controls.current_time_index()
        stride = self._controls.vector_overlay_stride()
        try:
            uv = extract_uv_field(self._dataset.raw, time_index=time_index, stride=stride)
        except Exception as exc:
            logger.warning("extract_uv_field failed: {}", exc)
            uv = None
        self._viewer.set_vector_overlay(uv)

    def _close_dataset(self) -> None:
        if self._dataset is not None:
            self._dataset.close()
            self._dataset = None
