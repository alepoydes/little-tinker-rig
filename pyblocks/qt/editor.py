"""Qt drawing and gestures over the frontend-independent structural index."""

from PySide6.QtCore import QPoint, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFontDatabase, QPainter, QPen, QTextCursor
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from pyblocks.core.edit import target_position, targets
from pyblocks.core.presentation import PALETTE, regions


def qt_offset(source: str, offset: int) -> int:
    return len(source[:offset].encode("utf-16-le")) // 2


def source_offset(source: str, offset: int) -> int:
    return len(
        source.encode("utf-16-le")[: offset * 2].decode("utf-16-le", errors="ignore")
    )


class SourceView(QPlainTextEdit):
    selected = Signal()
    changed = Signal()
    failed = Signal(str)
    snippet_dropped = Signal(str, object)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.setReadOnly(True)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setStyleSheet(
            "QPlainTextEdit { background: #fafbfc; color: #203040; border: 0; padding: 8px; }"
        )
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.presentation = ()
        self.folded = set()
        self.press_position = None
        self.hover = None
        self.intensity = 0.65
        self.fade_lines = set()
        self.fade_in = False
        self.fade = QVariantAnimation(self)
        self.fade.setDuration(140)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.valueChanged.connect(lambda value: self.viewport().update())
        self.fade.finished.connect(self._finish_fold)
        self.fold_after_fade = None
        self.drag_indent = None
        self.refresh_source()

    def refresh_source(self):
        source = self.session.document.state.source
        if source != self.toPlainText():
            self.fade.stop()
            self.fade_lines.clear()
            self.fold_after_fade = None
            self.hover = None
            self.setPlainText(source)
            self.folded.clear()
        self.presentation = regions(
            self.session.document.syntax, self.session.visible_matches
        )
        self.viewport().update()

    def offset_at(self, point):
        return source_offset(
            self.toPlainText(), self.cursorForPosition(point).position()
        )

    def _rect(self, line, column, end_column=None):
        block = self.document().findBlockByNumber(line - 1)
        if not block.isValid() or not block.isVisible():
            return None
        cursor = QTextCursor(block)
        cursor.setPosition(
            block.position() + qt_offset(block.text(), min(column, len(block.text())))
        )
        start = self.cursorRect(cursor)
        if end_column is None:
            end = self.viewport().width() - 8
        else:
            cursor.setPosition(
                block.position()
                + qt_offset(block.text(), min(end_column, len(block.text())))
            )
            end = self.cursorRect(cursor).x()
        return QRectF(start.x(), start.y(), max(3, end - start.x()), start.height())

    def paintEvent(self, event):
        super().paintEvent(event)
        first_line = self.cursorForPosition(QPoint(0, 0)).blockNumber() + 1
        last_line = (
            self.cursorForPosition(QPoint(0, self.viewport().height())).blockNumber()
            + 1
        )
        painter = QPainter(self.viewport())
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.setPen(Qt.PenStyle.NoPen)
        for region in self.presentation:
            color = QColor(PALETTE[region.role])
            color.setAlphaF(self.intensity)
            painter.setBrush(color)
            for line in range(
                max(first_line, region.line), min(last_line, region.end_line) + 1
            ):
                end = (
                    None
                    if region.extend_line or line < region.end_line
                    else region.end_column
                )
                rect = self._rect(
                    line,
                    region.column if region.extend_line or line == region.line else 0,
                    end,
                )
                if rect and rect.intersects(QRectF(event.rect())):
                    painter.drawRect(rect)
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        selected = match.span if match else syntax.spans[self.session.editor.selection]
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for span, color in ((self.hover, "#8999ac"), (selected, "#277d96")):
            if span is None:
                continue
            start, column = syntax.position(span.start)
            end, end_column = syntax.position(span.end)
            painter.setPen(QPen(QColor(color), 2 if span == selected else 1))
            for line in range(max(first_line, start), min(last_line, end) + 1):
                rect = self._rect(
                    line,
                    column if line == start else 0,
                    end_column if line == end else None,
                )
                if rect:
                    painter.drawRect(rect.adjusted(0, 0, -1, -1))
        move = self.session.editor.moving
        if move:
            offset, indent = target_position(move.syntax, move.targets[move.index])
            line, _ = syntax.position(offset)
            rect = self._rect(min(line, self.document().blockCount()), indent)
            if rect:
                painter.setPen(QPen(QColor("#168a66"), 3))
                painter.drawLine(rect.topLeft(), rect.topRight())
        if self.fade_lines:
            opacity = float(self.fade.currentValue() or 0)
            color = QColor("#fafbfc")
            color.setAlphaF(1 - opacity if self.fade_in else opacity)
            for line in self.fade_lines:
                rect = self._rect(line, 0)
                if rect:
                    painter.fillRect(rect, color)
        painter.end()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self.press_position = event.position().toPoint()
            self.session.editor.select(self.offset_at(self.press_position))
            self.selected.emit()
            self.viewport().update()

    def mouseMoveEvent(self, event):
        point = event.position().toPoint()
        editor = self.session.editor
        if (
            self.press_position is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            if (
                point - self.press_position
            ).manhattanLength() >= QApplication.startDragDistance():
                try:
                    move = editor.moving or self.session.begin_move()
                    offset = self.offset_at(point)
                    line, column = self.session.document.syntax.position(offset)
                    move.index = min(
                        range(len(move.targets)),
                        key=lambda i: self._distance(move.targets[i], line, column),
                    )
                    _, indent = target_position(move.syntax, move.targets[move.index])
                    if self.drag_indent is not None and indent < self.drag_indent:
                        self.folded.update(
                            (r.line, r.end_line)
                            for r in self.presentation
                            if r.foldable
                            and r.column > indent
                            and not r.line <= line <= r.end_line
                        )
                        self._apply_folds()
                    self.drag_indent = indent
                except (ValueError, SyntaxError) as error:
                    self.press_position = None
                    self.failed.emit(str(error))
        else:
            node = self.session.document.syntax.at(self.offset_at(point))
            self.hover = self.session.document.syntax.spans[node]
            match = next(
                (m for m in self.session.matches if m.span.contains(self.hover.start)),
                None,
            )
            self.setToolTip(
                match.snippet.help.splitlines()[0]
                if match and match.snippet.help
                else type(node).__name__
            )
        self.viewport().update()

    def _distance(self, target, line, column):
        syntax = self.session.document.syntax
        offset, indent = target_position(syntax, target)
        target_line = syntax.position(offset)[0]
        return abs(target_line - line) * 100 + abs(indent - column)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.press_position = None
        self.drag_indent = None
        if self.session.editor.moving:
            try:
                self.session.editor.commit_move()
                self.changed.emit()
            except (ValueError, SyntaxError) as error:
                self.failed.emit(str(error))

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-pyblocks-snippet"):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-pyblocks-snippet"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-pyblocks-snippet"):
            identity = bytes(
                event.mimeData().data("application/x-pyblocks-snippet")
            ).decode()
            offset = self.offset_at(event.position().toPoint())
            syntax = self.session.document.syntax
            line, column = syntax.position(offset)
            target = min(targets(syntax), key=lambda t: self._distance(t, line, column))
            self.session.editor.select(offset)
            self.snippet_dropped.emit(identity, target)
            event.acceptProposedAction()

    def fold_selection(self):
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        span = match.span if match else syntax.spans[self.session.editor.selection]
        start, _ = syntax.position(span.start)
        end, _ = syntax.position(span.end)
        pair = (start, end)
        self.fade.stop()
        self._finish_fold()
        self.fade_lines = set(range(start + 1, end + 1))
        if pair in self.folded:
            self.folded.remove(pair)
            self.fade_in = True
            self._apply_folds()
        else:
            self.fade_in = False
            self.fold_after_fade = pair
        self.fade.start()

    def _finish_fold(self):
        if self.fold_after_fade is not None:
            self.folded.add(self.fold_after_fade)
            self.fold_after_fade = None
            self._apply_folds()
        self.fade_lines.clear()
        self.viewport().update()

    def _apply_folds(self):
        hidden = {
            row for first, last in self.folded for row in range(first + 1, last + 1)
        }
        block = self.document().firstBlock()
        while block.isValid():
            visible = block.blockNumber() + 1 not in hidden
            block.setVisible(visible)
            block.setLineCount(1 if visible else 0)
            block = block.next()
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()
