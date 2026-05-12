"""Standalone GUI entry point for DeltaSuite.

Used by ``deltasuite-gui`` and as the default action of ``deltasuite``.
"""

from __future__ import annotations

import sys

from loguru import logger


def run() -> int:
    """Bootstrap Qt and show the main window. Returns the application exit code."""
    # Lightweight fast-path for ``--version`` and ``--help`` so packaged
    # smoke tests do not have to load PySide6 (and its 600 MB of
    # transitive DLLs) just to print one line.
    from deltasuite import APP_NAME, __version__

    args = sys.argv[1:]
    if any(a in ("--version", "-V") for a in args):
        print(f"{APP_NAME} {__version__}")
        return 0
    if any(a in ("--help", "-h") for a in args):
        print(
            f"{APP_NAME} {__version__}\n"
            "\nUsage: deltasuite [PROJECT_PATH]\n"
            "\nWith no arguments, opens the welcome screen.\n"
            "Pass a project directory or a ``deltasuite.toml`` to open it on launch."
        )
        return 0

    from deltasuite import APP_DOMAIN, APP_ORG
    from deltasuite.app.main_window import MainWindow
    from deltasuite.app.theme import apply_theme
    from deltasuite.core import configure_logging
    from deltasuite.core.settings import get_settings

    configure_logging()
    logger.info("Starting {} v{}", APP_NAME, __version__)

    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtWidgets import QApplication

    QCoreApplication.setApplicationName(APP_NAME)
    QCoreApplication.setOrganizationName(APP_ORG)
    QCoreApplication.setOrganizationDomain(APP_DOMAIN)
    QCoreApplication.setApplicationVersion(__version__)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts, True)

    qt_app = QApplication.instance() or QApplication(sys.argv)
    assert isinstance(qt_app, QApplication)

    settings = get_settings()
    apply_theme(qt_app, settings.general.theme)

    window = MainWindow()
    window.show()

    return qt_app.exec()
