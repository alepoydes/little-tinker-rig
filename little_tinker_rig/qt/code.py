"""Ordinary Python text editing, including unfinished saved programs."""

import keyword
import re

from PySide6.QtCore import QRect, QSignalBlocker, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QKeySequence,
    QPainter,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QMenu, QPlainTextEdit, QWidget

from little_tinker_rig.i18n import tr

from .completion import PythonAssist
from .editor import qt_offset, source_offset


class PythonHighlight(QSyntaxHighlighter):
    def highlightBlock(self, text):
        def color(start, end, value):
            self.setFormat(
                qt_offset(text, start),
                qt_offset(text, end) - qt_offset(text, start),
                QColor(value),
            )

        for match in re.finditer(r"\b[A-Za-z_]\w*\b|\b\d+(?:\.\d+)?\b", text):
            word = match.group()
            if keyword.iskeyword(word):
                color(*match.span(), "#8647a0")
            elif word[0].isdigit():
                color(*match.span(), "#a55319")
        self.setCurrentBlockState(0)
        index = 0
        previous = self.previousBlockState()
        if previous in (1, 2):
            quote = "'''" if previous == 1 else '"""'
            end = text.find(quote)
            color(0, len(text) if end < 0 else end + 3, "#377c46")
            if end < 0:
                self.setCurrentBlockState(previous)
                return
            index = end + 3
        while index < len(text):
            if text[index] == "#":
                color(index, len(text), "#778493")
                break
            if text[index] not in "\"'":
                index += 1
                continue
            start = index
            quote = text[index]
            triple = text.startswith(quote * 3, index)
            length = 3 if triple else 1
            index += length
            while index < len(text) and not text.startswith(quote * length, index):
                index += 2 if text[index] == "\\" else 1
            if index >= len(text) and triple:
                self.setCurrentBlockState(1 if quote == "'" else 2)
            index = min(len(text), index + length)
            color(start, index, "#377c46")


class LineNumbers(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        editor = self.editor
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#f0f3f7"))
        painter.setPen(QColor("#748294"))
        block = editor.firstVisibleBlock()
        top = (
            editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
        )
        while block.isValid() and top <= event.rect().bottom():
            height = editor.blockBoundingRect(block).height()
            if block.isVisible():
                painter.drawText(
                    0,
                    int(top),
                    self.width() - 9,
                    int(height),
                    Qt.AlignmentFlag.AlignRight,
                    str(block.blockNumber() + 1),
                )
            top += height
            block = block.next()


class CodeEdit(QPlainTextEdit):
    def __init__(self, path=None):
        super().__init__()
        self.path = path
        self.runtime_problem = None
        self.history = None
        self.history_group = object()
        self.document().undoCommandAdded.connect(self.new_history_group)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setStyleSheet(
            "QPlainTextEdit { background: #fafbfc; color: #203040; border: 0; padding: 8px; }"
        )
        self.highlighter = PythonHighlight(self.document())
        self.gutter = LineNumbers(self)
        self.blockCountChanged.connect(self.update_gutter)
        self.updateRequest.connect(lambda rect, dy: self.gutter.update())
        self.cursorPositionChanged.connect(self.highlight_line)
        self.textChanged.connect(self.highlight_line)
        self.assist = PythonAssist(self)
        self.update_gutter()

    def gutter_width(self):
        return 18 + self.fontMetrics().horizontalAdvance("9") * len(
            str(max(1, self.blockCount()))
        )

    def update_gutter(self, *_):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.gutter.setGeometry(
            QRect(
                self.contentsRect().topLeft(),
                QSize(self.gutter_width(), self.contentsRect().height()),
            )
        )

    def highlight_line(self):
        from PySide6.QtWidgets import QTextEdit

        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor("#edf2f8"))
        selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        selections = [selection]
        problem = self.runtime_problem
        if problem and self.toPlainText() == problem.source:
            block = self.document().findBlockByNumber(problem.line - 1)
            if block.isValid():
                error = QTextEdit.ExtraSelection()
                error.format.setBackground(QColor("#ffd8dc"))
                error.format.setProperty(
                    QTextCharFormat.Property.FullWidthSelection, True
                )
                error.cursor = QTextCursor(block)
                selections.append(error)
        self.setExtraSelections(selections)

    def keyPressEvent(self, event):
        if self.isReadOnly():
            return super().keyPressEvent(event)
        if self.history and event.matches(QKeySequence.StandardKey.Undo):
            self.undo()
            return
        if self.history and event.matches(QKeySequence.StandardKey.Redo):
            self.redo()
            return
        if self.assist.completer.popup().isVisible() and event.key() in (
            Qt.Key.Key_Enter,
            Qt.Key.Key_Return,
            Qt.Key.Key_Tab,
            Qt.Key.Key_Escape,
        ):
            event.ignore()
            return
        if (
            event.key() == Qt.Key.Key_Space
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.assist.ask(
                "help"
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
                else "complete"
            )
            return
        if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            cursor = self.textCursor()
            if not cursor.hasSelection() and event.key() == Qt.Key.Key_Tab:
                cursor.insertText(" " * (4 - cursor.positionInBlock() % 4))
            else:
                self.indent(-1 if event.key() == Qt.Key.Key_Backtab else 1)
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            prefix = cursor.block().text()[
                : source_offset(cursor.block().text(), cursor.positionInBlock())
            ]
            indent = (
                len(prefix)
                - len(prefix.lstrip())
                + (4 if prefix.rstrip().endswith(":") else 0)
            )
            cursor.insertText("\n" + " " * indent)
            return
        super().keyPressEvent(event)
        if event.text().isprintable() or event.key() in (
            Qt.Key.Key_Backspace,
            Qt.Key.Key_Delete,
        ):
            self.assist.timer.start()

    def new_history_group(self):
        self.history_group = object()

    def undo(self):
        self.history.undo() if self.history else super().undo()

    def redo(self):
        self.history.redo() if self.history else super().redo()

    def contextMenuEvent(self, event):
        if self.history is None:
            return super().contextMenuEvent(event)
        menu = QMenu(self)
        document = self.history.session.document
        for title, callback, enabled in (
            (tr("Undo"), self.undo, document.can_undo),
            (tr("Redo"), self.redo, document.can_redo),
            (tr("Cut"), self.cut, self.textCursor().hasSelection()),
            (tr("Copy"), self.copy, self.textCursor().hasSelection()),
            (tr("Paste"), self.paste, self.canPaste()),
            (
                tr("Delete"),
                lambda: self.textCursor().removeSelectedText(),
                self.textCursor().hasSelection(),
            ),
            (tr("Select all"), self.selectAll, bool(self.toPlainText())),
        ):
            action = menu.addAction(title, callback)
            action.setEnabled(
                enabled
                and (not self.isReadOnly() or callback in (self.copy, self.selectAll))
            )
        menu.exec(event.globalPos())
        menu.deleteLater()

    def sync_text(self, source):
        """Refresh a projection without recording a second user edit."""
        with QSignalBlocker(self):
            self.replace_formatted(source)

    def indent(self, direction):
        cursor = self.textCursor()
        start = self.document().findBlock(cursor.selectionStart()).blockNumber()
        end = (
            self.document()
            .findBlock(max(cursor.selectionStart(), cursor.selectionEnd() - 1))
            .blockNumber()
        )
        cursor.beginEditBlock()
        for row in range(end, start - 1, -1):
            block = self.document().findBlockByNumber(row)
            cursor.setPosition(block.position())
            if direction > 0:
                cursor.insertText("    ")
            else:
                count = min(4, len(block.text()) - len(block.text().lstrip(" ")))
                cursor.setPosition(
                    block.position() + count, QTextCursor.MoveMode.KeepAnchor
                )
                cursor.removeSelectedText()
        cursor.endEditBlock()

    def replace_formatted(self, source):
        if source == self.toPlainText():
            return
        previous = self.textCursor()
        line, column = previous.blockNumber(), previous.positionInBlock()
        cursor = QTextCursor(self.document())
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.insertText(source)
        cursor.endEditBlock()
        block = self.document().findBlockByNumber(min(line, self.blockCount() - 1))
        cursor.setPosition(block.position() + min(column, block.length() - 1))
        self.setTextCursor(cursor)
