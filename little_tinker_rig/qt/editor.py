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
    QPainterPath,
    QPen,
    QPolygonF,
    QRegion,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QApplication, QTextEdit

from little_tinker_rig.core import edit
from little_tinker_rig.core.analysis import identifiers
from little_tinker_rig.core.display import Display
from little_tinker_rig.core.edit import target_position
from little_tinker_rig.core.expressions import (
    EMPTY,
    Operation,
    Proposal,
    accepts,
    compose,
    empty,
    navigate,
    public,
)
from little_tinker_rig.core.parameters import default_bindings, has_choices, slots
from little_tinker_rig.core.presentation import (
    Region,
    regions,
    role,
    role_color,
    snippet_role,
)
from little_tinker_rig.core.snippets import instantiate
from little_tinker_rig.core.transfer import Transfer
from little_tinker_rig.i18n import language, tr

from .annotations import block_notes
from .colors import saturated
from .drag import BlockMime, cancel_drag, drag_block
from .parameters import ParameterEditor, unit_text
from .structure import StructureBar, block_menu


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
    definition_requested = Signal(object)
    help_requested = Signal(str)
    input_search_requested = Signal(object, object, bool)

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.display_modes = {}
        self.expression_level = "all"
        self.expression_ids = None
        self.expression_operations = None
        self.expression_popup = None
        self.input_target = None
        self.display = Display(session)
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
        self.runtime_problem = None
        self.folded = set()
        self.press_position = None
        self.hover = None
        self.hover_parameter = None
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
        self.parameter_issues = {}
        self.parameter_revision = None
        self.parameter_editor = None
        self.structure_bar = StructureBar(self)
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
            self.session.expanded_spans,
            language(),
            getattr(self.session, "ports", None),
            context.document.syntax if context else None,
            self.runtime_problem,
            tuple(self.display_modes.items()),
        )
        if revision == self.parameter_revision:
            self.viewport().update()
            return
        self.structure_bar.hide()
        source = self.session.document.state.source
        previous = self.display.source
        anchor = self.cursorForPosition(QPoint(0, 0))
        anchor.setPosition(anchor.block().position())
        old_offset = self.display.backward(
            source_offset(self.toPlainText(), anchor.position())
        )
        old_y = self.cursorRect(anchor).y()
        horizontal = self.horizontalScrollBar().value()
        self.document().setLayoutEnabled(False)
        try:
            if source != previous:
                self.display_modes = {
                    (edit.map_offset(previous, source, offset), identity): mode
                    for (offset, identity), mode in self.display_modes.items()
                }
            self.display = Display(self.session, self.display_modes.items())
            if self.toPlainText() != self.display.text:
                self.fade.stop()
                self.fade_lines.clear()
                self.fold_after_fade = None
                self.hover = None
                self.setPlainText(self.display.text)
                self.folded.clear()
            self.presentation = regions(
                self.session.document.syntax, self.session.visible_matches
            )
            if self.display.helpers:
                self.presentation = tuple(
                    r
                    for r in self.presentation
                    if not self.display.helpers.contains(r.span.start)
                )
            if revision != self.parameter_revision:
                self.parameter_revision = revision
                self.hover_parameter = None
                if self.parameter_editor:
                    self.parameter_editor.close()
                    self.parameter_editor = None
                self.parameter_slots = tuple(
                    slot
                    for slot in slots(self.session)
                    if not slot.container
                    and not (
                        self.display.helpers
                        and self.display.helpers.contains(slot.span.start)
                    )
                )
                self.parameter_lines = tuple(
                    self.session.document.syntax.position(slot.span.start)[0]
                    for slot in self.parameter_slots
                )
                self.parameter_choices = {
                    slot.span: has_choices(self.session, slot)
                    for slot in self.parameter_slots
                }
                diagnostics = sorted(
                    self.session.analysis.diagnostics(), key=lambda d: d.span.start
                )
                starts = [d.span.start for d in diagnostics]
                self.parameter_issues = {
                    slot.span: tuple(
                        d.message
                        for d in diagnostics[
                            bisect_left(starts, slot.span.start) : bisect_left(
                                starts, slot.span.end
                            )
                        ]
                    )
                    for slot in self.parameter_slots
                }
                self.notes = block_notes(self.session, self.runtime_problem)
                if self.display.helpers:
                    self.notes = {
                        line: notes
                        for line, notes in self.notes.items()
                        if not self.display.helpers.contains(
                            self.session.document.syntax.starts[line - 1]
                        )
                    }
                self.note_locations = {
                    note.span: (line, index)
                    for line, notes in self.notes.items()
                    for index, note in enumerate(notes)
                    if not note.error
                }
                cursor = QTextCursor(self.document())
                cursor.beginEditBlock()
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.setCharFormat(QTextCharFormat())
                block_format = QTextBlockFormat()
                block_format.setLineHeight(
                    140, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
                )
                cursor.setBlockFormat(block_format)
                first_notes = 0
                for line, notes in self.notes.items():
                    displayed = self.display.by_span.get(notes[0].span)
                    block = (
                        self.document().findBlockByNumber(
                            self.display.position(displayed.shown.start)[0] - 1
                        )
                        if displayed
                        else self.source_block(line)
                    )
                    cursor = QTextCursor(block)
                    note_format = QTextBlockFormat(block_format)
                    note_format.setTopMargin(
                        (self.fontMetrics().height() + 3) * len(notes)
                    )
                    cursor.setBlockFormat(note_format)
                    if block.blockNumber() == 0:
                        first_notes = len(notes)
                frame = self.document().rootFrame()
                frame_format = frame.frameFormat()
                frame_format.setTopMargin(
                    4 + (self.fontMetrics().height() + 3) * first_notes
                )
                frame.setFrameFormat(frame_format)
                for slot in self.parameter_slots:
                    start, _ = self.session.document.syntax.position(slot.span.start)
                    end, _ = self.session.document.syntax.position(slot.span.end)
                    if start != end:
                        continue
                    cursor.setPosition(
                        qt_offset(
                            self.display.text, self.display.forward(slot.span.start)
                        )
                    )
                    cursor.setPosition(
                        qt_offset(
                            self.display.text, self.display.forward(slot.span.end)
                        ),
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
            anchor.setPosition(
                qt_offset(self.display.text, self.display.forward(mapped))
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + self.cursorRect(anchor).y() - old_y
            )
            self.horizontalScrollBar().setValue(horizontal)
        self.viewport().update()

    def reveal(self, offset):
        line = self.session.document.syntax.position(offset)[0]
        hidden_by = {pair for pair in self.folded if pair[0] < line <= pair[1]}
        if hidden_by:
            self.folded -= hidden_by
            self._apply_folds()
        cursor = QTextCursor(self.document())
        cursor.setPosition(qt_offset(self.toPlainText(), self.display.forward(offset)))
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
        offset = source_offset(
            self.toPlainText(), self.cursorForPosition(point).position()
        )
        original = self.display.backward(offset)
        block = self.display.block_at(offset)
        if block and block.effective == "definition":
            return max(block.match.span.start, min(original, block.match.span.end - 1))
        return original

    def source_line_at(self, point):
        return self.session.document.syntax.position(self.offset_at(point))[0]

    def source_block(self, line):
        syntax = self.session.document.syntax
        offset = syntax.starts[min(line - 1, len(syntax.starts) - 1)]
        row, _ = self.display.position(self.display.forward(offset))
        return self.document().findBlockByNumber(row - 1)

    def displayed_block_at(self, point):
        offset = source_offset(
            self.toPlainText(), self.cursorForPosition(point).position()
        )
        return self.display.block_at(offset)

    def _rect(self, line, column, end_column=None, *, background=False):
        syntax = self.session.document.syntax
        text = syntax.lines[line - 1] if line <= len(syntax.lines) else ""
        offset = syntax.starts[min(line - 1, len(syntax.starts) - 1)]
        row, col = self.display.position(
            self.display.forward(offset + min(column, len(text.rstrip("\n"))))
        )
        end = None
        if end_column is not None:
            end_row, end = self.display.position(
                self.display.forward(offset + min(end_column, len(text.rstrip("\n"))))
            )
            if end_row != row:
                end = None
        rect = self._display_rect(row, col, end, background=background)
        if rect and column > len(text.rstrip("\n")):
            rect.translate(
                self.fontMetrics().horizontalAdvance(
                    " " * (column - len(text.rstrip("\n")))
                ),
                0,
            )
        return rect

    def _display_rect(self, line, column, end_column=None, *, background=False):
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
        rect = QRectF(start.x(), start.y(), max(3, end - start.x()), start.height())
        if background:
            following = block.next()
            while following.isValid() and not following.isVisible():
                following = following.next()
            if following.isValid():
                rect.setBottom(
                    self.cursorRect(QTextCursor(following)).top()
                    - following.blockFormat().topMargin()
                )
        return rect

    def background_rect(self, line, column, end_column=None):
        return self._rect(line, column, end_column, background=True)

    def region_rects(self, region, first_line, last_line):
        displayed = self.display.by_span.get(region.span)
        if region.extend_line and region.foldable and displayed is None:
            for child in self.display.blocks:
                if not (
                    region.span.start <= child.match.span.start
                    and child.match.span.end <= region.span.end
                ):
                    continue
                for span in (child.shown, child.preview):
                    if span is None:
                        continue
                    first, _ = self.display.position(span.start)
                    last, _ = self.display.position(max(span.start, span.end - 1))
                    for row in range(first, last + 1):
                        rect = self._display_rect(row, region.column, background=True)
                        if rect:
                            yield rect
        if displayed and displayed.preview:
            first, _ = self.display.position(displayed.preview.start)
            last, _ = self.display.position(displayed.preview.end - 1)
            for row in range(first, last + 1):
                rect = self._display_rect(row, 0, background=True)
                if rect:
                    yield rect
        if (
            displayed
            and displayed.effective == "definition"
            and displayed.match.snippet.expression
        ):
            first, column = self.display.position(displayed.shown.start)
            last, end_column = self.display.position(displayed.shown.end)
            for row in range(first, last + 1):
                rect = self._display_rect(
                    row,
                    column if row == first else 0,
                    end_column if row == last else None,
                )
                if rect:
                    yield rect
            if location := self.note_locations.get(region.span):
                if rect := self.note_rect(*location):
                    yield rect
            return
        if (
            displayed
            and displayed.effective == "definition"
            and not displayed.match.snippet.expression
        ):
            first, _ = self.display.position(displayed.shown.start)
            last, _ = self.display.position(
                max(displayed.shown.start, displayed.shown.end - 1)
            )
            for row in range(first, last + 1):
                rect = self._display_rect(row, region.column, background=True)
                if rect:
                    yield rect
            if location := self.note_locations.get(region.span):
                if rect := self.note_rect(*location):
                    yield rect
            return
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
                yield rect
            for index, note in enumerate(self.notes.get(line, ())):
                if not (
                    region.span == note.span
                    or region.extend_line
                    and region.span.start <= note.span.start
                    and note.span.end <= region.span.end
                ):
                    continue
                rect = self.note_rect(line, index)
                anchor = self._rect(line, region.column)
                if rect and anchor:
                    rect.setLeft(anchor.left())
                    yield rect

    def outline_path(self, region, first_line, last_line):
        path = QPainterPath()
        path.setFillRule(Qt.FillRule.WindingFill)
        # One offscreen row prevents false caps while scrolling through a block.
        for rect in self.region_rects(region, max(1, first_line - 1), last_line + 1):
            path.addRect(rect)
        return path.simplified()

    def paintEvent(self, event):
        super().paintEvent(event)
        first_line = self.source_line_at(QPoint(0, 0))
        last_line = self.source_line_at(QPoint(0, self.viewport().height()))
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
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        selection = self.session.editor.selection
        selected = (
            syntax.spans[selection]
            if public(self.session, selection)
            else match.span if match else syntax.spans[selection]
        )
        if self.session.editor.selection is syntax.tree:
            selected = None
        # Only active subexpressions need a region inside a recognized block.
        # This uses the same color pass as other blocks, with no permanent borders.
        for span in dict.fromkeys((self.hover, selected)):
            if span is None:
                continue
            node = next(
                (
                    n
                    for n in syntax.ancestors(syntax.at(span.start))
                    if syntax.spans[n] == span and public(self.session, n)
                ),
                None,
            )
            if node is None:
                continue
            owner = self.session.enclosing_match(node)
            line, column = syntax.position(span.start)
            end_line, end_column = syntax.position(span.end)
            visible_regions += (
                Region(
                    span,
                    0,
                    snippet_role(owner.snippet) if owner else role(node),
                    line,
                    column,
                    end_line,
                    end_column,
                    False,
                    False,
                    False,
                ),
            )
        pulse = float(self.pulse.currentValue() or 0)
        outlines = []
        for region in reversed(visible_regions):
            amount = max(
                (
                    amount
                    for span, amount in (
                        (self.hover, 0.45),
                        (selected, 0.65 + pulse * 0.3),
                    )
                    if span is not None
                    and span.start <= region.span.start
                    and region.span.end <= span.end
                ),
                default=0,
            )
            color = saturated(role_color(region.role), amount)
            color.setAlphaF(self.intensity)
            painter.setBrush(color)
            for rect in self.region_rects(region, first_line, last_line):
                if rect.intersects(QRectF(event.rect())):
                    area = QRegion(rect.toRect())
                    painter.setClipRegion(area - covered)
                    painter.drawRect(rect)
                    covered |= area
            if region.outlined:
                outlines.append((region, amount))
        painter.setClipping(False)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        seen = set()
        for region, amount in outlines:
            if region.span in seen:
                continue
            seen.add(region.span)
            path = self.outline_path(region, first_line, last_line)
            pen = QPen(saturated(role_color(region.role), 0.45 + amount * 0.4), 1)
            pen.setCosmetic(True)
            painter.setPen(pen)
            # Opaque shared edges occupy the same pixel without accumulating alpha.
            painter.drawPath(path)
            if region.foldable and region.extend_line:
                bounds = QRectF()
                for part in self.region_rects(region, first_line, last_line):
                    bounds = bounds.united(part)
                if not bounds.isEmpty():
                    painter.setPen(QPen(QColor("#72859a"), 2))
                    x = bounds.left() + 1
                    painter.drawLine(
                        QPointF(x, bounds.top()), QPointF(x, bounds.bottom() - 1)
                    )
                    if region.end_line <= last_line:
                        painter.drawLine(
                            QPointF(x, bounds.bottom() - 1),
                            QPointF(x + 14, bounds.bottom() - 1),
                        )
        note_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
        note_font.setBold(True)
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
                painter.setFont(note_font)
                painter.setPen(QColor("#ab2027" if note.error else "#49596d"))
                left = rect.left()
                symbol_font = self.font()
                symbol_font.setPixelSize(max(12, int(rect.height() - 2)))
                painter.setFont(symbol_font)
                width = max(
                    21, QFontMetrics(symbol_font).horizontalAdvance(note.icon) + 4
                )
                painter.drawText(
                    QRectF(left, rect.top(), width, rect.height()),
                    Qt.AlignmentFlag.AlignVCenter,
                    note.icon,
                )
                painter.setFont(note_font)
                text_rect = QRectF(
                    left + width,
                    rect.top(),
                    max(1, rect.right() - left - width - 4),
                    rect.height(),
                )
                painter.drawText(
                    text_rect,
                    Qt.AlignmentFlag.AlignVCenter,
                    QFontMetrics(note_font).elidedText(
                        note.description,
                        Qt.TextElideMode.ElideRight,
                        int(text_rect.width()) - 32,
                    ),
                )
                if note.error:
                    painter.save()
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#c02d35"), 2))
                    owner = next(
                        (r for r in visible_regions if r.span == note.span), None
                    )
                    if owner:
                        area = None
                        for part in self.region_rects(owner, first_line, last_line):
                            area = part if area is None else area.united(part)
                        if area:
                            painter.drawRect(area.adjusted(1, 1, -1, -1))
                    else:
                        end_line, end_column = syntax.position(note.span.end)
                        area = self._rect(
                            line, note.column, end_column if line == end_line else None
                        )
                        if area:
                            area.setTop(rect.top())
                            painter.drawRect(area.adjusted(1, 1, -1, -1))
                    painter.restore()
        painter.setFont(self.font())
        for region in visible_regions:
            block = self.display.by_span.get(region.span)
            if block is None:
                continue
            rect = self.mode_rect(block)
            if rect and rect.intersects(QRectF(event.rect())):
                painter.setPen(QColor("#41576d"))
                painter.setBrush(QColor("#fafbfc"))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignCenter,
                    {"auto": "◐", "source": "‹›", "definition": "≡"}[block.mode],
                )
        active = (
            self.parameter_editor.slot
            if self.parameter_editor and self.parameter_editor.isVisible()
            else self.hover_parameter
        )
        linked = set(self.linked_parameter_spans(active))
        for slot in self.parameter_slots[
            bisect_left(self.parameter_lines, first_line) : bisect_right(
                self.parameter_lines, last_line
            )
        ]:
            rect = self.parameter_rect(slot)
            if rect is None or not rect.intersects(QRectF(event.rect())):
                continue
            related = any(
                span.start <= slot.span.start and slot.span.end <= span.end
                for span in linked
            )
            issue = bool(self.parameter_issues.get(slot.span))
            painter.setPen(
                QPen(
                    QColor("#b65b18" if issue else "#246c9a" if related else "#9ca7b2"),
                    2 if related or issue else 1,
                )
            )
            painter.setBrush(
                QColor("#fff0cf" if issue else "#cbe6fa" if related else "#f8fafb")
            )
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
                    painter.setBrush(QColor("#76cba3"))
                    painter.drawRoundedRect(rect, 3, 3)
                else:
                    rect.setHeight(self.marker_height())
                    painter.fillRect(rect, QColor("#76cba3"))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QPen(QColor("#207348"), 2))
                    painter.drawRect(rect.adjusted(1, 1, -1, -1))
                    painter.setPen(QColor("#123e2b"))
                    painter.drawText(
                        rect.adjusted(5, 0, -5, 0),
                        Qt.AlignmentFlag.AlignVCenter,
                        "# ↳ " + self.target_label(target),
                    )
        if self.origin_span is not None:
            rect = self.origin_rect()
            if rect:
                painter.fillRect(rect, QColor("#ffe0a1"))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor("#ae6810"), 2))
                painter.drawRect(rect.adjusted(1, 1, -1, -1))
                painter.setPen(QColor("#603900"))
                painter.drawText(
                    rect.adjusted(5, 0, -5, 0),
                    Qt.AlignmentFlag.AlignVCenter,
                    ("" if self.origin_expression else "# ")
                    + "↶ "
                    + tr("Previous position"),
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
            parent = syntax.parent.get(nodes)
            if not isinstance(parent, ast.Expr):
                return syntax.spans[nodes], True
            nodes = parent
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
        shown = self.display.bounds(span)
        first_row, _ = self.display.position(shown.start)
        last_row, _ = self.display.position(max(shown.start, shown.end - 1))
        rect = (
            self._rect(line, column, end_column + 1)
            if expression and end_line == line
            else self._display_rect(first_row, column)
        )
        if rect is None:
            return self.viewport().grab()
        end_line, _ = syntax.position(max(span.start, span.end - 1))
        bottom = (
            self._rect(end_line, column)
            if expression
            else self._display_rect(last_row, column)
        )
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
        shown = self.display.bounds(self.origin_span)
        first = self.display.position(shown.start)[0]
        last = self.display.position(max(shown.start, shown.end - 1))[0]
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
        text = syntax.lines[line - 1]
        row, _ = self.display.position(self.display.bounds(self.origin_span).start)
        return self._display_rect(row, len(text) - len(text.lstrip()))

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
                    self.display.position(self.display.forward(offset))[0],
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
        displayed = self.display.by_span.get(note.span)
        if displayed:
            row, column = self.display.position(displayed.shown.start)
            rect = self._display_rect(
                row, column if displayed.match.snippet.expression else note.column
            )
        else:
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
                -self.source_block(line).blockFormat().topMargin(),
            )
        return rect

    def parameter_rect(self, slot):
        syntax = self.session.document.syntax
        line, column = syntax.position(slot.span.start)
        end, end_column = syntax.position(slot.span.end)
        return self._rect(line, column, end_column) if line == end else None

    def note_at(self, point):
        displayed = self.displayed_block_at(point)
        if displayed and (location := self.note_locations.get(displayed.match.span)):
            rect = self.note_rect(*location)
            if rect and rect.contains(QPointF(point)):
                return self.notes[location[0]][location[1]]
        line = self.source_line_at(point)
        for row in (line, line + 1):
            for index, note in enumerate(self.notes.get(row, ())):
                rect = self.note_rect(row, index)
                if rect:
                    rect.setLeft(self._rect(row, 0).left())
                    if rect.contains(QPointF(point)):
                        return note
        return None

    def node_at(self, point):
        syntax = self.session.document.syntax
        note = self.note_at(point)
        if note:
            return next(
                (node for node, span in syntax.spans.items() if span == note.span),
                syntax.at(note.span.start),
            )
        return syntax.at(self.offset_at(point))

    def parameter_at(self, point):
        if self.note_at(point):
            return None
        line = self.source_line_at(point)
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

    def linked_parameter_spans(self, slot):
        if slot is None or slot.syntax is not self.session.document.syntax:
            return ()
        if slot.match is None:
            return (slot.span,)
        nodes = slot.match.occurrences.get(slot.parameter.name, ())
        return tuple(slot.syntax.spans[node] for node in nodes) or (slot.span,)

    def parameter_tip(self, slot):
        name = slot.parameter.name
        count = len(self.linked_parameter_spans(slot))
        if count > 1:
            name = tr("{name} · {count} uses", name=name, count=count)
        unit = unit_text(slot.parameter.annotation)
        contract = slot.parameter.annotation or "Python"
        detail = name + " · " + (unit or contract)
        issues = self.parameter_issues.get(slot.span, ())
        if issues:
            detail += "\n" + "\n".join(issues)
            if isinstance(slot.node, ast.Name):
                scope = self.session.analysis.resolve(slot.node, slot.node.id)
                offset = scope.bindings.get(slot.node.id) if scope else None
                if offset is not None and offset > slot.span.start:
                    detail += "\n" + tr(
                        "Defined later at line {line}.",
                        line=slot.syntax.position(offset)[0],
                    )
                if offset is None or offset > slot.span.start:
                    detail += "\n" + tr(
                        "Create the value before this block, in a scope visible here."
                    )
        if slot.binding:
            return detail
        return (
            detail + "\n" + tr("Right-click: choose a value or find a creation block.")
        )

    def search_input(self, slot, providers=False):
        if slot.syntax is not self.session.document.syntax:
            return
        self.session.editor.selection = slot.node
        self.selected.emit()
        self.input_search_requested.emit(self, slot, providers)

    def target_label(self, target):
        suite = target.suite
        if target.index:
            previous = suite.statements[target.index - 1]
            if isinstance(previous, (ast.For, ast.While, ast.AsyncFor)):
                return tr("After loop")
            if isinstance(previous, ast.If):
                return tr("After condition")
        if isinstance(suite.owner, (ast.For, ast.While, ast.AsyncFor)):
            return (
                tr("Inside loop") if suite.field == "body" else tr("Inside loop else")
            )
        if isinstance(suite.owner, ast.If):
            return (
                tr("Inside condition") if suite.field == "body" else tr("Inside else")
            )
        if isinstance(suite.owner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return tr("Inside function")
        return (
            tr("At program level")
            if isinstance(suite.owner, ast.Module)
            else tr("Inside block")
        )

    def show_parameter(self, slot):
        if empty(slot.node):
            self.session.editor.selection = slot.node
            self.choose_expression()
            return
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
        self.viewport().update()

    def finish_parameter(self):
        field = self.parameter_editor
        return field is None or field.apply(focus=False)

    def edit_parameters(self):
        syntax = self.session.document.syntax
        match = self.session.selected_match()
        if (
            match
            and not match.snippet.historical
            and (
                match.snippet.advanced
                or match.snippet.family
                or any(
                    s.family == match.snippet.identity
                    for s in self.session.available_snippets
                )
            )
        ):
            self.edit_variant()
            return
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

    def edit_variant(self):
        from .variants import VariantDialog

        try:
            dialog = VariantDialog(self)
        except (ValueError, SyntaxError) as error:
            self.failed.emit(str(error))
            return
        accepted = dialog.exec()
        dialog.deleteLater()
        if accepted:
            self.refresh_source()
            self.changed.emit()
            self.reveal_selection()

    def mode_rect(self, block):
        if block.match.snippet.mode == "function":
            return None
        selected = self.session.document.syntax.spans[self.session.editor.selection]
        span = block.match.span
        if block.mode == "auto" and not any(
            value and span.start <= value.start and value.end <= span.end
            for value in (self.hover, selected)
        ):
            return None
        if location := self.note_locations.get(block.match.span):
            rect = self.note_rect(*location)
            if rect:
                rect.setLeft(rect.right() - 26)
            return rect
        return None

    def mode_at(self, point):
        note = self.note_at(point)
        block = (
            self.display.by_span.get(note.span)
            if note
            else self.displayed_block_at(point)
        )
        if block and (rect := self.mode_rect(block)) and rect.contains(QPointF(point)):
            return block
        return None

    def set_display_mode(self, block, mode):
        if mode not in {"auto", "source", "definition"}:
            raise ValueError("Unknown block display mode")
        key = (block.match.span.start, block.match.snippet.identity)
        if mode == "auto":
            self.display_modes.pop(key, None)
        else:
            self.display_modes[key] = mode
        self.refresh_source()
        self.layout_changed.emit()

    def cycle_display_mode(self, block):
        modes = ("auto", "source", "definition")
        self.set_display_mode(block, modes[(modes.index(block.mode) + 1) % len(modes)])

    def reveal_selection(self):
        span = self.session.document.syntax.spans[self.session.editor.selection]
        self.reveal(span.start)
        self.selected.emit()
        self.viewport().update()

    def choose_expression(self, *, wrap=False):
        from .expressions import ExpressionChooser

        if not public(self.session, self.session.editor.selection):
            return
        if self.parameter_editor:
            self.parameter_editor.close()
        if self.expression_popup:
            self.expression_popup.close()
        self.expression_popup = popup = ExpressionChooser(self, wrap=wrap)
        popup.destroyed.connect(
            lambda: (
                setattr(self, "expression_popup", None)
                if self.expression_popup is popup
                else None
            )
        )
        span = self.session.document.syntax.spans[self.session.editor.selection]
        line, column = self.session.document.syntax.position(span.start)
        point = self.viewport().mapToGlobal(
            self._rect(line, column).bottomLeft().toPoint()
        )
        screen = self.screen().availableGeometry()
        point.setX(max(screen.left(), min(point.x(), screen.right() - popup.width())))
        point.setY(max(screen.top(), min(point.y(), screen.bottom() - popup.height())))
        popup.move(point)
        popup.show()

    def select_statement(self):
        if self.parameter_editor:
            self.parameter_editor.close()
        if self.expression_popup:
            self.expression_popup.close()
        try:
            self.session.editor.selection = self.session.editor.statement()
        except ValueError:
            self.session.editor.selection = self.session.document.syntax.tree
        self.setFocus()
        self.reveal_selection()

    def delete_selection(self):
        if self.session.editor.selection is self.session.document.syntax.tree:
            return
        try:
            self.session.editor.commit(self.session.extract_selection()[1])
            self.refresh_source()
            self.changed.emit()
        except (ValueError, SyntaxError, OSError) as error:
            self.failed.emit(str(error))

    def keyPressEvent(self, event):
        key, modifiers = event.key(), event.modifiers()
        if key == Qt.Key.Key_Escape:
            self.cancel_interaction()
            return
        if key == Qt.Key.Key_Delete and not modifiers:
            self.delete_selection()
            return
        if (
            modifiers & Qt.KeyboardModifier.ControlModifier
            and key in (Qt.Key.Key_C, Qt.Key.Key_V)
            and public(self.session, self.session.editor.selection)
        ):
            node = self.session.editor.selection
            if key == Qt.Key.Key_C:
                QApplication.clipboard().setText(
                    self.session.document.syntax.text(node)
                )
            else:
                try:
                    compose(self.session, Proposal("", QApplication.clipboard().text()))
                    self.refresh_source()
                    self.changed.emit()
                    self.reveal_selection()
                except (ValueError, SyntaxError) as error:
                    self.failed.emit(str(error))
            return
        if key == Qt.Key.Key_Space and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.choose_expression(
                wrap=bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
            )
            return
        if key in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            navigate(self.session, "previous" if key == Qt.Key.Key_Backtab else "next")
            self.reveal_selection()
            return
        if modifiers & Qt.KeyboardModifier.AltModifier and key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
        ):
            navigate(self.session, "parent" if key == Qt.Key.Key_Left else "child")
            self.reveal_selection()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.choose_expression()
            return
        if event.text() in ("+", "-", "*", "/", "%", "<", ">", "&", "|") and public(
            self.session, self.session.editor.selection
        ):
            try:
                compose(
                    self.session,
                    Proposal(
                        event.text(),
                        operation=Operation(event.text(), f"$ {event.text()} {EMPTY}"),
                    ),
                    wrap=True,
                )
                self.refresh_source()
                self.changed.emit()
                self.reveal_selection()
            except (ValueError, SyntaxError) as error:
                self.failed.emit(str(error))
            return
        super().keyPressEvent(event)

    def focusNextPrevChild(self, next):
        # Qt also traverses focus when an inline field closes. Only keyboard
        # traversal from this view should move the structural selection.
        if not self.hasFocus():
            return super().focusNextPrevChild(next)
        navigate(self.session, "next" if next else "previous")
        self.reveal_selection()
        return True

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.finish_parameter():
                event.accept()
                return
            self.setFocus()
            point = event.position().toPoint()
            block = self.mode_at(point)
            if block:
                self.cycle_display_mode(block)
                return
            self.pending_parameter = self.parameter_at(point)
            self.press_position = point
            syntax = self.session.document.syntax
            node = self.node_at(point)
            self.session.editor.selection = (
                node
                if self.note_at(point)
                or self.pending_parameter
                or public(self.session, node)
                else next(
                    (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), node
                )
            )
            self.selected.emit()
            self.viewport().update()
            if self.pending_parameter:
                self.structure_bar.hide()
            else:
                self.structure_bar.activate(point)

    def contextMenuEvent(self, event):
        menu = block_menu(self, event.pos())
        if not menu.isEmpty():
            menu.exec(event.globalPos())
        menu.deleteLater()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "structure_bar") and self.structure_bar.isVisible():
            self.structure_bar.place()

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
                    self.structure_bar.hide()
                    drag_block(self, transfer)
                    return
                except (ValueError, SyntaxError) as error:
                    self.press_position = self.pending_parameter = None
                    self.failed.emit(str(error))
        else:
            syntax = self.session.document.syntax
            node = self.node_at(point)
            expression = public(self.session, node) and not self.note_at(point)
            if not self.note_at(point) and not expression:
                node = next(
                    (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), node
                )
            displayed = self.displayed_block_at(point)
            match = displayed.match if displayed else self.session.enclosing_match(node)
            self.hover = (
                syntax.spans[node]
                if expression
                else match.span if match else syntax.spans[node]
            )
            self.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor
                if self.parameter_at(point)
                else Qt.CursorShape.OpenHandCursor
            )
            parameter = self.parameter_at(point)
            self.hover_parameter = parameter
            self.setToolTip(
                self.parameter_tip(parameter)
                if parameter
                else (
                    tr(match.snippet.help).splitlines()[0]
                    if match and match.snippet.help
                    else type(node).__name__
                )
            )
            block = self.mode_at(point)
            if block:
                self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
                label = (
                    tr("Program comments")
                    if block.effective == "source"
                    else tr("Definition comments")
                )
                self.setToolTip(
                    tr("Auto: {mode}", mode=label) if block.mode == "auto" else label
                )
        self.viewport().update()

    def target_coordinates(self, point):
        line = self.source_line_at(point)
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

    def cancel_interaction(self):
        cancel_drag()
        self.press_position = self.pending_parameter = None
        self.session.editor.cancel_move()
        self.dragLeaveEvent(None)
        self.select_statement()

    def dragEnterEvent(self, event):
        self.structure_bar.hide()
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
        elif data.hasFormat("application/x-little-tinker-rig-snippet"):
            identity = bytes(
                data.data("application/x-little-tinker-rig-snippet")
            ).decode()
            self.drop_snippet = next(
                (
                    s
                    for s in self.session.available_snippets
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
            replacing = (
                self.drop_snippet is not None
                and self.input_target is not None
                and self.input_target.syntax is syntax
                and self.input_target.node is node
            )
            if node is not None and not slot.binding and (empty(node) or replacing):
                candidate = node
        else:
            candidate = self.pointer_target(point)
        if candidate is not None and candidate not in self.drop_validity:
            try:
                if not self.session.accepts_target(candidate):
                    raise ValueError(
                        "Expand the block to edit its fixed implementation"
                    )
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
                    from little_tinker_rig.core.types import known_type, numeric_literal

                    actual = known_type(
                        self.drop_snippet.result_type
                        if self.drop_snippet
                        else self.drop_transfer.result_type
                    )
                    literal = numeric_literal(ast.parse(text.strip(), mode="eval").body)
                    if not accepts(self.session, candidate, actual, literal=literal):
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
        last = self.document().lastBlock()
        while not last.isVisible() and last.previous().isValid():
            last = last.previous()
        rect = self.cursorRect(QTextCursor(last))
        # The visual tail is outside the final compound, independent of x.
        # Its body still accepts drops over the lower half of its last row.
        if point.y() > rect.bottom() or (
            not last.text().strip() and point.y() >= rect.top()
        ):
            suite = next(s for s in syntax.suites if s.owner is syntax.tree)
            return edit.Target(suite, len(suite.statements))
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
        self.hover_parameter = None
        self.viewport().update()
        super().leaveEvent(event)

    def showEvent(self, event):
        self.pulse.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self.pulse.stop()
        if self.parameter_editor and self.parameter_editor.completer:
            self.parameter_editor.completer.popup().hide()
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
            row
            for first, last in self.folded
            for row in range(
                self.source_block(first).blockNumber() + 2,
                self.source_block(last).blockNumber() + 2,
            )
        }
        block = self.document().firstBlock()
        while block.isValid():
            visible = block.blockNumber() + 1 not in hidden
            block.setVisible(visible)
            block.setLineCount(1 if visible else 0)
            block = block.next()
        self.document().markContentsDirty(0, self.document().characterCount())
        self.viewport().update()
