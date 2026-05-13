"""Glue widget: pairs :class:`MeshViewerWidget` with :class:`MeshControls`.

Owns the active :class:`MeshGeometry` and routes every signal coming
from the controls into the right :mod:`deltasuite.mesh` operation,
updating the viewer and the status line on success / failure.
"""

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

from deltasuite.core.mesh_adapter import load_mesh_from_path
from deltasuite.mesh import (
    make_rectangular_mesh,
    orthogonalize_mesh,
    refine_mesh_inside_polygon,
    save_mesh_to_ugrid_netcdf,
)
from deltasuite.views.mesh_viewer import MeshViewerWidget
from deltasuite.widgets.mesh_controls import MeshControls

if TYPE_CHECKING:
    from deltasuite.core.mesh_adapter import MeshGeometry


class MeshPanel(QWidget):
    """Coordinator widget that pairs the mesh viewer with its controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = MeshViewerWidget()
        self._controls = MeshControls()
        self._mesh: MeshGeometry | None = None

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

        self._controls.generate_rectangular_requested.connect(self._on_generate_rectangular)
        self._controls.refine_requested.connect(self._on_refine)
        self._controls.orthogonalize_requested.connect(self._on_orthogonalize)
        self._controls.open_mesh_requested.connect(self._on_open_mesh)
        self._controls.save_mesh_requested.connect(self._on_save_mesh)
        self._controls.clear_mesh_requested.connect(self._on_clear)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def viewer(self) -> MeshViewerWidget:
        return self._viewer

    @property
    def controls(self) -> MeshControls:
        return self._controls

    def current_mesh(self) -> MeshGeometry | None:
        return self._mesh

    def shutdown(self) -> None:
        """Release resources (no-op for now; symmetric with other panels)."""
        self._mesh = None

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_generate_rectangular(self, n_columns: int, n_rows: int, cell_size: float) -> None:
        result = make_rectangular_mesh(
            origin_x=0.0,
            origin_y=0.0,
            n_columns=n_columns,
            n_rows=n_rows,
            cell_size=cell_size,
        )
        if not result.ok:
            self._error("Generate", result.error or "unknown error")
            return
        self._set_mesh(result.mesh)
        self._controls.set_status(
            f"Generated rectangular mesh ({n_rows}x{n_columns}, cell={cell_size})."
        )

    def _on_refine(self, n_iterations: int) -> None:
        if self._mesh is None:
            return
        bbox = self._mesh_bbox_polygon()
        result = refine_mesh_inside_polygon(
            self._mesh,
            polygon_x=bbox[0],
            polygon_y=bbox[1],
            n_iterations=n_iterations,
        )
        if not result.ok:
            self._error("Refine", result.error or "unknown error")
            return
        self._set_mesh(result.mesh)
        self._controls.set_status(f"Refined mesh ({n_iterations} iteration(s)).")

    def _on_orthogonalize(self, outer_iterations: int) -> None:
        if self._mesh is None:
            return
        result = orthogonalize_mesh(self._mesh, outer_iterations=outer_iterations)
        if not result.ok:
            self._error("Orthogonalise", result.error or "unknown error")
            return
        self._set_mesh(result.mesh)
        self._controls.set_status(f"Orthogonalised mesh ({outer_iterations} outer iteration(s)).")

    def _on_open_mesh(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open UGRID NetCDF mesh",
            "",
            "NetCDF mesh files (*.nc);;All files (*)",
        )
        if not path_str:
            return
        result = load_mesh_from_path(Path(path_str))
        if not result.ok:
            self._error("Open mesh", result.error or "unknown error")
            return
        self._set_mesh(result.mesh)
        self._controls.set_status(f"Opened {Path(path_str).name}.")

    def _on_save_mesh(self) -> None:
        if self._mesh is None:
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save mesh as UGRID NetCDF",
            "mesh.nc",
            "NetCDF files (*.nc);;All files (*)",
        )
        if not path_str:
            return
        result = save_mesh_to_ugrid_netcdf(self._mesh, Path(path_str))
        if not result.ok:
            self._error("Save mesh", result.error or "unknown error")
            return
        self._controls.set_status(f"Saved {Path(path_str).name}.")

    def _on_clear(self) -> None:
        self._set_mesh(None)
        self._controls.set_status("Cleared.")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_mesh(self, mesh: MeshGeometry | None) -> None:
        self._mesh = mesh
        self._viewer.set_mesh(mesh)
        self._controls.set_mesh_loaded(mesh is not None)

    def _mesh_bbox_polygon(self) -> tuple[list[float], list[float]]:
        """Return a closed rectangle covering the current mesh extent."""
        assert self._mesh is not None
        x0 = float(self._mesh.node_x.min())
        x1 = float(self._mesh.node_x.max())
        y0 = float(self._mesh.node_y.min())
        y1 = float(self._mesh.node_y.max())
        return ([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0])

    def _error(self, action: str, message: str) -> None:
        logger.warning("Mesh action {} failed: {}", action, message)
        self._controls.set_status(f"{action} failed: {message}")
        QMessageBox.warning(self, action, message)
