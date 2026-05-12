"""Toolbar widget that drives the :class:`MapViewerWidget`.

Lets the user:

* pick the result file (when several are detected),
* pick a variable from that dataset,
* scrub time steps with a slider,
* change the colormap,
* enable / disable a fixed colour range.

The widget is purely presentational; it emits signals but performs no I/O,
so plumbing into different controllers (main window, standalone viewer
window, headless tests) is straightforward.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from deltasuite.core.results import ResultDataset

_BUILTIN_COLORMAPS: tuple[str, ...] = (
    "viridis",
    "plasma",
    "inferno",
    "magma",
    "cividis",
    "turbo",
    "RdBu_r",
    "coolwarm",
    "Spectral_r",
    "terrain",
    "ocean",
    "Blues",
    "Greys",
)


class ResultControls(QWidget):
    """Right-side panel that controls a result viewer.

    Signals
    -------
    file_selected(int)
        Emitted with the *index* of the chosen file in the list previously
        passed to :meth:`set_files`.
    variable_changed(str)
    time_changed(int)
    colormap_changed(str)
    range_changed(float | None, float | None)
    """

    file_selected = Signal(int)
    variable_changed = Signal(str)
    time_changed = Signal(int)
    colormap_changed = Signal(str)
    range_changed = Signal(object, object)
    vector_overlay_toggled = Signal(bool)
    """Emitted with the new state when the user toggles the U/V overlay."""
    vector_stride_changed = Signal(int)
    """Emitted with the new sampling stride for the vector overlay."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cached_times: list[datetime] = []
        self._play_timer = QTimer(self)
        self._play_timer.setInterval(400)
        self._play_timer.timeout.connect(self._tick_play)
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setSpacing(8)
        outer.addWidget(self._make_bold_label("Result viewer"))
        outer.addLayout(self._build_combo_form())
        outer.addWidget(self._build_time_box())
        outer.addWidget(self._build_range_box())
        outer.addWidget(self._build_vector_box())

        self._info_label = QLabel("No dataset loaded.")
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #888;")
        outer.addWidget(self._info_label)
        outer.addStretch(1)

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

        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(_BUILTIN_COLORMAPS)
        self._cmap_combo.currentTextChanged.connect(self.colormap_changed)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("File:", self._file_combo)
        form.addRow("Variable:", self._variable_combo)
        form.addRow("Colormap:", self._cmap_combo)
        return form

    def _build_time_box(self) -> QFrame:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._make_bold_label("Time step"))

        self._time_label = QLabel("-")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._time_label)

        row = QHBoxLayout()
        self._time_slider = QSlider(Qt.Orientation.Horizontal)
        self._time_slider.setMinimum(0)
        self._time_slider.setMaximum(0)
        self._time_slider.setSingleStep(1)
        self._time_slider.setPageStep(10)
        self._time_slider.valueChanged.connect(self._on_time_slider_changed)
        row.addWidget(self._time_slider, 1)

        self._time_index_label = QLabel("0 / 0")
        row.addWidget(self._time_index_label)
        layout.addLayout(row)

        playback = QHBoxLayout()
        self._play_btn = QPushButton("Play")
        self._play_btn.setEnabled(False)
        self._play_btn.setCheckable(True)
        self._play_btn.toggled.connect(self._on_play_toggled)
        playback.addWidget(self._play_btn)

        playback.addWidget(QLabel("Speed:"))
        self._speed_combo = QComboBox()
        for label, ms in (
            ("0.5x", 800),
            ("1x", 400),
            ("2x", 200),
            ("4x", 100),
            ("8x", 50),
        ):
            self._speed_combo.addItem(label, userData=ms)
        self._speed_combo.setCurrentIndex(1)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        playback.addWidget(self._speed_combo)

        self._loop_check = QCheckBox("Loop")
        self._loop_check.setChecked(True)
        playback.addWidget(self._loop_check)
        playback.addStretch(1)
        layout.addLayout(playback)
        return box

    def _build_vector_box(self) -> QFrame:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._make_bold_label("Vector overlay"))

        self._uv_check = QCheckBox("Show U/V arrows on map")
        self._uv_check.setChecked(False)
        self._uv_check.setEnabled(False)
        self._uv_check.toggled.connect(self.vector_overlay_toggled)
        layout.addWidget(self._uv_check)

        row = QHBoxLayout()
        row.addWidget(QLabel("Density (every Nth cell):"))
        self._uv_stride_spin = QSpinBox()
        self._uv_stride_spin.setRange(1, 32)
        self._uv_stride_spin.setValue(4)
        self._uv_stride_spin.setEnabled(False)
        self._uv_stride_spin.valueChanged.connect(self.vector_stride_changed)
        row.addWidget(self._uv_stride_spin)
        row.addStretch(1)
        layout.addLayout(row)

        # Wire enable/disable of the stride spin to the checkbox.
        self._uv_check.toggled.connect(self._uv_stride_spin.setEnabled)
        return box

    def _build_range_box(self) -> QFrame:
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._make_bold_label("Colour scale"))

        self._auto_range = QCheckBox("Auto (1-99 percentile)")
        self._auto_range.setChecked(True)
        self._auto_range.toggled.connect(self._on_auto_toggled)
        layout.addWidget(self._auto_range)

        form = QFormLayout()
        self._vmin_spin = QDoubleSpinBox()
        self._vmin_spin.setRange(-1e9, 1e9)
        self._vmin_spin.setDecimals(4)
        self._vmin_spin.setEnabled(False)
        self._vmin_spin.valueChanged.connect(self._emit_range)
        self._vmax_spin = QDoubleSpinBox()
        self._vmax_spin.setRange(-1e9, 1e9)
        self._vmax_spin.setDecimals(4)
        self._vmax_spin.setEnabled(False)
        self._vmax_spin.valueChanged.connect(self._emit_range)
        form.addRow("Min:", self._vmin_spin)
        form.addRow("Max:", self._vmax_spin)
        layout.addLayout(form)
        return box

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

    def set_dataset(self, dataset: ResultDataset | None) -> None:
        """Refresh variable / time controls from ``dataset``."""
        self._variable_combo.blockSignals(True)
        self._variable_combo.clear()
        if dataset is None:
            self._variable_combo.blockSignals(False)
            self._time_slider.setMaximum(0)
            self._time_label.setText("-")
            self._time_index_label.setText("0 / 0")
            self._info_label.setText("No dataset loaded.")
            self._play_btn.setChecked(False)
            self._play_btn.setEnabled(False)
            return

        for var in dataset.variables.values():
            self._variable_combo.addItem(var.display, userData=var.name)
        self._variable_combo.blockSignals(False)

        n_time = max(0, dataset.n_time - 1)
        self._time_slider.blockSignals(True)
        self._time_slider.setMinimum(0)
        self._time_slider.setMaximum(n_time)
        self._time_slider.setValue(0)
        self._time_slider.blockSignals(False)
        self._cached_times = dataset.time_steps()
        self._update_time_labels(0)

        self._info_label.setText(
            f"<b>{dataset.path.name}</b><br>"
            f"Grid: <code>{dataset.grid_kind.value}</code> &nbsp;&nbsp;"
            f"Variables: {self._variable_combo.count()} &nbsp;&nbsp;"
            f"Time steps: {dataset.n_time}"
        )
        if self._variable_combo.count() > 0:
            self._variable_combo.setCurrentIndex(0)
        self._play_btn.setEnabled(dataset.n_time > 1)

    def set_vector_overlay_available(self, available: bool) -> None:
        """Enable / disable the U/V overlay row.

        Disables the checkbox itself when no U/V variables exist in the
        current dataset; the user then sees the row but can't toggle it on.
        """
        self._uv_check.setEnabled(available)
        if not available:
            # Force-off so we don't render against a stale UV field after
            # switching to a result file that doesn't contain velocities.
            self._uv_check.setChecked(False)
        self._uv_stride_spin.setEnabled(available and self._uv_check.isChecked())

    def vector_overlay_enabled(self) -> bool:
        """Whether the vector overlay checkbox is currently checked."""
        return bool(self._uv_check.isChecked())

    def vector_overlay_stride(self) -> int:
        """Current stride value for U/V down-sampling."""
        return int(self._uv_stride_spin.value())

    def set_value_extents(self, vmin: float, vmax: float) -> None:
        """Pre-fill the manual min/max with the autoscale values."""
        self._vmin_spin.blockSignals(True)
        self._vmax_spin.blockSignals(True)
        self._vmin_spin.setValue(vmin)
        self._vmax_spin.setValue(vmax)
        self._vmin_spin.blockSignals(False)
        self._vmax_spin.blockSignals(False)

    def current_variable(self) -> str | None:
        """Currently selected variable, or ``None``."""
        if self._variable_combo.currentIndex() < 0:
            return None
        return str(self._variable_combo.currentData())

    def current_time_index(self) -> int:
        """Currently selected time index."""
        return int(self._time_slider.value())

    def current_colormap(self) -> str:
        """Currently selected colormap name."""
        return self._cmap_combo.currentText()

    def current_file_path(self) -> Path | None:
        """Currently selected file path, or ``None`` if none is selected."""
        if self._file_combo.currentIndex() < 0:
            return None
        data = self._file_combo.currentData()
        return data if isinstance(data, Path) else None

    def set_current_file_index(self, index: int) -> None:
        """Programmatically select a file in the combo (emits ``file_selected``)."""
        self._file_combo.setCurrentIndex(index)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_file_changed(self, index: int) -> None:
        if index >= 0:
            self.file_selected.emit(index)

    def _on_variable_changed(self, _index: int) -> None:
        var = self.current_variable()
        if var is not None:
            self.variable_changed.emit(var)

    def _on_time_slider_changed(self, value: int) -> None:
        self._update_time_labels(value)
        self.time_changed.emit(value)

    def _update_time_labels(self, value: int) -> None:
        n = self._time_slider.maximum() + 1
        self._time_index_label.setText(f"{value + 1} / {n}")
        if 0 <= value < len(self._cached_times):
            ts = self._cached_times[value]
            self._time_label.setText(ts.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            self._time_label.setText("-")

    def _on_play_toggled(self, playing: bool) -> None:
        self._play_btn.setText("Pause" if playing else "Play")
        if playing:
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _on_speed_changed(self, _index: int) -> None:
        ms = self._speed_combo.currentData()
        if isinstance(ms, int):
            self._play_timer.setInterval(ms)

    def _tick_play(self) -> None:
        if self._time_slider.maximum() <= 0:
            self._play_btn.setChecked(False)
            return
        next_value = self._time_slider.value() + 1
        if next_value > self._time_slider.maximum():
            if self._loop_check.isChecked():
                next_value = 0
            else:
                self._play_btn.setChecked(False)
                return
        self._time_slider.setValue(next_value)

    def _on_auto_toggled(self, checked: bool) -> None:
        self._vmin_spin.setEnabled(not checked)
        self._vmax_spin.setEnabled(not checked)
        self._emit_range()

    def _emit_range(self) -> None:
        if self._auto_range.isChecked():
            self.range_changed.emit(None, None)
        else:
            self.range_changed.emit(self._vmin_spin.value(), self._vmax_spin.value())
