"""One file owns its session, text draft, selection and undo histories."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.session import Session
from pyblocks.i18n import N_, tr

from .code import CodeEdit
from .editor import SourceView


class DocumentPage(QWidget):
    changed = Signal()
    failed = Signal(str)
    snippet_dropped = Signal(str, object)
    definition_requested = Signal(object)
    help_requested = Signal(str)
    mode_changed = Signal()

    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.session = Session(path, collections, allow_draft=True)
        self.session.editor.select(0)
        self.code_active = False
        self.source = SourceView(self.session)
        self.source.changed.connect(self.changed)
        self.source.transferred.connect(self.changed)
        self.source.selected.connect(self.changed)
        self.source.failed.connect(self.failed)
        self.source.snippet_dropped.connect(self.snippet_dropped)
        self.source.definition_requested.connect(self.definition_requested)
        self.source.help_requested.connect(self.help_requested)
        self.code = CodeEdit(path)
        self.code.setAcceptDrops(False)
        self.code.textChanged.connect(self.changed)
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.source)
        self.editor_stack.addWidget(self.code)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.find_bar = QLineEdit()
        self.find_bar.setPlaceholderText(N_("Find in program · Enter — next match"))
        self.find_bar.hide()
        row = QHBoxLayout()
        row.addWidget(self.message, 1)
        self.mode_actions = []
        group = QActionGroup(self)
        for index, (label, theme, fallback) in enumerate(
            (
                (
                    N_("Blocks"),
                    "view-grid",
                    QStyle.StandardPixmap.SP_FileDialogListView,
                ),
                (
                    "Python",
                    "text-x-script",
                    QStyle.StandardPixmap.SP_FileDialogContentsView,
                ),
            )
        ):
            action = QAction(
                QIcon.fromTheme(theme, self.style().standardIcon(fallback)), label, self
            )
            action.setCheckable(True)
            action.setToolTip(label)
            action.triggered.connect(lambda checked, mode=index: self.change_mode(mode))
            group.addAction(action)
            button = QToolButton()
            button.setDefaultAction(action)
            button.setAccessibleName(label)
            row.addWidget(button)
            self.mode_actions.append(action)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addLayout(row)
        layout.addWidget(self.find_bar)
        layout.addWidget(self.editor_stack, 1)
        if self.session.project.draft is not None:
            self.code_active = True
            self.code.setPlainText(self.session.project.draft)
            self.editor_stack.setCurrentIndex(1)
        self.update_mode()

    @property
    def dirty(self):
        return self.session.project.text_dirty(self.text)

    @property
    def text(self):
        return (
            self.code.toPlainText()
            if self.code_active
            else self.session.document.state.source
        )

    def prepare_save(self):
        try:
            self.commit_code()
        except (SyntaxError, ValueError):
            # Text persistence does not require a valid structural projection.
            self.session.project.draft = self.code.toPlainText()

    def save(self):
        self.prepare_save()
        self.session.project.save()

    def checkpoint(self):
        editor = self.code if self.code_active else self.source
        return dict(
            self.session.project.checkpoint(self.text),
            python=self.code_active,
            cursor=editor.textCursor().position(),
            scroll=editor.verticalScrollBar().value(),
        )

    def restore(self, checkpoint):
        self.session.project.restore(checkpoint)
        self.session.editor.select(0)
        self.session.set_snippets(self.session.load_snippets())
        self.code_active = (
            checkpoint["python"] or self.session.project.draft is not None
        )
        self.code.setPlainText(checkpoint["source"])
        self.editor_stack.setCurrentIndex(int(self.code_active))
        self.source.refresh_source()
        editor = self.code if self.code_active else self.source
        cursor = editor.textCursor()
        cursor.setPosition(
            min(checkpoint["cursor"], editor.document().characterCount() - 1)
        )
        editor.setTextCursor(cursor)
        editor.verticalScrollBar().setValue(checkpoint["scroll"])
        self.update_mode()
        self.changed.emit()

    def update_mode(self):
        self.mode_actions[int(self.code_active)].setChecked(True)
        self.message.setText(
            tr(
                "Python · Ctrl+Space — complete · Ctrl+Shift+Space — hint · Ctrl+Alt+L — format"
            )
            if self.code_active
            else tr("Drag blocks. Click a parameter to edit it.")
        )

    def change_mode(self, index):
        if bool(index) == self.code_active:
            return
        try:
            if index == 0:
                self.commit_code()
            else:
                self.code.setPlainText(self.session.document.state.source)
            self.code_active = bool(index)
            self.editor_stack.setCurrentIndex(index)
            (self.code if index else self.source).setFocus()
            self.changed.emit()
        except (ValueError, SyntaxError, OSError) as error:
            self.failed.emit(str(error))
        self.update_mode()
        self.mode_changed.emit()

    def commit_code(self):
        if self.code_active:
            self.session.editor.commit(self.code.toPlainText())
            self.session.project.draft = None
            self.code.replace_formatted(self.session.document.state.source)
            self.source.refresh_source()
