"""About dialog showing application metadata."""

from __future__ import annotations

import platform
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from deltasuite import APP_NAME, __version__


class AboutDialog(QDialog):
    """Modal *About* dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        layout.addLayout(header)

        logo = QLabel()
        logo.setPixmap(
            QPixmap(":/icons/logo.png").scaledToHeight(
                80, Qt.TransformationMode.SmoothTransformation
            )
        )
        logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)

        title = QLabel(self._title_html())
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setOpenExternalLinks(True)
        title.setWordWrap(True)
        header.addWidget(title, 1)

        details = QLabel(self._details_html())
        details.setTextFormat(Qt.TextFormat.RichText)
        details.setWordWrap(True)
        details.setOpenExternalLinks(True)
        layout.addWidget(details)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _title_html() -> str:
        return (
            f"<h2 style='margin:0'>{APP_NAME}</h2>"
            f"<p style='color:#888;margin:4px 0 0 0'>Version {__version__}</p>"
            "<p style='margin:8px 0 0 0'>"
            "Open source desktop suite for Delft3D modeling.<br>"
            "<a href='https://github.com/ghvmof/deltasuite'>"
            "https://github.com/ghvmof/deltasuite</a>"
            "</p>"
        )

    @staticmethod
    def _details_html() -> str:
        return (
            "<h4>System</h4>"
            f"<ul>"
            f"<li>Python {sys.version.split()[0]}</li>"
            f"<li>Platform: {platform.system()} {platform.release()} "
            f"({platform.machine()})</li>"
            "</ul>"
            "<h4>License</h4>"
            "<p>DeltaSuite is licensed under the GNU General Public License v3.0 or later. "
            "It links with Delft3D simulation kernels licensed under GPL-3.0 / AGPL-3.0 "
            "developed by <a href='https://www.deltares.nl'>Deltares</a>.</p>"
        )
