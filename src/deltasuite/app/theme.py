"""Theming for the Qt application.

Phase 0 ships with a Fusion-style dark and light theme. More advanced themes
(material, fluent) can be added as plugins in later phases.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

ThemeName = Literal["light", "dark", "auto"]


def apply_theme(app: QApplication, theme: str = "auto") -> None:
    """Apply ``theme`` to ``app``.

    :param theme: One of ``"light"``, ``"dark"``, or ``"auto"`` (follows the
        OS color scheme on Qt 6.5+).
    """
    if "Fusion" in QStyleFactory.keys():  # noqa: SIM118 - Qt enum-like keys() not iterable
        app.setStyle("Fusion")

    resolved = _resolve_theme(theme)
    if resolved == "dark":
        app.setPalette(_dark_palette())
    else:
        app.setPalette(_light_palette())


def _resolve_theme(theme: str) -> Literal["light", "dark"]:
    if theme in ("light", "dark"):
        return theme  # type: ignore[return-value]
    try:
        from PySide6.QtGui import QGuiApplication

        scheme = QGuiApplication.styleHints().colorScheme()
        return "dark" if scheme == Qt.ColorScheme.Dark else "light"
    except (ImportError, AttributeError):
        return "light"


def _dark_palette() -> QPalette:
    palette = QPalette()
    bg = QColor(45, 45, 48)
    base = QColor(30, 30, 30)
    alt_base = QColor(38, 38, 41)
    text = QColor(220, 220, 220)
    disabled = QColor(127, 127, 127)
    highlight = QColor(0, 122, 204)

    palette.setColor(QPalette.ColorRole.Window, bg)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, alt_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(60, 60, 64))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, bg)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(Qt.GlobalColor.red))
    palette.setColor(QPalette.ColorRole.Link, highlight)
    palette.setColor(QPalette.ColorRole.Highlight, highlight)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    return palette


def _light_palette() -> QPalette:
    return QPalette()
