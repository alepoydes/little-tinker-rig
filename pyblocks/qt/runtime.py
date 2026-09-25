"""Locate a runtime failure without confusing executed and edited source."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pyblocks.i18n import tr

from .annotations import runtime_span
from .code import CodeEdit


class RuntimePanel(QWidget):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.problem = None
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.message = QLabel()
        self.message.setTextFormat(Qt.TextFormat.PlainText)
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #ab2027")
        row.addWidget(self.message, 1)
        self.locate = QPushButton()
        self.locate.clicked.connect(lambda: window.perform(self.show_block))
        row.addWidget(self.locate)
        self.hide()

    def clear(self, program=None):
        self.problem = None
        self.hide()
        for i in range(self.window.documents.count()):
            page = self.window.documents.widget(i)
            page.source.runtime_problem = page.code.runtime_problem = None
            page.source.refresh_source()
            page.code.highlight_line()

    def receive(self, problem):
        self.problem = problem
        self.retranslate()
        self.show()
        for i in range(self.window.documents.count()):
            page = self.window.documents.widget(i)
            if page.session.project.path == problem.path:
                self.attach(page)
        self.window.error(problem.explanation)

    def attach(self, page):
        page.source.runtime_problem = page.code.runtime_problem = self.problem
        page.source.refresh_source()
        page.code.highlight_line()

    def retranslate(self):
        self.locate.setText(tr("Show block"))
        if self.problem:
            p = self.problem
            location = f"{p.path.name}:{p.line} · " if p.path else ""
            self.message.setText(location + p.explanation)
            self.message.setToolTip(p.kind + ": " + p.detail)
            self.locate.setEnabled(p.path is not None)

    def show_block(self):
        problem = self.problem
        if problem is None or problem.path is None:
            return
        window = self.window
        page = next(
            (
                window.documents.widget(i)
                for i in range(window.documents.count())
                if window.documents.widget(i).session.project.path == problem.path
            ),
            None,
        )
        if page is None:
            # Compare raw saved text before opening: loading can format Python.
            import tokenize

            try:
                with tokenize.open(problem.path) as stream:
                    same = stream.read() == problem.source
            except OSError:
                same = False
            if same:
                page = window.open_document(problem.path)
        if page is None or page.text != problem.source:
            dialog = QDialog(window)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.setWindowTitle(
                tr("Executed program · {name}", name=problem.path.name)
            )
            dialog.resize(850, 650)
            layout = QVBoxLayout(dialog)
            note = QLabel(
                tr(
                    "The program has changed since this run. This is the executed source; your current file is unchanged."
                )
            )
            note.setWordWrap(True)
            layout.addWidget(note)
            editor = CodeEdit()
            editor.setReadOnly(True)
            editor.runtime_problem = problem
            editor.setPlainText(problem.source)
            layout.addWidget(editor)
            dialog.show()
            self.locate_line(editor, problem.line)
            return
        window.documents.setCurrentWidget(page)
        window.set_mode(0)
        self.attach(page)
        if page.code_active:
            self.locate_line(page.code, problem.line)
        elif span := runtime_span(page.session, problem):
            page.session.editor.select(span.start)
            page.source.reveal(span.start)
            page.source.setFocus()
        window.refresh_views()

    @staticmethod
    def locate_line(editor, line):
        block = editor.document().findBlockByNumber(line - 1)
        if block.isValid():
            editor.setTextCursor(QTextCursor(block))
            editor.centerCursor()
            editor.setFocus()
