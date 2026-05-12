"""Modal Preferences dialog editing :class:`Settings` values."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from deltasuite.core.recent import DEFAULT_LIMIT, get_recent, save_recent
from deltasuite.core.settings import Settings, get_settings, save_settings


class PreferencesDialog(QDialog):
    """Edit the user's general / kernel / runner / recent settings.

    Emits :pyattr:`settings_applied` whenever the user clicks OK or Apply,
    so the main window can react (e.g. re-apply the theme).
    """

    settings_applied = Signal(Settings)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.resize(640, 460)

        self._settings = get_settings().model_copy(deep=True)

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_general_tab(), "General")
        self._tabs.addTab(self._build_kernels_tab(), "Kernels")
        self._tabs.addTab(self._build_runner_tab(), "Runner")
        self._tabs.addTab(self._build_recent_tab(), "Recent")
        layout.addWidget(self._tabs)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        self._buttons.accepted.connect(self._on_accept)
        self._buttons.rejected.connect(self.reject)
        apply_btn = self._buttons.button(QDialogButtonBox.StandardButton.Apply)
        if apply_btn is not None:
            apply_btn.clicked.connect(self._on_apply)
        layout.addWidget(self._buttons)

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        form = QFormLayout()
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Auto (follow OS)", userData="auto")
        self._theme_combo.addItem("Light", userData="light")
        self._theme_combo.addItem("Dark", userData="dark")
        self._select_combo_by_data(self._theme_combo, self._settings.general.theme)
        form.addRow("Theme:", self._theme_combo)

        self._language_combo = QComboBox()
        self._language_combo.addItem("English", userData="en")
        self._language_combo.addItem("Espanol (planned)", userData="es")
        self._select_combo_by_data(self._language_combo, self._settings.general.language)
        self._language_combo.setEnabled(False)
        form.addRow("Language:", self._language_combo)

        self._open_last = QCheckBox("Open last project on startup")
        self._open_last.setChecked(self._settings.general.open_last_project_on_startup)
        form.addRow("", self._open_last)

        self._show_welcome = QCheckBox("Show welcome screen when no project is open")
        self._show_welcome.setChecked(self._settings.general.show_welcome_screen)
        form.addRow("", self._show_welcome)

        self._check_updates = QCheckBox("Check for updates on startup")
        self._check_updates.setChecked(self._settings.general.check_for_updates)
        self._check_updates.setEnabled(False)
        form.addRow("", self._check_updates)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_kernels_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        intro = QLabel(
            "Override the automatic Delft3D kernel detection by pointing "
            "DeltaSuite at a specific install_*/bin folder."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #94a3b8;")
        layout.addWidget(intro)

        form = QFormLayout()
        self._preferred_bin = QLineEdit(str(self._settings.kernels.preferred_bin_dir or ""))
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_pick_bin_dir)
        bin_row = QHBoxLayout()
        bin_row.addWidget(self._preferred_bin, stretch=1)
        bin_row.addWidget(browse)
        bin_widget = QWidget()
        bin_widget.setLayout(bin_row)
        form.addRow("Preferred bin folder:", bin_widget)
        layout.addLayout(form)

        extra_box = QGroupBox("Additional search paths")
        extra_layout = QVBoxLayout(extra_box)
        self._extra_paths_edit = QLineEdit(
            "; ".join(str(p) for p in self._settings.kernels.extra_paths)
        )
        self._extra_paths_edit.setPlaceholderText(r"C:\path\to\one;C:\path\to\another")
        extra_layout.addWidget(self._extra_paths_edit)
        layout.addWidget(extra_box)

        layout.addStretch(1)
        return page

    def _build_runner_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self._num_proc = QSpinBox()
        self._num_proc.setRange(1, 256)
        self._num_proc.setValue(self._settings.runner.default_num_processes)
        form.addRow("Default processes (parallel runs):", self._num_proc)

        self._keep_logs = QCheckBox("Keep simulation log files")
        self._keep_logs.setChecked(self._settings.runner.keep_log_files)
        form.addRow("", self._keep_logs)

        self._auto_open = QCheckBox("Switch to results tab when a simulation succeeds")
        self._auto_open.setChecked(self._settings.runner.auto_open_results)
        form.addRow("", self._auto_open)

        layout.addLayout(form)
        layout.addStretch(1)
        return page

    def _build_recent_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        form = QFormLayout()

        self._recent_limit = QSpinBox()
        self._recent_limit.setRange(1, 50)
        self._recent_limit.setValue(get_recent().limit or DEFAULT_LIMIT)
        form.addRow("Maximum recent projects:", self._recent_limit)

        layout.addLayout(form)

        clear_btn = QPushButton("Clear recent list")
        clear_btn.clicked.connect(self._on_clear_recent)
        layout.addWidget(clear_btn)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_pick_bin_dir(self) -> None:
        start = self._preferred_bin.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Select Delft3D bin folder", start)
        if chosen:
            self._preferred_bin.setText(chosen)

    def _on_clear_recent(self) -> None:
        recent = get_recent()
        recent.clear()
        save_recent(recent)

    def _on_apply(self) -> None:
        self._collect()
        save_settings(self._settings)
        recent = get_recent()
        recent.limit = int(self._recent_limit.value())
        save_recent(recent)
        self.settings_applied.emit(self._settings)

    def _on_accept(self) -> None:
        self._on_apply()
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect(self) -> None:
        self._settings.general.theme = str(self._theme_combo.currentData())
        self._settings.general.language = str(self._language_combo.currentData())
        self._settings.general.open_last_project_on_startup = self._open_last.isChecked()
        self._settings.general.show_welcome_screen = self._show_welcome.isChecked()
        self._settings.general.check_for_updates = self._check_updates.isChecked()

        bin_text = self._preferred_bin.text().strip()
        self._settings.kernels.preferred_bin_dir = Path(bin_text).expanduser() if bin_text else None
        extras_text = self._extra_paths_edit.text().strip()
        self._settings.kernels.extra_paths = [
            Path(p.strip()).expanduser() for p in extras_text.split(";") if p.strip()
        ]

        self._settings.runner.default_num_processes = int(self._num_proc.value())
        self._settings.runner.keep_log_files = self._keep_logs.isChecked()
        self._settings.runner.auto_open_results = self._auto_open.isChecked()

    @staticmethod
    def _select_combo_by_data(combo: QComboBox, value: str) -> None:
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
