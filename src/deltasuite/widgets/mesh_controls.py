"""Side panel that drives :class:`MeshViewerWidget` and the mesh ops.

Exposes one *button per high-level mesh operation* plus a few key
parameter spin boxes (cell size, refinement iterations, orthogonalisation
iterations). Heavy work is delegated to :mod:`deltasuite.mesh`; this
widget only emits Qt signals so the surrounding panel can sequence the
calls and update the viewer.

The widget is purely presentational (no business logic, no I/O), which
makes it trivial to test with ``pytest-qt`` smoke tests.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class MeshControls(QWidget):
    """Compact toolbar of mesh-editing actions and their parameters."""

    # ---- signals (one per public action) -----------------------------
    generate_rectangular_requested = Signal(int, int, float)
    """Args: ``n_columns``, ``n_rows``, ``cell_size``."""
    refine_requested = Signal(int)
    """Refine the current mesh inside its full extent ``n_iterations`` times."""
    orthogonalize_requested = Signal(int)
    """Run the orthogonaliser for ``outer_iterations``."""
    open_mesh_requested = Signal()
    """User clicked *Open mesh…*."""
    save_mesh_requested = Signal()
    """User clicked *Save mesh as…*."""
    clear_mesh_requested = Signal()
    """User clicked *Clear*."""
    open_depth_requested = Signal()
    """User clicked *Open depth (.dep)…*."""
    clear_depth_requested = Signal()
    """User clicked *Clear depth*."""
    triangulate_from_file_requested = Signal()
    """User clicked *Triangulate from file (.pol/.ldb/.xy)…*."""
    triangulate_from_bbox_requested = Signal()
    """User clicked *Triangulate from current mesh bbox*."""
    refine_by_depth_requested = Signal(float, int)
    """Args: ``min_edge_size``, ``max_iterations``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setSpacing(10)

        outer.addWidget(self._build_io_box())
        outer.addWidget(self._build_depth_box())
        outer.addWidget(self._build_generate_box())
        outer.addWidget(self._build_triangulate_box())
        outer.addWidget(self._build_refine_box())
        outer.addWidget(self._build_refine_samples_box())
        outer.addWidget(self._build_ortho_box())
        outer.addStretch(1)

        self._status = QLabel("Ready.")
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

    def _build_io_box(self) -> QFrame:
        box, layout = self._box("Mesh I/O")
        self._open_btn = QPushButton("Open mesh…")
        self._save_btn = QPushButton("Save mesh as…")
        self._clear_btn = QPushButton("Clear")
        self._save_btn.setEnabled(False)
        self._clear_btn.setEnabled(False)
        layout.addRow(self._open_btn)
        layout.addRow(self._save_btn)
        layout.addRow(self._clear_btn)

        self._open_btn.clicked.connect(self.open_mesh_requested)
        self._save_btn.clicked.connect(self.save_mesh_requested)
        self._clear_btn.clicked.connect(self.clear_mesh_requested)
        return box

    def _build_depth_box(self) -> QFrame:
        box, layout = self._box("Bathymetry (.dep)")
        self._open_depth_btn = QPushButton("Open depth (.dep)…")
        self._clear_depth_btn = QPushButton("Clear depth")
        self._open_depth_btn.setEnabled(False)
        self._clear_depth_btn.setEnabled(False)
        self._depth_label = QLabel("No depth loaded.")
        self._depth_label.setStyleSheet("color: #94a3b8;")
        self._depth_label.setWordWrap(True)
        layout.addRow(self._open_depth_btn)
        layout.addRow(self._clear_depth_btn)
        layout.addRow(self._depth_label)

        self._open_depth_btn.clicked.connect(self.open_depth_requested)
        self._clear_depth_btn.clicked.connect(self.clear_depth_requested)
        return box

    def _build_generate_box(self) -> QFrame:
        box, layout = self._box("Generate rectangular")

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 10_000)
        self._cols_spin.setValue(20)

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 10_000)
        self._rows_spin.setValue(20)

        self._cell_spin = QDoubleSpinBox()
        self._cell_spin.setRange(0.001, 1_000_000.0)
        self._cell_spin.setDecimals(3)
        self._cell_spin.setValue(100.0)

        self._gen_btn = QPushButton("Generate")
        layout.addRow("Columns", self._cols_spin)
        layout.addRow("Rows", self._rows_spin)
        layout.addRow("Cell size", self._cell_spin)
        layout.addRow(self._gen_btn)

        self._gen_btn.clicked.connect(
            lambda: self.generate_rectangular_requested.emit(
                int(self._cols_spin.value()),
                int(self._rows_spin.value()),
                float(self._cell_spin.value()),
            )
        )
        return box

    def _build_triangulate_box(self) -> QFrame:
        box, layout = self._box("Triangulate (Delaunay)")
        self._triangulate_file_btn = QPushButton("From file (.pol / .ldb / .xy)…")
        self._triangulate_bbox_btn = QPushButton("From current mesh bbox")
        self._triangulate_bbox_btn.setEnabled(False)
        layout.addRow(self._triangulate_file_btn)
        layout.addRow(self._triangulate_bbox_btn)

        self._triangulate_file_btn.clicked.connect(self.triangulate_from_file_requested)
        self._triangulate_bbox_btn.clicked.connect(self.triangulate_from_bbox_requested)
        return box

    def _build_refine_box(self) -> QFrame:
        box, layout = self._box("Refine (full extent)")
        self._refine_iter_spin = QSpinBox()
        self._refine_iter_spin.setRange(1, 8)
        self._refine_iter_spin.setValue(1)
        self._refine_btn = QPushButton("Refine")
        self._refine_btn.setEnabled(False)
        layout.addRow("Iterations", self._refine_iter_spin)
        layout.addRow(self._refine_btn)

        self._refine_btn.clicked.connect(
            lambda: self.refine_requested.emit(int(self._refine_iter_spin.value()))
        )
        return box

    def _build_refine_samples_box(self) -> QFrame:
        box, layout = self._box("Refine by samples (uses depth)")
        # min_edge_size = 0 with node-aligned samples can drive
        # meshkernel into a runaway refinement loop. Force a tiny but
        # non-zero floor so the user has to deliberately set it lower
        # if they really want to.
        self._refine_min_edge_spin = QDoubleSpinBox()
        self._refine_min_edge_spin.setRange(0.001, 1_000_000.0)
        self._refine_min_edge_spin.setDecimals(3)
        self._refine_min_edge_spin.setValue(1.0)

        self._refine_max_iter_spin = QSpinBox()
        self._refine_max_iter_spin.setRange(1, 12)
        self._refine_max_iter_spin.setValue(3)

        self._refine_by_depth_btn = QPushButton("Refine using current depth")
        self._refine_by_depth_btn.setEnabled(False)
        layout.addRow("Min edge size", self._refine_min_edge_spin)
        layout.addRow("Max iterations", self._refine_max_iter_spin)
        layout.addRow(self._refine_by_depth_btn)

        self._refine_by_depth_btn.clicked.connect(
            lambda: self.refine_by_depth_requested.emit(
                float(self._refine_min_edge_spin.value()),
                int(self._refine_max_iter_spin.value()),
            )
        )
        return box

    def _build_ortho_box(self) -> QFrame:
        box, layout = self._box("Orthogonalise")
        self._ortho_iter_spin = QSpinBox()
        self._ortho_iter_spin.setRange(1, 50)
        self._ortho_iter_spin.setValue(2)
        self._ortho_btn = QPushButton("Orthogonalise")
        self._ortho_btn.setEnabled(False)
        layout.addRow("Outer iterations", self._ortho_iter_spin)
        layout.addRow(self._ortho_btn)

        self._ortho_btn.clicked.connect(
            lambda: self.orthogonalize_requested.emit(int(self._ortho_iter_spin.value()))
        )
        return box

    # ------------------------------------------------------------------
    # Public API used by MeshPanel
    # ------------------------------------------------------------------
    def set_mesh_loaded(self, loaded: bool) -> None:
        """Toggle the buttons that only make sense once a mesh exists."""
        for btn in (
            self._save_btn,
            self._clear_btn,
            self._refine_btn,
            self._ortho_btn,
            self._open_depth_btn,
            self._triangulate_bbox_btn,
        ):
            btn.setEnabled(loaded)
        if not loaded:
            self.set_depth_loaded(loaded=False)

    def set_depth_loaded(self, loaded: bool, summary: str | None = None) -> None:
        """Toggle the depth-related buttons and update the status label."""
        self._clear_depth_btn.setEnabled(loaded)
        # Refine by samples needs *both* a mesh and a depth to make sense.
        self._refine_by_depth_btn.setEnabled(loaded)
        if loaded and summary:
            self._depth_label.setText(summary)
            self._depth_label.setStyleSheet("color: #f1f5f9;")
        else:
            self._depth_label.setText("No depth loaded.")
            self._depth_label.setStyleSheet("color: #94a3b8;")

    def set_status(self, text: str) -> None:
        self._status.setText(text)

    def cell_size(self) -> float:
        return float(self._cell_spin.value())
