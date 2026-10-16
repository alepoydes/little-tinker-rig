import ast
from unittest.mock import patch

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.analysis import Analysis
from little_tinker_rig.core.parameters import change_parameter, slots
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import builtin_snippets, instantiate
from little_tinker_rig.core.structure import rename, sequence
from little_tinker_rig.core.syntax import Syntax


def session(source, snippets=()):
    return Session.fragment(source, snippets)


def field(owner, text, occurrence=0):
    return [
        s
        for s in slots(owner)
        if owner.document.syntax.source[s.span.start : s.span.end] == text
    ][occurrence]


def test_receiver_callee_method_parameters_and_nested_leaves_are_editable():
    owner = session("def action(speed=1):\n    left.run(speed + 2)\naction(3)\n")
    change_parameter(owner, field(owner, "left"), "right")
    change_parameter(owner, field(owner, "run"), "stop")
    change_parameter(owner, field(owner, "2"), "4 * 5")
    change_parameter(owner, field(owner, "action", 1), "other")
    assert "right.stop(speed + 4 * 5)" in owner.document.syntax.source
    assert "other(3)" in owner.document.syntax.source
    change_parameter(owner, field(owner, "speed"), "power")
    assert "def action(power=1)" in owner.document.syntax.source
    assert "right.stop(power + 4 * 5)" in owner.document.syntax.source


def test_rename_updates_only_resolved_uses_and_keywords_and_undo():
    owner = session(
        "def drive(speed):\n    speed = speed + 1\n    def inner():\n        nonlocal speed\n        speed += 1\n    return speed\ndef separate(speed):\n    return speed\ndrive(speed=2)\n"
    )
    before = owner.document.state
    change_parameter(owner, field(owner, "speed"), "power")
    source = owner.document.syntax.source
    assert "nonlocal power" in source and "power += 1" in source
    assert "drive(power=2)" in source and "def separate(speed)" in source
    owner.editor.undo()
    assert owner.document.state is before
    function = owner.document.syntax.tree.body[0]
    owner.editor.commit(rename(owner, function, "move"))
    assert "move(speed=2)" in owner.document.syntax.source
    assert "def move(speed)" in owner.document.syntax.source


@pytest.mark.parametrize(
    "subject, pattern",
    [
        ("1", "x"),
        ("1", "1 as x"),
        ("[1]", "[x]"),
        ("[0, 1]", "[0, *x]"),
        ('{"x": 1, "y": 2}', '{"x": _, **x}'),
    ],
)
def test_parameter_rename_preserves_match_bindings_and_shadowed_names(subject, pattern):
    source = (
        "def f(x):\n"
        "    def separate():\n"
        "        match 99:\n"
        "            case x:\n"
        "                return x\n"
        f"    match {subject}:\n"
        f"        case {pattern}:\n"
        "            pass\n"
        "    return x, separate()\n"
        "result = f(x=0)\n"
    )
    owner = session(source)
    before = owner.document.state
    change_parameter(owner, field(owner, "x"), "value")
    original, edited = {}, {}
    exec(source, original)
    exec(owner.document.state.source, edited)
    assert edited["result"] == original["result"]
    assert "case x:\n                return x" in owner.document.state.source
    owner.editor.undo()
    assert owner.document.state is before


def test_rename_rejects_capture_without_touching_source():
    owner = session(
        "def run(a):\n    def nested(b):\n        return a + b\n    return nested(1)\n"
    )
    before = owner.document.state
    with pytest.raises(ValueError, match="shadowed"):
        change_parameter(owner, field(owner, "a"), "b")
    assert owner.document.state is before


@pytest.mark.parametrize(
    "source",
    [
        "f()",
        "f(1, two=2)",
        "f((1 + 2), [3, 4])",
        "f(lambda x, y: x + y, 3)",
        "f(\n1, # keep\n2,\n# tail\n)",
    ],
)
def test_call_lists_preserve_existing_arguments_and_comments(source):
    syntax = Syntax(source + "\n")
    seq = sequence(syntax, syntax.tree.body[0].value)
    result = seq.change(len(seq.items), "insert", "extra=None")
    tree = ast.parse(result)
    assert (
        ast.dump(tree.body[0].value.args[0])
        == ast.dump(syntax.tree.body[0].value.args[0])
        if seq.items
        else True
    )
    assert tree.body[0].value.keywords[-1].arg == "extra"
    if "# keep" in source:
        assert "# keep" in result and "# tail" in result
    syntax = Syntax(result)
    seq = sequence(syntax, syntax.tree.body[0].value)
    result = seq.change(len(seq.items) - 1, "remove")
    assert ast.dump(ast.parse(result)) == ast.dump(ast.parse(source))


def test_parameter_lists_handle_defaults_annotations_and_syntax_constraints():
    syntax = Syntax("def f(a: int, /, b=2, *, c=None, **kwargs):\n    return a\n")
    seq = sequence(syntax, syntax.tree.body[0])
    result = seq.change(4, "insert", "d=3")
    assert "d=3" in result
    assert len(ast.parse(result).body[0].args.kwonlyargs) == 2
    with pytest.raises(SyntaxError):
        seq.change(3, "insert", "required")
    syntax = Syntax("def f(a, b):\n    return a - b\n")
    seq = sequence(syntax, syntax.tree.body[0])
    result = seq.change(1, "left")
    assert ast.parse(result).body[0].args.args[0].arg == "b"


def test_boolean_lists_keep_grouping_and_short_circuit_order():
    syntax = Syntax("result = a() and (b() or c())\n")
    seq = sequence(syntax, syntax.tree.body[0].value)
    result = seq.change(1, "insert", "d() or e()")
    order = []
    values = {"a": True, "b": False, "c": True, "d": False, "e": True}
    namespace = {
        name: (lambda name=name: order.append(name) or values[name]) for name in values
    }
    exec(result, namespace)
    assert order == ["a", "d", "e", "b", "c"] and namespace["result"]
    with pytest.raises(ValueError, match="at least 2"):
        seq.change(1, "remove")


def test_call_diagnostics_are_conservative_and_do_not_block_commits():
    owner = session(
        "def f(a, b=2, *, flag=True):\n    pass\nf()\nf(1, 2, 3)\nf(1, flag=False)\nf(*values)\nunknown(1, 2)\nrange(1, 10, 0)\n"
    )
    errors = [d for d in owner.analysis.diagnostics() if d.severity == "error"]
    assert len(errors) == 3
    assert [
        owner.document.syntax.source[d.span.start : d.span.end] for d in errors
    ] == ["f()", "f(1, 2, 3)", "range(1, 10, 0)"]
    rebound = Analysis(Syntax("def f(a):\n    pass\nf = unknown\nf()\n"))
    assert not any(d.severity == "error" for d in rebound.diagnostics())


def test_user_functions_and_contextual_templates():
    owner = session(
        "def move(distance, speed=100, *, stop=True):\n    return distance\n",
        builtin_snippets(),
    )
    snippet = next(
        s for s in owner.available_snippets if s.identity == "document/functions/move"
    )
    expansion = instantiate(snippet, {})
    assert expansion.source == "move(...)"
    owner.insert_snippet(snippet, {}, edit.Target(owner.document.syntax.suites[0], 1))
    assert "move(...)" in owner.document.syntax.source
    ret = next(s for s in owner.snippets if s.identity == "python/basics/return_value")
    assert not ret.expression and instantiate(ret, {}).source == "return 0"
    repeat = next(
        s for s in owner.snippets if s.identity == "python/basics/count_range"
    )
    assert "range(0, 10, 1)" in instantiate(repeat, {}).source


@pytest.mark.parametrize(
    "definition, expression",
    [
        ("def f():\n    print(1)\n", False),
        ("def f():\n    return None\n", False),
        ("def f():\n    def inner():\n        return 1\n    print(inner())\n", False),
        ("def f():\n    if ready:\n        return 1\n", True),
        ("def f():\n    yield 1\n", True),
        ("def f() -> int:\n    pass\n", True),
        ("@decorate\ndef f():\n    pass\n", True),
    ],
)
def test_user_function_cards_distinguish_actions_from_results(definition, expression):
    owner = session(definition)
    snippet = next(
        s for s in owner.available_snippets if s.identity == "document/functions/f"
    )
    assert snippet.expression is expression
    assert instantiate(snippet, {}).source == "f()"


def test_shared_binding_edits_nested_operands_consistently():
    from little_tinker_rig.core.snippets import load_module

    snippets = load_module(
        "def twice(x):\n    print(x)\n    print(x)\n", "example", "1"
    )
    owner = session("print(1 + 2)\nprint(1 + 2)\n", snippets)
    change_parameter(owner, field(owner, "2"), "3 - 4")
    assert owner.document.syntax.source == "print(1 + (3 - 4))\nprint(1 + (3 - 4))\n"


def test_ui_list_controls_and_red_diagnostic(qt_app):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QInputDialog

    from little_tinker_rig.qt.editor import SourceView

    owner = session("def f(a):\n    pass\nf()\n")
    view = SourceView(owner)
    view.resize(900, 600)
    view.show()
    qt_app.processEvents()
    try:
        assert any(note.error for notes in view.notes.values() for note in notes)
        point = view._rect(3, 2, 3).center().toPoint()
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        assert view.structure_bar.isVisible()
        with patch.object(
            QInputDialog,
            "getText",
            side_effect=AssertionError("No Python-fragment dialog"),
        ):
            QTest.mouseClick(
                view.structure_bar.buttons["insert"], Qt.MouseButton.LeftButton
            )
        assert owner.document.syntax.source.endswith("f(...)\n")
        chooser = view.expression_popup
        chooser.search.setText("1")
        QTest.keyClick(chooser.search, Qt.Key.Key_Return)
        assert owner.document.syntax.source.endswith("f(1)\n")
        assert not any(note.error for notes in view.notes.values() for note in notes)
        owner.editor.undo()
        owner.editor.undo()
        view.refresh_source()
        assert any(note.error for notes in view.notes.values() for note in notes)
    finally:
        view.close()


def test_operator_change_preserves_operand_tree_comments_and_binding_occurrences():
    from little_tinker_rig.core.snippets import load_module

    owner = session("result = a + b * c\n")
    change_parameter(owner, field(owner, "+"), "*")
    assert owner.document.syntax.source == "result = a * (b * c)\n"
    snippets = load_module("def twice(x):\n    print(x)\n    print(x)\n", "test", "1")
    owner = session("print(a + b * c)\nprint(a + b * c)\n", snippets)
    change_parameter(owner, field(owner, "+"), "*")
    assert owner.document.syntax.source.count("a * (b * c)") == 2
    owner = session("result = (a + # keep me\n b * c)\n")
    change_parameter(owner, field(owner, "+"), "*")
    assert "# keep me" in owner.document.syntax.source
    syntax = Syntax("result = (a and # still here\n b)\n")
    result = sequence(syntax, syntax.tree.body[0].value).change(2, "insert", "c")
    assert "# still here" in result
    assert len(ast.parse(result).body[0].value.values) == 3


def test_note_hover_shares_colors_and_origin_marker_keeps_indentation(qt_app):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QColor, QMouseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from little_tinker_rig.core.transfer import Transfer
    from little_tinker_rig.qt.editor import SourceView

    view = SourceView(session("while True:\n    if True:\n        print(1)\n"))
    view.resize(900, 600)
    view.show()
    QTest.qWaitForWindowExposed(view)
    QTest.mouseMove(view.viewport(), QPoint(1, 1))
    QTest.qWait(60)
    try:
        view.session.editor.selection = view.session.document.syntax.tree
        view.hover = None
        note = view.note_rect(3, 0)
        point = QPoint(round(note.right()) - 40, round(note.top()) + 2)
        before = view.viewport().grab().toImage().scaled(view.viewport().size())
        # Wayland forbids QCursor.setPos, which QTest.mouseMove uses for hover.
        # Deliver the same public viewport event without moving the system cursor.
        QApplication.sendEvent(
            view.viewport(),
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(point),
                QPointF(view.viewport().mapToGlobal(point)),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            ),
        )
        after = view.viewport().grab().toImage().scaled(view.viewport().size())
        assert before.pixelColor(point) != after.pixelColor(point)
        code = view._rect(3, 0)
        assert after.pixelColor(point) == after.pixelColor(
            point.x(), round(code.top()) + 2
        )
        # A note is owned by its block even when the pointer is over its text.
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        node = view.session.editor.selection
        assert isinstance(node, ast.Expr)
        origin_x = view._rect(3, 8).left()
        view.show_drag_origin(Transfer.capture(view.session))
        assert view.origin_rect().left() == origin_x
        image = view.viewport().grab().toImage().scaled(view.viewport().size())
        rect = view.origin_rect()
        assert image.pixelColor(
            round(rect.right()) - 10, round(rect.top()) + 5
        ) == QColor("#ffe0a1")
        view.hide_drag_origin()
    finally:
        view.close()


def test_library_search_uses_all_words_from_full_help_and_dynamic_functions(qt_app):
    from little_tinker_rig.qt.library import IDENTITY, Library

    owner = session("def greet(name):\n    print(name)\n", builtin_snippets())
    library = Library(owner.available_snippets)
    try:
        library.filter("program console", "all")
        visible = [
            card.data(0, IDENTITY)
            for card in library.rows.values()
            if not card.isHidden()
        ]
        assert "python/basics/display" in visible
        assert library.headings["functions"].text(0) == "Functions"
        owner.editor.commit("def wave():\n    pass\n")
        library.update_functions(owner.available_snippets)
        library.filter("wave")
        assert any(
            item.data(0, IDENTITY) == "document/functions/wave" and not item.isHidden()
            for item in library.rows.values()
        )
    finally:
        library.close()


def test_receivers_are_editable_and_fixed_methods_require_expansion():
    owner = session(
        "from pybricks.pupdevices import Motor\nfrom pybricks.parameters import Port\nleft = Motor(Port.A)\nleft.run(100)\nfor i in range(10):\n    print(i)\n",
        builtin_snippets(),
    )
    assert field(owner, "left", 1)
    assert not any(
        owner.document.syntax.source[s.span.start : s.span.end] == "run"
        for s in slots(owner)
    )
    owner.editor.selection = owner.document.syntax.tree.body[-2]
    owner.toggle_expansion()
    assert field(owner, "run").field == "attr"
    change_parameter(owner, field(owner, "run"), "stop")
    assert "left.stop(100)" in owner.document.syntax.source
    assert not any(
        owner.document.syntax.source[s.span.start : s.span.end] == "range"
        for s in slots(owner)
    )
    owner.editor.selection = owner.document.syntax.tree.body[-1]
    owner.toggle_expansion()
    assert field(owner, "range")


def test_removing_argument_preserves_neighbouring_comment_and_defaults_are_not_repeated():
    syntax = Syntax("f(1, # belongs to first\n2)\n")
    result = sequence(syntax, syntax.tree.body[0].value).change(1, "remove")
    assert (
        "# belongs to first" in result
        and len(ast.parse(result).body[0].value.args) == 1
    )
    owner = session("def f(a=make_default()):\n    return a\n")
    snippet = owner.available_snippets[-1]
    assert instantiate(snippet, {}).source == "f()"


def test_condition_operands_keep_their_own_type_suggestions():
    from little_tinker_rig.core.parameters import choices

    owner = session("if speed > 0 and count > 0:\n    pass\n", builtin_snippets())
    value = field(owner, "0")
    assert value.parameter.annotation == "number"
    assert "True" not in choices(owner, value.parameter, value.span.start)
