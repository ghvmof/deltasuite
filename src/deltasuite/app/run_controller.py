"""Qt-aware controller that runs a :class:`~deltasuite.core.run_config.RunConfig`.

Wraps :class:`PySide6.QtCore.QProcess`, exposes a small state machine
(``IDLE`` → ``STARTING`` → ``RUNNING`` → ``FINISHED_OK`` / ``FINISHED_ERROR``
/ ``CANCELLED``) and forwards stdout / stderr line by line.

Used by the main window's Run / Stop actions. Kept as a separate module so
that we can write GUI-less unit tests against the underlying ``QProcess``
behaviour using a fake kernel script.
"""

from __future__ import annotations

import os
from enum import StrEnum, unique
from pathlib import Path

from loguru import logger
from PySide6.QtCore import (
    QElapsedTimer,
    QObject,
    QProcess,
    QProcessEnvironment,
    Signal,
)

from deltasuite.core.run_config import RunConfig


@unique
class RunState(StrEnum):
    """Lifecycle of a single simulation run."""

    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    FINISHED_OK = "finished_ok"
    FINISHED_ERROR = "finished_error"
    CANCELLED = "cancelled"


@unique
class OutputChannel(StrEnum):
    """Source of an emitted output line."""

    STDOUT = "stdout"
    STDERR = "stderr"
    SYSTEM = "system"
    """Internal messages produced by the controller itself."""


class RunController(QObject):
    """Manage the lifecycle of a single simulation subprocess.

    Signals:

    * ``output_line(channel: str, text: str)`` — one line of output.
    * ``state_changed(state: str)`` — see :class:`RunState`.
    * ``finished(exit_code: int)`` — terminal signal, even on crash.
    """

    output_line = Signal(str, str)
    state_changed = Signal(str)
    finished = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._state: RunState = RunState.IDLE
        self._stdout_remainder: bytes = b""
        self._stderr_remainder: bytes = b""
        self._timer: QElapsedTimer = QElapsedTimer()
        self._current_config: RunConfig | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def state(self) -> RunState:
        """Current state of the run."""
        return self._state

    @property
    def is_running(self) -> bool:
        """``True`` while a kernel process is alive."""
        return self._state in (RunState.STARTING, RunState.RUNNING)

    @property
    def elapsed_ms(self) -> int:
        """Milliseconds since the most recent ``start()`` call (0 if never)."""
        if not self._timer.isValid():
            return 0
        return int(self._timer.elapsed())

    @property
    def current_config(self) -> RunConfig | None:
        """The :class:`RunConfig` of the in-flight or last-finished run."""
        return self._current_config

    def start(self, config: RunConfig) -> bool:
        """Spawn the process described by ``config``.

        :returns: ``True`` if the process was started, ``False`` if a
            previous run is still in flight.
        """
        if self.is_running:
            logger.warning("Refusing to start: a run is already in flight")
            return False

        self._current_config = config
        self._stdout_remainder = b""
        self._stderr_remainder = b""

        process = QProcess(self)
        process.setProgram(str(config.program))
        process.setArguments(list(config.args))
        process.setWorkingDirectory(str(config.working_dir))
        process.setProcessEnvironment(self._build_environment(config))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)

        process.readyReadStandardOutput.connect(self._on_ready_stdout)
        process.readyReadStandardError.connect(self._on_ready_stderr)
        process.errorOccurred.connect(self._on_error)
        process.finished.connect(self._on_finished)
        process.started.connect(self._on_started)

        self._process = process
        self._set_state(RunState.STARTING)
        self._emit_system(f"$ {config.program.name} {' '.join(config.args)}")
        self._emit_system(f"  cwd: {config.working_dir}")
        self._timer.start()
        process.start()
        return True

    def stop(self, *, force: bool = False, grace_ms: int = 5000) -> None:
        """Request termination of the running kernel.

        First attempts a graceful shutdown via ``terminate()``; after
        ``grace_ms`` without exit, falls back to ``kill()``. When ``force``
        is ``True`` the process is killed immediately.
        """
        if self._process is None or not self.is_running:
            return

        self._set_state(RunState.CANCELLED)
        if force:
            self._emit_system("Forcing kill...")
            self._process.kill()
            return

        self._emit_system("Sending terminate signal...")
        self._process.terminate()
        if not self._process.waitForFinished(grace_ms):
            self._emit_system("Process did not exit in time, killing...")
            self._process.kill()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_started(self) -> None:
        self._set_state(RunState.RUNNING)

    def _on_ready_stdout(self) -> None:
        if self._process is None:
            return
        chunk = self._process.readAllStandardOutput().data()
        self._stdout_remainder = self._emit_lines(
            self._stdout_remainder + chunk, OutputChannel.STDOUT
        )

    def _on_ready_stderr(self) -> None:
        if self._process is None:
            return
        chunk = self._process.readAllStandardError().data()
        self._stderr_remainder = self._emit_lines(
            self._stderr_remainder + chunk, OutputChannel.STDERR
        )

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self._emit_system(f"QProcess error: {error.name}")
        if self._state in (RunState.STARTING, RunState.RUNNING):
            self._set_state(RunState.FINISHED_ERROR)
            self.finished.emit(-1)

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._flush_remainders()
        elapsed = self._timer.elapsed() if self._timer.isValid() else 0
        self._emit_system(
            f"Process finished. exit_code={exit_code} status={exit_status.name} "
            f"elapsed={elapsed / 1000:.2f}s"
        )

        if self._state is RunState.CANCELLED:
            pass
        elif exit_status == QProcess.ExitStatus.CrashExit or exit_code != 0:
            self._set_state(RunState.FINISHED_ERROR)
        else:
            self._set_state(RunState.FINISHED_OK)

        self.finished.emit(exit_code)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_state(self, new_state: RunState) -> None:
        if self._state == new_state:
            return
        logger.debug("RunController state {} -> {}", self._state.value, new_state.value)
        self._state = new_state
        self.state_changed.emit(new_state.value)

    def _emit_lines(self, buffer: bytes, channel: OutputChannel) -> bytes:
        """Decode ``buffer`` line by line, emitting each complete line.

        Returns the unterminated tail to be prepended to the next chunk.
        """
        if b"\n" not in buffer:
            return buffer
        *lines, tail = buffer.split(b"\n")
        for raw in lines:
            text = raw.rstrip(b"\r").decode("utf-8", errors="replace")
            self.output_line.emit(channel.value, text)
        return tail

    def _flush_remainders(self) -> None:
        """Emit any buffered partial line as a final, complete line."""
        for buffer, channel in (
            (self._stdout_remainder, OutputChannel.STDOUT),
            (self._stderr_remainder, OutputChannel.STDERR),
        ):
            if buffer:
                text = buffer.rstrip(b"\r\n").decode("utf-8", errors="replace")
                if text:
                    self.output_line.emit(channel.value, text)
        self._stdout_remainder = b""
        self._stderr_remainder = b""

    def _emit_system(self, text: str) -> None:
        self.output_line.emit(OutputChannel.SYSTEM.value, text)

    @staticmethod
    def _build_environment(config: RunConfig) -> QProcessEnvironment:
        env = QProcessEnvironment.systemEnvironment()
        for key, value in config.extra_env.items():
            env.insert(key, value)
        env.insert("DELTASUITE_RUN_ROOT", str(config.working_dir))
        # Ensure subprocess writes UTF-8 output where possible.
        env.insert("PYTHONIOENCODING", "utf-8")
        if os.name == "nt":
            env.insert("PYTHONUTF8", "1")
        return env

    @staticmethod
    def is_supported_program(program: Path) -> bool:
        """Return ``True`` when ``program`` exists and is executable."""
        return program.is_file()
