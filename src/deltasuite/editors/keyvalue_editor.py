"""Generic editor for :class:`~deltasuite.core.config_files.ConfigDocument`.

The widget renders one expandable group per section, each group containing a
form with one row per ``key = value`` entry. Edits are tracked locally
(``dirty`` state) and committed back to disk via :meth:`save`.

It deliberately stays format-agnostic: ``.mdu`` (sections) and ``.mdf``
(single anonymous section) render with the same widget tree.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from deltasuite.core.config_files import (
    ConfigDocument,
    ConfigEntry,
    ConfigSection,
)


class KeyValueEditor(QWidget):
    """Editor backed by a :class:`ConfigDocument`.

    Signals
    -------
    dirty_changed(bool)
        Emitted when the unsaved-changes flag flips.
    saved(Path)
        Emitted after a successful :meth:`save`.
    """

    dirty_changed = Signal(bool)
    saved = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._document: ConfigDocument | None = None
        self._editors: dict[tuple[str, str], QLineEdit] = {}
        self._dirty = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setSpacing(4)
        outer.addLayout(self._build_header())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_inner = QWidget()
        self._scroll.setWidget(self._scroll_inner)
        self._inner_layout = QVBoxLayout(self._scroll_inner)
        self._inner_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self._scroll, stretch=1)

        self._show_placeholder("No configuration file loaded.")

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------
    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._title_label = QLabel("—")
        title_font = self._title_label.font()
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        row.addWidget(self._title_label)
        row.addStretch(1)

        self._save_btn = QPushButton("Save")
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self.save)
        self._reload_btn = QPushButton("Reload")
        self._reload_btn.setEnabled(False)
        self._reload_btn.clicked.connect(self.reload)
        row.addWidget(self._reload_btn)
        row.addWidget(self._save_btn)
        return row

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load(self, path: Path) -> None:
        """Open ``path`` and rebuild the form."""
        path = Path(path).expanduser().resolve()
        try:
            doc = ConfigDocument.load(path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Open configuration",
                f"DeltaSuite could not parse {path.name}:\n\n{exc}",
            )
            self.clear()
            return
        self.set_document(doc)

    def set_document(self, doc: ConfigDocument) -> None:
        """Bind ``doc`` to the editor and rebuild the UI."""
        self._document = doc
        self._editors.clear()
        self._set_dirty(False)
        self._title_label.setText(f"{doc.path.name}  —  format {doc.format.value}")
        self._reload_btn.setEnabled(True)
        self._populate()

    def reload(self) -> None:
        """Discard local edits and reread the file from disk."""
        if self._document is None:
            return
        if self._dirty:
            answer = QMessageBox.question(
                self,
                "Discard changes?",
                "Reloading will discard your unsaved changes. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.load(self._document.path)

    def save(self) -> None:
        """Push every editor value back to the document and write it out."""
        if self._document is None:
            return
        try:
            self._commit_to_document()
            self._document.save()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Save configuration", f"Could not save: {exc}")
            return
        self._set_dirty(False)
        logger.info("Saved configuration {}", self._document.path)
        self.saved.emit(self._document.path)

    def clear(self) -> None:
        """Reset the editor to the empty state."""
        self._document = None
        self._editors.clear()
        self._set_dirty(False)
        self._reload_btn.setEnabled(False)
        self._title_label.setText("—")
        self._show_placeholder("No configuration file loaded.")

    @property
    def is_dirty(self) -> bool:
        """``True`` when the user has unsaved edits."""
        return self._dirty

    @property
    def document(self) -> ConfigDocument | None:
        """The currently loaded document (or ``None``)."""
        return self._document

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _populate(self) -> None:
        self._reset_inner()
        if self._document is None:
            return
        for section in self._document.sections:
            self._inner_layout.addWidget(self._build_section_widget(section))
        self._inner_layout.addStretch(1)

    def _build_section_widget(self, section: ConfigSection) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel(section.name or "(default)")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(title_font.pointSize() + 1)
        title.setFont(title_font)
        layout.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        added_rows = 0
        for entry in section.entries:
            row = self._build_entry_row(section, entry)
            if row is not None:
                form.addRow(*row)
                added_rows += 1

        if added_rows == 0:
            empty = QLabel("(no entries in this section)")
            empty.setStyleSheet("color: #888; font-style: italic;")
            layout.addWidget(empty)
        layout.addLayout(form)
        return frame

    def _build_entry_row(
        self, section: ConfigSection, entry: ConfigEntry
    ) -> tuple[str, QWidget] | None:
        if not entry.key:
            return None
        editor = QLineEdit(entry.value)
        editor.setToolTip(entry.comment or entry.value)
        editor.textEdited.connect(self._on_value_edited)
        self._editors[(section.name, entry.key)] = editor

        label_text = entry.key + ":"
        wrapper = QWidget()
        wrap_layout = QHBoxLayout(wrapper)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(editor, stretch=1)
        if entry.comment:
            hint = QLabel(entry.comment)
            hint.setStyleSheet("color: #94a3b8;")
            hint.setMaximumWidth(260)
            wrap_layout.addWidget(hint)
        return label_text, wrapper

    def _commit_to_document(self) -> None:
        if self._document is None:
            return
        for (section_name, key), editor in self._editors.items():
            section = self._document.section(section_name)
            if section is None:
                continue
            section.set(key, editor.text().strip())

    def _on_value_edited(self, _text: str) -> None:
        if not self._dirty:
            self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._save_btn.setEnabled(dirty)
        self.dirty_changed.emit(dirty)

    def _reset_inner(self) -> None:
        while self._inner_layout.count():
            item = self._inner_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _show_placeholder(self, message: str) -> None:
        self._reset_inner()
        label = QLabel(message)
        label.setStyleSheet("color: #888; font-size: 13pt;")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._inner_layout.addWidget(label)
        self._inner_layout.addStretch(1)
