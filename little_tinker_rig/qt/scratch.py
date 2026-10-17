"""Visible, independent fragment cells sharing their owner's undo transaction."""

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from little_tinker_rig.core.edit import target_position
from little_tinker_rig.core.parameters import default_bindings
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.transfer import Transfer
from little_tinker_rig.i18n import N_, tr

from .code import CodeEdit
from .drag import BlockMime, drag_block
from .editor import SourceView
from .find import FindBar
from .localization import localize


class Grip(QLabel):
    def __init__(self, cell):
        super().__init__("⠿", cell)
        self.cell = cell
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(N_("Drag the whole fragment into the program or another cell"))
        self.setStyleSheet("font-size: 20px; color: #65788a; padding: 2px 8px")
        self.press = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.press = event.position().toPoint()

    def mouseMoveEvent(self, event):
        if self.press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if (
                event.position().toPoint() - self.press
            ).manhattanLength() >= QApplication.startDragDistance():
                self.press = None
                drag_block(
                    self.cell,
                    Transfer.capture(self.cell.pane.session, index=self.cell.index),
                )


class ScratchCell(QFrame):
    mode_changed = Signal()

    def __init__(self, pane, index, text):
        super().__init__()
        self.pane, self.index, self.text = pane, index, text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setObjectName("scratchCell")
        self.setStyleSheet(
            "#scratchCell { background: #fafbfc; border: 1px solid #ccd5df; border-radius: 7px; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        row = QHBoxLayout()
        row.addWidget(Grip(self))
        row.addStretch()
        self.blocks_button = QToolButton()
        self.blocks_button.setText("▦")
        self.blocks_button.setToolTip(N_("Blocks"))
        self.code_button = QToolButton()
        self.code_button.setText("</>")
        self.code_button.setToolTip("Python")
        for button in (self.blocks_button, self.code_button):
            button.setCheckable(True)
            row.addWidget(button)
        self.blocks_button.clicked.connect(lambda: self.change_mode(False))
        self.code_button.clicked.connect(lambda: self.change_mode(True))
        layout.addLayout(row)
        self.code = CodeEdit()
        self.code.setAcceptDrops(False)
        self.code.setPlainText(text)
        self.code.textChanged.connect(self.text_changed)
        self.source = SourceView(Session.fragment("", pane.session.snippets))
        self.source.scratch_owner = pane.session
        self.source.scratch_index = index
        self.source.changed.connect(self.structural_changed)
        self.source.transferred.connect(pane.changed)
        self.source.layout_changed.connect(self.fit)
        self.source.failed.connect(pane.failed)
        self.source.snippet_dropped.connect(self.insert_snippet)
        self.source.definition_requested.connect(pane.definition_requested)
        self.source.help_requested.connect(pane.help_requested)
        self.source.input_search_requested.connect(pane.input_search_requested)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.source)
        self.stack.addWidget(self.code)
        self.origin_marker = QLabel()
        self.origin_marker.setStyleSheet(
            "background: #ffe0a1; color: #804900; border: 2px solid #ae6810; padding: 5px"
        )
        self.stack.addWidget(self.origin_marker)
        self.whole_drag = False
        self.finder = FindBar(lambda: self.code if self.code_active else self.source)
        self.finder.visibility_changed.connect(self.fit)
        self.find_bar = self.finder.query
        layout.addWidget(self.finder)
        layout.addWidget(self.stack)
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet("color: #a03d39; padding: 4px")
        self.error.hide()
        layout.addWidget(self.error)
        self.code_active = True
        self.change_mode(False)
        localize(self)

    def change_mode(self, code):
        if not self.source.finish_parameter():
            return
        if not code:
            try:
                self.source.session = Session.fragment(
                    self.text, self.pane.session.snippets
                )
                self.source.session.context = self.pane.session
                self.source.refresh_source()
            except (SyntaxError, ValueError) as error:
                code = True
                self.error.setText(str(error))
                self.error.show()
        else:
            self.code.blockSignals(True)
            self.code.replace_formatted(self.text)
            self.code.blockSignals(False)
        self.code_active = code
        self.stack.setCurrentIndex(int(code))
        self.blocks_button.setChecked(not code)
        self.code_button.setChecked(code)
        if not code:
            self.error.hide()
        self.fit()
        (self.code if code else self.source).setFocus()
        self.mode_changed.emit()

    def show_drag_origin(self, transfer):
        self.whole_drag = True
        self.origin_marker.setText("# ↶ " + tr("Previous position"))
        self.stack.setCurrentWidget(self.origin_marker)
        self.fit()

    def hide_drag_origin(self):
        self.whole_drag = False
        self.stack.setCurrentIndex(int(self.code_active))
        self.fit()

    def fit(self):
        editor = self.code if self.code_active else self.source
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        if self.code_active:
            height = (
                editor.fontMetrics().lineSpacing()
                * max(3, editor.document().blockCount())
                + 24
            )
        else:
            height = (
                math.ceil(editor.document().documentLayout().documentSize().height())
                + 18
            )
        minimum = 36 if editor is self.source and editor.origin_span is not None else 76
        editor.setFixedHeight(max(minimum, height))
        self.stack.setFixedHeight(
            self.source.marker_height() + 10
            if self.whole_drag
            else max(minimum, height)
        )
        self.layout().activate()
        self.setFixedHeight(self.layout().sizeHint().height())
        self.pane.column.activate()

    def text_changed(self):
        self.text = self.code.toPlainText()
        self.pane.session.set_scratch(self.index, self.text)
        self.fit()
        self.pane.changed.emit()

    def structural_changed(self):
        text = self.source.session.document.state.source
        self.source.refresh_source()
        if text != self.text:
            self.text = text
            self.pane.session.set_scratch(self.index, text)
            self.pane.changed.emit()
        self.fit()

    def insert_snippet(self, identity, target=None):
        try:
            snippet = self.pane.catalog_snippet(identity)
            syntax = self.source.session.document.syntax
            offset = (
                target_position(syntax, target)[0]
                if target
                else syntax.spans[self.source.session.editor.selection].start
            )
            self.source.session.insert_snippet(
                snippet, default_bindings(self.source.session, snippet, offset), target
            )
            self.structural_changed()
            self.pane.snippet_inserted.emit(identity)
        except (ValueError, SyntaxError) as error:
            self.pane.failed.emit(str(error))


class ScratchPane(QScrollArea):
    block_drop_target = True
    changed = Signal()
    failed = Signal(str)
    definition_requested = Signal(object)
    help_requested = Signal(str)
    input_search_requested = Signal(object, object, bool)
    snippet_inserted = Signal(str)

    def __init__(self):
        super().__init__()
        self.session = None
        self.allowed_ids = None
        self.cells = []
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(220)
        self.content = QWidget()
        self.column = QVBoxLayout(self.content)
        self.column.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        self.column.setContentsMargins(8, 8, 8, 8)
        self.column.setSpacing(10)
        self.empty = QLabel(
            tr(
                "Drag a block here to set it aside.\nReturn it to the program when you need it."
            )
        )
        self.empty.setWordWrap(True)
        self.empty.setStyleSheet("color: #6a7989; padding: 12px; line-height: 150%")
        self.column.addWidget(self.empty)
        self.column.addStretch()
        self.setWidget(self.content)
        self.drop_position = None
        self.drop_padding = None
        self.indicator = QLabel(self.content)
        self.indicator.setStyleSheet(
            "background: #76cba3; color: #123e2b; padding: 7px; border: 2px solid #207348"
        )
        self.indicator.hide()

    def refresh(self, session):
        if self.session is not session:
            for cell in self.cells:
                self.column.removeWidget(cell)
                cell.deleteLater()
            self.cells = []
            self.session = session
        texts = session.document.state.scratch
        while len(self.cells) > len(texts):
            cell = self.cells.pop()
            self.column.removeWidget(cell)
            cell.deleteLater()
        for index, text in enumerate(texts):
            if index < len(self.cells) and self.cells[index].text == text:
                view = self.cells[index].source
                if view.session.snippets is not session.snippets:
                    view.session.set_snippets(session.snippets)
                view.refresh_source()
                self.cells[index].fit()
                continue
            cell = ScratchCell(self, index, text)
            cell.mode_changed.connect(self.changed)
            if index < len(self.cells):
                old = self.cells[index]
                self.column.removeWidget(old)
                old.deleteLater()
                self.cells[index] = cell
            else:
                self.cells.append(cell)
            self.column.insertWidget(index, cell)
        self.empty.setVisible(not self.cells)
        self.empty.setText(
            tr(
                "Drag a block here to set it aside.\nReturn it to the program when you need it."
            )
        )

    def focused_cell(self):
        focus = QApplication.focusWidget()
        return next(
            (cell for cell in self.cells if cell is focus or cell.isAncestorOf(focus)),
            None,
        )

    def dragEnterEvent(self, event):
        data = event.mimeData()
        if (
            isinstance(data, BlockMime)
            and data.transfer.owner is self.session
            or data.hasFormat("application/x-little-tinker-rig-snippet")
        ):
            if isinstance(data, BlockMime):
                try:
                    data.transfer.validate()
                except ValueError:
                    event.ignore()
                    return
            if self.drop_padding is None:
                self.drop_padding = self.column.contentsMargins()
                margins = self.column.contentsMargins()
                margins.setBottom(self.viewport().height() + 40)
                self.column.setContentsMargins(margins)
                self.column.activate()
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        point = self.content.mapFrom(self.viewport(), event.position().toPoint())
        if self.indicator.isVisible() and self.indicator.geometry().contains(point):
            event.acceptProposedAction()
            return
        position = next(
            (
                i
                for i, cell in enumerate(self.cells)
                if point.y() < cell.geometry().center().y()
            ),
            len(self.cells),
        )
        if position != self.drop_position:
            anchor = next(
                (cell for cell in self.cells if cell.geometry().bottom() >= point.y()),
                None,
            )
            y = (
                anchor.mapTo(self.viewport(), anchor.rect().topLeft()).y()
                if anchor
                else 0
            )
            self.column.removeWidget(self.indicator)
            self.drop_position = position
            index = (
                self.column.indexOf(self.cells[position])
                if position < len(self.cells)
                else self.column.count() - 1
            )
            self.column.insertWidget(index, self.indicator)
            self.indicator.setText("# ↳ " + tr("Insert here"))
            self.indicator.show()
            self.column.activate()
            if anchor:
                self.verticalScrollBar().setValue(
                    self.verticalScrollBar().value()
                    + anchor.mapTo(self.viewport(), anchor.rect().topLeft()).y()
                    - y
                )
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_position = None
        self.column.removeWidget(self.indicator)
        self.indicator.hide()
        if self.drop_padding is not None:
            self.column.setContentsMargins(self.drop_padding)
            self.drop_padding = None
            self.column.activate()

    def catalog_snippet(self, identity):
        if self.allowed_ids is not None and identity not in self.allowed_ids:
            raise ValueError(
                tr(
                    "This block is outside the current lesson palette. Enable Show all blocks to use it."
                )
            )
        for snippet in self.session.available_snippets:
            if snippet.identity == identity and not snippet.historical:
                return snippet
        raise ValueError(tr("This block is no longer available."))

    def dropEvent(self, event):
        position = len(self.cells) if self.drop_position is None else self.drop_position
        self.dragLeaveEvent(event)
        try:
            data = event.mimeData()
            if isinstance(data, BlockMime):
                if data.transfer.owner is not self.session:
                    raise ValueError("Choose a fragment from this document")
                data.transfer.to_scratch(position)
            else:
                identity = bytes(
                    data.data("application/x-little-tinker-rig-snippet")
                ).decode()
                snippet = self.catalog_snippet(identity)
                expansion = self.session.expand_snippet(
                    snippet, default_bindings(self.session, snippet)
                )
                items = list(self.session.document.state.scratch)
                items.insert(position, expansion.source)
                self.session.editor.commit(
                    self.session.document.state.source, tuple(items)
                )
                self.snippet_inserted.emit(identity)
            event.acceptProposedAction()
            self.changed.emit()
        except (ValueError, SyntaxError) as error:
            self.failed.emit(str(error))
            event.ignore()
        self.drop_position = None
        self.viewport().update()
