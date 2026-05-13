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


def test_mesh_panel_grd_dispatch_round_trip(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Save a generated mesh as .grd then re-open through the panel API."""
    pytest.importorskip("meshkernel")
    from deltasuite.core.mesh_adapter import load_mesh_from_path
    from deltasuite.mesh import (
        load_grd_mesh,
        make_rectangular_mesh,
        save_grd_mesh,
    )

    gen = make_rectangular_mesh(origin_x=0.0, origin_y=0.0, n_columns=3, n_rows=2, cell_size=5.0)
    assert gen.ok
    mesh = gen.mesh
    assert mesh is not None
    assert mesh.is_structured

    panel = MeshPanel()
    qtbot.addWidget(panel)
    panel._set_mesh(mesh)

    target_grd = tmp_path / "panel.grd"
    save = save_grd_mesh(panel.current_mesh(), target_grd)  # type: ignore[arg-type]
    assert save.ok, save.error
    assert target_grd.is_file()

    reload = load_grd_mesh(target_grd)
    assert reload.ok, reload.error
    panel._set_mesh(reload.mesh)
    assert panel.current_mesh() is not None
    # Sanity-check that the alternative loader (NetCDF dispatcher) is
    # still wired correctly for .nc files coming back through.
    target_nc = tmp_path / "panel.nc"
    save_mesh_to_ugrid_netcdf(panel.current_mesh(), target_nc)  # type: ignore[arg-type]
    nc_back = load_mesh_from_path(target_nc)
    assert nc_back.ok, nc_back.error
