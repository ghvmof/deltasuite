"""Dialog showing detected Delft3D kernel installations."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
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

from deltasuite.core.kernels import KernelSet, detect_kernels


class KernelsDialog(QDialog):
    """Modal dialog listing all discovered :class:`KernelSet` instances."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Detected Delft3D kernels")
        self.setMinimumSize(720, 420)

        self._sets: list[KernelSet] = []

        layout = QVBoxLayout(self)

        intro = QLabel(
            "DeltaSuite scanned your system for compiled Delft3D simulation "
            "engines. Locations are listed in priority order."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Kernel / Location", "Executable", "Launcher", "Size (MB)"])
        self._tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._tree, 1)

        self._summary = QLabel()
        layout.addWidget(self._summary)

        buttons = QDialogButtonBox()
        self._refresh_button = QPushButton("Re-scan")
        buttons.addButton(self._refresh_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.addButton(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        self._refresh_button.clicked.connect(self.refresh)
        layout.addWidget(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Re-run kernel detection and update the tree."""
        self._sets = detect_kernels()
        self._tree.clear()

        if not self._sets:
            placeholder = QTreeWidgetItem(["No Delft3D kernels detected"])
            font = QFont()
            font.setItalic(True)
            placeholder.setFont(0, font)
            self._tree.addTopLevelItem(placeholder)
            self._summary.setText(
                "Hint: set the DELTASUITE_KERNEL_DIR environment variable, "
                "or configure paths under Preferences."
            )
            return

        total = 0
        for ks in self._sets:
            root = QTreeWidgetItem([str(ks.bin_dir)])
            font = QFont()
            font.setBold(True)
            root.setFont(0, font)
            for kernel in sorted(ks, key=lambda k: k.display_name):
                child = QTreeWidgetItem(
                    [
                        kernel.display_name,
                        kernel.executable.name,
                        kernel.launcher.name if kernel.launcher else "—",
                        f"{kernel.size_mb:.2f}",
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, kernel)
                root.addChild(child)
                total += 1
            self._tree.addTopLevelItem(root)
            root.setExpanded(True)

        self._summary.setText(f"Found {total} kernel(s) across {len(self._sets)} location(s).")
