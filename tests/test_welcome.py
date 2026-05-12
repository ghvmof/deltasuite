"""Smoke tests for the welcome widget."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.app.welcome import WelcomeWidget
from deltasuite.core.recent import RecentEntry, RecentProjects


def test_welcome_renders_empty_recent(qtbot) -> None:  # type: ignore[no-untyped-def]
    widget = WelcomeWidget()
    qtbot.addWidget(widget)
    widget.set_recent(RecentProjects())
    assert widget._recent_list.count() == 0
    # In the empty state the placeholder should not be hidden by code.
    assert not widget._recent_empty.isHidden()


def test_welcome_renders_recent_entries(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    project_a = tmp_path / "a"
    project_a.mkdir()
    project_b = tmp_path / "b"
    project_b.mkdir()
    recent = RecentProjects()
    recent.entries.append(RecentEntry(path=project_a, name="A"))
    recent.entries.append(RecentEntry(path=project_b, name="B"))

    widget = WelcomeWidget()
    qtbot.addWidget(widget)
    widget.set_recent(recent)
    assert widget._recent_list.count() == 2
    assert widget._recent_empty.isHidden()


def test_welcome_signals_emit_on_tile_click(qtbot) -> None:  # type: ignore[no-untyped-def]
    widget = WelcomeWidget()
    qtbot.addWidget(widget)

    captured: list[str] = []
    widget.new_project_requested.connect(lambda: captured.append("new"))
    widget.open_sample_requested.connect(lambda: captured.append("sample"))

    # Find the buttons inside the tiles (each tile has exactly one QPushButton).
    from PySide6.QtWidgets import QPushButton

    buttons = widget.findChildren(QPushButton)
    # First six tile buttons in order: new, open, open_folder, browse, sample, detect.
    assert len(buttons) >= 6
    buttons[0].click()
    buttons[4].click()
    assert captured == ["new", "sample"]
