"""Qt drawing and gestures over the frontend-independent structural index."""

import ast

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPen,
    QPolygonF,
    QRegion,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from pyblocks.core import edit
from pyblocks.core.analysis import identifiers
from pyblocks.core.edit import insertion_targets, target_position
from pyblocks.core.parameters import default_bindings, slots
from pyblocks.core.presentation import PALETTE, regions
from pyblocks.core.snippets import instantiate
from pyblocks.i18n import tr

from .parameters import ParameterPopup


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
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursorWidth(0)
        self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
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
        self.parameter_slots = ()
        self.parameter_revision = None
        self.parameter_popup = None
        self.pending_parameter = None
        self.drop_target = None
        self.drop_candidates = ()
        self.drop_snippet = None
        self.pulse = QVariantAnimation(self)
        self.pulse.setDuration(2800)
        self.pulse.setStartValue(0.0)
        self.pulse.setKeyValueAt(0.5, 1.0)
        self.pulse.setEndValue(0.0)
        self.pulse.setLoopCount(-1)
        self.pulse.valueChanged.connect(lambda value: self.viewport().update())
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
        revision = (
            self.session.document.syntax,
            tuple(m.span for m in self.session.visible_matches),
        )
        if revision != self.parameter_revision:
            self.parameter_revision = revision
            if self.parameter_popup:
                self.parameter_popup.close()
                self.parameter_popup = None
            self.parameter_slots = slots(self.session)
            cursor = QTextCursor(self.document())
            cursor.select(QTextCursor.SelectionType.Document)
            cursor.setCharFormat(QTextCharFormat())
            block_format = QTextBlockFormat()
            block_format.setLineHeight(
                140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
            )
            cursor.setBlockFormat(block_format)
            for slot in self.parameter_slots:
                start, _ = self.session.document.syntax.position(slot.span.start)
                end, _ = self.session.document.syntax.position(slot.span.end)
                if start != end:
                    continue
                cursor.setPosition(qt_offset(source, slot.span.start))
                cursor.setPosition(
                    qt_offset(source, slot.span.end), QTextCursor.MoveMode.KeepAnchor
                )
                format = QTextCharFormat()
                format.setFontLetterSpacingType(QFont.SpacingType.AbsoluteSpacing)
                format.setFontLetterSpacing(
                    18 / max(1, slot.span.end - slot.span.start)
                )
                cursor.setCharFormat(format)
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
        covered = QRegion()
        # Each pixel takes the most specific region's color. Multiplying every
        # ancestor makes deeply nested programs progressively dark and muddy.
        for region in reversed(self.presentation):
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
                    area = QRegion(rect.toRect())
                    painter.setClipRegion(area - covered)
                    painter.drawRect(rect)
                    covered |= area
        painter.setClipping(False)
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        selected = match.span if match else syntax.spans[self.session.editor.selection]
        # Selection covers the entire structural region, including the tail of
        # each statement line. A slow saturation change keeps text readable.
        pulse = float(self.pulse.currentValue() or 0)
        painter.setPen(Qt.PenStyle.NoPen)
        for span, amount in ((self.hover, 0.10), (selected, 0.18 + pulse * 0.14)):
            if span is None:
                continue
            region = next((r for r in self.presentation if r.span == span), None)
            if region is None:
                continue
            color = QColor(PALETTE[region.role]).darker(145)
            color.setAlphaF(amount)
            painter.setBrush(color)
            for line in range(
                max(first_line, region.line), min(last_line, region.end_line) + 1
            ):
                rect = self._rect(
                    line,
                    region.column if region.extend_line or line == region.line else 0,
                    (
                        None
                        if region.extend_line or line < region.end_line
                        else region.end_column
                    ),
                )
                if rect:
                    painter.drawRect(rect)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setFont(self.font())
        for slot in self.parameter_slots:
            rect = self.parameter_rect(slot)
            if rect is None or not rect.intersects(QRectF(event.rect())):
                continue
            painter.setPen(QPen(QColor("#9ca7b2"), 1))
            painter.setBrush(QColor("#f8fafb"))
            painter.drawRoundedRect(rect.adjusted(-1, 1, -1, -1), 3, 3)
            painter.setPen(QColor("#243442"))
            painter.drawText(
                rect.adjusted(2, 0, -13, 0),
                Qt.AlignmentFlag.AlignVCenter,
                syntax.source[slot.span.start : slot.span.end],
            )
            x, y = rect.right() - 8, rect.center().y()
            painter.setBrush(QColor("#63717f"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPolygon(
                QPolygonF(
                    [QPointF(x - 3, y - 1), QPointF(x + 3, y - 1), QPointF(x, y + 2)]
                )
            )
        move = self.session.editor.moving
        target = move.targets[move.index] if move else self.drop_target
        if target is not None:
            if isinstance(target, ast.expr):
                span = syntax.spans[target]
                line, column = syntax.position(span.start)
                _, end_column = syntax.position(span.end)
                rect = self._rect(line, column, end_column)
            else:
                offset, indent = target_position(syntax, target)
                line, _ = syntax.position(offset)
                rect = self._rect(min(line, self.document().blockCount()), indent)
            if rect:
                painter.setPen(QPen(QColor("#256552"), 3))
                painter.drawLine(rect.topLeft(), rect.topRight())
                preview = self.session.selected_text() if move else self.drop_preview()
                lines = preview.strip().splitlines()
                visible = lines[:4] + (["…"] if len(lines) > 4 else [])
                height = self.fontMetrics().height() * len(visible) + 12
                ghost = QRectF(
                    rect.left(), rect.top() + 3, min(rect.width(), 560), height
                )
                if ghost.bottom() > self.viewport().height():
                    ghost.moveBottom(rect.top() - 3)
                painter.setPen(QPen(QColor("#748b81"), 1, Qt.PenStyle.DashLine))
                painter.setBrush(QColor("#f3f8f5"))
                painter.drawRoundedRect(ghost, 4, 4)
                painter.setPen(QColor("#29463a"))
                painter.drawText(
                    ghost.adjusted(6, 4, -6, -4),
                    Qt.AlignmentFlag.AlignTop,
                    "\n".join(visible),
                )
        if self.fade_lines:
            opacity = float(self.fade.currentValue() or 0)
            color = QColor("#fafbfc")
            color.setAlphaF(1 - opacity if self.fade_in else opacity)
            for line in self.fade_lines:
                rect = self._rect(line, 0)
                if rect:
                    painter.fillRect(rect, color)
        painter.end()

    def parameter_rect(self, slot):
        syntax = self.session.document.syntax
        line, column = syntax.position(slot.span.start)
        end, end_column = syntax.position(slot.span.end)
        return self._rect(line, column, end_column) if line == end else None

    def parameter_at(self, point):
        return next(
            (
                slot
                for slot in self.parameter_slots
                if (rect := self.parameter_rect(slot)) is not None
                and rect.contains(QPointF(point))
            ),
            None,
        )

    def show_parameter(self, slot):
        if self.parameter_popup:
            self.parameter_popup.close()
        popup = ParameterPopup(self, slot)
        self.parameter_popup = popup
        popup.applied.connect(self.changed)
        popup.destroyed.connect(
            lambda: (
                setattr(self, "parameter_popup", None)
                if self.parameter_popup is popup
                else None
            )
        )
        rect = self.parameter_rect(slot)
        if rect is None:
            return
        popup.adjustSize()
        point = self.viewport().mapToGlobal(rect.bottomLeft().toPoint())
        screen = self.screen().availableGeometry()
        point.setX(min(point.x(), screen.right() - popup.width()))
        point.setY(min(point.y(), screen.bottom() - popup.height()))
        popup.move(point)
        popup.show()
        popup.field.setFocus()
        popup.field.lineEdit().selectAll()

    def edit_parameters(self):
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        selected = match.span if match else syntax.spans[self.session.editor.selection]
        slot = next(
            (
                slot
                for slot in self.parameter_slots
                if selected.start <= slot.span.start < selected.end
            ),
            None,
        )
        if slot:
            self.show_parameter(slot)
        else:
            raise ValueError(tr("У этого блока нет изменяемых параметров"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            point = event.position().toPoint()
            self.pending_parameter = self.parameter_at(point)
            self.press_position = None if self.pending_parameter else point
            syntax = self.session.document.syntax
            node = syntax.at(self.offset_at(point))
            self.session.editor.selection = next(
                (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), node
            )
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
                    self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
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
            syntax = self.session.document.syntax
            node = syntax.at(self.offset_at(point))
            node = next(
                (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), node
            )
            self.hover = syntax.spans[node]
            self.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor
                if self.parameter_at(point)
                else Qt.CursorShape.OpenHandCursor
            )
            match = next(
                (m for m in self.session.matches if m.span.contains(self.hover.start)),
                None,
            )
            self.setToolTip(
                tr(match.snippet.help).splitlines()[0]
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
        if self.pending_parameter:
            slot, self.pending_parameter = self.pending_parameter, None
            self.show_parameter(slot)
            return
        self.press_position = None
        self.drag_indent = None
        if self.session.editor.moving:
            if not self.viewport().rect().contains(event.position().toPoint()):
                self.session.editor.cancel_move()
                self.viewport().update()
                return
            try:
                self.session.editor.commit_move()
                self.changed.emit()
            except (ValueError, SyntaxError) as error:
                self.failed.emit(str(error))

    def dragEnterEvent(self, event):
        if not event.mimeData().hasFormat("application/x-pyblocks-snippet"):
            return
        identity = bytes(
            event.mimeData().data("application/x-pyblocks-snippet")
        ).decode()
        self.drop_snippet = next(
            (
                s
                for s in self.session.snippets
                if s.identity == identity and not s.historical
            ),
            None,
        )
        if self.drop_snippet is None:
            return
        syntax = self.session.document.syntax
        expansion = instantiate(
            self.drop_snippet,
            default_bindings(self.session, self.drop_snippet),
            identifiers(syntax.tree),
        )
        if not self.drop_snippet.expression:
            self.drop_candidates = tuple(insertion_targets(syntax, expansion.source))
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self.drop_snippet is None:
            return
        point = event.position().toPoint()
        syntax = self.session.document.syntax
        offset = self.offset_at(point)
        if self.drop_snippet.expression:
            candidate = syntax.at(offset)
            self.drop_target = candidate if isinstance(candidate, ast.expr) else None
            if self.drop_target is not None:
                try:
                    edit.replace(syntax, candidate, self.drop_preview())
                except (ValueError, SyntaxError):
                    self.drop_target = None
        else:
            line, column = syntax.position(offset)
            self.drop_target = min(
                self.drop_candidates,
                key=lambda t: self._distance(t, line, column),
                default=None,
            )
        if self.drop_target is not None:
            event.acceptProposedAction()
        else:
            event.ignore()
        self.viewport().update()

    def drop_preview(self):
        if not self.drop_snippet:
            return ""
        syntax = self.session.document.syntax
        offset = (
            syntax.spans[self.drop_target].start
            if isinstance(self.drop_target, ast.expr)
            else target_position(syntax, self.drop_target)[0] if self.drop_target else 0
        )
        return instantiate(
            self.drop_snippet,
            default_bindings(self.session, self.drop_snippet, offset),
            identifiers(syntax.tree),
        ).source

    def dragLeaveEvent(self, event):
        self.drop_target = self.drop_snippet = None
        self.drop_candidates = ()
        self.viewport().update()

    def dropEvent(self, event):
        if self.drop_snippet is None or self.drop_target is None:
            event.ignore()
            return
        target = self.drop_target
        if isinstance(target, ast.expr):
            self.session.editor.selection = target
            target = None
        self.snippet_dropped.emit(self.drop_snippet.identity, target)
        self.drop_target = self.drop_snippet = None
        self.drop_candidates = ()
        event.acceptProposedAction()
        self.viewport().update()

    def leaveEvent(self, event):
        self.hover = None
        self.viewport().update()
        super().leaveEvent(event)

    def showEvent(self, event):
        self.pulse.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.pulse.stop()
        if self.parameter_popup:
            self.parameter_popup.close()
        super().hideEvent(event)

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
