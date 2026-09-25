"""Menus and linked fields must act on one logical block and one revision."""

import ast
from unittest.mock import patch

from pyblocks.core.authoring import DefinitionDraft, user_collection
from pyblocks.core.session import Session
from pyblocks.core.snippets import load_collection, load_module
from pyblocks.qt.editor import SourceView
from pyblocks.qt.structure import block_menu


def action(menu, title):
    return next(a for a in menu.actions() if a.text() == title)


def test_context_menu_targets_pointer_and_compound_undo(tmp_path, qt_app):
    from PySide6.QtWidgets import QMessageBox

    from pyblocks.qt.app import Studio

    path = tmp_path / "main.py"
    path.write_text("print(1)\nwhile True:\n    print(2)\nprint(3)\n")
    window = Studio(path)
    window.resize(1000, 800)
    window.show()
    qt_app.processEvents()
    view = window.source
    session = window.session
    try:
        original = session.document.state
        session.editor.selection = session.document.syntax.tree.body[0]
        # The generated loop comment belongs to the whole compound statement.
        point = view.note_rect(2, 0).center().toPoint()
        menu = block_menu(view, point)
        action(menu, "Duplicate").trigger()
        tree = session.document.syntax.tree
        assert [type(n) for n in tree.body] == [
            ast.Expr,
            ast.While,
            ast.While,
            ast.Expr,
        ]
        session.editor.undo()
        window.refresh_views()
        assert session.document.state is original
        menu = block_menu(view, point)
        action(menu, "Move to Scratch").trigger()
        assert len(session.document.state.scratch) == 1
        assert ast.dump(
            ast.parse(session.document.state.scratch[0]).body[0]
        ) == ast.dump(ast.parse(original.source).body[1])
        session.editor.undo()
        window.refresh_views()
        assert session.document.state is original
        menu = block_menu(view, point)
        action(menu, "Delete").trigger()
        assert [n.value.args[0].value for n in session.document.syntax.tree.body] == [
            1,
            3,
        ]
        session.editor.undo()
        window.refresh_views()
        assert session.document.state is original
        # Right-clicking a field retains expression editing alongside the menu.
        slot = next(
            s
            for s in view.parameter_slots
            if s.syntax.source[s.span.start : s.span.end] == "3"
        )
        menu = block_menu(view, view.parameter_rect(slot).center().toPoint())
        assert any(a.menu() for a in menu.actions())
        action(menu, "Open definition").trigger()
        assert window.block_editor.code.isReadOnly()
        assert window.block_editor.selected_name == "display"
    finally:
        with patch.object(
            QMessageBox, "question", return_value=QMessageBox.StandardButton.Discard
        ):
            window.close()


def test_history_definition_is_exact_readonly_version(tmp_path, qt_app):
    from pyblocks.qt.authoring import BlockEditor

    root = user_collection(tmp_path)
    (root / "history").mkdir()
    (root / "collection.toml").write_text(
        '[collection]\nid="custom"\nversion="2.0"\nformat=2\n[[history]]\npath="history"\nversion="1.0"\n'
    )
    (root / "actions.py").write_text(
        "@inline_block\ndef show(value=1):\n    print(value + 1)\n"
    )
    old = root / "history/actions.py"
    old.write_text("def show(value=1):\n    print(value)\n")
    snippets = load_collection(root)
    old_snippet = next(s for s in snippets if s.historical)
    draft = DefinitionDraft(old)
    assert draft.read_only and draft.version == "1.0"
    assert draft.inspect()[1][0].identity == "custom/actions/show"
    view = SourceView(Session.fragment("print(8)", snippets))
    editor = BlockEditor(lambda: root, lambda *_: None)
    editor.configure(snippets, (root,))
    view.definition_requested.connect(editor.open_definition)
    view.show()
    qt_app.processEvents()
    try:
        menu = block_menu(view, view.note_rect(1, 0).center().toPoint())
        action(menu, "Open definition").trigger()
        assert editor.code.draft.path == old_snippet.source_path.resolve()
        assert editor.code.isReadOnly()
        assert editor.preview_snippet.version == "1.0"
        assert editor.preview_snippet.historical
        editor.open_definition(next(s for s in snippets if not s.historical))
        assert not editor.code.isReadOnly()
    finally:
        view.close()
        editor.close()


def test_repeated_parameter_links_only_its_own_block(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    snippets = load_module(
        "@inline_block\ndef twice(value=1, other=1):\n    print(value)\n    print(other)\n    print(value)\n",
        "test",
        "1",
    )
    session = Session.fragment(
        "print(1)\nprint(1)\nprint(1)\nprint(1)\nprint(1)\nprint(1)", snippets
    )
    view = SourceView(session)
    view.resize(800, 600)
    view.show()
    qt_app.processEvents()
    try:
        values = [s for s in view.parameter_slots if s.parameter.name == "value"]
        assert len(values) == 4
        slot = values[1]
        assert len(view.linked_parameter_spans(slot)) == 2
        assert view.linked_parameter_spans(slot) == view.linked_parameter_spans(
            values[0]
        )
        assert set(view.linked_parameter_spans(slot)).isdisjoint(
            view.linked_parameter_spans(values[2])
        )
        assert view.parameter_tip(slot) == "value · 2 uses"
        original = session.document.state
        view.show_parameter(slot)
        field = view.parameter_editor
        field.line_edit.setText("7")
        QTest.keyClick(field.line_edit, Qt.Key.Key_Return)
        assert [n.value.args[0].value for n in session.document.syntax.tree.body] == [
            7,
            1,
            7,
            1,
            1,
            1,
        ]
        session.editor.undo()
        view.refresh_source()
        assert session.document.state is original
        slot = next(s for s in view.parameter_slots if s.parameter.name == "value")
        view.show_parameter(slot)
        field = view.parameter_editor
        field.line_edit.setText("9")
        QTest.keyClick(field.line_edit, Qt.Key.Key_Escape)
        assert session.document.state is original
    finally:
        view.close()


def test_expanded_recipe_menu_edits_the_pointed_child(qt_app):
    snippets = load_module(
        "@inline_block\ndef recipe(value=1):\n    print(value)\n    print(2)\n",
        "test",
        "1",
    )
    session = Session.fragment("print(1)\nprint(2)\n", snippets)
    view = SourceView(session)
    view.resize(700, 400)
    view.show()
    qt_app.processEvents()
    try:
        menu = block_menu(view, view.note_rect(1, 0).center().toPoint())
        action(menu, "Expand block").trigger()
        menu = block_menu(view, view.note_rect(2, 0).center().toPoint())
        assert action(menu, "Collapse block")
        action(menu, "Delete").trigger()
        assert session.document.state.source.strip() == "print(1)"
    finally:
        view.close()


def test_scratch_context_deletion_uses_owner_undo(tmp_path, qt_app):
    from pyblocks.qt.scratch import ScratchPane

    owner = Session(tmp_path / "main.py")
    owner.set_scratch(None, "print(1)\nprint(2)")
    original = owner.document.state
    pane = ScratchPane()
    pane.refresh(owner)
    pane.show()
    qt_app.processEvents()
    try:
        cell = pane.cells[0]
        view = cell.source
        menu = block_menu(view, view.note_rect(2, 0).center().toPoint())
        action(menu, "Delete").trigger()
        assert owner.document.state.scratch[0].strip() == "print(1)"
        owner.editor.undo()
        assert owner.document.state is original
    finally:
        pane.close()
