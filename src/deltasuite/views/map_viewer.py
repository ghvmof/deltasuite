"""Embedded matplotlib widget that renders a 2-D snapshot of a result field.

Curvilinear grids are drawn with ``pcolormesh``; unstructured meshes use
``tripcolor`` after a fan triangulation of each face. Both code paths share
the same colour-bar handling and auto / fixed value range logic.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from matplotlib.backends.backend_qtagg import (  # type: ignore[attr-defined]
    FigureCanvasQTAgg,
    NavigationToolbar2QT,
)
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from deltasuite.core.results import Field2D, GridKind

if TYPE_CHECKING:
    from matplotlib.collections import Collection
    from matplotlib.colorbar import Colorbar


class MapViewerWidget(QWidget):
    """Embed a Matplotlib :class:`~matplotlib.figure.Figure` in a QWidget.

    Use :meth:`set_field` to (re)draw the contents. The widget keeps the
    most recent field, axes limits and colour bar so that switching between
    time steps is fast.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._figure = Figure(figsize=(7, 5), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)  # type: ignore[no-untyped-call]
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)  # type: ignore[no-untyped-call]

        self._axes = self._figure.add_subplot(111)
        self._axes.set_aspect("equal", adjustable="datalim")
        self._axes.set_xlabel("x")
        self._axes.set_ylabel("y")
        self._mesh: Collection | None = None
        self._colorbar: Colorbar | None = None
        self._cmap: str = "viridis"
        self._fixed_range: tuple[float, float] | None = None
        self._field: Field2D | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        self._show_placeholder("No data loaded")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_field(self, field: Field2D) -> None:
        """Render ``field`` into the canvas."""
        self._field = field
        self._render()

    def set_colormap(self, cmap_name: str) -> None:
        """Change the active matplotlib colormap and redraw."""
        self._cmap = cmap_name
        if self._field is not None:
            self._render()

    def set_value_range(self, vmin: float | None, vmax: float | None) -> None:
        """Clamp the colour scale to ``[vmin, vmax]``. ``None`` re-enables auto."""
        if vmin is None or vmax is None:
            self._fixed_range = None
        else:
            self._fixed_range = (float(vmin), float(vmax))
        if self._field is not None:
            self._render()

    def clear(self) -> None:
        """Remove the current plot and reset the canvas."""
        self._field = None
        self._show_placeholder("No data loaded")

    def current_field(self) -> Field2D | None:
        """The field most recently passed to :meth:`set_field`."""
        return self._field

    def figure(self) -> Figure:
        """Underlying matplotlib :class:`Figure` (for tests / screenshots)."""
        return self._figure

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _render(self) -> None:
        assert self._field is not None
        field = self._field
        if self._colorbar is not None:
            with contextlib.suppress(KeyError, ValueError, AttributeError):
                self._colorbar.remove()
            self._colorbar = None
        self._axes.clear()
        self._axes.set_aspect("equal", adjustable="datalim")
        self._axes.set_xlabel("x")
        self._axes.set_ylabel("y")

        vmin, vmax = self._compute_range(field.values)
        try:
            if field.grid.kind is GridKind.CURVILINEAR:
                mesh = self._draw_curvilinear(field, vmin, vmax)
            elif field.grid.kind is GridKind.UNSTRUCTURED:
                mesh = self._draw_unstructured(field, vmin, vmax)
            else:
                self._show_placeholder("Unsupported grid kind")
                return
        except (ValueError, RuntimeError) as exc:
            logger.warning("Failed to render field {}: {}", field.name, exc)
            self._show_placeholder(f"Cannot render: {exc}")
            return

        self._mesh = mesh
        self._colorbar = self._figure.colorbar(mesh, ax=self._axes, shrink=0.85)
        units = f" [{field.units}]" if field.units else ""
        self._colorbar.set_label(f"{field.name}{units}")

        title_parts = [field.name]
        if field.time is not None:
            title_parts.append(field.time.strftime("%Y-%m-%d %H:%M:%S"))
        self._axes.set_title("  -  ".join(title_parts))

        self._canvas.draw_idle()  # type: ignore[no-untyped-call]

    def _draw_curvilinear(self, field: Field2D, vmin: float, vmax: float) -> Collection:
        x = field.grid.x
        y = field.grid.y
        values = field.values
        # pcolormesh wants Z aligned with corners; if shapes match, treat as
        # cell-centred and let matplotlib infer corners.
        if values.shape != x.shape:
            x, y, values = self._align_shapes(x, y, values)
        return self._axes.pcolormesh(
            x,
            y,
            np.ma.masked_invalid(values),
            shading="auto",
            cmap=self._cmap,
            vmin=vmin,
            vmax=vmax,
        )

    def _draw_unstructured(self, field: Field2D, vmin: float, vmax: float) -> Collection:
        from matplotlib.tri import Triangulation

        cells = field.grid.cells
        if cells is None:
            raise ValueError("Unstructured grid lacks face connectivity")
        triangles = self._fan_triangulate(cells)
        if triangles.size == 0:
            raise ValueError("No triangles to draw")

        triang = Triangulation(field.grid.x, field.grid.y, triangles)
        values = field.values
        if values.size == cells.shape[0]:
            return self._axes.tripcolor(
                triang,
                facecolors=np.ma.masked_invalid(values),
                cmap=self._cmap,
                vmin=vmin,
                vmax=vmax,
            )
        return self._axes.tripcolor(
            triang,
            np.ma.masked_invalid(values),
            shading="gouraud",
            cmap=self._cmap,
            vmin=vmin,
            vmax=vmax,
        )

    @staticmethod
    def _fan_triangulate(cells: np.ndarray) -> np.ndarray:
        """Fan triangulate each polygon face into 1 or more triangles."""
        triangles: list[tuple[int, int, int]] = []
        for face in cells:
            valid = face[face >= 0]
            for i in range(1, valid.size - 1):
                triangles.append((int(valid[0]), int(valid[i]), int(valid[i + 1])))
        return np.asarray(triangles, dtype=np.int64)

    @staticmethod
    def _align_shapes(
        x: np.ndarray, y: np.ndarray, values: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Reconcile common Delft3D layout mismatches between coords and values."""
        if values.shape[0] == x.shape[0] - 1 and values.shape[1] == x.shape[1] - 1:
            return x, y, values
        if values.shape[0] == x.shape[0] + 1 or values.shape[1] == x.shape[1] + 1:
            new_values = values[: x.shape[0], : x.shape[1]]
            return x, y, new_values
        raise ValueError(f"Mismatched shapes: coords {x.shape}, values {values.shape}")

    def _compute_range(self, values: np.ndarray) -> tuple[float, float]:
        if self._fixed_range is not None:
            return self._fixed_range
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            return -1.0, 1.0
        vmin = float(np.percentile(finite, 1))
        vmax = float(np.percentile(finite, 99))
        if vmin == vmax:
            vmax = vmin + 1.0
        return vmin, vmax

    def _show_placeholder(self, message: str) -> None:
        if self._colorbar is not None:
            with contextlib.suppress(KeyError, ValueError, AttributeError):
                self._colorbar.remove()
            self._colorbar = None
        self._axes.clear()
        self._axes.set_aspect("auto")
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
            color="#888888",
        )
        self._mesh = None
        self._canvas.draw_idle()  # type: ignore[no-untyped-call]
