"""End-to-end demo: open f34, build a RunConfig, launch d_hydro, capture log.

Run with::

    python scripts/demo_run_f34.py

It is also useful as a smoke test on a freshly compiled Delft3D installation.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop

from deltasuite.app.run_controller import OutputChannel, RunController
from deltasuite.core import (
    build_run_config,
    configure_logging,
    detect_kernels,
    detect_project,
)
from deltasuite.core.run_config import RunConfigError

DEFAULT_CASE = (
    Path.home()
    / "Downloads"
    / "Delft3D-main"
    / "Delft3D-main"
    / "examples"
    / "delft3d4"
    / "01_standard"
)


def main(case_dir: Path = DEFAULT_CASE) -> int:
    configure_logging(level="INFO")
    print("=== DeltaSuite end-to-end demo ===")
    print(f"Case directory : {case_dir}")
    if not case_dir.is_dir():
        print("ERROR: case directory does not exist", file=sys.stderr)
        return 2

    detected = detect_project(case_dir)
    print(f"Detected       : {detected.description}")
    if not detected.is_recognised:
        print("ERROR: no Delft3D model found in directory", file=sys.stderr)
        return 3

    kernels = detect_kernels()
    print(f"Kernel sets    : {len(kernels)}")
    try:
        config = build_run_config(detected, kernels)
    except RunConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 4

    print(f"Program        : {config.program}")
    print(f"Args           : {config.args}")
    print(f"Working dir    : {config.working_dir}")
    print()
    print("--- Live kernel output ---")

    QCoreApplication.instance() or QCoreApplication(sys.argv)
    controller = RunController()
    loop = QEventLoop()

    def _on_output(channel: str, text: str) -> None:
        prefix = {
            OutputChannel.STDOUT.value: "OUT",
            OutputChannel.STDERR.value: "ERR",
            OutputChannel.SYSTEM.value: "SYS",
        }.get(channel, channel)
        print(f"[{prefix}] {text}")

    final_code: dict[str, int] = {"value": -1}

    def _on_finished(code: int) -> None:
        final_code["value"] = code
        loop.quit()

    controller.output_line.connect(_on_output)
    controller.finished.connect(_on_finished)

    if not controller.start(config):
        print("ERROR: controller refused to start", file=sys.stderr)
        return 5

    loop.exec()
    print()
    print(f"=== Finished. Exit code: {final_code['value']} ===")
    return final_code["value"]


if __name__ == "__main__":
    sys.exit(main())
