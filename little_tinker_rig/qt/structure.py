"""Compact list controls and explicit expression operations over the core index."""

import ast

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QInputDialog,
    QMenu,
    QMessageBox,
    QToolButton,
    QWidget,
)

from little_tinker_rig.core import edit
from little_tinker_rig.core.expressions import (
    EMPTY,
    OPERATIONS,
    Proposal,
    accepts,
    children,
    compose,
    operation_fits,
    public,
    unwrap,
)
from little_tinker_rig.core.snippets import LEVELS
from little_tinker_rig.core.structure import declare_scope, function_field, sequence
from little_tinker_rig.core.transfer import Transfer
from little_tinker_rig.core.types import known_type
from little_tinker_rig.i18n import tr


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
                for kind, title in (
                    ("keyword", tr("Add named argument")),
                    ("star", tr("Unpack positional arguments")),
                    ("double_star", tr("Unpack named arguments")),
                ):
                    menu.addAction(
                        title, lambda checked=False, kind=kind: self.change(kind)
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
                owner,
                (
                    ast.Call,
                    ast.BoolOp,
                    ast.Compare,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.List,
                    ast.Tuple,
                    ast.Set,
                    ast.Dict,
                ),
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
                    else (
                        tr("Comparison operands")
                        if item.kind == "comparisons"
                        else (
                            tr("Collection items")
                            if item.kind in {"items", "entries"}
                            else tr("Arguments: {name}", name=ast.unparse(owner.func))
                        )
                    )
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
        for action in self.buttons["insert"].menu().actions()[1:]:
            action.setVisible(seq.kind == "arguments")

    def change(self, action):
        seq = self.current()
        if seq is None:
            return
        index = self.item_index(seq)
        text = None
        if action in {"keyword", "star", "double_star"}:
            if seq.kind != "arguments":
                return
            if action == "keyword":
                name, accepted = QInputDialog.getText(
                    self.view, tr("Add named argument"), tr("Argument name")
                )
                if not accepted:
                    return
                import keyword

                if not name.isidentifier() or keyword.iskeyword(name):
                    self.view.failed.emit(tr("Enter a Python identifier"))
                    return
                text = name + "=" + EMPTY
            else:
                text = ("*" if action == "star" else "**") + EMPTY
            action, index = "insert", len(seq.items)
        elif action in {"insert", "insert_before"}:
            index = (
                max(0, index)
                if action == "insert_before"
                else index + 1 if index >= 0 else len(seq.items)
            )
            action = "insert"
            if seq.kind == "parameters":
                text, accepted = QInputDialog.getText(
                    self.view,
                    tr("Add item"),
                    tr("Parameter (name, optionally = default)"),
                    text="parameter",
                )
                if not accepted:
                    return
            else:
                if isinstance(getattr(seq.node, "ctx", None), ast.Store):
                    text = "item"
                    suffix = 2
                    while text in self.view.session.analysis.used_names:
                        text, suffix = f"item{suffix}", suffix + 1
                else:
                    text = f"{EMPTY}: {EMPTY}" if seq.kind == "entries" else EMPTY
        try:
            if seq.syntax is not self.view.session.document.syntax:
                raise ValueError(tr("Document changed; choose the list again"))
            self.view.session.change_sequence(seq, index, action, text)
            self.view.refresh_source()
            self.view.changed.emit()
            if action == "insert" and seq.kind != "parameters":
                self.view.choose_expression()
        except (ValueError, SyntaxError) as error:
            QMessageBox.warning(self.view, tr("Cannot change this list"), str(error))


def block_menu(view, point):
    session = view.session
    syntax = session.document.syntax
    node = view.node_at(point)
    match = session.enclosing_match(node)
    if match:
        session.editor.selection = next(
            (
                n
                for n in syntax.ancestors(syntax.at(match.span.start))
                if syntax.spans[n] == match.span and isinstance(n, (ast.expr, ast.stmt))
            ),
            session._match_nodes(match)[0] if not match.snippet.expression else node,
        )
    else:
        session.editor.selection = next(
            (n for n in syntax.ancestors(node) if isinstance(n, ast.stmt)), node
        )
    view.setFocus()
    view.selected.emit()
    menu = QMenu(view)

    def perform(action, *, transfer=False):
        try:
            if syntax is not session.document.syntax:
                raise ValueError(tr("Document changed; choose the block again"))
            action()
            view.refresh_source()
            (view.transferred if transfer else view.changed).emit()
        except (ValueError, SyntaxError, OSError) as error:
            view.failed.emit(str(error))

    function = next(
        (
            n
            for n in syntax.ancestors(node)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ),
        None,
    )
    if function and view.expression_level in {"expert", "all"}:

        def add_function_field(kind):
            perform(lambda: function_field(session, function, kind))
            view.choose_expression()

        menu.addAction(tr("Add decorator"), lambda: add_function_field("decorator"))
        menu.addAction(
            tr("Edit return annotation"), lambda: add_function_field("returns")
        )

        def scope_choice(kind):
            scope = session.analysis.defined_scopes[function].parent
            names = set(session.analysis.root.bindings) if kind == "global" else set()
            while kind == "nonlocal" and scope and scope is not session.analysis.root:
                if not isinstance(scope.node, ast.ClassDef):
                    names.update(scope.bindings)
                scope = scope.parent
            name, accepted = QInputDialog.getItem(
                view,
                tr("Variable scope"),
                tr("Variable name"),
                sorted(names),
                editable=True,
            )
            if accepted:
                perform(lambda: declare_scope(session, node, name, kind))

        menu.addAction(tr("Use module variable"), lambda: scope_choice("global"))
        menu.addAction(
            tr("Use enclosing function variable"), lambda: scope_choice("nonlocal")
        )
        menu.addSeparator()

    definition = match or next(
        (m for m in session.matches if m.span.contains(syntax.spans[node].start)), None
    )
    if definition:
        menu.addAction(
            tr("Open definition"),
            lambda: view.definition_requested.emit(definition.snippet),
        )
        menu.addAction(
            tr("Help"), lambda: view.help_requested.emit(definition.snippet.identity)
        )
        menu.addAction(
            (
                tr("Collapse block")
                if definition.span in session.expanded_spans
                else tr("Expand block")
            ),
            lambda: perform(session.toggle_expansion),
        )
        menu.addSeparator()
    if session.editor.selection is not syntax.tree:
        expression = (
            match.snippet.expression
            if match
            else isinstance(session.editor.selection, ast.expr)
        )
        owner = view.scratch_owner or session
        if expression:
            menu.addAction(
                tr("Duplicate to Scratch"),
                lambda: perform(
                    lambda: owner.set_scratch(None, session.selected_text()),
                    transfer=True,
                ),
            )
        else:
            menu.addAction(
                tr("Duplicate"),
                lambda: perform(
                    lambda: session.editor.commit(
                        edit.insert(
                            syntax, session.destination(), session.selected_text()
                        )
                    )
                ),
            )

        def move():
            transfer = Transfer.capture(
                owner,
                index=view.scratch_index,
                fragment=session if view.scratch_owner else None,
            )
            transfer.to_scratch(len(owner.document.state.scratch))

        menu.addAction(tr("Move to Scratch"), lambda: perform(move, transfer=True))
        menu.addAction(
            tr("Delete"),
            lambda: perform(
                lambda: session.editor.commit(session.extract_selection()[1])
            ),
        )
        menu.addSeparator()
    expression_menu(view, point, menu=menu)
    return menu


def expression_menu(view, point, *, menu=None):
    syntax = view.session.document.syntax
    slot = view.parameter_at(point)
    node = (slot.node or syntax.at(slot.span.start)) if slot else view.node_at(point)
    standalone = menu is None
    menu = QMenu(view) if standalone else menu

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
        if not public(view.session, owner):
            continue
        text = syntax.text(owner)
        submenu = menu.addMenu(text[:65] + ("…" if len(text) > 65 else ""))

        def choose(checked=False, owner=owner, wrap=False):
            view.session.editor.selection = owner
            view.choose_expression(wrap=wrap)

        submenu.addAction(tr("Compose expression"), choose)
        submenu.addAction(
            tr("Copy expression"),
            lambda owner=owner: QApplication.clipboard().setText(syntax.text(owner)),
        )
        submenu.addAction(
            tr("Paste expression"),
            lambda owner=owner: replace(owner, QApplication.clipboard().text()),
        )
        submenu.addAction(
            tr("Edit expression"), lambda owner=owner: edit_expression(owner)
        )
        submenu.addAction(
            tr("Clear expression"), lambda owner=owner: replace(owner, EMPTY)
        )
        wrap = submenu.addMenu(tr("Wrap expression"))

        def apply(operation, owner):
            try:
                if syntax is not view.session.document.syntax:
                    raise ValueError(
                        tr("Document changed; choose the expression again")
                    )
                view.session.editor.selection = owner
                compose(
                    view.session,
                    Proposal(operation.label, operation=operation),
                    wrap=True,
                )
                view.refresh_source()
                view.changed.emit()
                view.reveal_selection()
            except (ValueError, SyntaxError) as error:
                view.failed.emit(str(error))

        for operation in OPERATIONS:
            if (
                view.expression_operations is not None
                and operation.template not in view.expression_operations
            ):
                continue
            level = view.expression_level
            if (
                level != "all"
                and LEVELS.index(operation.level) > LEVELS.index(level)
                or not operation_fits(view.session, owner, operation)
                or not accepts(view.session, owner, known_type(operation.result))
            ):
                continue
            wrap.addAction(
                tr(operation.label),
                lambda owner=owner, operation=operation: apply(operation, owner),
            )
        operands = children(view.session, owner)
        if operands:
            keep = submenu.addMenu(tr("Unwrap: keep an operand"))

            def keep_operand(owner, operand):
                if syntax is not view.session.document.syntax:
                    return
                view.session.editor.selection = owner
                unwrap(view.session, operand)
                view.refresh_source()
                view.changed.emit()

            for operand in operands:
                keep.addAction(
                    syntax.text(operand)[:65],
                    lambda owner=owner, operand=operand: keep_operand(owner, operand),
                )
    if menu.isEmpty():
        return
    if standalone:
        menu.exec(view.viewport().mapToGlobal(point))
