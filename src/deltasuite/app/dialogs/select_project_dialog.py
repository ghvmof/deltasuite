"""Dialog presenting a list of detected Delft3D projects in a folder.

Shown when the user opens a folder that contains multiple models, or when
they invoke *File → Open Examples Browser…*.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from deltasuite.core.project_detector import DetectedProject


_TYPE_COLOURS: dict[str, str] = {
    "delft3d4": "#2563eb",
    "dflowfm": "#7c3aed",
    "dimr": "#16a34a",
    "unknown": "#888888",
}


class SelectProjectDialog(QDialog):
    """List ``projects`` and let the user double-click or accept one to open."""

    def __init__(
        self,
        projects: list[DetectedProject],
        *,
        root: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._projects = projects
        self._root = root
        self._selected: DetectedProject | None = None

        self.setWindowTitle("Select a Delft3D model to open")
        self.setMinimumSize(900, 480)
        self.setModal(True)

        layout = QVBoxLayout(self)

        intro = QLabel(
            f"Found <b>{len(projects)}</b> Delft3D model(s) under "
            f"<code>{root}</code>.<br>"
            "Double-click a row or select one and press <b>Open</b>."
        )
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["#", "Type", "Location", "Entry point"])
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)

        header = self._tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        for index, project in enumerate(projects, start=1):
            try:
                rel_root = project.root.relative_to(root)
            except ValueError:
                rel_root = project.root
            entry_point = project.main_input.name if project.main_input is not None else "—"
            item = QTreeWidgetItem(
                [
                    str(index),
                    project.project_type.value,
                    str(rel_root),
                    entry_point,
                ]
            )
            font = QFont()
            font.setBold(True)
            item.setFont(1, font)
            colour = _TYPE_COLOURS.get(project.project_type.value, "#888888")
            item.setForeground(1, QColor(colour))
            item.setData(0, Qt.ItemDataRole.UserRole, project)
            self._tree.addTopLevelItem(item)

        if projects:
            first_item = self._tree.topLevelItem(0)
            if first_item is not None:
                self._tree.setCurrentItem(first_item)
        self._tree.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._tree, 1)

        buttons = QDialogButtonBox()
        self._open_button = QPushButton("&Open")
        self._open_button.setDefault(True)
        buttons.addButton(self._open_button, QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.rejected.connect(self.reject)
        self._open_button.clicked.connect(self._accept_selection)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def selected_project(self) -> DetectedProject | None:
        """Return the project chosen by the user, or ``None`` if cancelled."""
        return self._selected

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _accept_selection(self) -> None:
        item = self._tree.currentItem()
        if item is None:
            return
        self._selected = item.data(0, Qt.ItemDataRole.UserRole)
        self.accept()

    def _on_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        self._selected = item.data(0, Qt.ItemDataRole.UserRole)
        self.accept()
