"""One file owns its session, text draft, selection and undo histories."""

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.session import Session
from little_tinker_rig.core.source_file import utf8_source
from little_tinker_rig.i18n import N_, tr

from .code import CodeEdit
from .editor import SourceView
from .find import FindBar
from .scratch import ScratchPane


class DocumentPage(QWidget):
    changed = Signal()
    failed = Signal(str)
    snippet_dropped = Signal(str, object)
    definition_requested = Signal(object)
    help_requested = Signal(str)
    input_search_requested = Signal(object, object, bool)
    mode_changed = Signal()

    def __init__(self, path: Path, collections=()):
        super().__init__()
        self.session = Session(path, collections, allow_draft=True)
        self.scratch = ScratchPane(self)
        self.unnamed = False
        self.unsaved_scope = "unsaved:" + uuid4().hex
        self.lesson_project = None
        self.example_work = None
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
        self.source.input_search_requested.connect(self.input_search_requested)
        self.code = CodeEdit(path)
        self.code.history = self
        self.code.setAcceptDrops(False)
        self.code.setPlainText(self.session.document.state.source)
        self.code.textChanged.connect(self.text_changed)
        self.editor_stack = QStackedWidget()
        self.editor_stack.addWidget(self.source)
        self.editor_stack.addWidget(self.code)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.finder = FindBar(lambda: self.code if self.code_active else self.source)
        self.find_bar = self.finder.query
        row = QHBoxLayout()
        row.addWidget(self.message, 1)
        self.scroll_left = QToolButton()
        self.scroll_right = QToolButton()
        for button, direction, label, symbol in (
            (self.scroll_left, -1, N_("Scroll program left"), "←"),
            (self.scroll_right, 1, N_("Scroll program right"), "→"),
        ):
            button.setObjectName(
                "sourceScrollLeft" if direction < 0 else "sourceScrollRight"
            )
            button.setText(symbol)
            button.setToolTip(label)
            button.setAccessibleName(label)
            button.setFixedWidth(30)
            button.clicked.connect(
                lambda checked=False, step=direction: self.scroll_source(step)
            )
            row.addWidget(button)
        scrollbar = self.source.horizontalScrollBar()
        scrollbar.rangeChanged.connect(self.update_scroll_controls)
        scrollbar.valueChanged.connect(self.update_scroll_controls)
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
        layout.addWidget(self.finder)
        layout.addWidget(self.editor_stack, 1)
        if self.session.project.draft is not None:
            self.code_active = True
            self.code.sync_text(self.session.project.draft)
            self.editor_stack.setCurrentIndex(1)
        self.update_mode()

    def scroll_source(self, direction):
        if not self.source.finish_parameter():
            return
        scrollbar = self.source.horizontalScrollBar()
        distance = max(160, self.source.viewport().width() * 2 // 3)
        scrollbar.setValue(scrollbar.value() + direction * distance)

    def update_scroll_controls(self, *_):
        scrollbar = self.source.horizontalScrollBar()
        visible = not self.code_active and scrollbar.maximum() > scrollbar.minimum()
        self.scroll_left.setVisible(visible)
        self.scroll_right.setVisible(visible)
        self.scroll_left.setEnabled(visible and scrollbar.value() > scrollbar.minimum())
        self.scroll_right.setEnabled(visible and scrollbar.value() < scrollbar.maximum())

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
        if not self.source.finish_parameter():
            raise ValueError(tr("Correct the highlighted parameter before continuing."))
        source = utf8_source(self.text)
        if not self.code_active:
            if source != self.text:
                self.session.editor.commit(source)
                self.source.refresh_source()
            return
        self.code.replace_formatted(source)
        try:
            self.commit_code()
        except (SyntaxError, ValueError):
            # Text persistence does not require a valid structural projection.
            self.session.project.draft = self.code.toPlainText()

    def text_changed(self):
        self.session.document.set_draft(
            self.code.toPlainText(), group=self.code.history_group
        )
        self.changed.emit()

    def sync_text(self):
        state = self.session.document.state
        self.code.sync_text(state.text)
        if state.draft is not None and not self.code_active:
            self.code_active = True
            self.editor_stack.setCurrentIndex(1)
            self.update_mode()

    def undo(self):
        self.session.editor.undo()
        self.sync_text()
        self.scratch.refresh(self.session)
        self.changed.emit()

    def redo(self):
        self.session.editor.redo()
        self.sync_text()
        self.scratch.refresh(self.session)
        self.changed.emit()

    def save(self):
        self.prepare_save()
        self.session.project.save()

    def reload(self):
        if not self.session.project.path.is_file():
            raise FileNotFoundError(self.session.project.path)
        session = Session(
            self.session.project.path, self.session.collection_paths, allow_draft=True
        )
        self.session = self.source.session = session
        self.session.editor.select(0)
        self.source.display_modes.clear()
        self.source.runtime_problem = self.code.runtime_problem = None
        self.code_active = self.code_active or session.project.draft is not None
        self.code.sync_text(
            session.project.draft
            if session.project.draft is not None
            else session.document.state.source
        )
        self.source.refresh_source()
        self.editor_stack.setCurrentIndex(int(self.code_active))
        self.update_mode()
        self.mode_changed.emit()
        self.changed.emit()

    @property
    def catalog_scope(self):
        return (
            self.unsaved_scope
            if self.unnamed
            else str(self.session.project.path.resolve())
        )

    def checkpoint(self):
        editor = self.code if self.code_active else self.source
        return dict(
            self.session.project.checkpoint(self.text),
            python=self.code_active,
            unnamed=self.unnamed,
            catalog_scope=self.unsaved_scope,
            cursor=editor.textCursor().position(),
            scroll=editor.verticalScrollBar().value(),
            lesson_project=(
                self.lesson_project.checkpoint() if self.lesson_project else None
            ),
        )

    def restore(self, checkpoint):
        self.session.project.restore(checkpoint)
        self.unnamed = checkpoint.get("unnamed", False)
        scope = checkpoint.get("catalog_scope")
        if isinstance(scope, str) and scope.startswith("unsaved:"):
            self.unsaved_scope = scope
        self.session.editor.select(0)
        self.session.set_snippets(self.session.load_snippets())
        self.code_active = (
            checkpoint["python"] or self.session.project.draft is not None
        )
        self.code.sync_text(checkpoint["source"])
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
        self.update_scroll_controls()
        self.message.setText(
            tr(
                "Python · Ctrl+Space — complete · Ctrl+Shift+Space — hint · Ctrl+Alt+L — format"
            )
            if self.code_active
            else tr("Drag blocks. Click a parameter to edit it.")
        )
        if self.example_work:
            self.message.setToolTip(
                tr(
                    "Your example work is saved automatically, including unfinished Python."
                )
            )

    def change_mode(self, index):
        if bool(index) == self.code_active:
            return
        try:
            if not self.source.finish_parameter():
                self.update_mode()
                return
            if index == 0:
                self.commit_code()
            else:
                self.code.sync_text(self.session.document.state.text)
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
            self.session.editor.commit(self.code.toPlainText(), apply_draft=True)
            self.code.sync_text(self.session.document.state.source)
            self.source.refresh_source()
