import ast

import pytest

from little_tinker_rig.core.authoring import copy_definition
from little_tinker_rig.core.catalog import families
from little_tinker_rig.core.snippets import instantiate, load_module, recognize
from little_tinker_rig.core.syntax import Syntax

SOURCE = '''"""Motor actions."""
__category__ = "movement"

@inline_block(level="beginner", variant="Wait")
def turn(motor=motor, angle=90):
    motor.run_angle(300, angle)

@inline_block(level="expert", family="test/motors/turn", variant="Options",
              advanced=("wait",), bindings={"rotation": "angle"})
def options(motor=motor, rotation=90, wait=True):
    motor.run_angle(300, rotation, wait=wait)

@inline_block(level="expert", family="test/motors/turn")
def old(motor=motor, angle=90, wait=True):
    motor.run_angle(rotation_angle=angle, speed=300, wait=wait)
'''


def test_family_filter_keeps_exact_lesson_variants_and_recognition():
    snippets = load_module(SOURCE, "test/motors", "1")
    (family,) = families(snippets)
    assert family.category == "movement"
    assert family.choices("beginner") == snippets[:1]
    assert family.choices() == snippets[:2]
    assert family.choices(allowed={snippets[2].identity}) == snippets[2:]
    assert family.choices("beginner", allowed={snippets[2].identity}) == ()
    assert family.choices(eligible={snippets[1].identity}) == snippets[1:2]

    expanded = instantiate(snippets[2], {"angle": "angle()", "wait": "wait()"})
    calls = []

    class Motor:
        def run_angle(self, **kwargs):
            calls.append(kwargs)

    namespace = {
        "motor": Motor(),
        "angle": lambda: calls.append("angle") or 10,
        "wait": lambda: calls.append("wait") or False,
    }
    exec(expanded.source, namespace)
    assert calls == [
        "angle",
        "wait",
        {"rotation_angle": 10, "speed": 300, "wait": False},
    ]
    (match,) = recognize(Syntax(expanded.source), snippets)
    assert match.snippet.identity == snippets[2].identity
    assert ast.unparse(match.bindings["angle"]) == "angle()"


@pytest.mark.parametrize(
    "replacement",
    [
        "__category__ = run_code()",
        '__category__ = "unknown"',
        '__category__ = "movement"\n__category__ = "input"',
    ],
)
def test_module_category_is_static_and_unambiguous(replacement):
    with pytest.raises(ValueError):
        load_module(
            SOURCE.replace('__category__ = "movement"', replacement), "test/motors", "1"
        )


@pytest.mark.parametrize(
    "options",
    [
        "family=12",
        "variant=[]",
        'variant=""',
        "category=[]",
        'advanced=("missing",)',
        'advanced=("required",)',
        'bindings={"missing": "value"}',
        'bindings={"value": "required"}',
    ],
)
def test_invalid_family_fields_are_rejected(options):
    with pytest.raises(ValueError):
        load_module(
            f"@inline_block({options})\ndef action(required, value=1):\n    print(value)\n",
            "test/motors",
            "1",
        )


def test_family_cannot_alias_another_family_or_change_insertion_kind():
    snippets = load_module(SOURCE, "test/motors", "1")
    with pytest.raises(ValueError, match="primary"):
        families(snippets[1:])
    changed = load_module(
        SOURCE.replace('family="test/motors/turn"', 'family="test/motors/options"', 1),
        "test/motors",
        "1",
    )
    with pytest.raises(ValueError, match="primary"):
        families(changed)
    changed = load_module(
        SOURCE.replace(
            "    motor.run_angle(300, rotation, wait=wait)",
            "    return motor.run_angle(300, rotation, wait=wait)",
        ),
        "test/motors",
        "1",
    )
    with pytest.raises(ValueError, match="insertion kind"):
        families(changed)


def test_copying_variant_detaches_its_family_and_preserves_category():
    copied = copy_definition(SOURCE, "options")
    (snippet,) = load_module(copied, "personal/custom", "1")
    assert not snippet.family
    assert snippet.category == "movement"
    assert snippet.advanced == ("wait",)
    assert snippet.bindings == {"rotation": "angle"}
    assert families((snippet,))[0].identity == "personal/custom/options"
