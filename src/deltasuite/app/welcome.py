"""Interactive welcome screen shown when no project is open.

The widget is a thin presentational layer: it emits high-level signals
that ``MainWindow`` wires to its existing actions, so all behaviour stays
in one place.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from deltasuite import APP_NAME, __version__
from deltasuite.core.recent import RecentEntry, RecentProjects


class WelcomeWidget(QWidget):
    """Welcome page with action tiles and a recent-projects list.

    Signals
    -------
    new_project_requested
    open_project_requested
    open_folder_requested
    browse_examples_requested
    detect_kernels_requested
    open_sample_requested
    recent_selected(Path)
    clear_recents_requested
    """

    new_project_requested = Signal()
    open_project_requested = Signal()
    open_folder_requested = Signal()
    browse_examples_requested = Signal()
    detect_kernels_requested = Signal()
    open_sample_requested = Signal()
    recent_selected = Signal(Path)
    clear_recents_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(48, 36, 48, 36)
        outer.setSpacing(36)

        outer.addLayout(self._build_left_column(), stretch=3)
        outer.addLayout(self._build_right_column(), stretch=2)

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def _build_left_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(20)

        title = QLabel(APP_NAME)
        title_font = title.font()
        title_font.setPointSize(34)
        title_font.setBold(True)
        title.setFont(title_font)
        column.addWidget(title)

        subtitle = QLabel(
            "Open-source desktop suite for Delft3D pre-processing, simulation and post-processing."
        )
        subtitle.setStyleSheet("color: #94a3b8;")
        subtitle.setWordWrap(True)
        column.addWidget(subtitle)

        column.addSpacing(8)
        column.addWidget(self._section_header("Get started"))
        column.addLayout(self._build_tiles_grid())
        column.addStretch(1)

        version = QLabel(f"Version {__version__}  -  Python / Qt 6")
        version.setStyleSheet("color: #64748b; font-size: 9pt;")
        column.addWidget(version)
        return column

    def _build_tiles_grid(self) -> QGridLayout:
        from PySide6.QtCore import SignalInstance

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)

        tiles: list[tuple[str, str, str, SignalInstance]] = [
            (
                "New project",
                "Create a fresh DeltaSuite project in an empty folder.",
                "Ctrl+N",
                self.new_project_requested,
            ),
            (
                "Open project",
                "Open an existing deltasuite.toml file.",
                "Ctrl+O",
                self.open_project_requested,
            ),
            (
                "Open model folder",
                "Detect the model in a directory (.mdf / .mdu / dimr_config.xml).",
                "",
                self.open_folder_requested,
            ),
            (
                "Browse examples",
                "Recursively scan a folder for every Delft3D model inside.",
                "Ctrl+B",
                self.browse_examples_requested,
            ),
            (
                "Open sample",
                "Try DeltaSuite immediately with a tiny built-in example.",
                "",
                self.open_sample_requested,
            ),
            (
                "Detect kernels",
                "Scan the system for compiled Delft3D simulation engines.",
                "",
                self.detect_kernels_requested,
            ),
        ]
        for index, (title, description, shortcut, signal) in enumerate(tiles):
            tile = self._make_tile(title, description, shortcut, signal)
            grid.addWidget(tile, index // 2, index % 2)
        return grid

    @staticmethod
    def _make_tile(title: str, description: str, shortcut: str, signal: object) -> QFrame:
        tile = QFrame()
        tile.setObjectName("WelcomeTile")
        tile.setFrameShape(QFrame.Shape.StyledPanel)
        tile.setStyleSheet(
            """
            QFrame#WelcomeTile {
                border: 1px solid palette(mid);
                border-radius: 8px;
                background: palette(alternate-base);
            }
            QFrame#WelcomeTile:hover {
                border-color: #2563eb;
            }
            """
        )
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header = QLabel(title)
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(header_font.pointSize() + 1)
        header.setFont(header_font)
        header_row.addWidget(header)
        header_row.addStretch(1)
        if shortcut:
            shortcut_label = QLabel(shortcut)
            shortcut_label.setStyleSheet(
                "color: #64748b; background: palette(window); "
                "border: 1px solid palette(mid); border-radius: 4px; "
                "padding: 1px 6px;"
            )
            header_row.addWidget(shortcut_label)
        layout.addLayout(header_row)

        body = QLabel(description)
        body.setWordWrap(True)
        body.setStyleSheet("color: #94a3b8;")
        layout.addWidget(body)

        button = QPushButton("Open")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(signal)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
        return tile

    def _build_right_column(self) -> QVBoxLayout:
        column = QVBoxLayout()
        column.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.addWidget(self._section_header("Recent projects"))
        header_row.addStretch(1)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFlat(True)
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self.clear_recents_requested)
        header_row.addWidget(self._clear_btn)
        column.addLayout(header_row)

        self._recent_list = QListWidget()
        self._recent_list.setAlternatingRowColors(True)
        self._recent_list.itemActivated.connect(self._on_recent_activated)
        column.addWidget(self._recent_list, stretch=1)

        self._recent_empty = QLabel("(no recent projects yet)")
        self._recent_empty.setStyleSheet("color: #94a3b8; font-style: italic;")
        column.addWidget(self._recent_empty)
        return column

    @staticmethod
    def _section_header(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        font.setCapitalization(QFont.Capitalization.AllUppercase)
        font.setPointSize(font.pointSize() - 1)
        label.setFont(font)
        label.setStyleSheet("color: #94a3b8; letter-spacing: 1px;")
        return label

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_recent(self, recent: RecentProjects) -> None:
        """Populate the recent-projects list."""
        self._recent_list.clear()
        alive = recent.alive()
        for entry in alive:
            self._add_recent_item(entry)
        has_any = bool(alive)
        self._recent_list.setVisible(has_any)
        self._recent_empty.setVisible(not has_any)
        self._clear_btn.setEnabled(bool(recent.entries))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _add_recent_item(self, entry: RecentEntry) -> None:
        item = QListWidgetItem()
        when = self._humanise_when(entry.opened_at)
        item.setText(f"{entry.name}\n{entry.path}  -  {when}")
        item.setToolTip(str(entry.path))
        item.setData(Qt.ItemDataRole.UserRole, entry.path)
        self._recent_list.addItem(item)

    def _on_recent_activated(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, Path):
            self.recent_selected.emit(data)

    @staticmethod
    def _humanise_when(when: datetime) -> str:
        try:
            local = when.astimezone()
            return local.strftime("%Y-%m-%d %H:%M")
        except (ValueError, OSError):  # pragma: no cover
            return when.isoformat()
