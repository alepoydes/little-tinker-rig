"""Static Python assistance; serialize Jedi work outside the GUI thread."""

from dataclasses import dataclass
from html import escape

import jedi
from PySide6.QtCore import (
    QEvent,
    QObject,
    QRunnable,
    QStringListModel,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
)
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QCompleter, QToolTip

from little_tinker_rig.i18n import tr

from .editor import qt_offset, source_offset


@dataclass(frozen=True)
class Suggestions:
    words: tuple = ()
    signature: str = ""
    parameter: str = ""
    description: str = ""
    error: str = ""


def analyze(source, path, line, column, mode):
    script = jedi.Script(source, path=path)
    prefix = source.split("\n")[line - 1][:column]
    word = prefix.rsplit(".", 1)[-1]
    complete = mode == "complete" or (
        mode == "auto"
        and (prefix.endswith(".") or (len(word) >= 2 and word[-2:].isidentifier()))
    )
    words = (
        tuple(
            (item.name_with_symbols, item.get_completion_prefix_length())
            for item in script.complete(line, column)
            if item.type != "path"
        )
        if complete
        else ()
    )
    signatures = script.get_signatures(line, column)
    definition = signatures[0] if signatures else None
    if definition is None and mode == "help":
        definitions = script.help(line, column)
        definition = definitions[0] if definitions else None
    description = (
        definition.docstring(raw=True) if definition and mode == "help" else ""
    )
    # Keep popups readable even for long upstream docstrings.
    description = description[:1800]
    signature = signatures[0] if signatures else None
    parameter = (
        signature.params[signature.index].to_string()
        if signature
        and signature.index is not None
        and signature.index < len(signature.params)
        else ""
    )
    return Suggestions(
        words, signature.to_string() if signature else "", parameter, description
    )


class AnalysisTask(QRunnable):
    def __init__(self, finished, owner, request):
        super().__init__()
        self.finished, self.owner, self.request = finished, owner, request

    def run(self):
        try:
            result = analyze(*self.request)
        except Exception as error:
            # An analysis failure must never interrupt text editing.
            result = Suggestions(error=str(error))
        self.finished.emit(self.owner, self.request, result)


class AnalysisQueue(QObject):
    finished = Signal(object, object, object)

    def __init__(self, parent):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.pending = {}
        self.running = False
        self.finished.connect(self.advance)

    def submit(self, owner, request):
        # Coalesce queued edits, including edits in several open documents.
        self.pending[owner] = request
        if not self.running:
            self.advance()

    def advance(self, *_):
        self.running = bool(self.pending)
        if self.pending:
            owner = next(iter(self.pending))
            request = self.pending.pop(owner)
            self.pool.start(AnalysisTask(self.finished, owner, request))


class PythonAssist(QObject):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        app = QApplication.instance()
        if not hasattr(app, "python_analysis"):
            # Jedi's shared parser cache is not thread-safe, even across Scripts.
            app.python_analysis = AnalysisQueue(app)
        self.queue = app.python_analysis
        self.owner = object()
        self.request = None
        self.words = {}
        self.completer = QCompleter(self)
        self.completer.setWidget(editor)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.model = QStringListModel(self)
        self.completer.setModel(self.model)
        self.completer.activated.connect(self.complete)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(lambda: self.ask("auto"))
        self.queue.finished.connect(self.receive)
        owner, pending = self.owner, self.queue.pending
        self.destroyed.connect(lambda: pending.pop(owner, None))
        editor.textChanged.connect(self.invalidate)
        editor.cursorPositionChanged.connect(self.invalidate)
        editor.installEventFilter(self)

    def invalidate(self):
        self.timer.stop()
        self.request = None
        self.queue.pending.pop(self.owner, None)
        self.completer.popup().hide()
        QToolTip.hideText()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Hide or (
            event.type() == QEvent.Type.FocusOut
            and event.reason() != Qt.FocusReason.PopupFocusReason
        ):
            self.invalidate()
        elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
            self.invalidate()
        return False

    def ask(self, mode):
        editor = self.editor
        if editor.isReadOnly() or not editor.hasFocus():
            return
        cursor = editor.textCursor()
        if cursor.hasSelection():
            return
        self.invalidate()
        request = (
            editor.toPlainText(),
            editor.path,
            cursor.blockNumber() + 1,
            source_offset(cursor.block().text(), cursor.positionInBlock()),
            mode,
        )
        self.request = request
        self.queue.submit(self.owner, request)

    def receive(self, owner, request, result):
        editor = self.editor
        if (
            owner is not self.owner
            or request is not self.request
            or editor.isReadOnly()
            or not editor.hasFocus()
            or not editor.isVisible()
            or editor.path != request[1]
        ):
            return
        self.words = dict(result.words)
        if self.words:
            self.model.setStringList(list(self.words))
            self.completer.setCompletionPrefix("")
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            rect = editor.cursorRect()
            rect.setWidth(max(280, popup.sizeHintForColumn(0) + 25))
            self.completer.complete(rect)
        else:
            self.completer.popup().hide()
            parts = [escape(result.signature)]
            if result.parameter:
                parts.append("<b>" + escape(result.parameter) + "</b>")
            if result.description:
                parts.append(escape(result.description).replace("\n", "<br>"))
            if result.error and request[-1] != "auto":
                parts.append(
                    escape(tr("Python assistance failed: {error}", error=result.error))
                )
            if not any(parts) and request[-1] != "auto":
                parts.append(escape(tr("No Python suggestions here")))
            if any(parts):
                QToolTip.showText(
                    editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft()),
                    "<div style='white-space:pre-wrap'>"
                    + "<br>".join(parts)
                    + "</div>",
                    editor,
                )

    def complete(self, word):
        if (
            self.request is None
            or word not in self.words
            or self.editor.isReadOnly()
            or self.editor.path != self.request[1]
        ):
            return
        editor = self.editor
        source = editor.toPlainText()
        cursor = editor.textCursor()
        position = source_offset(source, cursor.position())
        start = position - self.words[word]
        end = position
        while end < len(source) and ("a" + source[end]).isidentifier():
            end += 1
        if word.endswith("=") and source[end : end + 1] == "=":
            end += 1
        cursor.beginEditBlock()
        cursor.setPosition(qt_offset(source, start))
        cursor.setPosition(qt_offset(source, end), QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(word)
        cursor.endEditBlock()
        editor.setTextCursor(cursor)
        self.invalidate()
