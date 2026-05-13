"""Smoke tests for ``Mesh3DViewerWidget``, ``Mesh3DControls`` and ``Mesh3DPanel``."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.views.mesh3d_panel import Mesh3DPanel
from deltasuite.views.mesh3d_viewer import Mesh3DViewerWidget
from deltasuite.widgets.mesh3d_controls import DEFAULT_COLORMAPS, Mesh3DControls


def _square_mesh() -> MeshGeometry:
    return MeshGeometry(
        node_x=np.array([0.0, 1.0, 0.0, 1.0]),
        node_y=np.array([0.0, 0.0, 1.0, 1.0]),
        edge_nodes=np.array(
            [[0, 1], [1, 3], [3, 2], [2, 0], [0, 3]],
            dtype=np.int64,
        ),
        face_nodes=np.array([[0, 1, 3], [0, 3, 2]], dtype=np.int64),
    )


def test_mesh3d_viewer_renders_without_mesh(qtbot) -> None:  # type: ignore[no-untyped-def]
    viewer = Mesh3DViewerWidget()
    qtbot.addWidget(viewer)
    assert viewer.current_mesh() is None
    viewer.set_mesh(None)


def test_mesh3d_viewer_renders_geometry_in_both_modes(qtbot) -> None:  # type: ignore[no-untyped-def]
    viewer = Mesh3DViewerWidget()
    qtbot.addWidget(viewer)
    viewer.set_mesh(_square_mesh())
    assert viewer.current_mesh() is not None
    viewer.set_mode("extruded")
    viewer.set_z_scale(2.0)
    viewer.set_node_values(np.array([0.0, 0.5, 0.5, 1.0]))
    viewer.set_show_faces(False)
    viewer.set_show_faces(True)
    viewer.set_show_edges(False)
    viewer.set_show_edges(True)
    viewer.set_colormap("plasma")
    viewer.set_camera(elev=45.0, azim=10.0)


def test_mesh3d_controls_default_colormaps_listed(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = Mesh3DControls()
    qtbot.addWidget(controls)
    items = [controls._cmap_combo.itemText(i) for i in range(controls._cmap_combo.count())]
    assert items == list(DEFAULT_COLORMAPS)
    assert controls.selected_mode() == "flat"
    assert controls.selected_colormap() in items


def test_mesh3d_panel_refresh_from_provider(qtbot) -> None:  # type: ignore[no-untyped-def]
    state = {"mesh": _square_mesh()}
    panel = Mesh3DPanel(mesh_provider=lambda: state["mesh"])
    qtbot.addWidget(panel)
    panel.refresh_from_provider()
    assert panel.viewer.current_mesh() is state["mesh"]

    state["mesh"] = None  # type: ignore[assignment]
    panel.refresh_from_provider()
    assert panel.viewer.current_mesh() is None


def test_mesh3d_panel_set_mesh_directly(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = Mesh3DPanel()
    qtbot.addWidget(panel)
    mesh = _square_mesh()
    panel.set_mesh(mesh)
    assert panel.viewer.current_mesh() is mesh


def test_mesh3d_panel_controls_drive_viewer(qtbot) -> None:  # type: ignore[no-untyped-def]
    panel = Mesh3DPanel()
    qtbot.addWidget(panel)
    panel.set_mesh(_square_mesh())
    panel.controls.mode_changed.emit("extruded")
    panel.controls.z_scale_changed.emit(3.5)
    panel.controls.colormap_changed.emit("magma")
    panel.controls.show_faces_changed.emit(False)
    panel.controls.show_edges_changed.emit(False)
    panel.controls.elevation_changed.emit(20.0)
    panel.controls.azimuth_changed.emit(80.0)
    assert panel.viewer.current_mesh() is not None
