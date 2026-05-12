"""Re-usable QAction definitions for menus and toolbars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtGui import QAction, QIcon, QKeySequence

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtCore import QObject


@dataclass(frozen=True)
class ActionSpec:
    """Declarative description of a QAction."""

    text: str
    shortcut: QKeySequence.StandardKey | str | None = None
    icon: str = ""
    tooltip: str = ""
    statustip: str = ""

    def build(
        self,
        parent: QObject,
        slot: Callable[[], object] | None = None,
    ) -> QAction:
        action = QAction(self.text, parent)
        if self.shortcut is not None:
            if isinstance(self.shortcut, QKeySequence.StandardKey):
                action.setShortcut(QKeySequence(self.shortcut))
            else:
                action.setShortcut(QKeySequence(self.shortcut))
        if self.icon:
            action.setIcon(QIcon.fromTheme(self.icon))
        if self.tooltip:
            action.setToolTip(self.tooltip)
        if self.statustip:
            action.setStatusTip(self.statustip)
        if slot is not None:
            action.triggered.connect(slot)
        return action


# ----------------------------------------------------------------------
# Catalogue
# ----------------------------------------------------------------------
NEW_PROJECT = ActionSpec(
    text="&New Project…",
    shortcut=QKeySequence.StandardKey.New,
    icon="document-new",
    statustip="Create a new DeltaSuite project",
)

OPEN_PROJECT = ActionSpec(
    text="&Open Project…",
    shortcut=QKeySequence.StandardKey.Open,
    icon="document-open",
    statustip="Open an existing DeltaSuite project",
)

OPEN_FOLDER = ActionSpec(
    text="Open &Folder as Project…",
    shortcut="Ctrl+Shift+O",
    icon="folder-open",
    statustip="Open a folder containing a Delft3D model (.mdf, .mdu, dimr_config.xml)",
)

BROWSE_EXAMPLES = ActionSpec(
    text="Browse &Models in Folder…",
    shortcut="Ctrl+B",
    icon="system-search",
    statustip="Recursively scan a folder and pick from all detected Delft3D models",
)

SAVE_PROJECT = ActionSpec(
    text="&Save",
    shortcut=QKeySequence.StandardKey.Save,
    icon="document-save",
    statustip="Save the current project",
)

CLOSE_PROJECT = ActionSpec(
    text="&Close Project",
    shortcut="Ctrl+W",
    icon="window-close",
    statustip="Close the current project",
)

QUIT = ActionSpec(
    text="E&xit",
    shortcut=QKeySequence.StandardKey.Quit,
    icon="application-exit",
    statustip="Exit DeltaSuite",
)

PREFERENCES = ActionSpec(
    text="&Preferences…",
    shortcut=QKeySequence.StandardKey.Preferences,
    icon="preferences-system",
    statustip="Edit application settings",
)

DETECT_KERNELS = ActionSpec(
    text="Detect &Delft3D kernels…",
    icon="system-search",
    statustip="Scan the system for compiled Delft3D simulation engines",
)

OPEN_RESULT = ActionSpec(
    text="Open &Result File…",
    shortcut="Ctrl+R",
    icon="document-open",
    statustip="Open a NetCDF result file in the map viewer",
)

OPEN_HISTORY = ActionSpec(
    text="Open &Time-series File…",
    shortcut="Ctrl+T",
    icon="document-open",
    statustip="Open a NetCDF history file in the time-series viewer",
)

RUN_SIMULATION = ActionSpec(
    text="&Run Simulation",
    shortcut="F5",
    icon="media-playback-start",
    statustip="Run the current model with the configured kernel",
)

STOP_SIMULATION = ActionSpec(
    text="&Stop Simulation",
    shortcut="Shift+F5",
    icon="media-playback-stop",
    statustip="Terminate the running simulation",
)

ABOUT = ActionSpec(
    text="&About DeltaSuite",
    icon="help-about",
    statustip="Show information about this application",
)

ABOUT_QT = ActionSpec(
    text="About &Qt",
    statustip="Show information about the Qt framework",
)

USER_GUIDE = ActionSpec(
    text="&User Guide",
    shortcut=QKeySequence.StandardKey.HelpContents,
    icon="help-contents",
    statustip="Open the online user guide",
)
