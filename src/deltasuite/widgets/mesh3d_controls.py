"""Side panel that drives :class:`Mesh3DViewerWidget`.

Mirrors :class:`MeshControls` (same look-and-feel, status line at the
bottom) but only contains *display* options -- the 3-D viewer never
mutates the mesh. The actual geometry is owned by the *Mesh* tab and
pushed into here read-only.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

DEFAULT_COLORMAPS: tuple[str, ...] = (
    "viridis",
    "plasma",
    "magma",
    "cividis",
    "turbo",
    "terrain",
    "RdBu_r",
)


class Mesh3DControls(QWidget):
    """Compact toolbar of display options for the 3-D mesh viewer."""

    mode_changed = Signal(str)
    """Emitted with ``'flat'`` or ``'extruded'``."""
    z_scale_changed = Signal(float)
    show_faces_changed = Signal(bool)
    show_edges_changed = Signal(bool)
    colormap_changed = Signal(str)
    elevation_changed = Signal(float)
    azimuth_changed = Signal(float)
    refresh_from_mesh_requested = Signal()
    """User clicked *Sync from Mesh tab*."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(10)
        outer.addWidget(self._build_source_box())
        outer.addWidget(self._build_extrusion_box())
        outer.addWidget(self._build_overlays_box())
        outer.addWidget(self._build_camera_box())
        outer.addStretch(1)

        self._status = QLabel("No mesh loaded.")
        self._status.setStyleSheet("color: #94a3b8;")
        self._status.setWordWrap(True)
        outer.addWidget(self._status)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def _box(self, title: str) -> tuple[QFrame, QFormLayout]:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QFormLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layout.addRow(QLabel(f"<b>{title}</b>"))
        return frame, layout

    def _build_source_box(self) -> QFrame:
        box, layout = self._box("Source")
        self._sync_btn = QPushButton("Sync from Mesh tab")
        layout.addRow(self._sync_btn)
        self._sync_btn.clicked.connect(self.refresh_from_mesh_requested)
        return box

    def _build_extrusion_box(self) -> QFrame:
        box, layout = self._box("Extrusion")

        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Flat (z=0)", "flat")
        self._mode_combo.addItem("Demo extruded", "extruded")
        self._mode_combo.currentIndexChanged.connect(
            lambda _i: self.mode_changed.emit(self._mode_combo.currentData())
        )
        layout.addRow("Mode", self._mode_combo)

        self._z_scale_spin = QDoubleSpinBox()
        self._z_scale_spin.setRange(0.0, 100.0)
        self._z_scale_spin.setSingleStep(0.1)
        self._z_scale_spin.setValue(1.0)
        self._z_scale_spin.valueChanged.connect(self.z_scale_changed)
        layout.addRow("Z scale", self._z_scale_spin)
        return box

    def _build_overlays_box(self) -> QFrame:
        box, layout = self._box("Overlays")

        self._faces_chk = QCheckBox("Show faces")
        self._faces_chk.setChecked(True)
        self._faces_chk.toggled.connect(self.show_faces_changed)

        self._edges_chk = QCheckBox("Show edges")
        self._edges_chk.setChecked(True)
        self._edges_chk.toggled.connect(self.show_edges_changed)

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(DEFAULT_COLORMAPS)
        self._cmap_combo.currentTextChanged.connect(self.colormap_changed)

        layout.addRow(self._faces_chk)
        layout.addRow(self._edges_chk)
        layout.addRow("Colormap", self._cmap_combo)
        return box

    def _build_camera_box(self) -> QFrame:
        box, layout = self._box("Camera")

        self._elev_slider = QSlider(Qt.Orientation.Horizontal)
        self._elev_slider.setRange(-90, 90)
        self._elev_slider.setValue(30)
        self._elev_slider.valueChanged.connect(lambda v: self.elevation_changed.emit(float(v)))

        self._azim_slider = QSlider(Qt.Orientation.Horizontal)
        self._azim_slider.setRange(-180, 180)
        self._azim_slider.setValue(-60)
        self._azim_slider.valueChanged.connect(lambda v: self.azimuth_changed.emit(float(v)))

        layout.addRow("Elevation", self._elev_slider)
        layout.addRow("Azimuth", self._azim_slider)
        return box

    # ------------------------------------------------------------------
    # Public API used by Mesh3DPanel
    # ------------------------------------------------------------------
    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def selected_mode(self) -> str:
        return str(self._mode_combo.currentData())

    def selected_colormap(self) -> str:
        return str(self._cmap_combo.currentText())
