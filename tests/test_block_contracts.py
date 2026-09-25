import ast

import pytest

from pyblocks.core.snippets import instantiate, load_collection, load_module, recognize
from pyblocks.core.syntax import Syntax
from pyblocks.core.types import (
    Compatibility,
    ValueType,
    annotation_types,
    compatibility,
)


def test_decorator_is_the_authoritative_static_definition(tmp_path):
    source = '''"""Motion. Small robot actions."""
@inline_block(level="beginner", icon="↻", color="#5684ab", names=("motor",))
def create(port: "Port" = Port.A):
    """Create the drive motor."""
    from pybricks.pupdevices import Motor
    from pybricks.parameters import Port
    motor: "Motor" = Motor(port)
'''
    (snippet,) = load_module(source, "robot/motion", "1")
    assert (snippet.level, snippet.icon, snippet.color) == ("beginner", "↻", "#5684ab")
    assert snippet.group_help == "Motion. Small robot actions."
    assert snippet.names == {"motor": "motor"}
    expanded = instantiate(snippet, {"motor": "left"})
    assert "left: 'Motor' = Motor(Port.A)" == expanded.source
    (match,) = recognize(Syntax(expanded.source + "\n"), (snippet,))
    assert match.locals == {"motor": "left"}
    assert ast.unparse(match.bindings["port"]) == "Port.A"
    (tmp_path / "motion.py").write_text(source)
    manifest = tmp_path / "collection.toml"
    manifest.write_text('[collection]\nid="robot"\nversion="1"\nformat=2\n')
    assert load_collection(tmp_path)[0].level == "beginner"
    manifest.write_text(manifest.read_text() + '[levels]\n"motion/create"="expert"\n')
    with pytest.raises(ValueError, match="source decorators"):
        load_collection(tmp_path)


@pytest.mark.parametrize(
    "options",
    [
        'level="all"',
        'color="unknown"',
        'names=("typo",)',
        "kind=[]",
        "context={}",
        'icon=""',
        'icon="x\\n"',
        'icon=" "',
        "level=run_code()",
    ],
)
def test_invalid_metadata_is_rejected_without_execution(options):
    with pytest.raises(ValueError):
        load_module(f"@inline_block({options})\ndef go():\n    print(1)\n", "test", "1")


def test_function_blocks_keep_private_locals_and_evaluate_arguments_once():
    source = """
def twice(value):
    return value * 2

@block(level="beginner", icon="+", color="value")
def calculate(value: "int" = 3) -> "int":
    temp = twice(value)
    return temp + value
"""
    (snippet,) = load_module(source, "test", "1")
    assert snippet.mode == "function"
    assert snippet.expression and snippet.result_type == "int"
    expanded = instantiate(snippet, {"value": "next(values)"})
    namespace = {"values": iter([4, 99]), "temp": "outside"}
    exec("\n\n".join(expanded.helpers), namespace)
    assert eval(expanded.source, namespace) == 12
    assert next(namespace["values"]) == 99
    assert namespace["temp"] == "outside"
    assert len(expanded.helpers) == 2
    (match,) = recognize(Syntax("result = " + expanded.source + "\n"), (snippet,))
    assert ast.unparse(match.bindings["value"]) == "next(values)"


def test_shared_helper_identity_tracks_code_but_not_presentation():
    source = """
def twice(value):
    return value * 2

@block(level="beginner")
def calculate(value=3):
    return twice(value)

@inline_block
def display(value=3):
    print(twice(value))
"""
    first, second = load_module(source, "test", "1")
    assert first.helpers[0].name == second.helpers[0].name
    old_call = instantiate(first, {}).source
    updated, _ = load_module(
        source.replace('level="beginner"', 'level="expert"'), "test", "2"
    )
    assert instantiate(updated, {}).source == old_call
    updated, _ = load_module(source.replace("value * 2", "value * 3"), "test", "2")
    assert instantiate(updated, {}).source != old_call
    namespace = {}
    expanded = instantiate(second, {})
    exec("\n\n".join(expanded.helpers), namespace)
    assert len(expanded.helpers) == 1


def test_helpers_respect_shadowing_and_new_modules_can_contain_only_helpers():
    source = """
def helper(value):
    return value + 1

@block
def invoke(helper=lambda: 42):
    return helper()
"""
    (snippet,) = load_module(source, "test", "1")
    assert len(snippet.helpers) == 1
    expanded = instantiate(snippet, {})
    namespace = {}
    exec("\n\n".join(expanded.helpers), namespace)
    assert eval(expanded.source, namespace) == 42
    assert load_module("def helper():\n    return 3\n", "test", "1", legacy=False) == ()


def test_function_block_action_with_explicit_none_return():
    (snippet,) = load_module(
        '@block\ndef show(value=1) -> "None":\n    print(value)\n    return None\n',
        "test",
        "1",
    )
    assert not snippet.expression
    expanded = instantiate(snippet, {})
    namespace = {}
    exec("\n\n".join(expanded.helpers), namespace)
    assert eval(expanded.source, namespace) is None


@pytest.mark.parametrize("decorator", ["block", "inline_block"])
def test_runtime_helper_calls_distinguish_block_fields_from_python_defaults(decorator):
    source = """
def twice(value=3):
    return value * 2

@block
def calculate(value=3):
    return twice() + value

@block
def display():
    return calculate()
"""
    source = source.replace("@block\ndef display", f"@{decorator}\ndef display")
    with pytest.raises(ValueError, match="must supply every field"):
        load_module(source, "test", "1")
    _, snippet = load_module(
        source.replace("return calculate()", "return calculate(value=5)"), "test", "1"
    )
    expanded = instantiate(snippet, {})
    namespace = {}
    exec("\n\n".join(expanded.helpers), namespace)
    assert eval(expanded.source, namespace) == 11


def test_declared_names_are_lexical_and_collision_checked():
    (snippet,) = load_module(
        """
@inline_block(names=("action", "action.value"))
def define():
    def action(value):
        return value + 1
    result = action(value=2)
""",
        "test",
        "1",
    )
    expanded = instantiate(snippet, {"action": "advance", "action.value": "steps"})
    namespace = {}
    exec(expanded.source, namespace)
    assert namespace["result"] == 3
    assert namespace["advance"](steps=10) == 11
    with pytest.raises(ValueError, match="conflicts"):
        instantiate(snippet, {"action": "advance"}, {"advance"})
    with pytest.raises(ValueError, match="declared name"):
        instantiate(snippet, {"action": "motor.run"})


def test_types_preserve_numeric_precision_units_and_uncertainty():
    assert annotation_types("int[ms] | Motor") == (
        ValueType("int", "ms"),
        ValueType("Motor"),
    )
    assert (
        compatibility("number[deg/s]", ValueType("int"), literal=True)
        is Compatibility.COMPATIBLE
    )
    assert compatibility("number[deg/s]", ValueType("int")) is Compatibility.UNKNOWN
    assert (
        compatibility("number[deg/s]", ValueType("float", "mm/s"))
        is Compatibility.INCOMPATIBLE
    )
    assert compatibility("int", ValueType("float")) is Compatibility.INCOMPATIBLE
    assert compatibility("float", ValueType("int")) is Compatibility.COMPATIBLE
    assert (
        compatibility("Motor | DriveBase", ValueType("DriveBase"))
        is Compatibility.COMPATIBLE
    )
    assert compatibility("Motor", None) is Compatibility.UNKNOWN
    with pytest.raises(ValueError):
        annotation_types("__import__('os').system('exit 1')")


def test_known_incompatible_units_inside_expressions_remain_visible():
    from pyblocks.core.analysis import Analysis

    syntax = Syntax("""
distance: "int[mm]" = 10
angle: "number[deg]" = 90
bad_sum = distance + angle
bad_comparison = distance < angle
product = distance * angle
unknown = distance + external
""")
    errors = [d for d in Analysis(syntax).diagnostics() if d.severity == "error"]
    assert len(errors) == 2
    assert [syntax.position(d.span.start)[0] for d in errors] == [4, 5]
    assert all("number[mm]" in d.message and "number[deg]" in d.message for d in errors)


def test_helper_lifecycle_is_atomic_with_scratch_and_undo(tmp_path):
    from pyblocks.core.session import Session

    snippets = load_module(
        """
from math import sqrt

def magnitude(value):
    return sqrt(value * value)

@block
def show(value=3):
    print(magnitude(value))
""",
        "test",
        "1",
    )
    session = Session(tmp_path / "main.py")
    session.set_snippets(snippets)
    before = session.document.state
    session.insert_snippet(snippets[0], {})
    inserted = session.document.state
    assert "from math import sqrt" in inserted.source
    assert (
        len(
            [
                node
                for node in session.document.syntax.tree.body
                if isinstance(node, ast.FunctionDef)
            ]
        )
        == 2
    )
    assert session.selected_match().snippet is snippets[0]
    assert not [
        s for s in session.available_snippets if s.identity.startswith("document/")
    ]
    session.to_scratch()
    detached = session.document.state
    assert len(detached.scratch) == 1
    assert "from math import sqrt" in detached.source
    assert "def _pyblocks_" in detached.source
    session.editor.commit(detached.source, ())
    assert "_pyblocks_" not in session.document.state.source
    assert "from math" not in session.document.state.source
    session.editor.undo()
    assert session.document.state is detached
    session.editor.undo()
    assert session.document.state is inserted
    session.editor.undo()
    assert session.document.state is before


def test_helper_cleanup_preserves_user_code_comments_and_changed_implementations():
    from pyblocks.core.helpers import manage_helpers

    (snippet,) = load_module("@block\ndef value():\n    return 1\n", "test", "1")
    expanded = instantiate(snippet, {})
    helpers = {fn.name: fn for fn in snippet.helpers}
    source, _ = manage_helpers(
        '"""Program."""\nfrom __future__ import annotations\n# My code\nprint('
        + expanded.source
        + ")\n",
        helpers,
    )
    assert (
        source.index("from __future__")
        < source.index("def _pyblocks")
        < source.index("# My code")
    )
    edited = source.replace("return 1", "# Keep my implementation\n    return 2")
    retained, _ = manage_helpers(edited, helpers)
    assert retained == edited
    assert manage_helpers(retained, helpers)[0] == retained
    # A disconnected collection and an unfinished Scratch fragment retain code.
    name = next(iter(helpers))
    detached = retained.replace("print(" + expanded.source + ")", "pass")
    assert "return 2" in manage_helpers(detached, {}, retain=(name + "(",))[0]
    cleaned, _ = manage_helpers(detached, {})
    assert "def _pyblocks" not in cleaned and "# My code" in cleaned
    assert '"""Program."""' in cleaned and "from __future__" in cleaned


def test_helper_roots_respect_local_shadowing_and_report_global_collisions():
    from pyblocks.core.helpers import manage_helpers

    (snippet,) = load_module("@block\ndef value():\n    return 1\n", "test", "1")
    helpers = {fn.name: fn for fn in snippet.helpers}
    name = next(iter(helpers))
    source = f"def user({name}):\n    return {name}()\n"
    assert manage_helpers(source, helpers) == (source, ())
    with pytest.raises(ValueError, match="conflicts"):
        manage_helpers(f"{name} = external\nprint({name}())\n", helpers)


def test_typed_declarations_recognize_existing_unannotated_source(tmp_path):
    from pyblocks.core.session import Session

    (snippet,) = load_module(
        """
@inline_block(names=("speed",))
def measure(sensor=device):
    speed: "number[deg/s]" = sensor.speed()
""",
        "test",
        "1",
    )
    path = tmp_path / "main.py"
    source = "measured = device.speed()\nprint(measured)\n"
    path.write_text(source)
    session = Session(path)
    session.set_snippets((snippet,))
    assert session.document.state.source == source
    assert session.matches[0].locals == {"speed": "measured"}
    use = session.document.syntax.tree.body[-1].value.args[0]
    assert session.analysis.type_info(use) == ValueType("number", "deg/s")


def test_parameter_errors_keep_recognition_and_unknown_values_are_allowed(tmp_path):
    from pyblocks.core.session import Session

    (snippet,) = load_module(
        """
@inline_block
def start(motor: "Motor" = left, speed: "number[deg/s]" = 300):
    motor.run(speed)
""",
        "test",
        "1",
    )
    path = tmp_path / "main.py"
    path.write_text(
        'motor: "Motor"\nangle: "int[deg]" = 90\nmotor.run(angle)\nmotor.run(-300)\nmotor.run(dynamic())\n'
    )
    session = Session(path)
    session.set_snippets((snippet,))
    assert len(session.matches) == 3
    errors = [
        error for error in session.analysis.diagnostics() if error.severity == "error"
    ]
    assert len(errors) == 1
    assert "number[deg/s]" in errors[0].message and "int[deg]" in errors[0].message
    assert (
        session.document.state.source[errors[0].span.start : errors[0].span.end]
        == "angle"
    )


def test_type_contracts_apply_to_function_calls_returns_and_numeric_units():
    from pyblocks.core.analysis import Analysis

    analysis = Analysis(Syntax("""
def elapsed() -> "int[ms]":
    return 500

def wait(duration: "int[ms]"):
    pass

wait(elapsed())
wait(0.5)
wait(True)
wait(dynamic())
distance: "number[mm]" = elapsed()
"""))
    calls = [node for node in analysis.syntax.tree.body if isinstance(node, ast.Expr)]
    assert analysis.type_info(calls[0].value.args[0]) == ValueType("int", "ms")
    errors = [error for error in analysis.diagnostics() if error.severity == "error"]
    assert len(errors) == 3
    assert any("float" in error.message for error in errors)
    assert any("bool" in error.message for error in errors)
    assert any("number[mm]" in error.message for error in errors)


def test_suggestions_use_the_same_type_and_unit_contract(tmp_path):
    from pyblocks.core.parameters import choices
    from pyblocks.core.session import Session
    from pyblocks.core.snippets import Parameter

    path = tmp_path / "main.py"
    path.write_text(
        'duration: "int[ms]" = 10\nangle: "number[deg]" = 90\ncount = 5\nfraction = 0.5\nready = True\n'
    )
    session = Session(path)
    options = choices(
        session,
        Parameter("duration", "100", "int[ms]"),
        len(session.document.state.source),
    )
    assert {"duration", "count", "100"} <= set(options)
    assert not {"angle", "fraction", "ready"} & set(options)


def test_fixed_implementation_is_closed_across_structural_operations():
    from pyblocks.core import edit
    from pyblocks.core.parameters import change_parameter, slots
    from pyblocks.core.session import Session
    from pyblocks.core.structure import sequence

    (snippet,) = load_module(
        """
@inline_block(names=("reading",))
def measure(sensor=device, offset=0):
    reading: "number[mm]" = sensor.distance() + offset
    hidden = reading * 2
    print(hidden)
""",
        "test",
        "1",
    )
    source = instantiate(snippet, {}).source + "\nprint(reading)\n"
    session = Session.fragment(source, (snippet,))
    visible = {
        session.document.syntax.source[slot.span.start : slot.span.end]: slot
        for slot in slots(session)
        if slot.span.end <= session.matches[0].span.end
    }
    assert {"device", "0", "reading"} <= visible.keys()
    assert not {"distance", "hidden", "print", "+", "*", "2"} & visible.keys()
    reading = next(slot for slot in slots(session) if slot.field == "id")
    change_parameter(session, reading, "measured")
    assert session.document.state.source.endswith("print(measured)\n")
    assert "hidden = measured * 2" in session.document.state.source
    syntax = session.document.syntax
    call = syntax.tree.body[0].value.left
    assert not session.editable(call)
    with pytest.raises(ValueError, match="Expand"):
        session.replace_expression(call, "device.speed()")
    with pytest.raises(ValueError, match="Expand"):
        session.change_sequence(sequence(syntax, call), 0, "insert", "1")
    assert not session.accepts_target(edit.Target(syntax.suites[0], 1))
    assert session.accepts_target(edit.Target(syntax.suites[0], 0))
    assert session.accepts_target(edit.Target(syntax.suites[0], 3))
    session.editor.selection = syntax.tree.body[0]
    session.toggle_expansion()
    assert session.editable(call)
    session.replace_expression(call, "device.speed()")
    assert not session.matches


def test_public_expression_lists_repeat_edits_and_fixed_operations_stay_fixed():
    from pyblocks.core.session import Session
    from pyblocks.core.structure import sequence

    (snippet,) = load_module(
        "@inline_block\ndef twice(value=1):\n    print(value)\n    print(value)\n",
        "test",
        "1",
    )
    session = Session.fragment("print(calculate(1))\nprint(calculate(1))\n", (snippet,))
    syntax = session.document.syntax
    expression = syntax.tree.body[0].value.args[0]
    assert session.editable(expression, "sequence")
    assert not session.editable(syntax.tree.body[0].value, "sequence")
    session.change_sequence(sequence(syntax, expression), 1, "insert", "2")
    assert (
        session.document.state.source
        == "print(calculate(1, 2))\nprint(calculate(1, 2))\n"
    )


def test_source_metadata_drives_cards_help_notes_and_units(qt_app):
    from pyblocks.core.session import Session
    from pyblocks.qt.annotations import block_notes
    from pyblocks.qt.help import group_document
    from pyblocks.qt.library import COLOR, ICON, LEVEL, Library
    from pyblocks.qt.parameters import unit_text

    (snippet,) = load_module(
        '''"""Robot motions\n\nSmall precise movements."""
@inline_block(level="advanced", color="#88bbcc", icon="↪")
def move(duration: "int[ms]" = 10):
    """Move briefly."""
    wait(duration)
''',
        "test/motions",
        "1",
    )
    library = Library((snippet,))
    try:
        group = library.topLevelItem(0)
        card = group.child(0)
        assert group.text(0) == "Robot motions"
        assert (card.data(0, COLOR), card.data(0, ICON), card.data(0, LEVEL)) == (
            "#88bbcc",
            "↪",
            "advanced",
        )
        session = Session.fragment("wait(10)\n", (snippet,))
        note = block_notes(session)[1][0]
        assert (note.icon, note.role) == ("↪", "#88bbcc")
        help_text = group_document("test/motions", (snippet,))
        assert "Robot motions" in help_text and "Small precise movements." in help_text
        assert "int[ms]" in help_text
        assert unit_text("int[ms]") == "ms"
        assert unit_text("number[deg/s]") == "°/s"
    finally:
        library.close()


def test_metadata_controls_edit_literals_without_replacing_python_or_comments():
    from pyblocks.core.block_metadata import change_property

    source = '''# Module note.
@inline_block(
    level="beginner",  # Visible early.
)
def show(value=1):
    """Show a value."""
    print(value)  # Keep this comment.
'''
    updated = change_property(source, "show", "level", "advanced")
    assert updated == source.replace('level="beginner"', "level='advanced'")
    updated = change_property(updated, "show", "color", "#8899aa")
    (snippet,) = load_module(updated, "test", "1")
    assert (snippet.level, snippet.color) == ("advanced", "#8899aa")
    assert "# Visible early." in updated
    assert updated[updated.index("def show") :] == source[source.index("def show") :]
    with pytest.raises(ValueError, match="unknown block level"):
        change_property(updated, "show", "level", "all")


def test_helper_local_bindings_do_not_conflict_with_global_imports(tmp_path):
    from pyblocks.core.session import Session

    (snippet,) = load_module(
        """
from math import sqrt

def increment(sqrt):
    return sqrt + 1

@block
def calculate(value=4):
    return increment(sqrt(value))
""",
        "test",
        "1",
    )
    session = Session(tmp_path / "main.py")
    session.set_snippets((snippet,))
    session.insert_snippet(snippet, {})
    namespace = {}
    exec(session.document.state.source, namespace)
    assert "from math import sqrt" in session.document.state.source
    # The remaining local parameter named sqrt must not retain a global import.
    syntax = session.document.syntax
    source = session.document.state.source.replace(
        syntax.text(syntax.tree.body[-1]), "def user(sqrt):\n    return sqrt + 1"
    )
    session.editor.commit(source)
    assert "import sqrt" not in session.document.state.source
    assert "def _pyblocks" not in session.document.state.source


def test_helper_imports_follow_selected_implementations_after_library_reload(tmp_path):
    from pyblocks.core.session import Session

    source = """
from math import sqrt as operation
@block
def calculate(value=4):
    return operation(value)
"""
    old = load_module(source, "first", "1")[0]
    other = load_module(source.replace("sqrt", "cos"), "second", "1")[0]
    session = Session(tmp_path / "main.py")
    session.set_snippets((old, other))
    # Pasting a generated call also inserts its own helper dependencies.
    session.editor.commit("answer = " + instantiate(old, {}).source)
    assert "from math import sqrt as operation" in session.document.state.source
    changed = load_module(source.replace("sqrt", "sin"), "first", "2")[0]
    session.set_snippets((changed, other))
    session.editor.commit(session.document.state.source + "print(answer)\n")
    namespace = {}
    exec(session.document.state.source, namespace)
    assert namespace["answer"] == 2
    assert "import sin" not in session.document.state.source


def test_inserting_a_standalone_definition_adds_its_helpers_atomically(tmp_path):
    from pyblocks.core.session import Session

    (snippet,) = load_module(
        """
from math import sqrt
@block
def show(value=9):
    print(sqrt(value))
""",
        "test",
        "1",
    )
    session = Session(tmp_path / "main.py")
    before = session.document.state
    session.insert_snippet(snippet, {})
    assert "from math import sqrt" in session.document.state.source
    exec(session.document.state.source, {})
    session.document.undo()
    assert session.document.state == before


def test_builtin_definitions_are_source_complete_and_migration_is_idempotent():
    from pyblocks.core.migration import migrate_module
    from pyblocks.core.presentation import block_icon, snippet_role
    from pyblocks.core.snippets import builtin_snippets

    groups = {}
    for snippet in builtin_snippets():
        groups.setdefault(snippet.source_path, []).append(snippet)
    for path, old in groups.items():
        collection = old[0].identity.rsplit("/", 1)[0]
        levels = {s.identity.rsplit("/", 1)[1]: s.level for s in old}
        migrated = migrate_module(path.read_text(), collection, old[0].version, levels)
        new = load_module(migrated, collection, old[0].version, legacy=False)
        assert len(new) == len(old)
        for before, after in zip(old, new, strict=True):
            assert before.mode == after.mode
            assert before.mode in {"inline", "function"}
            assert before.identity == after.identity
            assert (after.level, after.icon, after.color) == (
                before.level,
                block_icon(before),
                snippet_role(before),
            )
            bindings = {
                p.name: "device" for p in before.parameters if p.default is None
            }
            expanded_before, expanded_after = instantiate(
                before, bindings
            ), instantiate(after, bindings)
            assert ast.dump(ast.parse(expanded_before.source)) == ast.dump(
                ast.parse(expanded_after.source)
            )
            assert expanded_before.imports == expanded_after.imports
            assert expanded_before.helpers == expanded_after.helpers
        assert migrate_module(migrated, collection, old[0].version, levels) == migrated


def test_function_defaults_are_caller_fields_not_helper_dependencies():
    snippets = load_module(
        """
@inline_block
def drive():
    pass

@block
def motion(drive=drive):
    drive.stop()
""",
        "test",
        "1",
        legacy=False,
    )
    expansion = instantiate(snippets[1], {})
    assert len(expansion.helpers) == 1
    calls = []
    from types import SimpleNamespace

    scope = {"drive": SimpleNamespace(stop=lambda: calls.append("stop"))}
    exec("\n".join(expansion.helpers), scope)
    exec(expansion.source, scope)
    assert calls == ["stop"]


def test_class_skeleton_can_be_named_and_filled_without_exposing_class_locals():
    from pyblocks.core import edit
    from pyblocks.core.parameters import slots
    from pyblocks.core.session import Session
    from pyblocks.core.snippets import builtin_snippets

    snippets = builtin_snippets()
    skeleton = next(s for s in snippets if s.identity == "python/objects/define_class")
    session = Session.fragment(instantiate(skeleton, {}).source, snippets)
    slot = next(s for s in slots(session) if s.field == "name")
    from pyblocks.core.parameters import change_parameter

    change_parameter(session, slot, "Rover")
    syntax = session.document.syntax
    target = edit.Target(
        next(s for s in syntax.suites if isinstance(s.owner, ast.ClassDef)), 0
    )
    assert session.accepts_target(target)
    session.editor.commit(edit.insert(syntax, target, "def move(self):\n    return 1"))
    scope = {}
    exec(session.document.state.source, scope)
    assert scope["Rover"]().move() == 1
    with pytest.raises(ValueError, match="classes belong"):
        load_module(
            "@inline_block\ndef bad():\n    class Robot:\n        state=1\n",
            "test",
            "1",
        )
