"""Compact list controls and explicit expression operations over the core index."""

import ast

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
)

from pyblocks.core.structure import sequence
from pyblocks.i18n import tr


class StructureBar(QWidget):
    def __init__(self, view):
        super().__init__(view.viewport())
        self.view = view
        self.sequences = []
        self.offset = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 1, 2, 1)
        layout.setSpacing(1)
        self.choice = QComboBox()
        self.choice.setMaximumWidth(160)
        layout.addWidget(self.choice)
        self.choice.currentIndexChanged.connect(self.update_actions)
        self.buttons = {}
        for action, symbol, title in (
            ("insert", "+", tr("Add item")),
            ("remove", "−", tr("Remove item")),
            ("left", "←", tr("Move item left")),
            ("right", "→", tr("Move item right")),
        ):
            button = QToolButton()
            button.setText(symbol)
            button.setToolTip(title)
            button.clicked.connect(
                lambda checked=False, action=action: self.change(action)
            )
            if action == "insert":
                menu = QMenu(button)
                menu.addAction(
                    tr("Insert before selected item"),
                    lambda: self.change("insert_before"),
                )
                button.setMenu(menu)
                button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
            layout.addWidget(button)
            self.buttons[action] = button
        self.setStyleSheet(
            "StructureBar { background: #f8fafc; border: 1px solid #617187; }"
        )
        self.hide()

    def activate(self, point):
        syntax = self.view.session.document.syntax
        node = self.view.node_at(point)
        if isinstance(node, ast.Expr):
            node = node.value
        self.offset = (
            syntax.spans[node].start
            if self.view.note_at(point)
            else self.view.offset_at(point)
        )
        self.sequences = []
        labels = []
        for owner in syntax.ancestors(node):
            if not isinstance(
                owner, (ast.Call, ast.BoolOp, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            if self.view.session.simplified_range(owner):
                continue
            if not self.view.session.editable(owner, "sequence"):
                continue
            item = sequence(syntax, owner)
            self.sequences.append(item)
            labels.append(
                tr("Parameters: {name}", name=owner.name)
                if item.kind == "parameters"
                else (
                    tr(
                        "Operands: {operator}",
                        operator="and" if isinstance(owner.op, ast.And) else "or",
                    )
                    if item.kind == "operands"
                    else tr("Arguments: {name}", name=ast.unparse(owner.func))
                )
            )
        self.choice.blockSignals(True)
        self.choice.clear()
        self.choice.addItems(labels)
        self.choice.blockSignals(False)
        if not self.sequences:
            self.hide()
            return
        self.update_actions()
        self.adjustSize()
        line = self.view.cursorForPosition(point).blockNumber() + 1
        rect = self.view._rect(line, 0)
        self.move(
            max(0, self.view.viewport().width() - self.width() - 5),
            max(
                0,
                min(
                    int(rect.bottom() + 2),
                    self.view.viewport().height() - self.height(),
                ),
            ),
        )
        self.show()
        self.raise_()

    def current(self):
        index = self.choice.currentIndex()
        return self.sequences[index] if 0 <= index < len(self.sequences) else None

    def item_index(self, seq):
        return next(
            (i for i, span in enumerate(seq.items) if span.contains(self.offset)), -1
        )

    def update_actions(self, *_):
        seq = self.current()
        if seq is None:
            return
        index = self.item_index(seq)
        self.buttons["remove"].setEnabled(index >= 0 and len(seq.items) > seq.minimum)
        self.buttons["left"].setEnabled(index > 0)
        self.buttons["right"].setEnabled(0 <= index < len(seq.items) - 1)

    def change(self, action):
        seq = self.current()
        if seq is None:
            return
        index = self.item_index(seq)
        text = None
        if action in {"insert", "insert_before"}:
            index = (
                max(0, index)
                if action == "insert_before"
                else index + 1 if index >= 0 else len(seq.items)
            )
            action = "insert"
            text, accepted = QInputDialog.getText(
                self.view,
                tr("Add item"),
                (
                    tr("Parameter (name, optionally = default)")
                    if seq.kind == "parameters"
                    else tr("Python expression or named argument")
                ),
                text="parameter" if seq.kind == "parameters" else "None",
            )
            if not accepted:
                return
        try:
            if seq.syntax is not self.view.session.document.syntax:
                raise ValueError(tr("Document changed; choose the list again"))
            self.view.session.change_sequence(seq, index, action, text)
            self.view.refresh_source()
            self.view.changed.emit()
        except (ValueError, SyntaxError) as error:
            QMessageBox.warning(self.view, tr("Cannot change this list"), str(error))


def expression_menu(view, point):
    syntax = view.session.document.syntax
    node = view.node_at(point)
    menu = QMenu(view)

    def replace(owner, text):
        try:
            if syntax is not view.session.document.syntax:
                raise ValueError(tr("Document changed; choose the expression again"))
            view.session.replace_expression(owner, text)
            view.refresh_source()
            view.changed.emit()
        except (ValueError, SyntaxError) as error:
            QMessageBox.warning(view, tr("Cannot change this expression"), str(error))

    def edit_expression(owner):
        text, accepted = QInputDialog.getMultiLineText(
            view, tr("Edit expression"), tr("Python expression"), syntax.text(owner)
        )
        if accepted:
            replace(owner, text)

    for owner in syntax.ancestors(node):
        if not isinstance(owner, ast.expr) or not view.session.editable(owner):
            continue
        text = syntax.text(owner)
        submenu = menu.addMenu(text[:65] + ("…" if len(text) > 65 else ""))
        submenu.addAction(
            tr("Edit expression"), lambda owner=owner: edit_expression(owner)
        )
        submenu.addAction(
            tr("Clear expression"), lambda owner=owner: replace(owner, "None")
        )
        wrap = submenu.addMenu(tr("Wrap expression"))
        for operation in (
            "({value}) and None",
            "({value}) or None",
            "not ({value})",
            "({value}) + None",
            "({value}) - None",
            "({value}) * None",
            "({value}) / None",
            "({value}) == None",
            "({value}) < None",
            "({value}) > None",
        ):
            wrap.addAction(
                operation.format(value="…"),
                lambda owner=owner, operation=operation: replace(
                    owner, operation.format(value=syntax.text(owner))
                ),
            )
    if menu.isEmpty():
        return
    menu.exec(view.viewport().mapToGlobal(point))
