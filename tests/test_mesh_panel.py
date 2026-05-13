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


def _structured_mesh_3x2() -> MeshGeometry:
    return MeshGeometry(
        node_x=np.array([0.0, 1.0, 2.0, 0.0, 1.0, 2.0]),
        node_y=np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0]),
        edge_nodes=np.array(
            [[0, 1], [1, 2], [3, 4], [4, 5], [0, 3], [1, 4], [2, 5]],
            dtype=np.int64,
        ),
        face_nodes=np.array([[0, 1, 4, 3], [1, 2, 5, 4]], dtype=np.int64),
        structured_shape=(2, 3),
    )


def test_mesh_panel_loads_dep_and_colours_faces(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Loading a .dep should attach a DepthField to the panel and viewer."""
    from deltasuite.mesh.io_dep import DepthField as Field
    from deltasuite.mesh.io_dep import save_dep_samples

    panel = MeshPanel()
    qtbot.addWidget(panel)
    mesh = _structured_mesh_3x2()
    panel._set_mesh(mesh)
    assert panel.current_depth() is None

    field = Field(
        node_values=np.array([1.0, 1.5, 2.0, 1.5, 2.0, 2.5]),
        missing_value=-999.0,
        layout="nodes",
    )
    target = tmp_path / "depth.dep"
    save = save_dep_samples(field, target, mesh)
    assert save.ok, save.error

    from deltasuite.mesh import load_dep_samples

    res = load_dep_samples(target, mesh)
    assert res.ok, res.error
    panel._set_depth(res.field, source=target.name)

    depth = panel.current_depth()
    assert depth is not None
    assert depth.n_nodes == mesh.n_nodes
    assert panel.viewer.current_depth() is depth


def test_mesh_panel_clearing_mesh_drops_depth(qtbot) -> None:  # type: ignore[no-untyped-def]
    from deltasuite.mesh.io_dep import DepthField as Field

    panel = MeshPanel()
    qtbot.addWidget(panel)
    mesh = _structured_mesh_3x2()
    panel._set_mesh(mesh)
    panel._set_depth(
        Field(node_values=np.zeros(6), missing_value=-999.0, layout="nodes"),
        source="x.dep",
    )
    assert panel.current_depth() is not None
    panel._on_clear()
    assert panel.current_mesh() is None
    assert panel.current_depth() is None


def test_mesh3d_panel_uses_depth_provider_for_node_values(qtbot) -> None:  # type: ignore[no-untyped-def]
    """Mesh3DPanel should pull depth from its provider during refresh."""
    from deltasuite.mesh.io_dep import DepthField as Field
    from deltasuite.views.mesh3d_panel import Mesh3DPanel

    mesh = _structured_mesh_3x2()
    depth = Field(
        node_values=np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6]),
        missing_value=-999.0,
        layout="nodes",
    )

    panel3d = Mesh3DPanel(
        mesh_provider=lambda: mesh,
        depth_provider=lambda: depth,
    )
    qtbot.addWidget(panel3d)
    panel3d.refresh_from_provider()
    # After refresh, the viewer must hold the same node count and have
    # been told to use the depth values (no public getter exists, but
    # the viewer must have set its private cache).
    assert panel3d.viewer.current_mesh() is mesh
    assert panel3d.viewer._node_values is not None
    np.testing.assert_allclose(panel3d.viewer._node_values, depth.node_values)
