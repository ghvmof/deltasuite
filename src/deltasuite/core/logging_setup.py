"""Centralized logging configuration based on Loguru."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from deltasuite.core.paths import get_app_paths

if TYPE_CHECKING:
    from collections.abc import Callable

    from loguru import Record

_DEFAULT_FORMAT: str = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def configure_logging(
    *,
    level: str = "INFO",
    log_file: Path | None = None,
    rotation: str = "10 MB",
    retention: str = "30 days",
    serialize: bool = False,
) -> Path:
    """Configure the global logger.

    :param level: Minimum log level (TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL).
    :param log_file: Optional path for the log file. Defaults to a file inside
        the user's log directory.
    :param rotation: Loguru rotation specification (size or time).
    :param retention: Loguru retention specification.
    :param serialize: If ``True`` the file sink emits JSON, useful for log
        aggregation.
    :returns: The resolved path to the log file being written.
    """
    logger.remove()

    # PyInstaller's *windowed* (no-console) bootloader replaces both
    # ``sys.stdout`` and ``sys.stderr`` with ``None``. Loguru rejects
    # ``None`` sinks with ``TypeError``, so guard against that case
    # before adding the stream handler.
    stream = sys.stderr if sys.stderr is not None else sys.stdout
    if stream is not None:
        logger.add(
            stream,
            level=level,
            format=_DEFAULT_FORMAT,
            colorize=True,
            backtrace=True,
            diagnose=False,
        )

    if log_file is None:
        log_file = get_app_paths().log_dir / "deltasuite.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_file,
        level=level,
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        enqueue=True,
        serialize=serialize,
        backtrace=True,
        diagnose=False,
    )

    logger.debug("Logging configured. Level={} file={}", level, log_file)
    return log_file


def filter_qt_noise() -> Callable[[Record], bool]:
    """Filter Qt's noisy debug messages out of log files."""

    def _filter(record: Record) -> bool:
        msg = record["message"].lower()
        return not any(s in msg for s in ("qaccessible", "qfont::", "qpainter::"))

    return _filter
