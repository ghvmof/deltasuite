"""Glue widget: pairs :class:`Mesh3DViewerWidget` with :class:`Mesh3DControls`.

Owns no mesh state of its own -- it pulls the geometry from the *Mesh*
tab via the ``mesh_provider`` callable supplied by ``MainWindow``. That
keeps the source of truth in a single place (the editor) and avoids
having to duplicate ``MeshGeometry`` instances or wire complex signals
across panels.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSizePolicy,
    QSplitter,
    QWidget,
)

from deltasuite.views.mesh3d_viewer import Mesh3DViewerWidget
from deltasuite.widgets.mesh3d_controls import Mesh3DControls

if TYPE_CHECKING:
    from deltasuite.core.mesh_adapter import MeshGeometry
    from deltasuite.mesh.io_dep import DepthField


MeshProvider = Callable[[], "MeshGeometry | None"]
DepthProvider = Callable[[], "DepthField | None"]


class Mesh3DPanel(QWidget):
    """Coordinator widget that pairs the 3-D viewer with its controls."""

    def __init__(
        self,
        mesh_provider: MeshProvider | None = None,
        parent: QWidget | None = None,
        *,
        depth_provider: DepthProvider | None = None,
    ) -> None:
        super().__init__(parent)
        self._viewer = Mesh3DViewerWidget()
        self._controls = Mesh3DControls()
        self._mesh_provider: MeshProvider | None = mesh_provider
        self._depth_provider: DepthProvider | None = depth_provider

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

        self._controls.refresh_from_mesh_requested.connect(self.refresh_from_provider)
        self._controls.mode_changed.connect(self._viewer.set_mode)  # type: ignore[arg-type]
        self._controls.z_scale_changed.connect(self._viewer.set_z_scale)
        self._controls.show_faces_changed.connect(self._viewer.set_show_faces)
        self._controls.show_edges_changed.connect(self._viewer.set_show_edges)
        self._controls.colormap_changed.connect(self._viewer.set_colormap)
        self._controls.elevation_changed.connect(lambda elev: self._viewer.set_camera(elev=elev))
        self._controls.azimuth_changed.connect(lambda azim: self._viewer.set_camera(azim=azim))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def viewer(self) -> Mesh3DViewerWidget:
        return self._viewer

    @property
    def controls(self) -> Mesh3DControls:
        return self._controls

    def set_mesh_provider(self, provider: MeshProvider | None) -> None:
        """Wire / re-wire the callable that supplies the active mesh."""
        self._mesh_provider = provider

    def set_depth_provider(self, provider: DepthProvider | None) -> None:
        """Wire / re-wire the callable that supplies a per-node depth."""
        self._depth_provider = provider

    def refresh_from_provider(self) -> None:
        """Pull the current mesh (and depth) from the providers and redraw."""
        if self._mesh_provider is None:
            self._controls.set_status("No mesh source connected.")
            return
        mesh = self._mesh_provider()
        self._viewer.set_mesh(mesh)
        depth_status = ""
        if self._depth_provider is not None and mesh is not None:
            depth = self._depth_provider()
            if depth is not None and depth.n_nodes == mesh.n_nodes:
                self._viewer.set_node_values(depth.node_values)
                depth_status = f" / depth {depth.n_valid}/{depth.n_nodes} valid"
            else:
                self._viewer.set_node_values(None)
        else:
            self._viewer.set_node_values(None)
        if mesh is None:
            self._controls.set_status("No mesh loaded.")
        else:
            self._controls.set_status(
                f"Synced: {mesh.n_nodes} nodes, {mesh.n_edges} edges, "
                f"{mesh.n_faces} faces{depth_status}."
            )

    def set_mesh(self, mesh: MeshGeometry | None) -> None:
        """Push a mesh directly into the viewer (used by tests)."""
        self._viewer.set_mesh(mesh)
        if mesh is None:
            self._controls.set_status("No mesh loaded.")
        else:
            self._controls.set_status(
                f"Mesh set: {mesh.n_nodes} nodes, {mesh.n_edges} edges, {mesh.n_faces} faces."
            )

    def shutdown(self) -> None:
        self._mesh_provider = None
        self._depth_provider = None
