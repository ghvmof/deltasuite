"""Integration tests for the Qt-aware ``RunController`` with a fake kernel."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from deltasuite.app.run_controller import OutputChannel, RunController, RunState
from deltasuite.core.run_config import RunConfig

pytestmark = pytest.mark.gui


def _fake_kernel_script(tmp_path: Path, *, exit_code: int = 0, lines: int = 3) -> Path:
    """Create a tiny Python script that mimics a long-running kernel."""
    script = tmp_path / "fake_kernel.py"
    script.write_text(
        "import sys\n"
        "import time\n"
        f"for i in range({lines}):\n"
        "    print(f'tick {i}', flush=True)\n"
        "    time.sleep(0.05)\n"
        "print('SIM-ERR sample warning', file=sys.stderr, flush=True)\n"
        f"sys.exit({exit_code})\n",
        encoding="utf-8",
    )
    return script


def _make_config(script: Path) -> RunConfig:
    return RunConfig(
        program=Path(sys.executable),
        args=[str(script)],
        working_dir=script.parent,
        description=f"Fake kernel ({script.name})",
    )


def test_run_controller_emits_lines_and_finishes_ok(qtbot, tmp_path: Path) -> None:
    script = _fake_kernel_script(tmp_path, exit_code=0, lines=3)
    controller = RunController()

    received: list[tuple[str, str]] = []
    states: list[str] = []
    finished_codes: list[int] = []

    controller.output_line.connect(lambda channel, text: received.append((channel, text)))
    controller.state_changed.connect(states.append)
    controller.finished.connect(finished_codes.append)

    with qtbot.waitSignal(controller.finished, timeout=10_000):
        assert controller.start(_make_config(script))

    assert finished_codes == [0]
    assert controller.state is RunState.FINISHED_OK
    assert any(text.startswith("tick 0") for _channel, text in received)
    assert any(channel == OutputChannel.STDERR.value for channel, _text in received)
    assert RunState.RUNNING.value in states
    assert RunState.FINISHED_OK.value in states


def test_run_controller_reports_nonzero_exit_as_error(qtbot, tmp_path: Path) -> None:
    script = _fake_kernel_script(tmp_path, exit_code=42, lines=1)
    controller = RunController()

    finished_codes: list[int] = []
    controller.finished.connect(finished_codes.append)

    with qtbot.waitSignal(controller.finished, timeout=10_000):
        controller.start(_make_config(script))

    assert finished_codes == [42]
    assert controller.state is RunState.FINISHED_ERROR


def test_run_controller_refuses_concurrent_starts(qtbot, tmp_path: Path) -> None:
    script = _fake_kernel_script(tmp_path, exit_code=0, lines=10)
    controller = RunController()

    controller.start(_make_config(script))
    second = controller.start(_make_config(script))
    assert second is False

    with qtbot.waitSignal(controller.finished, timeout=10_000):
        pass


def test_run_controller_stop_cancels_run(qtbot, tmp_path: Path) -> None:
    script = tmp_path / "long_kernel.py"
    script.write_text(
        "import time\n"
        "for i in range(1000):\n"
        "    print(f'tick {i}', flush=True)\n"
        "    time.sleep(0.1)\n",
        encoding="utf-8",
    )
    controller = RunController()
    controller.start(_make_config(script))

    qtbot.wait(200)
    with qtbot.waitSignal(controller.finished, timeout=10_000):
        controller.stop(grace_ms=1000)

    assert controller.state is RunState.CANCELLED
