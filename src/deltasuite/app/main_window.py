"""DeltaSuite main window.

This is the central widget of the application. It hosts the project explorer
on the left, the editor area in the center and a logs/status area at the
bottom. Phase 0 ships a minimal but functional version (welcome screen +
empty docks + working menus); subsequent phases will fill in the editors
and viewers.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import ClassVar

from loguru import logger
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor, QKeySequence, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from deltasuite import APP_NAME, __version__
from deltasuite.app import actions
from deltasuite.app.dialogs import (
    AboutDialog,
    KernelsDialog,
    PreferencesDialog,
    SelectProjectDialog,
)
from deltasuite.app.run_controller import OutputChannel, RunController, RunState
from deltasuite.app.theme import apply_theme
from deltasuite.app.welcome import WelcomeWidget
from deltasuite.core.kernels import detect_kernels
from deltasuite.core.project import Project, ProjectMeta
from deltasuite.core.project_detector import (
    DetectedProject,
    detect_project,
    discover_projects,
)
from deltasuite.core.recent import get_recent, push_recent, save_recent
from deltasuite.core.results import find_result_files
from deltasuite.core.run_config import RunConfigError, build_run_config
from deltasuite.core.samples import open_bundled_sample
from deltasuite.core.settings import Settings
from deltasuite.core.timeseries import find_history_files
from deltasuite.editors import KeyValueEditor
from deltasuite.views import MeshPanel, ResultPanel, TimeSeriesPanel


class MainWindow(QMainWindow):
    """Top-level window of the DeltaSuite application."""

    def __init__(self) -> None:
        super().__init__()
        self._current_project: Project | None = None
        self._standalone_results_open: bool = False
        self._run_controller = RunController(self)
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(500)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._build_central()
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self._build_docks()
        self._build_statusbar()
        self._wire_run_controller()

        self._update_title()
        self._update_actions_state()
        self.statusBar().showMessage(f"Ready — {APP_NAME} v{__version__}", 5000)

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_central(self) -> None:
        # Outer stack toggles between the welcome page and the workspace.
        self._central_stack = QStackedWidget()
        self.setCentralWidget(self._central_stack)

        self._welcome_page = self._build_welcome_widget()
        self._central_stack.addWidget(self._welcome_page)

        self._workspace_tabs = QTabWidget()
        self._workspace_tabs.setTabPosition(QTabWidget.TabPosition.North)
        self._workspace_tabs.setMovable(True)
        self._workspace_tabs.setDocumentMode(True)

        self._overview_tab = self._build_overview_tab()
        self._workspace_tabs.addTab(self._overview_tab, "Overview")

        self._setup_editor = KeyValueEditor()
        self._setup_editor.dirty_changed.connect(self._on_setup_dirty_changed)
        self._workspace_tabs.addTab(self._setup_editor, "Setup")

        self._result_panel = ResultPanel()
        self._workspace_tabs.addTab(self._result_panel, "Map")

        self._series_panel = TimeSeriesPanel()
        self._workspace_tabs.addTab(self._series_panel, "Series")

        self._mesh_panel = MeshPanel()
        self._workspace_tabs.addTab(self._mesh_panel, "Mesh")

        self._central_stack.addWidget(self._workspace_tabs)
        self._central_stack.setCurrentIndex(0)

    def _build_welcome_widget(self) -> QWidget:
        welcome = WelcomeWidget()
        welcome.new_project_requested.connect(self.on_new_project)
        welcome.open_project_requested.connect(self.on_open_project)
        welcome.open_folder_requested.connect(self.on_open_folder)
        welcome.browse_examples_requested.connect(self.on_browse_examples)
        welcome.detect_kernels_requested.connect(self.on_detect_kernels)
        welcome.open_sample_requested.connect(self.on_open_sample)
        welcome.recent_selected.connect(self._open_recent_path)
        welcome.clear_recents_requested.connect(self._on_clear_recents)
        self._welcome_widget = welcome
        return welcome

    def _build_overview_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overview_label = QLabel("No project open.")
        self._overview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._overview_label.setTextFormat(Qt.TextFormat.RichText)
        self._overview_label.setStyleSheet("color: #94a3b8; font-size: 13pt;")
        layout.addWidget(self._overview_label)
        return page

    def _build_actions(self) -> None:
        self._act_new = actions.NEW_PROJECT.build(self, self.on_new_project)
        self._act_open = actions.OPEN_PROJECT.build(self, self.on_open_project)
        self._act_open_folder = actions.OPEN_FOLDER.build(self, self.on_open_folder)
        self._act_browse_examples = actions.BROWSE_EXAMPLES.build(self, self.on_browse_examples)
        self._act_save = actions.SAVE_PROJECT.build(self, self.on_save_project)
        self._act_close = actions.CLOSE_PROJECT.build(self, self.on_close_project)
        self._act_quit = actions.QUIT.build(self, self.close)
        self._act_preferences = actions.PREFERENCES.build(self, self.on_preferences)
        self._act_detect = actions.DETECT_KERNELS.build(self, self.on_detect_kernels)
        self._act_open_result = actions.OPEN_RESULT.build(self, self.on_open_result_file)
        self._act_open_history = actions.OPEN_HISTORY.build(self, self.on_open_history_file)
        self._act_run = actions.RUN_SIMULATION.build(self, self.on_run_simulation)
        self._act_stop = actions.STOP_SIMULATION.build(self, self.on_stop_simulation)
        self._act_about = actions.ABOUT.build(self, self.on_about)
        self._act_about_qt = actions.ABOUT_QT.build(self, self.on_about_qt)
        self._act_user_guide = actions.USER_GUIDE.build(self, self.on_user_guide)

    def _build_menus(self) -> None:
        bar = self.menuBar()

        file_menu = bar.addMenu("&File")
        file_menu.addAction(self._act_new)
        file_menu.addAction(self._act_open)
        file_menu.addAction(self._act_open_folder)
        file_menu.addAction(self._act_browse_examples)
        file_menu.addSeparator()
        file_menu.addAction(self._act_save)
        file_menu.addAction(self._act_close)
        file_menu.addSeparator()
        file_menu.addAction(self._act_open_result)
        file_menu.addAction(self._act_open_history)
        file_menu.addSeparator()
        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._refresh_recent_menu()
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)

        edit_menu = bar.addMenu("&Edit")
        edit_menu.addAction(self._act_preferences)

        run_menu = bar.addMenu("&Run")
        run_menu.addAction(self._act_run)
        run_menu.addAction(self._act_stop)
        run_menu.addSeparator()
        run_menu.addAction(self._act_detect)

        view_menu = bar.addMenu("&View")
        self._view_menu = view_menu  # populated when docks are built

        help_menu = bar.addMenu("&Help")
        help_menu.addAction(self._act_user_guide)
        help_menu.addSeparator()
        help_menu.addAction(self._act_about)
        help_menu.addAction(self._act_about_qt)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main toolbar")
        toolbar.setIconSize(QSize(20, 20))
        toolbar.setMovable(False)
        toolbar.setObjectName("MainToolbar")
        self.addToolBar(toolbar)
        toolbar.addAction(self._act_new)
        toolbar.addAction(self._act_open)
        toolbar.addAction(self._act_open_folder)
        toolbar.addAction(self._act_browse_examples)
        toolbar.addAction(self._act_save)
        toolbar.addSeparator()
        toolbar.addAction(self._act_run)
        toolbar.addAction(self._act_stop)

    def _build_docks(self) -> None:
        # Project explorer
        self._project_tree = QTreeWidget()
        self._project_tree.setHeaderLabels(["Project"])
        self._project_tree.setRootIsDecorated(True)

        explorer = QDockWidget("Project Explorer", self)
        explorer.setObjectName("ProjectExplorer")
        explorer.setWidget(self._project_tree)
        explorer.setAllowedAreas(
            Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, explorer)
        self._view_menu.addAction(explorer.toggleViewAction())

        # Logs panel
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        self._log_view.setStyleSheet("font-family: Consolas, 'Courier New', monospace;")

        logs = QDockWidget("Output", self)
        logs.setObjectName("OutputDock")
        logs.setWidget(self._log_view)
        logs.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, logs)
        self._view_menu.addAction(logs.toggleViewAction())

        with contextlib.suppress(ValueError, RuntimeError):
            logger.add(
                lambda msg: self._log_view.appendPlainText(msg.rstrip()),
                level="INFO",
                format="{time:HH:mm:ss} | {level: <7} | {message}",
                enqueue=False,
            )

    def _build_statusbar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)

        self._run_status = QLabel("Idle")
        self._run_status.setStyleSheet("padding: 0 12px; color: #888;")
        bar.addPermanentWidget(self._run_status)

        self._elapsed_status = QLabel()
        self._elapsed_status.setStyleSheet("padding: 0 12px; font-family: Consolas, monospace;")
        bar.addPermanentWidget(self._elapsed_status)

        self._kernel_status = QLabel()
        bar.addPermanentWidget(self._kernel_status)
        self._update_kernel_status()

    def _wire_run_controller(self) -> None:
        """Connect the run controller's signals to the UI."""
        self._run_controller.output_line.connect(self._on_run_output)
        self._run_controller.state_changed.connect(self._on_run_state_changed)
        self._run_controller.finished.connect(self._on_run_finished)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def _update_title(self) -> None:
        if self._current_project is None:
            self.setWindowTitle(APP_NAME)
        else:
            self.setWindowTitle(f"{self._current_project.meta.name} — {APP_NAME}")

    def _update_actions_state(self) -> None:
        has_project = self._current_project is not None
        is_running = self._run_controller.is_running
        self._act_save.setEnabled(has_project and not is_running)
        self._act_close.setEnabled(has_project and not is_running)
        self._act_new.setEnabled(not is_running)
        self._act_open.setEnabled(not is_running)
        self._act_open_folder.setEnabled(not is_running)
        self._act_browse_examples.setEnabled(not is_running)
        self._act_open_result.setEnabled(not is_running)
        self._act_open_history.setEnabled(not is_running)
        self._act_run.setEnabled(has_project and not is_running)
        self._act_stop.setEnabled(is_running)
        show_workspace = has_project or self._standalone_results_open
        self._central_stack.setCurrentIndex(1 if show_workspace else 0)

    def _update_kernel_status(self) -> None:
        sets = detect_kernels()
        total = sum(len(s) for s in sets)
        if total == 0:
            self._kernel_status.setText("⚠ No Delft3D kernels detected")
            self._kernel_status.setStyleSheet("color: #d97706;")  # amber
        else:
            self._kernel_status.setText(f"{total} kernel(s) detected")
            self._kernel_status.setStyleSheet("color: #16a34a;")  # green

    def _refresh_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = get_recent()
        alive = recent.alive()
        if not alive:
            empty = self._recent_menu.addAction("(no recent projects)")
            empty.setEnabled(False)
        else:
            for entry in alive:
                action = self._recent_menu.addAction(f"{entry.name}\t{entry.path.name}")
                action.setToolTip(str(entry.path))
                action.triggered.connect(
                    lambda _checked=False, p=entry.path: self._open_recent_path(p)
                )
            self._recent_menu.addSeparator()
            clear = self._recent_menu.addAction("Clear list")
            clear.triggered.connect(self._on_clear_recents)
        if hasattr(self, "_welcome_widget"):
            self._welcome_widget.set_recent(recent)

    def _open_recent_path(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            QMessageBox.warning(
                self,
                "Recent project missing",
                f"The path no longer exists:\n{path}\n\nIt has been removed from recent.",
            )
            recent = get_recent()
            recent.remove(path)
            save_recent(recent)
            self._refresh_recent_menu()
            return
        try:
            project = Project.open(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open project", str(exc))
            return
        self._remember_recent(project)
        self._set_current_project(project)

    def _remember_recent(self, project: Project) -> None:
        push_recent(project.root, name=project.meta.name)
        self._refresh_recent_menu()

    def _on_clear_recents(self) -> None:
        recent = get_recent()
        recent.clear()
        save_recent(recent)
        self._refresh_recent_menu()

    def _refresh_project_tree(self) -> None:
        self._project_tree.clear()
        if self._current_project is None:
            self._project_tree.setHeaderLabels(["Project"])
            return

        meta = self._current_project.meta
        self._project_tree.setHeaderLabels([f"{meta.name} ({meta.project_type.value})"])

        root = self._current_project.root
        root_item = QTreeWidgetItem([root.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, str(root))
        root_item.setToolTip(0, str(root))
        font = root_item.font(0)
        font.setBold(True)
        root_item.setFont(0, font)
        self._project_tree.addTopLevelItem(root_item)

        self._populate_tree_directory(root_item, root, depth=0)
        root_item.setExpanded(True)

    _TREE_MAX_DEPTH: ClassVar[int] = 4
    _TREE_MAX_ITEMS_PER_DIR: ClassVar[int] = 500
    _TREE_SKIP_DIRS: ClassVar[frozenset[str]] = frozenset(
        {".git", ".svn", "__pycache__", ".venv", "venv", "node_modules"}
    )

    def _populate_tree_directory(
        self, parent: QTreeWidgetItem, directory: Path, *, depth: int
    ) -> None:
        try:
            entries = sorted(
                directory.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except (OSError, PermissionError):
            return

        if len(entries) > self._TREE_MAX_ITEMS_PER_DIR:
            entries = entries[: self._TREE_MAX_ITEMS_PER_DIR]
            truncated = QTreeWidgetItem(
                parent, [f"… ({len(entries)} entries shown — directory truncated)"]
            )
            truncated.setForeground(0, QColor("#888888"))

        for entry in entries:
            if entry.is_dir():
                if entry.name.startswith(".") or entry.name.lower() in self._TREE_SKIP_DIRS:
                    continue
                child = QTreeWidgetItem(parent, [entry.name + "/"])
                child.setData(0, Qt.ItemDataRole.UserRole, str(entry))
                child.setForeground(0, QColor("#94a3b8"))
                child.setToolTip(0, str(entry))
                if depth + 1 < self._TREE_MAX_DEPTH:
                    self._populate_tree_directory(child, entry, depth=depth + 1)
                else:
                    placeholder = QTreeWidgetItem(child, ["…"])
                    placeholder.setForeground(0, QColor("#888888"))
            else:
                label = entry.name
                kb = entry.stat().st_size / 1024 if entry.is_file() else 0
                if kb >= 1:
                    label = f"{entry.name}  ({kb:,.1f} KB)"
                child = QTreeWidgetItem(parent, [label])
                child.setData(0, Qt.ItemDataRole.UserRole, str(entry))
                child.setToolTip(0, str(entry))
                colour = self._colour_for_file(entry)
                if colour:
                    child.setForeground(0, QColor(colour))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def on_new_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select an empty directory for the new project",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not directory:
            return

        try:
            project = Project.create(Path(directory), name=Path(directory).name)
        except FileExistsError as exc:
            QMessageBox.warning(self, "Cannot create project", str(exc))
            return
        self._set_current_project(project)
        self.statusBar().showMessage(f"Created project '{project.meta.name}'", 5000)
        logger.info("Created project '{}'", project.meta.name)

    def _set_current_project(self, project: Project | None) -> None:
        """Centralised state mutation when the active project changes."""
        self._current_project = project
        self._standalone_results_open = False
        self._update_title()
        self._update_actions_state()
        self._refresh_project_tree()
        self._refresh_overview()
        self._refresh_setup()
        self._refresh_results()
        self._refresh_history()
        if project is not None:
            self._remember_recent(project)

    def _refresh_overview(self) -> None:
        if self._current_project is None:
            self._overview_label.setText("No project open.")
            return
        meta = self._current_project.meta
        self._overview_label.setText(
            f"<h2>{meta.name}</h2>"
            f"<p><b>Type:</b> {meta.project_type.value}<br>"
            f"<b>Root:</b> <code>{self._current_project.root}</code><br>"
            f"<b>Entry point:</b> <code>{meta.main_input_file or '—'}</code></p>"
            "<p style='color:#888'>Press <b>F5</b> to run, "
            "switch to the <b>Map</b> tab to view results.</p>"
        )

    def _refresh_results(self) -> None:
        """Update the result panel to reflect the project's NetCDF outputs."""
        if self._current_project is None:
            self._result_panel.set_files([])
            return
        files = find_result_files(self._current_project.root)
        self._result_panel.set_files(files)
        if files:
            logger.info(
                "Found {} NetCDF result file(s) in {}",
                len(files),
                self._current_project.root,
            )

    def _refresh_setup(self) -> None:
        """Load the project's main configuration file into the Setup tab."""
        if self._current_project is None:
            self._setup_editor.clear()
            return
        meta = self._current_project.meta
        if not meta.main_input_file:
            self._setup_editor.clear()
            return
        target = (self._current_project.root / meta.main_input_file).resolve()
        if not target.is_file() or target.suffix.lower() not in (".mdf", ".mdu"):
            self._setup_editor.clear()
            return
        self._setup_editor.load(target)

    def _on_setup_dirty_changed(self, dirty: bool) -> None:
        if dirty:
            self.statusBar().showMessage("Setup has unsaved changes.", 0)

    def _refresh_history(self) -> None:
        """Update the time-series panel to reflect the project's history files."""
        if self._current_project is None:
            self._series_panel.set_files([])
            return
        files = find_history_files(self._current_project.root)
        self._series_panel.set_files(files)
        if files:
            logger.info(
                "Found {} NetCDF history file(s) in {}",
                len(files),
                self._current_project.root,
            )

    def on_open_project(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open DeltaSuite project",
            "",
            "DeltaSuite project (deltasuite.toml);;All files (*.*)",
        )
        if not path_str:
            return

        try:
            project = Project.open(Path(path_str))
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(self, "Failed to open project", str(exc))
            return
        self._set_current_project(project)
        self.statusBar().showMessage(f"Opened project '{project.meta.name}'", 5000)
        logger.info("Opened project '{}'", project.meta.name)

    def on_open_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select a folder containing a Delft3D model",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not directory:
            return

        root = Path(directory)
        detected = detect_project(root)

        if detected.is_recognised:
            self._open_detected(detected, source_root=root)
            return

        # No direct match: try recursive discovery before giving up.
        nested = discover_projects(root, max_depth=5)
        if not nested:
            QMessageBox.warning(
                self,
                "No model found",
                "DeltaSuite did not find any .mdf, .mdu or dimr_config.xml in:\n\n"
                f"{root}\n\n"
                "(Subfolders were also scanned, up to 5 levels deep.)",
            )
            return

        if len(nested) == 1:
            self._open_detected(nested[0], source_root=root)
            return

        self._show_project_picker(nested, root)

    def on_browse_examples(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select a folder to scan for Delft3D models",
            "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if not directory:
            return
        root = Path(directory)
        nested = discover_projects(root, max_depth=6)
        if not nested:
            QMessageBox.information(
                self,
                "No models found",
                f"No Delft3D models were found under:\n\n{root}",
            )
            return
        self._show_project_picker(nested, root)

    def _show_project_picker(self, projects: list[DetectedProject], root: Path) -> None:
        dialog = SelectProjectDialog(projects, root=root, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        chosen = dialog.selected_project()
        if chosen is None:
            return
        self._open_detected(chosen, source_root=root)

    def _open_detected(self, detected: DetectedProject, *, source_root: Path) -> None:
        """Materialise a :class:`Project` from a :class:`DetectedProject`."""
        existing = detected.root / "deltasuite.toml"
        if existing.is_file():
            project = Project.open(existing)
        else:
            main_input = (
                str(detected.main_input.relative_to(detected.root))
                if detected.main_input is not None
                else None
            )
            meta = ProjectMeta(
                name=detected.root.name,
                project_type=detected.project_type,
                main_input_file=main_input,
                description=f"Auto-imported from {source_root}",
            )
            project = Project(detected.root, meta)

        self._set_current_project(project)
        self.statusBar().showMessage(
            f"Opened '{detected.root.name}' ({detected.description})", 7000
        )
        logger.info(
            "Opened folder as project: type={} root={} main_input={}",
            detected.project_type.value,
            detected.root,
            detected.main_input,
        )

    def on_save_project(self) -> None:
        if self._current_project is None:
            return
        self._current_project.save()
        self.statusBar().showMessage("Project saved", 3000)

    def on_close_project(self) -> None:
        if self._current_project is None:
            return
        name = self._current_project.meta.name
        self._set_current_project(None)
        self.statusBar().showMessage(f"Closed project '{name}'", 3000)

    def on_preferences(self) -> None:
        dialog = PreferencesDialog(self)
        dialog.settings_applied.connect(self._on_settings_applied)
        dialog.exec()

    def _on_settings_applied(self, settings: Settings) -> None:
        """Re-apply theme and refresh recent menu after preferences change."""
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            apply_theme(app, settings.general.theme)  # type: ignore[arg-type]
        self._refresh_recent_menu()
        self._update_kernel_status()
        self.statusBar().showMessage("Preferences applied.", 4000)

    def on_open_sample(self) -> None:
        try:
            project = open_bundled_sample("f34")
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self, "Open sample", f"Could not open the bundled sample:\n\n{exc}"
            )
            return
        self._set_current_project(project)
        self.statusBar().showMessage(f"Opened bundled sample: {project.meta.name}", 6000)

    def on_detect_kernels(self) -> None:
        dialog = KernelsDialog(self)
        dialog.exec()
        self._update_kernel_status()

    def on_open_result_file(self) -> None:
        start_dir = (
            str(self._current_project.root)
            if self._current_project is not None
            else str(Path.home())
        )
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open NetCDF result file",
            start_dir,
            "NetCDF files (*.nc);;All files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        self.open_result_file(path)

    def open_result_file(self, path: Path) -> None:
        """Programmatic entry point used by the GUI action and demo scripts."""
        try:
            self._result_panel.open_file(path)
        except (OSError, RuntimeError) as exc:
            QMessageBox.critical(
                self,
                "Could not open file",
                f"DeltaSuite failed to open {path.name}:\n\n{exc}",
            )
            return
        self._standalone_results_open = True
        self._update_actions_state()
        self._workspace_tabs.setCurrentWidget(self._result_panel)
        self.statusBar().showMessage(f"Opened result: {path.name}", 5000)

    def on_open_history_file(self) -> None:
        start_dir = (
            str(self._current_project.root)
            if self._current_project is not None
            else str(Path.home())
        )
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open NetCDF history file",
            start_dir,
            "NetCDF files (*.nc);;All files (*)",
        )
        if not path_str:
            return
        self.open_history_file(Path(path_str))

    def open_history_file(self, path: Path) -> None:
        """Programmatic entry point used by the GUI action and demo scripts."""
        try:
            self._series_panel.open_file(path)
        except (OSError, RuntimeError) as exc:
            QMessageBox.critical(
                self,
                "Could not open file",
                f"DeltaSuite failed to open {path.name}:\n\n{exc}",
            )
            return
        self._standalone_results_open = True
        self._update_actions_state()
        self._workspace_tabs.setCurrentWidget(self._series_panel)
        self.statusBar().showMessage(f"Opened time-series: {path.name}", 5000)

    def on_run_simulation(self) -> None:
        if self._current_project is None:
            return
        if self._run_controller.is_running:
            return

        try:
            detected = detect_project(self._current_project.root)
            kernels = detect_kernels()
            config = build_run_config(detected, kernels)
        except (NotADirectoryError, RunConfigError) as exc:
            QMessageBox.critical(self, "Cannot run simulation", str(exc))
            return

        self._log_view.clear()
        self._append_log(OutputChannel.SYSTEM.value, f"=== {config.description} ===")
        started = self._run_controller.start(config)
        if not started:
            QMessageBox.warning(self, "Run", "A simulation is already in progress.")

    def on_stop_simulation(self) -> None:
        if not self._run_controller.is_running:
            return
        answer = QMessageBox.question(
            self,
            "Stop simulation",
            "Stop the running simulation?\n\n"
            "DeltaSuite will first try a graceful terminate, then kill if needed.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._run_controller.stop()

    def on_about(self) -> None:
        AboutDialog(self).exec()

    def on_about_qt(self) -> None:
        QMessageBox.aboutQt(self, f"{APP_NAME} — About Qt")

    def on_user_guide(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://deltasuite.readthedocs.io"))

    # ------------------------------------------------------------------
    # Run controller integration
    # ------------------------------------------------------------------
    def _on_run_output(self, channel: str, text: str) -> None:
        """Slot invoked for every line emitted by the runner."""
        self._append_log(channel, text)

    def _on_run_state_changed(self, state_value: str) -> None:
        labels = {
            RunState.IDLE: ("Idle", "color: #888;"),
            RunState.STARTING: ("Starting…", "color: #2563eb;"),
            RunState.RUNNING: ("Running", "color: #16a34a; font-weight: bold;"),
            RunState.FINISHED_OK: ("Finished OK", "color: #16a34a;"),
            RunState.FINISHED_ERROR: ("Finished with errors", "color: #dc2626;"),
            RunState.CANCELLED: ("Cancelled", "color: #d97706;"),
        }
        state = RunState(state_value)
        text, style = labels[state]
        self._run_status.setText(text)
        self._run_status.setStyleSheet(f"padding: 0 12px; {style}")

        if state in (RunState.STARTING, RunState.RUNNING):
            if not self._elapsed_timer.isActive():
                self._elapsed_timer.start()
        else:
            self._elapsed_timer.stop()
            self._tick_elapsed()
        self._update_actions_state()

    def _on_run_finished(self, exit_code: int) -> None:
        self._refresh_project_tree()
        self._refresh_results()
        self._refresh_history()
        self._update_kernel_status()
        if exit_code == 0:
            self.statusBar().showMessage("Simulation finished successfully.", 8000)
            if self._has_loadable_results():
                self._workspace_tabs.setCurrentWidget(self._result_panel)
            elif self._has_loadable_history():
                self._workspace_tabs.setCurrentWidget(self._series_panel)
        else:
            self.statusBar().showMessage(f"Simulation finished with exit code {exit_code}.", 8000)

    def _has_loadable_results(self) -> bool:
        if self._current_project is None:
            return False
        return bool(find_result_files(self._current_project.root))

    def _has_loadable_history(self) -> bool:
        if self._current_project is None:
            return False
        return bool(find_history_files(self._current_project.root))

    def _tick_elapsed(self) -> None:
        ms = self._run_controller.elapsed_ms
        seconds_total = ms // 1000
        hours, remainder = divmod(seconds_total, 3600)
        minutes, seconds = divmod(remainder, 60)
        self._elapsed_status.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    _FILE_COLOUR_BY_SUFFIX: ClassVar[dict[str, str]] = {
        ".mdf": "#2563eb",
        ".mdu": "#7c3aed",
        ".xml": "#16a34a",
        ".grd": "#ea580c",
        ".dep": "#ea580c",
        ".bnd": "#0891b2",
        ".bca": "#0891b2",
        ".bch": "#0891b2",
        ".bct": "#0891b2",
        ".dis": "#0891b2",
        ".obs": "#9333ea",
        ".crs": "#9333ea",
        ".enc": "#9333ea",
        ".ldb": "#9333ea",
        ".par": "#9333ea",
        ".thd": "#9333ea",
        ".wnd": "#9333ea",
        ".src": "#9333ea",
        ".dry": "#9333ea",
        ".nc": "#dc2626",
        ".dat": "#dc2626",
        ".def": "#dc2626",
        ".log": "#888888",
        ".bat": "#16a34a",
        ".sh": "#16a34a",
    }

    @classmethod
    def _colour_for_file(cls, entry: Path) -> str | None:
        return cls._FILE_COLOUR_BY_SUFFIX.get(entry.suffix.lower())

    def _append_log(self, channel: str, text: str) -> None:
        """Append a line to the Output dock with channel-specific formatting."""
        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if channel == OutputChannel.STDERR.value:
            fmt.setForeground(QColor("#dc2626"))
        elif channel == OutputChannel.SYSTEM.value:
            fmt.setForeground(QColor("#2563eb"))
            fmt.setFontItalic(True)
        else:
            fmt.setForeground(QColor("#cbd5e1"))
        cursor.insertText(text + "\n", fmt)
        scrollbar = self._log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._run_controller.is_running:
            answer = QMessageBox.question(
                self,
                "Simulation in progress",
                "A simulation is still running. Stop it and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._run_controller.stop(force=True)
        self._result_panel.shutdown()
        self._series_panel.shutdown()
        self._mesh_panel.shutdown()
        logger.info("Closing {}", APP_NAME)
        super().closeEvent(event)

    def keyPressEvent(self, event):  # type: ignore[no-untyped-def]
        if event.matches(QKeySequence.StandardKey.Cancel):
            self.statusBar().clearMessage()
        super().keyPressEvent(event)
