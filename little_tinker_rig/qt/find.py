"""In-place search owned by the editor being searched."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStyle,
    QWidget,
)

from little_tinker_rig.i18n import N_, tr

from .editor import SourceView, source_offset
from .navigation import tool_button


class FindBar(QWidget):
    visibility_changed = Signal()

    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.missing = False
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.query = QLineEdit()
        self.query.setPlaceholderText(
            N_("Find · Enter — next · Shift+Enter — previous")
        )
        self.query.setAccessibleName(N_("Find in this editor"))
        self.query.installEventFilter(self)
        self.query.returnPressed.connect(self.find)
        self.query.textChanged.connect(lambda: self.find(advance=False))
        row.addWidget(self.query, 1)
        self.status = QLabel()
        self.status.setProperty("translationSources", {})
        row.addWidget(self.status)
        for label, icon, callback in (
            (
                N_("Previous match"),
                QStyle.StandardPixmap.SP_ArrowUp,
                lambda: self.find(True),
            ),
            (N_("Next match"), QStyle.StandardPixmap.SP_ArrowDown, self.find),
            (
                N_("Close search"),
                QStyle.StandardPixmap.SP_DialogCloseButton,
                self.dismiss,
            ),
        ):
            button = tool_button(label, icon)
            button.clicked.connect(lambda checked=False, fn=callback: fn())
            row.addWidget(button)
        self.hide()

    def open(self):
        self.show()
        self.visibility_changed.emit()
        self.query.setFocus()
        self.query.selectAll()

    def dismiss(self):
        self.hide()
        self.visibility_changed.emit()
        self.editor().setFocus()

    def find(self, previous=False, *, advance=True):
        query = self.query.text()
        self.missing = False
        self.status.clear()
        if not query:
            return
        editor = self.editor()
        cursor = editor.textCursor()
        start = (
            cursor.selectionEnd()
            if advance and not previous
            else cursor.selectionStart()
        )
        flags = (
            QTextDocument.FindFlag.FindBackward
            if previous
            else QTextDocument.FindFlag(0)
        )
        match = editor.document().find(query, start, flags)
        if match.isNull():
            match = editor.document().find(
                query, editor.document().characterCount() - 1 if previous else 0, flags
            )
        if match.isNull():
            self.missing = True
            self.retranslate()
            return
        editor.setTextCursor(match)
        if isinstance(editor, SourceView):
            offset = editor.display.backward(
                source_offset(editor.toPlainText(), match.selectionStart())
            )
            editor.session.editor.select(offset)
            editor.reveal(offset)
            editor.selected.emit()
        else:
            editor.ensureCursorVisible()

    def retranslate(self):
        self.status.setText(tr("Not found") if self.missing else "")

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.ShortcutOverride
            and event.key() == Qt.Key.Key_Escape
        ):
            event.accept()
            return True
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Escape:
                self.dismiss()
                return True
            if (
                event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return)
                and event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            ):
                self.find(True)
                return True
        return super().eventFilter(watched, event)
