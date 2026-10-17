import ast

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.analysis import Analysis
from little_tinker_rig.core.imports import manage_imports
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import load_module
from little_tinker_rig.core.syntax import Syntax


@pytest.mark.parametrize(
    "source, lines",
    [
        (
            "try:\n    raise ValueError()\nexcept ValueError as error:\n    print(error)\nprint(error)\n",
            [5],
        ),
        (
            "error = 1\ntry:\n    raise ValueError()\nexcept ValueError as error:\n    pass\nprint(error)\nerror = 2\nprint(error)\n",
            [6],
        ),
        ("len = 1\ndel len\nresult = len([1, 2])\n", []),
        ("def f():\n    len = 1\n    del len\n    return len([])\n", [4]),
        ("value = 1\nclass C:\n    del value\n", [3]),
        ("value = 1\nclass C:\n    value = 2\n    del value\n    result = value\n", []),
        ("class C:\n    len = 1\n    del len\n    result = len([])\n", []),
        ("del len\n", [1]),
    ],
)
def test_binding_cleanup_and_builtin_fallback(source, lines):
    syntax = Syntax(source)
    assert [
        syntax.position(d.span.start)[0] for d in Analysis(syntax).diagnostics()
    ] == lines


@pytest.mark.parametrize(
    "body",
    [
        "class C:\n    pi = pi\nresult = C.pi\n",
        "class C:\n    pi: float\n    result = pi\nresult = C.result\n",
        "def outer():\n    pi = 42\n    class C:\n        pi = pi\n    return C.pi\nresult = outer()\n",
    ],
)
def test_class_fallback_keeps_global_import_on_unrelated_edits(tmp_path, body):
    source = (
        "# --- automatically managed imports ---\nfrom math import pi\n"
        "# --- user imports ---\n" + body
    )
    path = tmp_path / "main.py"
    path.write_text(source)
    session = Session(path)
    before = session.document.state
    original = {}
    exec(before.source, original)
    session.editor.commit(before.source + "unrelated = 1\n")
    edited = {}
    exec(session.document.state.source, edited)
    assert edited["result"] == original["result"]
    assert not session.analysis.diagnostics()
    session.editor.undo()
    assert session.document.state is before


@pytest.mark.parametrize("annotation", ['"Counter"', 'list["Counter"]'])
def test_return_annotation_keeps_managed_dependency(tmp_path, annotation):
    from typing import get_type_hints

    source = (
        "# --- automatically managed imports ---\nfrom collections import Counter\n"
        f"# --- user imports ---\ndef make() -> {annotation}:\n    return None\n"
    )
    path = tmp_path / "main.py"
    path.write_text(source)
    session = Session(path)
    before = session.document.state
    original = {}
    exec(before.source, original)
    expected = get_type_hints(original["make"])
    session.editor.commit(before.source + "unrelated = 1\n")
    edited = {}
    exec(session.document.state.source, edited)
    assert get_type_hints(edited["make"]) == expected
    session.editor.undo()
    assert session.document.state is before


def test_source_without_final_newline_has_correct_end_position():
    syntax = Syntax("answer = 42")
    assert syntax.position(len(syntax.source)) == (1, len(syntax.source))
    assert edit.delete(syntax, syntax.tree.body[0]) == ""


def test_marker_text_in_string_is_not_an_import_section():
    source = 'text = """\n# --- automatically managed imports ---\n# --- user imports ---\n"""\nprint(text)\n'
    assert manage_imports(source) == source


@pytest.mark.parametrize(
    "expression",
    [
        "[pi for _ in items]",
        "{pi for _ in items}",
        "{item: pi for item in items}",
        "tuple(pi for _ in items)",
    ],
)
def test_class_comprehensions_keep_global_imports_on_unrelated_edits(
    tmp_path, expression
):
    source = (
        "# --- automatically managed imports ---\n"
        "from math import pi\n"
        "# --- user imports ---\n"
        "class C:\n"
        "    pi = 3\n"
        "    items = (1, 2)\n"
        f"    values = {expression}\n"
        "result = C.values\n"
    )
    path = tmp_path / "main.py"
    path.write_text(source)
    owner = Session(path)
    before = owner.document.state
    owner.editor.commit(before.source + "unrelated = 1\n")
    original, edited = {}, {}
    exec(source, original)
    exec(owner.document.state.source, edited)
    assert edited["result"] == original["result"]
    owner.editor.undo()
    assert owner.document.state is before


def test_parameter_edit_preserves_internal_comments_and_all_occurrences(tmp_path):
    path = tmp_path / "main.py"
    path.write_text(
        "# file header\nprint(3)  # first\n# second explanation\nprint(3)\n"
    )
    session = Session(path)
    session.snippets = load_module(
        "def twice(x):\n    print(x)\n    print(x)\n", "test", "1.0"
    )
    session.editor.select(session.document.state.source.index("print"))
    session.edit_parameters({"x": "4 + 2"})
    source = session.document.state.source
    assert source.count("4 + 2") == 2
    assert "# first" in source
    assert "# second explanation" in source


def test_compound_snippet_moves_as_one_region(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("print(3)\nprint(3)\nx = 1\n")
    session = Session(path)
    session.snippets = load_module(
        "def twice(x):\n    print(x)\n    print(x)\n", "test", "1.0"
    )
    session.editor.select(0)
    moving = session.begin_move()
    target = edit.Target(session.document.syntax.suites[0], 3)
    source = edit.move(session.document.syntax, moving.node, target)
    assert source == "x = 1\nprint(3)\nprint(3)\n"


def test_scratch_keeps_attached_comments_and_dependencies(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("x = 1\n# turn now\nmotor.run(500)\n")
    session = Session(path)
    session.editor.selection = session.document.syntax.tree.body[-1]
    session.to_scratch()
    assert "# turn now" in session.document.state.scratch[0]
    assert "# turn now" not in session.document.state.source


def test_statement_group_removal_repairs_empty_suite():
    syntax = Syntax("if True:\n    x = 1\n    y = 2\nz = 3\n")
    nodes = tuple(syntax.tree.body[0].body)
    result = edit.move(syntax, nodes, edit.Target(syntax.suites[0], 2))
    tree = ast.parse(result)
    assert isinstance(tree.body[0].body[0], ast.Pass)
    assert [node.targets[0].id for node in tree.body[1:]] == ["z", "x", "y"]


def test_reindent_preserves_multiline_f_string_contents():
    source = 'text = f"""hello\n  {1 + 2}\n  world\n"""\n'
    original, moved = {}, {}
    exec(source, original)
    exec("if True:\n" + edit.reindent(source, 4), moved)
    assert moved["text"] == original["text"]


def test_comments_select_their_owner_and_file_header_stays_put():
    syntax = Syntax(
        "#!/usr/bin/env python\n# coding: utf-8\nx = 1\n# belongs to y\ny = 2  # inline\n"
    )
    assert syntax.at(0) is syntax.tree
    assert syntax.at(syntax.source.index("belongs")) is syntax.tree.body[1]
    assert syntax.at(syntax.source.index("inline")) is syntax.tree.body[1]
    moved = edit.move(syntax, syntax.tree.body[0], edit.Target(syntax.suites[0], 2))
    assert moved.startswith("#!/usr/bin/env python\n# coding: utf-8\n# belongs to y\n")


def test_declared_names_resolve_in_their_binding_scope():
    syntax = Syntax(
        "def outer():\n    global total\n    total = 1\n    local = 2\n    def inner():\n        nonlocal local\n        local += total\n        return local\n    return inner()\n"
    )
    analysis = Analysis(syntax)
    assert not analysis.diagnostics()
    assert {"local", "total"} <= set(
        analysis.available(syntax.source.index("return local"))
    )


def test_expansion_allows_generic_edit_and_expression_scratch_round_trip(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("print(2 + 3)\n")
    session = Session(path)
    session.editor.select(session.document.state.source.index("2 +"))
    assert session.selected_match() is not None
    session.toggle_expansion()
    assert session.selected_match() is None
    session.editor.parent()
    session.to_scratch()
    assert session.document.state.source == "print(...)\n"
    session.editor.select(session.document.state.source.index("..."))
    session.restore_scratch(0)
    assert ast.dump(ast.parse(session.document.state.source)) == ast.dump(
        ast.parse("print(2 + 3)")
    )
    assert not session.document.state.scratch
