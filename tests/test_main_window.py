"""Smoke tests for the Qt main window using ``pytest-qt``."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from deltasuite.app.main_window import MainWindow

pytestmark = pytest.mark.gui


def test_main_window_constructs(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "DeltaSuite"
    assert window.menuBar() is not None
    assert window.statusBar() is not None


def test_main_window_has_required_menus(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    titles = [
        m.title().replace("&", "")
        for m in window.menuBar().findChildren(type(window.menuBar().addMenu("x")))
    ]
    for expected in ("File", "Edit", "Run", "View", "Help"):
        assert expected in titles, f"missing menu: {expected}"


def test_main_window_actions_initial_state(qtbot) -> None:  # type: ignore[no-untyped-def]
    window = MainWindow()
    qtbot.addWidget(window)
    assert not window._act_save.isEnabled()
    assert not window._act_close.isEnabled()
    assert not window._act_run.isEnabled()
    assert not window._act_stop.isEnabled()
