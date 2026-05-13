"""Standalone matplotlib viewer for a 2-D mesh wireframe.

Dedicated widget (rather than reusing :class:`MapViewerWidget`) because
the *Mesh* tab does not need a colour field, only a clean line-drawing
canvas with the same Qt navigation toolbar users already know from the
*Map* and *Series* tabs.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.backends.backend_qtagg import (  # type: ignore[attr-defined]
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from matplotlib.collections import LineCollection, PolyCollection

    from deltasuite.core.mesh_adapter import MeshGeometry
    from deltasuite.mesh.io_dep import DepthField


class MeshViewerWidget(QWidget):
    """Embeds a matplotlib canvas that renders a :class:`MeshGeometry` as edges."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mesh: MeshGeometry | None = None
        self._depth: DepthField | None = None
        self._line_color: str = "#1f3a8a"
        self._line_width: float = 0.6
        self._colorbar: Any | None = None  # matplotlib.colorbar.Colorbar

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(6, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)  # type: ignore[no-untyped-call]
        self._toolbar = NavigationToolbar2QT(self._canvas, self)  # type: ignore[no-untyped-call]
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._axes = self._figure.add_subplot(111)
        self._show_placeholder("No mesh loaded")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_mesh(self, mesh: MeshGeometry | None) -> None:
        """Render ``mesh``, or clear the canvas if ``None``."""
        self._mesh = mesh
        # Depth is bound to a specific mesh; drop it on every change.
        self._depth = None
        if mesh is None or mesh.n_edges == 0:
            self._show_placeholder("No mesh loaded")
            return
        self._render()

    def set_depth(self, depth: DepthField | None) -> None:
        """Attach (or clear) a per-node depth field used to colour faces."""
        self._depth = depth
        if self._mesh is None or self._mesh.n_edges == 0:
            return
        self._render()

    def current_mesh(self) -> MeshGeometry | None:
        return self._mesh

    def current_depth(self) -> DepthField | None:
        return self._depth

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _show_placeholder(self, text: str) -> None:
        self._axes.clear()
        self._axes.set_axis_off()
        self._axes.text(
            0.5,
            0.5,
            text,
            ha="center",
            va="center",
            color="#94a3b8",
            transform=self._axes.transAxes,
            fontsize=12,
        )
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def _render(self) -> None:
        assert self._mesh is not None
        mesh = self._mesh
        self._reset_axes()

        if self._depth is not None and self._depth.n_nodes == mesh.n_nodes:
            self._add_face_color(mesh)

        wire = self._build_edge_collection(mesh)
        if wire is None:
            self._show_placeholder("Mesh has no drawable edges")
            return
        self._axes.add_collection(wire)
        self._axes.set_xlim(float(mesh.node_x.min()), float(mesh.node_x.max()))
        self._axes.set_ylim(float(mesh.node_y.min()), float(mesh.node_y.max()))
        self._axes.set_aspect("equal", adjustable="box")
        self._axes.set_xlabel("x")
        self._axes.set_ylabel("y")
        self._axes.set_title(f"{mesh.n_nodes} nodes — {mesh.n_edges} edges — {mesh.n_faces} faces")
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def _reset_axes(self) -> None:
        if self._colorbar is not None:
            with contextlib.suppress(KeyError, ValueError, AttributeError):
                self._colorbar.remove()
            self._colorbar = None
        self._axes.clear()
        self._axes.set_axis_on()

    def _add_face_color(self, mesh: MeshGeometry) -> None:
        """Overlay a per-face colour patch coloured by the average node depth."""
        polys = self._build_face_collection(mesh)
        if polys is None:
            return
        self._axes.add_collection(polys)
        self._colorbar = self._figure.colorbar(polys, ax=self._axes, shrink=0.8)
        self._colorbar.set_label("depth")

    def _build_edge_collection(self, mesh: MeshGeometry) -> LineCollection | None:
        from matplotlib.collections import LineCollection

        edges = mesh.edge_nodes
        nx = mesh.node_x
        ny = mesh.node_y
        mask = (edges >= 0).all(axis=1) & (edges < nx.size).all(axis=1)
        if not mask.any():
            return None
        edges = edges[mask]
        segments = np.empty((edges.shape[0], 2, 2), dtype=float)
        segments[:, 0, 0] = nx[edges[:, 0]]
        segments[:, 0, 1] = ny[edges[:, 0]]
        segments[:, 1, 0] = nx[edges[:, 1]]
        segments[:, 1, 1] = ny[edges[:, 1]]
        return LineCollection(
            segments,  # type: ignore[arg-type]
            colors=self._line_color,
            linewidths=self._line_width,
        )

    def _build_face_collection(self, mesh: MeshGeometry) -> PolyCollection | None:
        from matplotlib.collections import PolyCollection

        if mesh.n_faces == 0 or self._depth is None or mesh.face_nodes is None:
            return None
        faces = mesh.face_nodes
        nx = mesh.node_x
        ny = mesh.node_y
        depth = self._depth.node_values

        verts: list[np.ndarray] = []
        values: list[float] = []
        for face in faces:
            valid = face[face >= 0]
            if valid.size < 3:
                continue
            face_depth = depth[valid]
            if np.all(np.isnan(face_depth)):
                continue
            poly = np.column_stack((nx[valid], ny[valid]))
            verts.append(poly)
            values.append(float(np.nanmean(face_depth)))
        if not verts:
            return None
        coll = PolyCollection(
            verts,  # type: ignore[arg-type]
            array=np.asarray(values, dtype=float),
            cmap="viridis",
            edgecolors="none",
        )
        return coll
