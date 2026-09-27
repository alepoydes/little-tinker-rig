import ast

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.document import Document
from little_tinker_rig.core.interaction import Editor
from little_tinker_rig.core.presentation import regions
from little_tinker_rig.core.syntax import Syntax, parse


def test_unicode_offsets_and_ownership():
    syntax = Syntax('имя = "ёж"\nprint(имя)\n')
    offset = syntax.source.index("имя", 1)
    node = syntax.at(offset)
    assert isinstance(node, ast.Name)
    assert syntax.text(node) == "имя"
    assert syntax.position(offset) == (2, 6)
    assert syntax.offset(2, 6) == offset
    assert list(syntax.ancestors(node))[-1] is syntax.tree
    assert all(
        0 <= r.span.start <= r.span.end <= len(syntax.source) for r in regions(syntax)
    )


def test_formatting_ignores_working_directory_settings(tmp_path, monkeypatch):
    (tmp_path / "ruff.toml").write_text("unknown-setting = true\n")
    monkeypatch.chdir(tmp_path)
    source = "greeting='Привет 😀'\nitems = [1,2,3]\n"
    document = Document(source)
    assert document.state.source == 'greeting = "Привет 😀"\nitems = [1, 2, 3]\n'
    assert ast.dump(document.syntax.tree) == ast.dump(ast.parse(source))


@pytest.mark.parametrize("source", ["return 1\n", "break\n", "await f()\n", "x =\n"])
def test_context_errors_do_not_mutate_document(source):
    document = Document("x = 1\n")
    before, syntax = document.state, document.syntax
    with pytest.raises(SyntaxError):
        document.commit(source, ("unfinished(",))
    assert document.state == before
    assert document.syntax is syntax
    assert not document.can_undo


def test_scratch_and_history_are_one_transaction():
    editor = Editor(Document("if True:\n    print('hello')\n"))
    original = editor.document.state
    editor.select(editor.document.state.source.index("print"))
    editor.selection = editor.statement()
    editor.to_scratch()
    removed = editor.document.state
    assert "pass" in removed.source
    assert "print" in removed.scratch[0]
    assert editor.undo()
    assert editor.document.state == original
    assert editor.redo()
    assert editor.document.state == removed
    suite = editor.document.syntax.suites[1]
    editor.from_scratch(0, edit.Target(suite, 0))
    assert editor.document.state == original


def test_move_preserves_comments_and_multiline_string_value():
    source = 'x = 1\n# explanation\ntext = """first\n  literal\n"""\nif x:\n    pass\n'
    syntax = Syntax(source)
    node = syntax.tree.body[1]
    expected = node.value.value
    result = edit.move(syntax, node, edit.Target(syntax.suites[1], 0))
    tree = parse(result)
    assert tree.body[1].body[0].value.value == expected
    assert "    # explanation\n" in result
    assert "pass" not in result


def test_move_rejects_break_outside_loop():
    editor = Editor(Document("while True:\n    break\nprint(1)\n"))
    editor.select(editor.document.state.source.index("break"))
    with pytest.raises(ValueError, match="No legal destination"):
        editor.begin_move()


def test_expression_replacement_preserves_precedence():
    syntax = Syntax("value = 2 * 3\n")
    result = edit.replace(syntax, syntax.tree.body[0].value.right, "4 + 5")
    tree = parse(result)
    assert isinstance(tree.body[0].value.right, ast.BinOp)
    assert ast.literal_eval(tree.body[0].value.right.left) == 4


@pytest.mark.parametrize(
    "source, expected",
    [
        ("(1 + 2)\n", ""),
        ("print(0)\n# owned comment\n(1 + 2)\nprint(3)\n", "print(0)\nprint(3)\n"),
        ("if True:\n    (1 + 2)\n", "if True:\n    pass\n"),
        ("value = 1 + 2\n", "value = ...\n"),
    ],
)
def test_expression_removal_respects_statement_ownership(source, expected):
    syntax = Syntax(source)
    expression = next(n for n in ast.walk(syntax.tree) if isinstance(n, ast.BinOp))
    assert edit.delete(syntax, expression) == expected
    before = syntax.source
    destination = Syntax(source + "result = 2 * None\n")
    expression = next(
        n
        for n in ast.walk(destination.tree)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add)
    )
    target = destination.tree.body[-1].value.right
    moved = edit.move(destination, expression, target)
    assert ast.dump(ast.parse(moved)) == ast.dump(
        ast.parse(expected + "result = 2 * (1 + 2)\n")
    )
    assert moved.count("# owned comment") == source.count("# owned comment")
    assert syntax.source == before


def test_decorators_move_with_definition():
    syntax = Syntax("@decorator\ndef f():\n    pass\nx = 1\n")
    result = edit.move(syntax, syntax.tree.body[0], edit.Target(syntax.suites[0], 2))
    assert result.startswith("x = 1\n@decorator\ndef f")


def test_failed_scratch_restore_keeps_both_workspaces():
    document = Document("x = 1\n", ("not finished(",))
    editor = Editor(document)
    before = document.state
    with pytest.raises((ValueError, SyntaxError)):
        editor.from_scratch(0, edit.Target(document.syntax.suites[0], 1))
    assert document.state == before


def test_new_commit_discards_redo_and_noop_keeps_history():
    document = Document("x=1")
    document.commit("x=2")
    document.undo()
    assert not document.commit(document.state.source)
    assert document.can_redo
    document.commit("x=3")
    assert not document.can_redo


@pytest.mark.parametrize(
    "source",
    [
        "a=1\nb=2\nif a:\n    c=3\nelse:\n    d=4\n",
        "while True:\n    if flag:\n        break\n    continue\nprint(1)\n",
        "def f():\n    return 1\nx=2\n",
        "async def f():\n    await task()\n    async for x in items:\n        print(x)\nx=2\n",
        "x=0\ndef f():\n    global x\n    x=1\n    print(x)\n",
        "from __future__ import annotations\nx=1\ny=2\n",
        "def f():\n    x=1\n    def g():\n        nonlocal x\n        x=2\n    return g\n",
        "try:\n    f()\nexcept* ValueError:\n    print(1)\nwhile flag:\n    break\n",
    ],
)
def test_move_targets_agree_with_exhaustive_compiler_check(source):
    document = Document(source)
    syntax = document.syntax
    for suite in syntax.suites:
        for node in suite.statements:
            expected = []
            for target in edit.targets(syntax):
                try:
                    edit.move(syntax, node, target)
                except (ValueError, SyntaxError):
                    continue
                expected.append(target)
            editor = Editor(document)
            editor.selection = node
            if not expected:
                with pytest.raises(ValueError, match="No legal destination"):
                    editor.begin_move()
            else:
                assert set(editor.begin_move().targets) == set(expected)
