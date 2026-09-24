"""Qt drawing and gestures over the frontend-independent structural index."""

import ast
from bisect import bisect_left, bisect_right
from functools import lru_cache

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, QVariantAnimation, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QFontMetrics,
    QPainter,
    QPen,
    QPolygonF,
    QRegion,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QApplication, QTextEdit

from pyblocks.core import edit
from pyblocks.core.analysis import identifiers
from pyblocks.core.edit import target_position
from pyblocks.core.parameters import default_bindings, has_choices, slots
from pyblocks.core.presentation import PALETTE, regions
from pyblocks.core.snippets import instantiate
from pyblocks.core.transfer import Transfer
from pyblocks.i18n import language, tr

from .annotations import block_notes
from .drag import BlockMime, cancel_drag, drag_block
from .parameters import ParameterEditor, unit_text


@lru_cache(maxsize=8)
def _surrogates(source):
    positions = tuple(index for index, char in enumerate(source) if ord(char) > 0xFFFF)
    return positions, tuple(
        position + index + 1 for index, position in enumerate(positions)
    )


def qt_offset(source: str, offset: int) -> int:
    return (
        offset
        if source.isascii()
        else offset + bisect_left(_surrogates(source)[0], offset)
    )


def source_offset(source: str, offset: int) -> int:
    return min(
        len(source),
        (
            offset
            if source.isascii()
            else offset - bisect_right(_surrogates(source)[1], offset)
        ),
    )


class SourceView(QTextEdit):
    block_drop_target = True
    selected = Signal()
    changed = Signal()
    transferred = Signal()
    layout_changed = Signal()
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
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)
        self.setStyleSheet(
            "QTextEdit { background: #fafbfc; color: #203040; border: 0; padding: 8px; }"
        )
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)
        self.presentation = ()
        self.notes = {}
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
        self.parameter_slots = ()
        self.parameter_lines = ()
        self.parameter_choices = {}
        self.parameter_revision = None
        self.parameter_editor = None
        self.pending_parameter = None
        self.scratch_owner = None
        self.scratch_index = None
        self.origin_span = None
        self.origin_blocks = []
        self.origin_frame = None
        self.drop_gap = None
        self.drop_padding = None
        self.drop_origin = False
        self.drop_validity = {}
        self.drop_transfer = None
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
        context = getattr(self.session, "context", None)
        revision = (
            self.session.document.syntax,
            self.session.visible_matches,
            language(),
            getattr(self.session, "ports", None),
            context.document.syntax if context else None,
        )
        if revision == self.parameter_revision:
            self.viewport().update()
            return
        source = self.session.document.state.source
        previous = self.toPlainText()
        anchor = self.cursorForPosition(QPoint(0, 0))
        anchor.setPosition(anchor.block().position())
        old_offset = source_offset(previous, anchor.position())
        old_y = self.cursorRect(anchor).y()
        horizontal = self.horizontalScrollBar().value()
        self.document().setLayoutEnabled(False)
        try:
            if source != previous:
                self.fade.stop()
                self.fade_lines.clear()
                self.fold_after_fade = None
                self.hover = None
                self.setPlainText(source)
                self.folded.clear()
            self.presentation = regions(
                self.session.document.syntax, self.session.visible_matches
            )
            if revision != self.parameter_revision:
                self.parameter_revision = revision
                if self.parameter_editor:
                    self.parameter_editor.close()
                    self.parameter_editor = None
                self.parameter_slots = slots(self.session)
                self.parameter_lines = tuple(
                    self.session.document.syntax.position(slot.span.start)[0]
                    for slot in self.parameter_slots
                )
                self.parameter_choices = {
                    slot.span: has_choices(self.session, slot)
                    for slot in self.parameter_slots
                }
                self.notes = block_notes(self.session)
                cursor = QTextCursor(self.document())
                cursor.beginEditBlock()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.setCharFormat(QTextCharFormat())
                block_format = QTextBlockFormat()
                block_format.setLineHeight(
                    140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
                )
                cursor.setBlockFormat(block_format)
                for line, notes in self.notes.items():
                    cursor = QTextCursor(self.document().findBlockByNumber(line - 1))
                    note_format = QTextBlockFormat(block_format)
                    note_format.setTopMargin(
                        (self.fontMetrics().height() + 3) * len(notes)
                    )
                    cursor.setBlockFormat(note_format)
                frame = self.document().rootFrame()
                frame_format = frame.frameFormat()
                frame_format.setTopMargin(
                    4 + (self.fontMetrics().height() + 3) * len(self.notes.get(1, ()))
                )
                frame.setFrameFormat(frame_format)
                for slot in self.parameter_slots:
                    start, _ = self.session.document.syntax.position(slot.span.start)
                    end, _ = self.session.document.syntax.position(slot.span.end)
                    if start != end:
                        continue
                    cursor.setPosition(qt_offset(source, slot.span.start))
                    cursor.setPosition(
                        qt_offset(source, slot.span.end),
                        QTextCursor.MoveMode.KeepAnchor,
                    )
                    format = QTextCharFormat()
                    format.setFontLetterSpacingType(QFont.SpacingType.AbsoluteSpacing)
                    unit = unit_text(slot.parameter.annotation)
                    padding = (
                        (18 if self.parameter_choices[slot.span] else 6)
                        + self.fontMetrics().horizontalAdvance(unit)
                        + (6 if unit else 0)
                    )
                    format.setFontLetterSpacing(
                        padding / max(1, slot.span.end - slot.span.start)
                    )
                    cursor.setCharFormat(format)
                cursor.endEditBlock()
        finally:
            self.document().setLayoutEnabled(True)
        if previous:
            mapped = edit.map_offset(previous, source, old_offset)
            anchor.setPosition(qt_offset(source, mapped))
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + self.cursorRect(anchor).y() - old_y
            )
            self.horizontalScrollBar().setValue(horizontal)
        self.viewport().update()

    def reveal(self, offset):
        cursor = QTextCursor(self.document())
        cursor.setPosition(qt_offset(self.toPlainText(), offset))
        rect = self.cursorRect(cursor)
        top = rect.top() - cursor.blockFormat().topMargin()
        bottom = rect.bottom()
        delta = top if top < 0 else max(0, bottom - self.viewport().height() + 8)
        if delta:
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + round(delta)
            )
        horizontal = min(0, rect.left()) or max(
            0, rect.right() - self.viewport().width() + 8
        )
        if horizontal:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + horizontal
            )

    def centerCursor(self):
        rect = self.cursorRect()
        self.verticalScrollBar().setValue(
            self.verticalScrollBar().value()
            + rect.center().y()
            - self.viewport().height() // 2
        )

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
        # Blank source lines still carry every enclosing indentation band.
        if column > len(block.text()):
            start.translate(
                self.fontMetrics().horizontalAdvance(
                    " " * (column - len(block.text()))
                ),
                0,
            )
        if end_column is None:
            end = self.viewport().width() - 8
        else:
            cursor.setPosition(
                block.position()
                + qt_offset(block.text(), min(end_column, len(block.text())))
            )
            end = self.cursorRect(cursor).x()
        return QRectF(start.x(), start.y(), max(3, end - start.x()), start.height())

    def background_rect(self, line, column, end_column=None):
        rect = self._rect(line, column, end_column)
        if rect is None:
            return None
        block = self.document().findBlockByNumber(line - 1)
        rect.setTop(rect.top() - block.blockFormat().topMargin())
        following = block.next()
        while following.isValid() and not following.isVisible():
            following = following.next()
        if following.isValid():
            cursor = QTextCursor(following)
            rect.setBottom(
                self.cursorRect(cursor).top() - following.blockFormat().topMargin()
            )
        return rect

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
        visible_regions = tuple(
            r
            for r in self.presentation
            if r.line <= last_line and r.end_line >= first_line
        )
        for region in reversed(visible_regions):
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
                rect = self.background_rect(
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
            region = next((r for r in visible_regions if r.span == span), None)
            if region is None:
                continue
            color = QColor(PALETTE[region.role]).darker(145)
            color.setAlphaF(amount)
            painter.setBrush(color)
            for line in range(
                max(first_line, region.line), min(last_line, region.end_line) + 1
            ):
                rect = self.background_rect(
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
        note_font = self.font()
        note_font.setPointSize(9)
        note_font.setItalic(True)
        for line in range(first_line, last_line + 1):
            for index, note in enumerate(self.notes.get(line, ())):
                if (
                    self.origin_span is not None
                    and self.origin_span.start <= note.span.start
                    and note.span.end <= self.origin_span.end
                ):
                    continue
                rect = self.note_rect(line, index)
                if rect is None or not rect.intersects(QRectF(event.rect())):
                    continue
                painter.fillRect(
                    QRectF(0, rect.top(), self.viewport().width(), rect.height()),
                    QColor("#fafbfc"),
                )
                for ancestor in visible_regions:
                    if (
                        ancestor.extend_line
                        and ancestor.span != note.span
                        and ancestor.span.start <= note.span.start
                        and note.span.end <= ancestor.span.end
                    ):
                        band = self._rect(line, ancestor.column)
                        if band:
                            band.setTop(rect.top())
                            band.setBottom(rect.bottom())
                            color = QColor(PALETTE[ancestor.role])
                            color.setAlphaF(self.intensity)
                            painter.fillRect(band, QColor("#fafbfc"))
                            painter.fillRect(band, color)
                color = QColor(PALETTE[note.role])
                color.setAlphaF(self.intensity)
                painter.fillRect(rect, QColor("#fafbfc"))
                painter.fillRect(rect, color)
                painter.setFont(note_font)
                painter.setPen(QColor("#617187"))
                painter.drawText(
                    rect.adjusted(23, 0, -4, 0),
                    Qt.AlignmentFlag.AlignVCenter,
                    QFontMetrics(note_font).elidedText(
                        "# " + note.description,
                        Qt.TextElideMode.ElideRight,
                        max(1, int(rect.width() - 27)),
                    ),
                )
                symbol_font = self.font()
                symbol_font.setPointSize(12)
                painter.setFont(symbol_font)
                painter.drawText(
                    QRectF(rect.left(), rect.top(), 21, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    note.icon,
                )
        painter.setFont(self.font())
        for slot in self.parameter_slots[
            bisect_left(self.parameter_lines, first_line) : bisect_right(
                self.parameter_lines, last_line
            )
        ]:
            rect = self.parameter_rect(slot)
            if rect is None or not rect.intersects(QRectF(event.rect())):
                continue
            painter.setPen(QPen(QColor("#9ca7b2"), 1))
            painter.setBrush(QColor("#f8fafb"))
            painter.drawRoundedRect(rect.adjusted(-1, 1, -1, -1), 3, 3)
            arrow = 13 if self.parameter_choices[slot.span] else 4
            painter.setPen(QColor("#243442"))
            painter.drawText(
                rect.adjusted(
                    2,
                    0,
                    -arrow
                    - self.fontMetrics().horizontalAdvance(
                        unit_text(slot.parameter.annotation)
                    ),
                    0,
                ),
                Qt.AlignmentFlag.AlignVCenter,
                syntax.source[slot.span.start : slot.span.end],
            )
            unit = unit_text(slot.parameter.annotation)
            if unit:
                painter.setPen(QColor("#68788a"))
                painter.drawText(
                    rect.adjusted(2, 0, -arrow - 2, 0),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    unit,
                )
            if self.parameter_choices[slot.span]:
                x, y = rect.right() - 8, rect.center().y()
                painter.setBrush(QColor("#63717f"))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon(
                    QPolygonF(
                        [
                            QPointF(x - 3, y - 1),
                            QPointF(x + 3, y - 1),
                            QPointF(x, y + 2),
                        ]
                    )
                )
        move = self.session.editor.moving
        target = move.targets[move.index] if move else self.drop_target
        if target is not None:
            rect = self.target_rect(target)
            if rect:
                if isinstance(target, ast.expr):
                    painter.setPen(QPen(QColor("#277c63"), 2))
                    painter.setBrush(QColor(220, 244, 234, 180))
                    painter.drawRoundedRect(rect, 3, 3)
                else:
                    rect.setHeight(self.marker_height())
                    painter.fillRect(rect, QColor("#d9f0e7"))
                    painter.setPen(QColor("#205e4b"))
                    painter.drawText(
                        rect.adjusted(5, 0, -5, 0),
                        Qt.AlignmentFlag.AlignVCenter,
                        "↳ # " + tr("Insert here"),
                    )
        if self.origin_span is not None:
            rect = self.origin_rect()
            if rect:
                painter.fillRect(rect, QColor("#ffe0a1"))
                painter.setPen(QPen(QColor("#ae6810"), 2))
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
                painter.drawText(
                    rect.adjusted(5, 0, -5, 0),
                    Qt.AlignmentFlag.AlignVCenter,
                    "↶ "
                    + (
                        tr("Previous position")
                        if self.origin_expression
                        else "# " + tr("Previous position")
                    ),
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

    def marker_height(self):
        return self.fontMetrics().height() + 10

    def transfer_span(self, transfer):
        syntax = self.session.document.syntax
        nodes = transfer.nodes
        if nodes is None:
            return syntax.spans[syntax.tree], False
        if isinstance(nodes, ast.expr):
            return syntax.spans[nodes], True
        return edit.statement_group(syntax, nodes)[1], False

    def drag_pixmap(self, transfer):
        span, expression = self.transfer_span(transfer)
        syntax = self.session.document.syntax
        line, column = syntax.position(span.start)
        if not expression:
            column = (
                len(syntax.lines[line - 1]) - len(syntax.lines[line - 1].lstrip())
                if syntax.lines
                else 0
            )
        previous = self.verticalScrollBar().value()
        self.reveal(span.start)
        end_line, end_column = syntax.position(max(span.start, span.end - 1))
        rect = (
            self._rect(line, column, end_column + 1)
            if expression and end_line == line
            else self.background_rect(line, column)
        )
        if rect is None:
            return self.viewport().grab()
        end_line, _ = syntax.position(max(span.start, span.end - 1))
        bottom = self._rect(end_line, column)
        full_height = (bottom.bottom() - rect.top()) if bottom else rect.height()
        height = min((self.fontMetrics().height() + 3) * 4, full_height)
        rect.setHeight(max(self.fontMetrics().height(), height))
        rect.setWidth(min(rect.width(), 640))
        pixmap = self.viewport().grab(rect.toRect())
        self.preview_origin = self.viewport().mapToGlobal(rect.topLeft().toPoint())
        if full_height > height:
            painter = QPainter(pixmap)
            painter.setFont(self.font())
            painter.setPen(QColor("#243442"))
            corner = QRectF(
                pixmap.deviceIndependentSize().width() - 34, height - 24, 32, 22
            )
            painter.fillRect(corner, QColor("#fafbfc"))
            painter.drawText(corner, Qt.AlignmentFlag.AlignCenter, "…")
            painter.end()
        self.verticalScrollBar().setValue(previous)
        return pixmap

    def show_drag_origin(self, transfer):
        self.hide_drag_origin()
        self.origin_span, self.origin_expression = self.transfer_span(transfer)
        if self.origin_expression:
            self.viewport().update()
            return
        syntax = self.session.document.syntax
        first = syntax.position(self.origin_span.start)[0]
        last = syntax.position(max(self.origin_span.start, self.origin_span.end - 1))[0]
        self.document().setLayoutEnabled(False)
        try:
            for line in range(first, last + 1):
                block = self.document().findBlockByNumber(line - 1)
                self.origin_blocks.append(
                    (block, block.isVisible(), block.lineCount(), block.blockFormat())
                )
                if line == first:
                    fmt = block.blockFormat()
                    fmt.setTopMargin(0)
                    QTextCursor(block).setBlockFormat(fmt)
                else:
                    block.setVisible(False)
                    block.setLineCount(0)
            if first == 1:
                frame = self.document().rootFrame()
                self.origin_frame = frame.frameFormat()
                fmt = frame.frameFormat()
                fmt.setTopMargin(4)
                frame.setFrameFormat(fmt)
            self.document().markContentsDirty(0, self.document().characterCount())
        finally:
            self.document().setLayoutEnabled(True)
        self.layout_changed.emit()
        self.viewport().update()

    def hide_drag_origin(self):
        self.document().setLayoutEnabled(False)
        try:
            for block, visible, count, fmt in self.origin_blocks:
                if block.isValid():
                    block.setVisible(visible)
                    block.setLineCount(count)
                    QTextCursor(block).setBlockFormat(fmt)
            if self.origin_frame is not None:
                self.document().rootFrame().setFrameFormat(self.origin_frame)
            if self.origin_blocks:
                self.document().markContentsDirty(0, self.document().characterCount())
        finally:
            self.document().setLayoutEnabled(True)
        self.origin_span = self.origin_frame = None
        self.origin_blocks = []
        self.layout_changed.emit()
        self.viewport().update()

    def origin_rect(self):
        if self.origin_span is None:
            return None
        syntax = self.session.document.syntax
        line, column = syntax.position(self.origin_span.start)
        if self.origin_expression:
            _, end = syntax.position(self.origin_span.end)
            return self._rect(line, column, end)
        return self._rect(line, 0)

    def scroll_area(self):
        widget = self.parentWidget() if self.scratch_owner else self
        while widget is not None:
            if hasattr(widget, "verticalScrollBar"):
                return widget
            widget = widget.parentWidget()
        return self

    def begin_drop_layout(self):
        if self.drop_padding is not None:
            return
        area = self.scroll_area()
        if area is self:
            frame = self.document().rootFrame()
            fmt = frame.frameFormat()
            self.drop_padding = fmt.bottomMargin()
            fmt.setBottomMargin(self.viewport().height() + self.marker_height())
            frame.setFrameFormat(fmt)
        else:
            self.drop_padding = area.column.contentsMargins()
            margins = area.column.contentsMargins()
            margins.setBottom(area.viewport().height() + self.marker_height())
            area.column.setContentsMargins(margins)
            area.column.activate()

    def end_drop_layout(self):
        if self.drop_padding is None:
            return
        area = self.scroll_area()
        if area is self:
            frame = self.document().rootFrame()
            fmt = frame.frameFormat()
            fmt.setBottomMargin(self.drop_padding)
            frame.setFrameFormat(fmt)
        else:
            area.column.setContentsMargins(self.drop_padding)
            area.column.activate()
        self.drop_padding = None

    def set_drop_target(self, target, point=None):
        if target == self.drop_target:
            return
        anchor = self.cursorForPosition(point or QPoint(0, 0))
        anchor.setPosition(anchor.block().position())
        y = self.viewport().mapToGlobal(self.cursorRect(anchor).topLeft()).y()
        self.document().setLayoutEnabled(False)
        try:
            if self.drop_gap:
                block, fmt, frame_fmt = self.drop_gap
                if block.isValid():
                    QTextCursor(block).setBlockFormat(fmt)
                if frame_fmt is not None:
                    self.document().rootFrame().setFrameFormat(frame_fmt)
                self.drop_gap = None
            self.drop_target = target
            if isinstance(target, edit.Target):
                offset, _ = target_position(self.session.document.syntax, target)
                line = min(
                    self.session.document.syntax.position(offset)[0],
                    self.document().blockCount(),
                )
                block = self.document().findBlockByNumber(line - 1)
                fmt = block.blockFormat()
                changed = QTextBlockFormat(fmt)
                changed.setTopMargin(fmt.topMargin() + self.marker_height())
                QTextCursor(block).setBlockFormat(changed)
                frame_fmt = None
                if line == 1:
                    frame = self.document().rootFrame()
                    frame_fmt = frame.frameFormat()
                    changed_frame = frame.frameFormat()
                    changed_frame.setTopMargin(
                        frame_fmt.topMargin() + self.marker_height()
                    )
                    frame.setFrameFormat(changed_frame)
                self.drop_gap = (block, fmt, frame_fmt)
        finally:
            self.document().setLayoutEnabled(True)
        self.layout_changed.emit()
        area = self.scroll_area()
        area.updateGeometry()
        if area is not self:
            area.column.activate()
        bar = area.verticalScrollBar()
        bar.setValue(
            bar.value()
            + self.viewport().mapToGlobal(self.cursorRect(anchor).topLeft()).y()
            - y
        )
        self.viewport().update()

    def note_rect(self, line, index):
        note = self.notes[line][index]
        rect = self._rect(line, note.column)
        if rect is None:
            return None
        height = self.fontMetrics().height() + 3
        return QRectF(
            rect.left(),
            rect.top() - height * (len(self.notes[line]) - index),
            rect.width(),
            height,
        )

    def target_rect(self, target):
        syntax = self.session.document.syntax
        if isinstance(target, ast.expr):
            span = syntax.spans[target]
            line, column = syntax.position(span.start)
            _, end_column = syntax.position(span.end)
            return self._rect(line, column, end_column)
        offset, indent = target_position(syntax, target)
        line = min(syntax.position(offset)[0], self.document().blockCount())
        rect = self._rect(line, indent)
        if rect:
            rect.translate(
                0,
                -self.document().findBlockByNumber(line - 1).blockFormat().topMargin(),
            )
        return rect

    def parameter_rect(self, slot):
        syntax = self.session.document.syntax
        line, column = syntax.position(slot.span.start)
        end, end_column = syntax.position(slot.span.end)
        return self._rect(line, column, end_column) if line == end else None

    def parameter_at(self, point):
        line = self.cursorForPosition(point).blockNumber() + 1
        return next(
            (
                slot
                for slot in self.parameter_slots[
                    bisect_left(self.parameter_lines, line) : bisect_right(
                        self.parameter_lines, line
                    )
                ]
                if (rect := self.parameter_rect(slot)) is not None
                and rect.contains(QPointF(point))
            ),
            None,
        )

    def show_parameter(self, slot):
        if self.parameter_editor:
            self.parameter_editor.close()
        self.reveal(slot.span.start)
        rect = self.parameter_rect(slot)
        if rect is None:
            return
        field = ParameterEditor(self, slot)
        self.parameter_editor = field
        field.applied.connect(self.changed)
        field.destroyed.connect(
            lambda: (
                setattr(self, "parameter_editor", None)
                if self.parameter_editor is field
                else None
            )
        )
        field.setGeometry(rect.toRect().adjusted(-1, 0, 2, 0))
        field.begin()

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
            raise ValueError(tr("This block has no editable parameters"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            point = event.position().toPoint()
            self.pending_parameter = self.parameter_at(point)
            self.press_position = point
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
                    node = None
                    if self.pending_parameter:
                        slot = self.pending_parameter
                        if slot.binding:
                            return
                        node = next(
                            n
                            for n, span in slot.syntax.spans.items()
                            if span == slot.span and isinstance(n, ast.expr)
                        )
                    owner = self.scratch_owner or self.session
                    transfer = Transfer.capture(
                        owner,
                        index=self.scratch_index,
                        fragment=self.session if self.scratch_owner else None,
                        node=node,
                    )
                    self.press_position = self.pending_parameter = None
                    editor.cancel_move()
                    drag_block(self, transfer)
                    return
                except (ValueError, SyntaxError) as error:
                    self.press_position = self.pending_parameter = None
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
            parameter = self.parameter_at(point)
            self.setToolTip(
                parameter.parameter.name
                + (
                    " · " + unit_text(parameter.parameter.annotation)
                    if unit_text(parameter.parameter.annotation)
                    else ""
                )
                if parameter
                else (
                    tr(match.snippet.help).splitlines()[0]
                    if match and match.snippet.help
                    else type(node).__name__
                )
            )
        self.viewport().update()

    def target_coordinates(self, point):
        line = self.cursorForPosition(point).blockNumber() + 1
        origin = self._rect(line, 0)
        column = max(
            0,
            round(
                (point.x() - origin.left()) / self.fontMetrics().horizontalAdvance(" ")
            ),
        )
        return line, column

    def _distance(self, target, line, column):
        syntax = self.session.document.syntax
        offset, indent = target_position(syntax, target)
        target_line = syntax.position(offset)[0]
        return abs(target_line - line) * 100 + abs(indent - column)

    def mouseReleaseEvent(self, event):
        self.press_position = None
        if self.pending_parameter:
            slot, self.pending_parameter = self.pending_parameter, None
            self.show_parameter(slot)
            return
        self.press_position = None
        if self.session.editor.moving:
            if not self.viewport().rect().contains(event.position().toPoint()):
                self.session.editor.cancel_move()
                self.viewport().update()
                return
            try:
                self.session.editor.commit_move()
                self.changed.emit()
                self.reveal(
                    self.session.document.syntax.spans[
                        self.session.editor.selection
                    ].start
                )
            except (ValueError, SyntaxError) as error:
                self.failed.emit(str(error))

    def cancel_pointer_move(self):
        cancel_drag()
        self.press_position = self.pending_parameter = None
        self.session.editor.cancel_move()
        self.dragLeaveEvent(None)

    def dragEnterEvent(self, event):
        self.dragLeaveEvent(None)
        data = event.mimeData()
        if isinstance(data, BlockMime):
            if data.transfer.owner is not (self.scratch_owner or self.session):
                return
            try:
                data.transfer.validate()
            except ValueError:
                return
            self.drop_transfer = data.transfer
        elif data.hasFormat("application/x-pyblocks-snippet"):
            identity = bytes(data.data("application/x-pyblocks-snippet")).decode()
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
        else:
            return
        # Choose the geometric destination first, then validate that destination.
        # An invalid context must never snap to another, distant legal target.
        self.drop_candidates = tuple(edit.targets(self.session.document.syntax))
        self.begin_drop_layout()
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if self.drop_snippet is None and self.drop_transfer is None:
            event.ignore()
            return
        point = event.position().toPoint()
        origin = self.origin_rect()
        self.drop_origin = bool(origin and origin.contains(QPointF(point)))
        if self.drop_origin:
            self.set_drop_target(None, point)
            event.acceptProposedAction()
            return
        if self.drop_target is not None and self.drop_gap:
            marker = self.target_rect(self.drop_target)
            if marker:
                marker.setHeight(self.marker_height())
                if marker.contains(QPointF(point)):
                    event.acceptProposedAction()
                    return
        syntax = self.session.document.syntax
        slot = self.parameter_at(point)
        candidate = None
        if slot:
            node = next(
                (
                    n
                    for n, span in syntax.spans.items()
                    if span == slot.span and isinstance(n, ast.expr)
                ),
                None,
            )
            if (
                isinstance(node, ast.Constant)
                and node.value is None
                and not slot.binding
            ):
                candidate = node
        else:
            candidate = self.pointer_target(point)
        if candidate is not None and candidate not in self.drop_validity:
            try:
                text = self.drop_preview(candidate)
                transfer = self.drop_transfer
                same = transfer is not None and transfer.origin == self.scratch_index
                if same:
                    if transfer.nodes is None:
                        raise ValueError(
                            "Return a whole fragment to its original position"
                        )
                    transfer.validate()
                    if (
                        transfer.fragment_syntax is not None
                        and transfer.fragment_syntax is not syntax
                    ):
                        raise ValueError("Fragment changed during drag")
                    edit.move(syntax, transfer.nodes, candidate)
                elif isinstance(candidate, ast.expr):
                    edit.replace(syntax, candidate, text)
                else:
                    edit.insert(syntax, candidate, text)
                if isinstance(candidate, ast.expr) and slot:
                    from pyblocks.core.analysis import value_type

                    expected = value_type(slot.parameter.annotation)
                    actual = value_type(
                        self.drop_snippet.result_type
                        if self.drop_snippet
                        else self.drop_transfer.result_type
                    )
                    if expected and actual and expected != actual:
                        raise ValueError("The expression does not fit this parameter")
                self.drop_validity[candidate] = True
            except (SyntaxError, ValueError):
                self.drop_validity[candidate] = False
        target = (
            candidate
            if candidate is not None and self.drop_validity[candidate]
            else None
        )
        self.set_drop_target(target, point)
        if target is None:
            event.ignore()
        else:
            event.acceptProposedAction()

    def pointer_target(self, point):
        syntax = self.session.document.syntax
        line, column = self.target_coordinates(point)
        if self.origin_span is not None and self.origin_span.contains(
            syntax.offset(line)
        ):
            return None
        text = syntax.lines[line - 1].strip() if line <= len(syntax.lines) else ""
        if not text:
            return min(
                self.drop_candidates,
                key=lambda t: self._distance(t, line, column),
                default=None,
            )
        node = syntax.at(
            syntax.offset(
                line, len(syntax.lines[line - 1]) - len(syntax.lines[line - 1].lstrip())
            )
        )
        node = next(
            (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), None
        )
        if node is None:
            return None
        suite = syntax.statement_suite[node]
        rect = self._rect(line, 0)
        above = point.y() < rect.center().y()
        if text.startswith(
            ("elif ", "else:", "except ", "except:", "except*", "finally:", "case ")
        ):
            indent = len(syntax.lines[line - 1]) - len(syntax.lines[line - 1].lstrip())
            if above:
                container = next(
                    (
                        n
                        for n in syntax.ancestors(node)
                        if isinstance(n, ast.stmt) and n.lineno < line
                    ),
                    node,
                )
                boundaries = [
                    (offset, target)
                    for target in self.drop_candidates
                    if target.index == len(target.suite.statements)
                    for offset, depth in (target_position(syntax, target),)
                    if depth == indent + 4
                    and syntax.spans[container].start < offset <= syntax.offset(line)
                ]
                return (
                    max(boundaries, key=lambda item: item[0])[1] if boundaries else None
                )
            bodies = [
                s
                for s in syntax.suites
                if s.statements
                and s.statements[0].lineno > line
                and s.statements[0].col_offset == indent + 4
            ]
            return (
                edit.Target(min(bodies, key=lambda s: s.statements[0].lineno), 0)
                if bodies
                else None
            )
        children = [s for s in syntax.suites if s.owner is node]
        if not above and children:
            following = [
                s for s in children if s.statements and s.statements[0].lineno > line
            ]
            if following:
                child = min(following, key=lambda s: s.statements[0].lineno)
                return edit.Target(child, 0)
        return edit.Target(suite, suite.statements.index(node) + (not above))

    def drop_preview(self, target=None):
        if self.drop_transfer is not None:
            return self.drop_transfer.text
        if not self.drop_snippet:
            return ""
        syntax = self.session.document.syntax
        target = target or self.drop_target
        offset = (
            syntax.spans[target].start
            if isinstance(target, ast.expr)
            else target_position(syntax, target)[0] if target else 0
        )
        return instantiate(
            self.drop_snippet,
            default_bindings(self.session, self.drop_snippet, offset),
            identifiers(syntax.tree),
        ).source

    def dragLeaveEvent(self, event):
        self.set_drop_target(None)
        self.end_drop_layout()
        self.drop_origin = False
        self.drop_validity = {}
        self.drop_target = self.drop_snippet = self.drop_transfer = None
        self.drop_candidates = ()
        self.viewport().update()

    def dropEvent(self, event):
        if self.drop_origin:
            self.dragLeaveEvent(event)
            event.acceptProposedAction()
            return
        if self.drop_target is None:
            event.ignore()
            return
        target, transfer, snippet = (
            self.drop_target,
            self.drop_transfer,
            self.drop_snippet,
        )
        self.dragLeaveEvent(event)
        try:
            if transfer is not None:
                if self.scratch_owner is None:
                    transfer.to_program(target)
                else:
                    transfer.to_fragment(self.scratch_index, self.session, target)
                self.transferred.emit()
            else:
                if isinstance(target, ast.expr):
                    self.session.editor.selection = target
                    target = None
                self.snippet_dropped.emit(snippet.identity, target)
            event.acceptProposedAction()
            self.reveal(
                self.session.document.syntax.spans[self.session.editor.selection].start
            )
        except (ValueError, SyntaxError) as error:
            event.ignore()
            self.failed.emit(str(error))

    def leaveEvent(self, event):
        self.hover = None
        self.viewport().update()
        super().leaveEvent(event)

    def showEvent(self, event):
        self.pulse.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.pulse.stop()
        if self.parameter_editor:
            self.parameter_editor.close()
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
