"""Visible, independent fragment cells sharing their owner's undo transaction."""

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pyblocks.core.parameters import default_bindings
from pyblocks.core.session import Session
from pyblocks.core.snippets import instantiate
from pyblocks.core.transfer import Transfer
from pyblocks.i18n import N_, tr

from .code import CodeEdit
from .drag import BlockMime, drag_block
from .editor import SourceView
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
        self.source.failed.connect(pane.failed)
        self.source.snippet_dropped.connect(self.insert_snippet)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.source)
        self.stack.addWidget(self.code)
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
            self.code.setPlainText(self.text)
            self.code.blockSignals(False)
        self.code_active = code
        self.stack.setCurrentIndex(int(code))
        self.blocks_button.setChecked(not code)
        self.code_button.setChecked(code)
        if not code:
            self.error.hide()
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
        editor.setFixedHeight(max(76, height))
        self.stack.setFixedHeight(max(76, height))

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
        snippet = next(
            s for s in self.source.session.snippets if s.identity == identity
        )
        try:
            self.source.session.insert_snippet(
                snippet, default_bindings(self.source.session, snippet), target
            )
            self.structural_changed()
        except (ValueError, SyntaxError) as error:
            self.pane.failed.emit(str(error))


class ScratchPane(QScrollArea):
    changed = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.session = None
        self.cells = []
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumWidth(220)
        self.content = QWidget()
        self.column = QVBoxLayout(self.content)
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
                self.cells[index].source.refresh_source()
                self.cells[index].fit()
                continue
            cell = ScratchCell(self, index, text)
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
            or data.hasFormat("application/x-pyblocks-snippet")
        ):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        point = self.content.mapFrom(self.viewport(), event.position().toPoint())
        self.drop_position = next(
            (
                i
                for i, cell in enumerate(self.cells)
                if point.y() < cell.geometry().center().y()
            ),
            len(self.cells),
        )
        event.acceptProposedAction()
        self.viewport().update()

    def dragLeaveEvent(self, event):
        self.drop_position = None
        self.viewport().update()

    def dropEvent(self, event):
        position = len(self.cells) if self.drop_position is None else self.drop_position
        try:
            data = event.mimeData()
            if isinstance(data, BlockMime):
                if data.transfer.owner is not self.session:
                    raise ValueError("Choose a fragment from this document")
                data.transfer.to_scratch(position)
            else:
                identity = bytes(data.data("application/x-pyblocks-snippet")).decode()
                snippet = next(
                    s
                    for s in self.session.snippets
                    if s.identity == identity and not s.historical
                )
                expansion = instantiate(
                    snippet, default_bindings(self.session, snippet)
                )
                items = list(self.session.document.state.scratch)
                items.insert(position, expansion.source)
                self.session.editor.commit(
                    self.session.document.state.source, tuple(items)
                )
            event.acceptProposedAction()
            self.changed.emit()
        except (ValueError, SyntaxError) as error:
            self.failed.emit(str(error))
            event.ignore()
        self.drop_position = None
        self.viewport().update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drop_position is None:
            return
        y = (
            self.cells[self.drop_position].y() - 5
            if self.drop_position < len(self.cells)
            else self.cells[-1].geometry().bottom() + 5 if self.cells else 8
        )
        y = self.content.mapTo(self.viewport(), self.content.rect().topLeft()).y() + y
        painter = QPainter(self.viewport())
        painter.setPen(QPen(QColor("#277c63"), 3))
        painter.drawLine(8, y, self.viewport().width() - 8, y)
