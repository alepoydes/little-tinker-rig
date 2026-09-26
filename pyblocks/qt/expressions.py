"""Local search for structural expression construction, with optional text entry."""

import ast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
)

from pyblocks.core.expressions import Proposal, compose, proposals
from pyblocks.core.types import numeric_literal
from pyblocks.i18n import tr


class ExpressionChooser(QDialog):
    def __init__(self, view, *, wrap=False):
        super().__init__(view, Qt.WindowType.Popup)
        self.view = view
        self.syntax = view.session.document.syntax
        self.node = view.session.editor.selection
        self.options = {}
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle(tr("Compose expression"))
        layout = QVBoxLayout(self)
        self.mode = QComboBox()
        self.mode.addItems((tr("Replace expression"), tr("Wrap expression")))
        self.mode.setCurrentIndex(int(wrap))
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Search operations, names and blocks…"))
        self.results = QListWidget()
        self.message = QLabel()
        self.message.setWordWrap(True)
        layout.addWidget(self.mode)
        layout.addWidget(self.search)
        layout.addWidget(self.results)
        layout.addWidget(self.message)
        self.search.textChanged.connect(self.refresh)
        self.search.returnPressed.connect(self.apply)
        self.results.itemActivated.connect(self.apply)
        self.mode.currentIndexChanged.connect(self.refresh)
        self.resize(440, 360)
        self.refresh()

    def refresh(self, *_):
        if self.syntax is not self.view.session.document.syntax:
            self.close()
            return
        self.view.session.editor.selection = self.node
        wrap = bool(self.mode.currentIndex())
        if wrap not in self.options:
            self.options[wrap] = proposals(
                self.view.session, self.view.expression_level, wrap=wrap
            )
        words = self.search.text().casefold().split()
        self.entries = [
            p
            for p in self.options[wrap]
            if all(
                w
                in (
                    tr(p.label) + " " + (p.snippet.identity if p.snippet else "")
                ).casefold()
                for w in words
            )
        ]
        text = self.search.text().strip()
        self.entries.sort(
            key=lambda p: (p.source != text, tr(p.label).casefold() != text.casefold())
        )
        if text and not self.mode.currentIndex():
            try:
                expression = ast.parse(text, mode="eval").body
            except SyntaxError:
                pass
            else:
                proposal = Proposal(tr("Use Python: {text}", text=text), text)
                if isinstance(expression, ast.Constant) or numeric_literal(expression):
                    self.entries.insert(0, proposal)
                elif not any(p.source == text for p in self.entries):
                    self.entries.append(proposal)
        self.results.clear()
        for entry in self.entries:
            label = tr(entry.label).splitlines()[0]
            self.results.addItem(label)
            self.results.item(self.results.count() - 1).setToolTip(tr(entry.label))
        if self.entries:
            self.results.setCurrentRow(0)

    def apply(self, *_):
        index = self.results.currentRow()
        if not 0 <= index < len(self.entries):
            return
        try:
            if self.syntax is not self.view.session.document.syntax:
                raise ValueError(tr("Document changed; choose the expression again"))
            self.view.session.editor.selection = self.node
            compose(
                self.view.session,
                self.entries[index],
                wrap=bool(self.mode.currentIndex()),
            )
            self.view.refresh_source()
            self.view.changed.emit()
        except (ValueError, SyntaxError, OSError) as error:
            self.message.setText(str(error))
            return
        self.close()
        self.view.setFocus()
        self.view.reveal_selection()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            delta = 1 if event.key() == Qt.Key.Key_Down else -1
            self.results.setCurrentRow(
                max(0, min(self.results.count() - 1, self.results.currentRow() + delta))
            )
            return
        super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.search.setFocus()
