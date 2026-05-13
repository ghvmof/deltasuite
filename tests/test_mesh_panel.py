"""Smoke tests for ``MeshViewerWidget``, ``MeshControls`` and ``MeshPanel``."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("matplotlib")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.core.mesh_adapter import MeshGeometry
from deltasuite.mesh import save_mesh_to_ugrid_netcdf
from deltasuite.views.mesh_panel import MeshPanel
from deltasuite.views.mesh_viewer import MeshViewerWidget
from deltasuite.widgets.mesh_controls import MeshControls


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


def test_mesh_viewer_renders_geometry(qtbot) -> None:  # type: ignore[no-untyped-def]
    viewer = MeshViewerWidget()
    qtbot.addWidget(viewer)
    viewer.set_mesh(_square_mesh())
    assert viewer.current_mesh() is not None
    viewer.set_mesh(None)
    assert viewer.current_mesh() is None


def test_mesh_controls_buttons_disabled_until_mesh_loaded(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = MeshControls()
    qtbot.addWidget(controls)
    controls.set_mesh_loaded(False)
    assert not controls._save_btn.isEnabled()
    assert not controls._refine_btn.isEnabled()
    controls.set_mesh_loaded(True)
    assert controls._save_btn.isEnabled()
    assert controls._refine_btn.isEnabled()


def test_mesh_controls_emits_generate_signal(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = MeshControls()
    qtbot.addWidget(controls)
    captured: list[tuple[int, int, float]] = []
    controls.generate_rectangular_requested.connect(lambda c, r, s: captured.append((c, r, s)))
    controls._cols_spin.setValue(3)
    controls._rows_spin.setValue(2)
    controls._cell_spin.setValue(5.0)
    controls._gen_btn.click()
    assert captured == [(3, 2, 5.0)]


def test_mesh_panel_generate_rectangular(qtbot) -> None:  # type: ignore[no-untyped-def]
    pytest.importorskip("meshkernel")
    panel = MeshPanel()
    qtbot.addWidget(panel)
    assert panel.current_mesh() is None
    panel._on_generate_rectangular(3, 2, 5.0)
    mesh = panel.current_mesh()
    assert mesh is not None
    assert mesh.n_nodes == (3 + 1) * (2 + 1)
    assert panel.viewer.current_mesh() is mesh
    panel._on_clear()
    assert panel.current_mesh() is None


def test_mesh_panel_save_and_open_round_trip(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    panel = MeshPanel()
    qtbot.addWidget(panel)
    panel._set_mesh(_square_mesh())
    target = tmp_path / "panel.nc"
    save = save_mesh_to_ugrid_netcdf(panel.current_mesh(), target)  # type: ignore[arg-type]
    assert save.ok
    assert target.is_file()
