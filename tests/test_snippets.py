import ast

import pytest

from little_tinker_rig.core.analysis import Analysis
from little_tinker_rig.core.imports import manage_imports
from little_tinker_rig.core.snippets import (
    builtin_snippets,
    instantiate,
    load_module,
    recognize,
    upgrade,
)
from little_tinker_rig.core.syntax import Syntax


def test_loading_never_executes_source():
    snippets = load_module(
        'raise RuntimeError("executed")\ndef show(x=1):\n    """Help."""\n    print(x)\n',
        "test",
        "1.0",
    )
    assert snippets[0].help == "Help."
    assert instantiate(snippets[0], {}).source == "print(1)"


def test_repeat_binding_requires_same_expression():
    (snippet,) = load_module("def twice(x):\n    return x + x\n", "test", "1.0")
    matches = recognize(Syntax("a = f(1) + f(1)\n"), (snippet,))
    assert ast.unparse(matches[0].bindings["x"]) == "f(1)"
    assert not recognize(Syntax("a = f(1) + f(2)\n"), (snippet,))


def test_hygienic_expansion_remains_recognizable():
    (snippet,) = load_module(
        "def scale(x, gain=2):\n    error = x - 1\n    print(error * gain)\n",
        "test",
        "1.0",
    )
    expansion = instantiate(snippet, {"x": "sensor.read()"}, {"error"})
    assert "error_2" in expansion.source
    (match,) = recognize(Syntax(expansion.source + "\n"), (snippet,))
    assert match.locals == {"error": "error_2"}
    assert ast.unparse(match.bindings["x"]) == "sensor.read()"


@pytest.mark.parametrize(
    ("template", "bindings", "occupied"),
    [
        ("def invoke(callback):\n    return callback(1)\n", {"callback": "run"}, set()),
        ("def identity(value):\n    return value\n", {"value": "left + right"}, set()),
        ("def invoke():\n    callback()\n    callback = handler\n", {}, {"callback"}),
    ],
)
def test_recognition_keeps_variable_roots_and_callees(template, bindings, occupied):
    (snippet,) = load_module(template, "test", "1.0")
    expansion = instantiate(snippet, bindings, occupied)
    (match,) = recognize(Syntax(expansion.source + "\n"), (snippet,))
    assert {
        name: ast.unparse(value) for name, value in match.bindings.items()
    } == bindings
    assert (
        instantiate(snippet, match.bindings, local_names=match.locals).source
        == expansion.source
    )


def test_historical_upgrade_preserves_bindings_and_names():
    (old,) = load_module(
        "def show(x):\n    temp = x\n    print(temp)\n", "test", "1.0", historical=True
    )
    (new,) = load_module(
        "def show(x, extra=1):\n    temp = x\n    print(temp, extra)\n", "test", "1.1"
    )
    (match,) = recognize(Syntax("temp_2 = 42\nprint(temp_2)\n"), (new, old))
    result = upgrade(match, new)
    assert result.source == "temp_2 = 42\nprint(temp_2, 1)"


def test_larger_match_wins_and_edits_fall_back_to_python():
    snippets = load_module(
        "def pair(x):\n    print(x)\n    print(x)\ndef single(x):\n    print(x)\n",
        "test",
        "1.0",
    )
    matches = recognize(Syntax("print(3)\nprint(3)\n"), snippets)
    assert len(matches) == 1
    assert matches[0].snippet.identity == "test/pair"
    assert not recognize(Syntax("result = 3\n"), snippets)


def test_managed_imports_keep_user_imports_and_unrecognized_uses():
    source = (
        '"""Module."""\nfrom __future__ import annotations\nimport math\nprint(wait)\n'
    )
    result = manage_imports(source, ("from pybricks.tools import wait",))
    assert result.index("from __future__") < result.index("automatically managed")
    assert "import math" in result
    assert manage_imports(result) == result
    without_use = result.replace("print(wait)", "print(1)")
    cleaned = manage_imports(without_use)
    assert "from pybricks.tools" not in cleaned
    assert "import math" in cleaned


def test_import_collision_is_explicit():
    with pytest.raises(ValueError, match="conflicts"):
        manage_imports("wait = 3\nwait(1)\n", ("from pybricks.tools import wait",))


def test_builtins_and_lexical_names():
    syntax = Syntax(
        "import math\nx = 2\ndef f(a):\n    y = a + x\n    return y + missing\n"
    )
    analysis = Analysis(syntax)
    names = analysis.available(syntax.source.index("missing"))
    assert {"a", "y", "x", "math", "print"} <= set(names)
    assert [d.message for d in analysis.diagnostics()] == [
        "Name 'missing' is not defined"
    ]


def test_bundled_libraries_can_load_without_robot_dependencies():
    snippets = builtin_snippets()
    assert len(snippets) >= 10
    for snippet in snippets:
        bindings = {p.name: "device" for p in snippet.parameters if p.default is None}
        expansion = instantiate(snippet, bindings)
        if (
            snippet.context in ("loop", "async")
            or not snippet.expression
            and any(
                isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom))
                for root in snippet.body
                for node in ast.walk(root)
            )
        ):
            from textwrap import indent

            wrapper = (
                "while True:\n"
                if snippet.context == "loop"
                else (
                    "async def example():\n"
                    if snippet.context == "async"
                    else "def example():\n"
                )
            )
            Syntax(wrapper + indent(expansion.source + "\n", "    "))
        else:
            Syntax(expansion.source + "\n")


def test_await_template_only_offers_async_destinations():
    from little_tinker_rig.core.edit import insertion_targets

    snippet = next(
        s for s in builtin_snippets() if s.identity == "pybricks/tasks/await_task"
    )
    source = instantiate(snippet, {"operation": "operation()"}).source
    syntax = Syntax("async def task():\n    pass\n\ndef ordinary():\n    pass\n")
    targets = tuple(insertion_targets(syntax, source))
    assert targets
    assert all(isinstance(t.suite.owner, ast.AsyncFunctionDef) for t in targets)
    with pytest.raises(SyntaxError, match="await"):
        Syntax(source)


def test_hygiene_respects_nested_shadowing_and_keyword_arguments():
    (snippet,) = load_module(
        "def outer(x):\n    def inner(x):\n        return x + 1\n    result = inner(x=2) + x\n",
        "test",
        "1.0",
    )
    expansion = instantiate(snippet, {"x": "value"}, {"x", "result"})
    namespace = {"value": 10}
    exec(expansion.source, namespace)
    assert namespace["result_2"] == 13
    assert "return value" not in expansion.source
    matches = recognize(Syntax(expansion.source + "\n"), (snippet,))
    assert len(matches) == 1
    assert ast.unparse(matches[0].bindings["x"]) == "value"


def test_hygiene_prevents_capture_inside_comprehension():
    (snippet,) = load_module(
        "def offset(x):\n    return [x + i for i in range(3)]\n", "test", "1.0"
    )
    expansion = instantiate(snippet, {"x": "i"})
    assert eval(expansion.source, {"i": 10}) == [10, 11, 12]
    assert (
        len(recognize(Syntax("result = " + expansion.source + "\n"), (snippet,))) == 1
    )


def test_dependency_conflict_with_function_is_not_silent():
    source = "def wait(ms):\n    print(ms)\nwait(30)\n"
    with pytest.raises(ValueError, match="conflicts"):
        manage_imports(source, ("from pybricks.tools import wait",))


def test_managed_import_survives_dirty_scratch_and_forward_annotation():
    source = manage_imports(
        "motor = Motor()\n", ("from pybricks.pupdevices import Motor",)
    )
    source = source.replace("motor = Motor()", "pass")
    assert "import Motor" in manage_imports(source, retain=("Motor(",))
    annotated = source.replace("pass", 'motor: "Motor"')
    assert "import Motor" in manage_imports(annotated)


def test_difficulty_metadata_rejects_all_and_unknown_blocks(tmp_path):
    from little_tinker_rig.core.snippets import load_collection

    (tmp_path / "motions.py").write_text(
        'def go():\n    """Start moving."""\n    print("go")\n'
    )
    manifest = tmp_path / "collection.toml"
    base = '[collection]\nid = "robot"\nversion = "1.0.0"\n'
    manifest.write_text(base)
    assert load_collection(tmp_path)[0].level == "intermediate"
    manifest.write_text(base + '[levels]\n"motions/go" = "standard"\n')
    assert load_collection(tmp_path)[0].level == "intermediate"
    manifest.write_text(base + '[levels]\n"motions/go" = "beginner"\n')
    assert load_collection(tmp_path)[0].level == "beginner"
    for field in ('"motions/go" = "all"', '"motions/typo" = "expert"'):
        manifest.write_text(base + "[levels]\n" + field + "\n")
        with pytest.raises(ValueError, match="difficulty"):
            load_collection(tmp_path)
