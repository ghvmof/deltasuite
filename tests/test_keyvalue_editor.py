"""Smoke tests for the KeyValueEditor widget."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.editors.keyvalue_editor import KeyValueEditor  # noqa: E402

_MDU_SAMPLE = """\
[General]
Program          = D-Flow FM
Version          = 1.0

[Numerics]
CFLMax           = 0.7
MaxIter          = 100
"""


def test_editor_loads_and_marks_dirty(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "case.mdu"
    target.write_text(_MDU_SAMPLE, encoding="utf-8")

    editor = KeyValueEditor()
    qtbot.addWidget(editor)
    editor.load(target)

    assert editor.document is not None
    assert editor.is_dirty is False

    editor._editors[("Numerics", "CFLMax")].setText("0.95")
    editor._on_value_edited("0.95")
    assert editor.is_dirty is True


def test_editor_save_persists_changes(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    target = tmp_path / "case.mdu"
    target.write_text(_MDU_SAMPLE, encoding="utf-8")

    editor = KeyValueEditor()
    qtbot.addWidget(editor)
    editor.load(target)
    editor._editors[("Numerics", "CFLMax")].setText("0.95")
    editor._on_value_edited("0.95")
    editor.save()
    assert editor.is_dirty is False
    assert "0.95" in target.read_text(encoding="utf-8")
