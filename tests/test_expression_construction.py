"""Expression semantics, linked fields and focused editor interaction invariants."""

import ast

import pytest

from pyblocks.core.expressions import (
    OPERATIONS,
    Proposal,
    children,
    compose,
    copy_to,
    empty,
    navigate,
    proposals,
    targets,
    unwrap,
)
from pyblocks.core.session import Session
from pyblocks.core.snippets import builtin_snippets, load_module
from pyblocks.core.structure import sequence
from pyblocks.pybricks.program import Program


def select_value(session, text):
    syntax = session.document.syntax
    session.editor.selection = next(
        n for n in syntax.spans if isinstance(n, ast.expr) and syntax.text(n) == text
    )
    return session.editor.selection


def operation(label):
    item = next(o for o in OPERATIONS if o.label == label)
    return Proposal(label, operation=item)


def test_build_nested_expression_preserves_evaluation_and_short_circuit():
    owner = Session.fragment("answer = ...\n", ())
    select_value(owner, "...")
    compose(owner, operation("… and …"))
    compose(owner, Proposal("ready", "ready"))
    compose(owner, operation("… < …"))
    compose(owner, operation("… + …"))
    compose(owner, Proposal("x", "x"))
    compose(owner, operation("… * …"))
    compose(owner, Proposal("y", "y"))
    compose(owner, Proposal("z", "z"))
    compose(owner, Proposal("limit", "limit"))
    source = owner.document.state.source
    expected = "answer = ready and x + y * z < limit"
    assert ast.dump(ast.parse(source)) == ast.dump(ast.parse(expected))
    namespace = {"ready": False}
    exec(source, namespace)
    assert namespace["answer"] is False  # Undefined operands are not evaluated.
    namespace = dict(ready=True, x=2, y=3, z=4, limit=15)
    exec(source, namespace)
    assert namespace["answer"] is True
    select_value(owner, "x + y * z")
    compose(owner, operation("… * …"), wrap=True)
    compose(owner, Proposal("factor", "2"))
    assert "(x + y * z) * 2" in owner.document.state.source
    owner.editor.undo()
    owner.editor.undo()
    assert owner.document.state.source == source


@pytest.mark.parametrize(
    "source,kind",
    [
        ("[1, 2]", list),
        ("(1, 2)", tuple),
        ("1, 2", tuple),
        ("{1, 2}", set),
        ("{'a': 1, 'b': 2}", dict),
    ],
)
def test_collection_editing_keeps_kind_and_order(source, kind):
    owner = Session.fragment("value = " + source + "\n", ())

    def current():
        return sequence(owner.document.syntax, owner.document.syntax.tree.body[0].value)

    owner.change_sequence(current(), 0, "remove")
    owner.change_sequence(current(), 1, "insert", "'c': 3" if kind is dict else "3")
    owner.change_sequence(current(), 1, "left")
    scope = {}
    exec(owner.document.state.source, scope)
    assert isinstance(scope["value"], kind)
    assert list(scope["value"])[0] == ("c" if kind is dict else 2 if kind is set else 3)
    if kind is set:
        owner.change_sequence(current(), 0, "remove")
        owner.change_sequence(current(), 0, "remove")
        exec(owner.document.state.source, scope)
        assert scope["value"] == set()


def test_linked_fields_wrap_copy_replace_with_snippet_and_undo():
    snippets = load_module(
        """@inline_block
def twice(value=1):
    print(value)
    print(value)
@inline_block
def sum_value(a=2, b=3):
    return a + b
""",
        "test",
        "1",
    )
    owner = Session.fragment("print(1)\nprint(1)\n", snippets)
    select_value(owner, "1")
    compose(owner, operation("… + …"), wrap=True)
    compose(owner, Proposal("two", "2"))
    assert owner.document.state.source.count("print(1 + 2)") == 2
    node = select_value(owner, "1 + 2")
    unwrap(owner, children(owner, node)[0])
    assert owner.document.state.source.count("print(1)") == 2
    select_value(owner, "1")
    owner.insert_snippet(snippets[1], {})
    assert owner.document.state.source.count("print(2 + 3)") == 2
    owner.editor.undo()
    assert owner.document.state.source.count("print(1)") == 2


def test_move_expression_and_navigation_use_exact_nodes():
    owner = Session.fragment("a = (1 + 2) * 3\nb = ...\n", ())
    value = select_value(owner, "1 + 2")
    target = select_value(owner, "...")
    copy_to(owner, value, target, move=True)
    assert ast.dump(ast.parse(owner.document.state.source)) == ast.dump(
        ast.parse("a = ... * 3\nb = 1 + 2\n")
    )
    select_value(owner, "1")
    assert isinstance(navigate(owner, "parent"), ast.BinOp)
    assert owner.document.syntax.text(navigate(owner, "child")) == "1"
    assert owner.document.syntax.text(navigate(owner, "next")) == "2"
    owner.editor.undo()
    assert "(1 + 2) * 3" in owner.document.state.source


def test_comparison_chain_evaluates_middle_operand_once_and_short_circuits():
    owner = Session.fragment("answer = lower() < middle()\n", ())
    node = owner.document.syntax.tree.body[0].value
    owner.change_sequence(sequence(owner.document.syntax, node), 2, "insert", "upper()")
    calls = []
    scope = {
        name: (lambda name=name, value=value: (calls.append(name), value)[1])
        for name, value in (("lower", 1), ("middle", 2), ("upper", 3))
    }
    exec(owner.document.state.source, scope)
    assert calls == ["lower", "middle", "upper"]
    assert scope["answer"] is True
    calls.clear()
    scope["lower"] = lambda: 10
    exec(owner.document.state.source, scope)
    assert calls == ["middle"] and scope["answer"] is False


def test_attribute_and_unpacking_targets_use_structural_tools():
    from pyblocks.core.parameters import change_parameter, slots

    owner = Session.fragment("target = 12\n", builtin_snippets())
    select_value(owner, "target")
    compose(owner, operation("Attribute: ….name"))
    slot = next(s for s in slots(owner) if s.field == "attr")
    change_parameter(owner, slot, "speed")
    assert owner.document.state.source == "target.speed = 12\n"
    owner.editor.undo()
    owner.editor.undo()
    select_value(owner, "target")
    compose(owner, operation("Tuple: (…,)"))
    target = owner.document.syntax.tree.body[0].targets[0]
    owner.change_sequence(sequence(owner.document.syntax, target), 1, "insert", "other")
    assert "target, other" in owner.document.state.source
    value = owner.document.syntax.tree.body[0].value
    owner.replace_expression(value, "[3, 5]")
    scope = {}
    exec(owner.document.state.source, scope)
    assert (scope["target"], scope["other"]) == (3, 5)


def test_outer_scope_actions_preserve_docstrings_and_validate_atomically(tmp_path):
    from pyblocks.core.structure import declare_scope

    path = tmp_path / "scopes.py"
    path.write_text(
        'total = 0\ndef outer():\n    local = 0\n    def update():\n        """Keep documentation."""\n        total = 1\n        local = 2\n    update()\n    return local\nanswer = outer()\n'
    )
    owner = Session(path)

    def body():
        return owner.document.syntax.tree.body[1].body[1].body[-1]

    declare_scope(owner, body(), "total", "global")
    declare_scope(owner, body(), "local", "nonlocal")
    scope = {}
    exec(owner.document.state.source, scope)
    assert scope["total"] == 1 and scope["answer"] == 2
    assert '"""Keep documentation."""' in owner.document.state.source
    before = owner.document.state
    assert declare_scope(owner, body(), "local", "nonlocal") is False
    assert owner.document.state is before
    with pytest.raises(SyntaxError):
        declare_scope(owner, body(), "missing", "nonlocal")
    assert owner.document.state is before
    owner.editor.undo()
    assert "nonlocal local" not in owner.document.state.source


def test_imports_and_sequence_edits_keep_focus_on_the_new_input(tmp_path):
    path = tmp_path / "focus.py"
    path.write_text("old = ...\nvalue = [...]\nlater = ...\n")
    owner = Session(path)
    collection = owner.document.syntax.tree.body[1].value
    owner.change_sequence(
        sequence(owner.document.syntax, collection), 0, "insert", "..."
    )
    assert empty(owner.editor.selection)
    assert (
        owner.document.syntax.parent[owner.editor.selection]
        is owner.document.syntax.tree.body[1].value
    )
    compose(owner, Proposal("port", "Port.A"))
    syntax = owner.document.syntax
    assert empty(owner.editor.selection)
    assert isinstance(syntax.parent[owner.editor.selection], ast.List)
    assert "from pybricks.parameters import Port" in owner.document.state.source


def test_structural_header_actions_preserve_executable_python(tmp_path):
    from pyblocks.core.parameters import change_parameter, slots
    from pyblocks.core.structure import add_import, function_field

    path = tmp_path / "headers.py"
    path.write_text(
        '"""Module documentation."""\nfrom __future__ import annotations\nvalue = 3\nvalue += 4\ndef action():\n    return value\n'
    )
    owner = Session(path)
    add_import(owner, "math", "sqrt as root")
    before = owner.document.state
    assert add_import(owner, "math", "sqrt as root") is False
    with pytest.raises(ValueError):
        add_import(owner, "math; value = 0")
    assert owner.document.state is before
    change_parameter(
        owner,
        next(
            s for s in slots(owner) if s.parameter.annotation == "assignment operator"
        ),
        "*=",
    )
    function_field(owner, owner.document.syntax.tree.body[-1], "decorator")
    compose(owner, Proposal("identity", "lambda f: f"))
    function_field(owner, owner.document.syntax.tree.body[-1], "returns")
    compose(owner, Proposal("int", "int"))
    scope = {}
    exec(owner.document.state.source, scope)
    assert scope["action"]() == 12
    assert scope["root"](9) == 3
    assert scope["__doc__"] == "Module documentation."


def test_context_retains_unknown_types_and_requires_disambiguation():
    snippets = load_module(
        """@inline_block
def action(distance: "number[mm]"=1, speed: "number[mm/s]"=2):
    move(distance, speed)
@inline_block
def length() -> "number[mm]":
    return read_distance()
@inline_block
def unknown():
    return mystery()
""",
        "test",
        "1",
    )
    owner = Session.fragment("move(1, 2)\n", snippets)
    owner.editor.selection = owner.document.syntax.tree.body[0]
    assert [owner.document.syntax.text(n) for n in targets(owner, snippets[1])] == ["1"]
    assert len(targets(owner, snippets[2])) == 2
    select_value(owner, "1")
    entries = proposals(owner)
    assert any(p.snippet is snippets[1] for p in entries)
    assert any(p.snippet is snippets[2] for p in entries)
    assert not any(p.source == '""' for p in entries)


def test_unfinished_inputs_persist_and_prevent_running_without_confusing_none(tmp_path):
    path = tmp_path / "draft.py"
    path.write_text("value = None\nother = ...\n")
    owner = Session(path)
    assert (
        len([d for d in owner.analysis.diagnostics() if "Fill this input" in d.message])
        == 1
    )
    owner.project.save()
    restored = Session(path)
    assert any(empty(n) for n in restored.document.syntax.spans)
    with pytest.raises(ValueError, match="Fill this input"):
        Program(path)
    select_value(restored, "...")
    compose(restored, Proposal("None", "None"))
    restored.project.save()
    program = Program(path)
    program.cleanup()


def test_qt_composition_search_keyboard_and_collection_controls(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from pyblocks.qt.editor import SourceView

    owner = Session.fragment("result = ...\n", builtin_snippets())
    view = SourceView(owner)
    view.resize(1100, 700)
    view.show()
    qt_app.processEvents()
    try:
        select_value(owner, "...")
        view.setFocus()
        QTest.keyClick(view, Qt.Key.Key_Space, Qt.KeyboardModifier.ControlModifier)
        popup = view.expression_popup
        assert popup and popup.isVisible()
        popup.search.setText("List:")
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        assert owner.document.state.source == "result = [...]\n"
        assert empty(owner.editor.selection)
        QTest.keyClick(view, Qt.Key.Key_Return)
        popup = view.expression_popup
        # A literal beats snippets whose descriptions happen to mention its digits.
        popup.search.setText("2")
        QTest.keyClick(popup.search, Qt.Key.Key_Return)
        assert owner.document.state.source == "result = [2]\n"
        select_value(owner, "2")
        QTest.keyClick(view, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        assert isinstance(owner.editor.selection, ast.List)
        assert view.session.document.syntax.text(owner.editor.selection) == "[2]"
        point = view._rect(1, 10, 11).center().toPoint()
        view.structure_bar.activate(point)
        assert view.structure_bar.isVisible()
        QTest.mouseClick(
            view.structure_bar.buttons["insert"], Qt.MouseButton.LeftButton
        )
        assert "2, ..." in owner.document.state.source
        assert view.expression_popup.isVisible()
    finally:
        view.close()


def test_ambiguous_palette_target_is_explicit_and_cancel_preserves_selection(
    tmp_path, qt_app
):
    from pyblocks.qt.app import Studio

    window = Studio(tmp_path / "targets.py")
    window.confirm_close = lambda *_: True
    try:
        window.session.editor.commit("pair(1, 2)\n")
        snippet = next(
            s for s in window.session.snippets if s.identity == "python/numbers/minimum"
        )
        selected = window.session.document.syntax.tree.body[0]
        window.session.editor.selection = selected
        window.insert_snippet(snippet.identity)
        menu = window.input_menu
        # Choose a particular numbered argument, then cancel the first attempt.
        action = next(a for a in menu.actions() if a.text().endswith("· 2"))
        action.hover()
        assert (
            window.session.document.syntax.text(window.session.editor.selection) == "2"
        )
        menu.hide()
        assert window.session.editor.selection is selected
        before = window.session.document.state
        window.insert_snippet(snippet.identity)
        action = next(
            a for a in window.input_menu.actions() if a.text().endswith("· 2")
        )
        action.trigger()
        assert "pair(1, min(" in window.session.document.state.source
        window.session.editor.undo()
        assert window.session.document.state is before
    finally:
        window.close()
