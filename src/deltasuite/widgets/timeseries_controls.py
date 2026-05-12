"""Toolbar widget that drives the :class:`TimeSeriesViewerWidget`."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from deltasuite.core.timeseries import TimeSeriesDataset


class TimeSeriesControls(QWidget):
    """Right-hand panel controlling the time-series viewer.

    Signals
    -------
    file_selected(int)
    variable_changed(str)
    stations_changed(list[str])
    select_all_requested()
    select_none_requested()
    export_csv_requested()
    """

    file_selected = Signal(int)
    variable_changed = Signal(str)
    stations_changed = Signal(list)
    select_all_requested = Signal()
    select_none_requested = Signal()
    export_csv_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.addWidget(self._make_bold_label("Time-series viewer"))
        outer.addLayout(self._build_combo_form())
        outer.addWidget(self._build_stations_box(), stretch=1)
        outer.addLayout(self._build_buttons_row())

        self._info_label = QLabel("No dataset loaded.")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #888;")
        outer.addWidget(self._info_label)

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    @staticmethod
    def _make_bold_label(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    def _build_combo_form(self) -> QFormLayout:
        self._file_combo = QComboBox()
        self._file_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._file_combo.currentIndexChanged.connect(self._on_file_changed)

        self._variable_combo = QComboBox()
        self._variable_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._variable_combo.currentIndexChanged.connect(self._on_variable_changed)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("File:", self._file_combo)
        form.addRow("Variable:", self._variable_combo)
        return form

    def _build_stations_box(self) -> QFrame:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._make_bold_label("Stations"))

        self._stations_list = QListWidget()
        self._stations_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._stations_list.itemSelectionChanged.connect(self._emit_station_selection)
        layout.addWidget(self._stations_list, stretch=1)

        bulk_row = QHBoxLayout()
        all_btn = QPushButton("All")
        all_btn.clicked.connect(self.select_all_requested)
        none_btn = QPushButton("None")
        none_btn.clicked.connect(self.select_none_requested)
        bulk_row.addWidget(all_btn)
        bulk_row.addWidget(none_btn)
        bulk_row.addStretch(1)
        layout.addLayout(bulk_row)
        return box

    def _build_buttons_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_csv_requested)
        row.addWidget(self._export_btn)
        row.addStretch(1)
        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_files(self, files: list[Path]) -> None:
        """Populate the file selector. Pass ``[]`` to clear it."""
        self._file_combo.blockSignals(True)
        self._file_combo.clear()
        for path in files:
            self._file_combo.addItem(path.name, userData=path)
        self._file_combo.setCurrentIndex(0 if files else -1)
        self._file_combo.blockSignals(False)
        if files:
            self.file_selected.emit(0)

    def set_current_file_index(self, index: int) -> None:
        """Programmatically select a file in the combo."""
        self._file_combo.setCurrentIndex(index)

    def set_dataset(self, dataset: TimeSeriesDataset | None) -> None:
        """Refresh variable and station controls from ``dataset``."""
        self._variable_combo.blockSignals(True)
        self._variable_combo.clear()
        self._stations_list.blockSignals(True)
        self._stations_list.clear()

        if dataset is None:
            self._variable_combo.blockSignals(False)
            self._stations_list.blockSignals(False)
            self._info_label.setText("No dataset loaded.")
            self._export_btn.setEnabled(False)
            return

        for var in dataset.variables.values():
            self._variable_combo.addItem(var.display, userData=var.name)
        for station in dataset.stations:
            QListWidgetItem(station, self._stations_list)
        self._variable_combo.blockSignals(False)
        self._stations_list.blockSignals(False)

        self._info_label.setText(
            f"<b>{dataset.path.name}</b><br>"
            f"Variables: {self._variable_combo.count()} &nbsp;&nbsp;"
            f"Stations: {dataset.n_stations} &nbsp;&nbsp;"
            f"Time steps: {len(dataset.time_steps())}"
        )

        if self._variable_combo.count() > 0:
            self._variable_combo.setCurrentIndex(0)
        if self._stations_list.count() > 0:
            self._stations_list.item(0).setSelected(True)

        self._export_btn.setEnabled(True)

    def current_variable(self) -> str | None:
        """Currently selected variable name."""
        if self._variable_combo.currentIndex() < 0:
            return None
        return str(self._variable_combo.currentData())

    def current_stations(self) -> list[str]:
        """List of station names currently selected in the list widget."""
        return [item.text() for item in self._stations_list.selectedItems()]

    def select_all_stations(self) -> None:
        """Select every station in the list."""
        self._stations_list.blockSignals(True)
        for i in range(self._stations_list.count()):
            self._stations_list.item(i).setSelected(True)
        self._stations_list.blockSignals(False)
        self._emit_station_selection()

    def clear_station_selection(self) -> None:
        """Deselect every station in the list."""
        self._stations_list.blockSignals(True)
        self._stations_list.clearSelection()
        self._stations_list.blockSignals(False)
        self._emit_station_selection()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_file_changed(self, index: int) -> None:
        if index >= 0:
            self.file_selected.emit(index)

    def _on_variable_changed(self, _index: int) -> None:
        var = self.current_variable()
        if var is not None:
            self.variable_changed.emit(var)

    def _emit_station_selection(self) -> None:
        self.stations_changed.emit(self.current_stations())
