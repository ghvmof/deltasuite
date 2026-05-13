"""3-D mesh viewer built on top of matplotlib's ``Axes3D``.

Deliberately matplotlib-only (no PyVista / VTK dependency) so the
viewer ships with the same wheel as the rest of DeltaSuite. PyVistaQt
remains a candidate optional extra for users who need huge meshes or
real-time interactivity, but for the typical D-Flow FM domain (≤ 10⁵
faces) ``Axes3D`` is plenty and integrates cleanly with our existing
matplotlib stack.

The widget understands two visual modes:

* **flat** -- every node sits at ``z = 0``. Useful as a sanity preview
  of an edited mesh; rotation still gives the user a sense of scale.
* **extruded** -- node ``z`` is taken from a user-supplied array and
  multiplied by ``z_scale``. The default extrusion is a smooth
  radial function so an empty mesh is not boring; once the user wires
  up bathymetry / water level, the array can be replaced via
  :meth:`set_node_values`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
from matplotlib.backends.backend_qtagg import (  # type: ignore[attr-defined]
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from deltasuite.core.mesh_adapter import MeshGeometry

DisplayMode = Literal["flat", "extruded"]


class Mesh3DViewerWidget(QWidget):
    """Matplotlib ``Axes3D`` canvas for a :class:`MeshGeometry`."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mesh: MeshGeometry | None = None
        self._node_values: np.ndarray | None = None
        self._mode: DisplayMode = "flat"
        self._z_scale: float = 1.0
        self._show_faces: bool = True
        self._show_edges: bool = True
        self._face_cmap: str = "viridis"
        self._face_alpha: float = 0.85
        self._edge_color: str = "#1e293b"
        self._edge_width: float = 0.4
        self._elev: float = 30.0
        self._azim: float = -60.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figure = Figure(figsize=(6, 4), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)  # type: ignore[no-untyped-call]
        self._toolbar = NavigationToolbar2QT(self._canvas, self)  # type: ignore[no-untyped-call]
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._axes = self._figure.add_subplot(111, projection="3d")
        self._show_placeholder("No mesh loaded")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_mesh(self, mesh: MeshGeometry | None) -> None:
        self._mesh = mesh
        if mesh is None or mesh.n_edges == 0:
            self._show_placeholder("No mesh loaded")
            return
        self._render()

    def set_node_values(self, values: np.ndarray | None) -> None:
        """Set per-node Z values (any 1-D array of length ``n_nodes``)."""
        if values is not None and self._mesh is not None and values.size != self._mesh.n_nodes:
            return
        self._node_values = None if values is None else np.asarray(values, dtype=np.float64)
        if self._mesh is not None:
            self._render()

    def set_mode(self, mode: DisplayMode) -> None:
        self._mode = mode
        if self._mesh is not None:
            self._render()

    def set_z_scale(self, scale: float) -> None:
        self._z_scale = max(float(scale), 0.0)
        if self._mesh is not None:
            self._render()

    def set_camera(self, *, elev: float | None = None, azim: float | None = None) -> None:
        if elev is not None:
            self._elev = float(elev)
        if azim is not None:
            self._azim = float(azim)
        self._axes.view_init(elev=self._elev, azim=self._azim)
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def set_show_faces(self, value: bool) -> None:
        self._show_faces = bool(value)
        if self._mesh is not None:
            self._render()

    def set_show_edges(self, value: bool) -> None:
        self._show_edges = bool(value)
        if self._mesh is not None:
            self._render()

    def set_colormap(self, name: str) -> None:
        self._face_cmap = name
        if self._mesh is not None:
            self._render()

    def current_mesh(self) -> MeshGeometry | None:
        return self._mesh

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _show_placeholder(self, text: str) -> None:
        self._axes.clear()
        self._axes.set_axis_off()
        self._axes.text2D(
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

    def _node_z(self) -> np.ndarray:
        assert self._mesh is not None
        if self._mode == "flat":
            return np.zeros(self._mesh.n_nodes, dtype=np.float64)
        if self._node_values is not None and self._node_values.size == self._mesh.n_nodes:
            return self._node_values * self._z_scale
        # Demo extrusion: smooth radial sinusoid centred on the mesh
        # bbox. Magnitude is scaled to ~10 % of the larger horizontal
        # extent so it's visible without the user touching ``z_scale``.
        mesh = self._mesh
        xc = 0.5 * (mesh.node_x.min() + mesh.node_x.max())
        yc = 0.5 * (mesh.node_y.min() + mesh.node_y.max())
        extent = max(
            mesh.node_x.max() - mesh.node_x.min(),
            mesh.node_y.max() - mesh.node_y.min(),
            1.0,
        )
        rx = (mesh.node_x - xc) / extent
        ry = (mesh.node_y - yc) / extent
        z = 0.1 * extent * self._z_scale * np.cos(np.pi * np.hypot(rx, ry))
        return np.asarray(z, dtype=np.float64)

    def _add_faces(
        self,
        nx: np.ndarray,
        ny: np.ndarray,
        nz: np.ndarray,
    ) -> None:
        from matplotlib import colormaps
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        assert self._mesh is not None
        mesh = self._mesh
        if mesh.face_nodes is None or mesh.face_nodes.size == 0:
            return
        faces_xyz: list[np.ndarray] = []
        face_z_means: list[float] = []
        for row in mesh.face_nodes:
            valid = row[row != -1]
            if valid.size < 3:
                continue
            idx = valid.astype(int)
            poly = np.column_stack([nx[idx], ny[idx], nz[idx]])
            faces_xyz.append(poly)
            face_z_means.append(float(nz[idx].mean()))
        if not faces_xyz:
            return
        z_array = np.asarray(face_z_means, dtype=np.float64)
        z_min, z_max = float(z_array.min()), float(z_array.max())
        if z_max <= z_min:
            z_max = z_min + 1.0
        norm = (z_array - z_min) / (z_max - z_min)
        cmap = colormaps[self._face_cmap]
        faces = Poly3DCollection(
            faces_xyz,
            facecolors=cmap(norm),
            alpha=self._face_alpha,
            linewidths=0.0,
        )
        self._axes.add_collection3d(faces)

    def _add_edges(
        self,
        nx: np.ndarray,
        ny: np.ndarray,
        nz: np.ndarray,
    ) -> None:
        from mpl_toolkits.mplot3d.art3d import Line3DCollection

        assert self._mesh is not None
        edges = self._mesh.edge_nodes
        mask = (edges >= 0).all(axis=1) & (edges < nx.size).all(axis=1)
        if not mask.any():
            return
        e = edges[mask]
        segs = np.empty((e.shape[0], 2, 3), dtype=float)
        segs[:, 0, 0] = nx[e[:, 0]]
        segs[:, 0, 1] = ny[e[:, 0]]
        segs[:, 0, 2] = nz[e[:, 0]]
        segs[:, 1, 0] = nx[e[:, 1]]
        segs[:, 1, 1] = ny[e[:, 1]]
        segs[:, 1, 2] = nz[e[:, 1]]
        lines = Line3DCollection(
            segs,
            colors=self._edge_color,
            linewidths=self._edge_width,
        )
        self._axes.add_collection3d(lines)

    def _apply_axes_limits(self, nx: np.ndarray, ny: np.ndarray, nz: np.ndarray) -> None:
        assert self._mesh is not None
        mesh = self._mesh
        self._axes.set_xlim(float(nx.min()), float(nx.max()))
        self._axes.set_ylim(float(ny.min()), float(ny.max()))
        z_lo = float(nz.min())
        z_hi = float(nz.max())
        if z_hi <= z_lo:
            z_hi = z_lo + 1.0
        self._axes.set_zlim(z_lo, z_hi)
        self._axes.view_init(elev=self._elev, azim=self._azim)
        self._axes.set_xlabel("x")
        self._axes.set_ylabel("y")
        self._axes.set_zlabel("z")
        self._axes.set_title(
            f"3D - {mesh.n_nodes} nodes / {mesh.n_edges} edges / {mesh.n_faces} faces"
        )

    def _render(self) -> None:
        assert self._mesh is not None
        mesh = self._mesh
        self._axes.clear()
        self._axes.set_axis_on()
        nx = mesh.node_x
        ny = mesh.node_y
        nz = self._node_z()
        if self._show_faces:
            self._add_faces(nx, ny, nz)
        if self._show_edges:
            self._add_edges(nx, ny, nz)
        self._apply_axes_limits(nx, ny, nz)
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]
