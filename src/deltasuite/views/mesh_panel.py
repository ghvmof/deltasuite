"""Glue widget: pairs :class:`MeshViewerWidget` with :class:`MeshControls`.

Owns the active :class:`MeshGeometry` and routes every signal coming
from the controls into the right :mod:`deltasuite.mesh` operation,
updating the viewer and the status line on success / failure.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
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
    load_dep_samples,
    load_grd_mesh,
    load_polygon_file,
    make_rectangular_mesh,
    make_triangular_mesh_from_polygon,
    orthogonalize_mesh,
    refine_mesh_based_on_samples,
    refine_mesh_inside_polygon,
    save_grd_mesh,
    save_mesh_to_ugrid_netcdf,
)
from deltasuite.views.mesh_viewer import MeshViewerWidget
from deltasuite.widgets.mesh_controls import MeshControls

if TYPE_CHECKING:
    from deltasuite.core.mesh_adapter import MeshGeometry
    from deltasuite.mesh.io_dep import DepthField


class MeshPanel(QWidget):
    """Coordinator widget that pairs the mesh viewer with its controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._viewer = MeshViewerWidget()
        self._controls = MeshControls()
        self._mesh: MeshGeometry | None = None
        self._depth: DepthField | None = None

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
        self._controls.open_depth_requested.connect(self._on_open_depth)
        self._controls.clear_depth_requested.connect(self._on_clear_depth)
        self._controls.triangulate_from_file_requested.connect(self._on_triangulate_from_file)
        self._controls.triangulate_from_bbox_requested.connect(self._on_triangulate_from_bbox)
        self._controls.refine_by_depth_requested.connect(self._on_refine_by_depth)

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

    def current_depth(self) -> DepthField | None:
        return self._depth

    def shutdown(self) -> None:
        """Release resources (no-op for now; symmetric with other panels)."""
        self._mesh = None
        self._depth = None

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
            "Open mesh (UGRID NetCDF or Delft3D RGFGRID)",
            "",
            (
                "All supported meshes (*.nc *.grd);;"
                "UGRID NetCDF (*.nc);;"
                "Delft3D RGFGRID (*.grd);;"
                "All files (*)"
            ),
        )
        if not path_str:
            return
        path = Path(path_str)
        result = load_grd_mesh(path) if path.suffix.lower() == ".grd" else load_mesh_from_path(path)
        if not result.ok:
            self._error("Open mesh", result.error or "unknown error")
            return
        self._set_mesh(result.mesh)
        self._controls.set_status(f"Opened {path.name}.")

    def _on_save_mesh(self) -> None:
        if self._mesh is None:
            return
        # Default suffix depends on whether the mesh is structured. A
        # locally-refined or triangular mesh cannot be saved as .grd,
        # so we pre-select .nc to avoid the user picking an extension
        # that we'll reject later.
        default_name = "mesh.grd" if self._mesh.is_structured else "mesh.nc"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save mesh as…",
            default_name,
            ("UGRID NetCDF (*.nc);;Delft3D RGFGRID (*.grd);;All files (*)"),
        )
        if not path_str:
            return
        path = Path(path_str)
        result = (
            save_grd_mesh(self._mesh, path)
            if path.suffix.lower() == ".grd"
            else save_mesh_to_ugrid_netcdf(self._mesh, path)
        )
        if not result.ok:
            self._error("Save mesh", result.error or "unknown error")
            return
        self._controls.set_status(f"Saved {path.name}.")

    def _on_clear(self) -> None:
        self._set_mesh(None)
        self._controls.set_status("Cleared.")

    def _on_open_depth(self) -> None:
        if self._mesh is None:
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Delft3D depth (.dep)",
            "",
            "Delft3D depth (*.dep);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        result = load_dep_samples(path, self._mesh)
        if not result.ok or result.field is None:
            self._error("Open depth", result.error or "unknown error")
            return
        self._set_depth(result.field, source=path.name)

    def _on_clear_depth(self) -> None:
        self._set_depth(None)
        self._controls.set_status("Depth cleared.")

    def _on_triangulate_from_file(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Triangulate from polygon file",
            "",
            (
                "Delft3D polygon (*.pol *.ldb *.xy);;"
                "Polygon (*.pol);;"
                "Land boundary (*.ldb);;"
                "XY pairs (*.xy);;"
                "All files (*)"
            ),
        )
        if not path_str:
            return
        path = Path(path_str)
        loaded = load_polygon_file(path)
        if not loaded.ok:
            self._error("Triangulate", loaded.error or "no polygon found")
            return
        polygon = loaded.largest()
        if polygon is None or polygon.n_vertices < 3:
            self._error(
                "Triangulate",
                f"polygon needs >= 3 vertices to triangulate (got {polygon.n_vertices if polygon else 0})",
            )
            return
        self._triangulate(polygon.x, polygon.y, source=f"{path.name} ({polygon.name})")

    def _on_triangulate_from_bbox(self) -> None:
        if self._mesh is None:
            return
        px, py = self._mesh_bbox_polygon()
        self._triangulate(
            np.asarray(px, dtype=float), np.asarray(py, dtype=float), source="current mesh bbox"
        )

    def _on_refine_by_depth(self, min_edge_size: float, max_iterations: int) -> None:
        if self._mesh is None or self._depth is None:
            return
        # Sample coordinates = mesh node positions; sample values = depth.
        # NaN samples are dropped so meshkernel only sees finite numbers.
        nx = self._mesh.node_x
        ny = self._mesh.node_y
        values = self._depth.node_values
        valid_mask = ~np.isnan(values)
        if not valid_mask.any():
            self._error("Refine by samples", "depth field has no valid samples")
            return
        # Defensive floor on min_edge_size: with samples placed at the
        # mesh nodes themselves and min_edge_size <= 0, meshkernel can
        # spiral into runaway refinement. Refuse early in that case.
        if min_edge_size <= 0.0:
            self._error(
                "Refine by samples",
                "min_edge_size must be > 0 when samples coincide with mesh nodes",
            )
            return
        result = refine_mesh_based_on_samples(
            self._mesh,
            sample_x=nx[valid_mask],
            sample_y=ny[valid_mask],
            sample_values=values[valid_mask],
            min_edge_size=min_edge_size,
            max_refinement_iterations=max_iterations,
        )
        if not result.ok or result.mesh is None:
            self._error("Refine by samples", result.error or "unknown error")
            return
        new_mesh = result.mesh
        self._set_mesh(new_mesh)
        self._controls.set_status(
            f"Refined by samples: {new_mesh.n_nodes} nodes "
            f"(max_iter={max_iterations}, min_edge={min_edge_size})."
        )

    def _triangulate(self, polygon_x: np.ndarray, polygon_y: np.ndarray, *, source: str) -> None:
        result = make_triangular_mesh_from_polygon(polygon_x, polygon_y)
        if not result.ok or result.mesh is None:
            self._error("Triangulate", result.error or "unknown error")
            return
        new_mesh = result.mesh
        self._set_mesh(new_mesh)
        self._controls.set_status(
            f"Triangulated from {source}: {new_mesh.n_nodes} nodes / {new_mesh.n_faces} faces."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_mesh(self, mesh: MeshGeometry | None) -> None:
        # Mesh changes invalidate the depth (it is keyed by node count).
        self._depth = None
        self._mesh = mesh
        self._viewer.set_mesh(mesh)
        self._controls.set_mesh_loaded(mesh is not None)
        self._controls.set_depth_loaded(loaded=False)

    def _set_depth(self, depth: DepthField | None, *, source: str | None = None) -> None:
        self._depth = depth
        self._viewer.set_depth(depth)
        if depth is None:
            self._controls.set_depth_loaded(loaded=False)
            return
        lo, hi = depth.value_range
        summary = (
            f"{source}: {depth.n_valid}/{depth.n_nodes} valid samples, range {lo:.2f} - {hi:.2f}"
        )
        self._controls.set_depth_loaded(loaded=True, summary=summary)
        self._controls.set_status(f"Loaded depth from {source}.")

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
