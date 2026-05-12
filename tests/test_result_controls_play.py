"""Tests for the playback animation in ResultControls."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest_qt = pytest.importorskip("pytestqt.qtbot")

from deltasuite.widgets.result_controls import ResultControls


class _FakeDataset:
    """Minimal stand-in for :class:`ResultDataset` in widget tests."""

    def __init__(self, n_time: int, n_vars: int = 2) -> None:
        self.n_time = n_time
        self.path = type("P", (), {"name": "fake.nc"})()
        self.grid_kind = type("K", (), {"value": "curvilinear"})()
        self._vars = {
            f"var_{i}": type(
                "V",
                (),
                {
                    "display": f"Variable {i}",
                    "name": f"var_{i}",
                    "units": "m",
                    "long_name": f"Variable {i}",
                    "n_time": n_time,
                },
            )()
            for i in range(n_vars)
        }
        self.variables = self._vars

    def time_steps(self) -> list:
        return []


def test_play_button_disabled_for_static_dataset(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = ResultControls()
    qtbot.addWidget(controls)
    controls.set_dataset(_FakeDataset(n_time=1))
    assert controls._play_btn.isEnabled() is False


def test_play_advances_time_index(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = ResultControls()
    qtbot.addWidget(controls)
    controls.set_dataset(_FakeDataset(n_time=10))
    assert controls._play_btn.isEnabled() is True
    controls._play_btn.setChecked(True)
    controls._tick_play()
    controls._tick_play()
    assert controls.current_time_index() == 2


def test_play_loops(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = ResultControls()
    qtbot.addWidget(controls)
    controls.set_dataset(_FakeDataset(n_time=3))
    controls._play_btn.setChecked(True)
    for _ in range(5):
        controls._tick_play()
    # After looping it should still be playing and within range.
    assert 0 <= controls.current_time_index() <= 2
    assert controls._play_btn.isChecked()


def test_play_stops_at_end_when_loop_disabled(qtbot) -> None:  # type: ignore[no-untyped-def]
    controls = ResultControls()
    qtbot.addWidget(controls)
    controls.set_dataset(_FakeDataset(n_time=3))
    controls._loop_check.setChecked(False)
    controls._play_btn.setChecked(True)
    for _ in range(5):
        controls._tick_play()
    assert controls._play_btn.isChecked() is False
