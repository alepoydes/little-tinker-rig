"""Learning paths must compose into runnable programs, not just preview cards."""

import asyncio
import math
import sys
from pathlib import Path
from queue import Queue
from unittest.mock import patch

import pytest

from little_tinker_rig.core import edit
from little_tinker_rig.core.parameters import choices, default_bindings
from little_tinker_rig.core.session import Session
from little_tinker_rig.core.snippets import builtin_snippets, instantiate
from little_tinker_rig.pybricks.sim_runtime import install_modules
from little_tinker_rig.pybricks.simulation import World
from little_tinker_rig.pybricks.virtual import VirtualConnection


def test_focus_is_conspicuous_without_recoloring_descendants(qt_app):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QColor

    from little_tinker_rig.core.presentation import PALETTE
    from little_tinker_rig.qt.colors import saturated
    from little_tinker_rig.qt.editor import SourceView

    for original in PALETTE.values():
        base = QColor(original)
        for amount in (0.45, 0.65, 0.95):
            active = saturated(base, amount)
            assert active.hslSaturationF() > base.hslSaturationF()
            assert 0.05 < base.lightnessF() - active.lightnessF() < 0.2
            assert active.hslHueF() == pytest.approx(base.hslHueF(), abs=0.0001)

    owner = Session.fragment("while True:\n    if True:\n        print(1)\n", ())
    view = SourceView(owner)
    view.resize(900, 500)
    view.show()
    qt_app.processEvents()
    view.pulse.stop()
    try:
        syntax = owner.document.syntax
        owner.editor.selection = syntax.tree
        view.hover = None
        before = view.viewport().grab().toImage().scaled(view.viewport().size())
        owner.editor.selection = syntax.tree.body[0]
        after = view.viewport().grab().toImage().scaled(view.viewport().size())
        colors = []
        for line in (1, 2, 3):
            note = view.note_rect(line, 0)
            point = QPoint(round(note.right()) - 40, round(note.top()) + 2)
            inactive, active = before.pixelColor(point), after.pixelColor(point)
            # Note bands may already have maximum HSL saturation.
            assert active.hslSaturationF() >= inactive.hslSaturationF()
            assert 0.025 < inactive.lightnessF() - active.lightnessF() < 0.15
            assert active.hslHueF() == pytest.approx(inactive.hslHueF(), abs=0.03)
            assert active != after.pixelColor(
                point.x(), round(view._rect(line, 0).top()) + 2
            )
            colors.append(active.name())
        assert len(set(colors)) == 3
    finally:
        view.close()


def test_levels_are_cumulative_and_beginner_is_the_initial_view(tmp_path, qt_app):
    from little_tinker_rig.qt.app import Studio
    from little_tinker_rig.qt.library import IDENTITY, LEVEL

    path = tmp_path / "main.py"
    program = Path(__file__).parents[1] / "examples/data_pipeline.py"
    path.write_text(program.read_text())
    window = Studio(path)
    try:
        assert window.level_filter.value == "beginner"
        before = window.session.document.state.source
        items = window.library.rows.values()
        sets = []
        for level in ("beginner", "intermediate", "advanced", "expert", "all"):
            window.level_filter.select(level)
            sets.append(
                {item.data(0, IDENTITY) for item in items if not item.isHidden()}
            )
        assert sets[0] < sets[1] < sets[2] < sets[3] == sets[4]
        window.change_editor(1)
        assert window.code_active and window.code.toPlainText() == before
        window.change_editor(0)
        assert not window.code_active and window.session.document.state.source == before
        assert len(sets[0]) <= 20
        assert all(
            item.data(0, LEVEL) == "beginner"
            for item in items
            if item.data(0, IDENTITY) in sets[0]
        )
        window.level_filter.select("intermediate")
        window.search.setText("dictionary")
        assert all(
            item.isHidden() or item.data(0, LEVEL) in {"beginner", "intermediate"}
            for item in items
        )
        assert window.settings.value("blockLevel") == "intermediate"
    finally:
        window.close()
    reopened = Studio(tmp_path / "main.py")
    try:
        assert reopened.level_filter.value == "intermediate"
    finally:
        reopened.close()


def test_virtual_moves_use_unrounded_positions_and_signed_wheel_geometry(monkeypatch):
    world = World()
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        from pybricks.parameters import Direction, Port
        from pybricks.pupdevices import Motor
        from pybricks.robotics import DriveBase

        left = Motor(Port.A)
        # At 88.6°, the displayed 89° must not satisfy a 1° stop tolerance.
        monkeypatch.setattr(
            "little_tinker_rig.pybricks.sim_runtime.time.sleep",
            lambda _: world.advance(88.6 / 360),
        )
        left.run_target(360, 90)
        assert world.snapshot()["A"]["angle"] == 90
        right = Motor(Port.B, Direction.COUNTERCLOCKWISE)
        drive = DriveBase(left, right, 56, 112)
        drive.straight(-math.pi * 56, wait=False)
        world.advance(2)
        assert drive.distance() == pytest.approx(-math.pi * 56)
        assert drive.angle() == 0
        assert world.snapshot()["B"]["angle"] == 360
        drive.turn(-90, wait=False)
        world.advance(2)
        assert drive.angle() == -90
        assert drive.distance() == pytest.approx(-math.pi * 56)
        assert world.snapshot()["B"]["angle"] == 180


@pytest.mark.parametrize("device", ["ColorSensor", "ColorDistanceSensor"])
def test_shared_color_blocks_choose_and_recognize_either_sensor(tmp_path, device):
    path = tmp_path / "main.py"
    path.write_text(
        f"from pybricks.pupdevices import {device}\nfrom pybricks.parameters import Port\neye = {device}(Port.D)\n"
    )
    owner = Session(path)
    snippet = next(s for s in owner.snippets if s.identity.endswith("/wait_color"))
    offset = len(owner.document.state.source)
    parameter = snippet.parameters[0]
    assert choices(owner, parameter, offset) == ("eye",)
    assert default_bindings(owner, snippet, offset)["sensor"] == "eye"
    owner.insert_snippet(
        snippet, {"sensor": "eye"}, edit.Target(owner.document.syntax.suites[0], 3)
    )
    assert any(m.snippet.identity == snippet.identity for m in owner.matches)
    assert "while eye.color() != Color.WHITE:" in owner.document.state.source
    assert "from pybricks.tools import wait" in owner.document.state.source
    assert not owner.analysis.diagnostics()
    owner.editor.commit(owner.document.state.source + "eye.reflection()\n")
    reading = owner.document.syntax.tree.body[-1].value
    assert owner.analysis.type_of(reading) == "number"


def test_loop_control_templates_use_compiler_context_and_undo(tmp_path):
    path = tmp_path / "main.py"
    path.write_text("for i in range(3):\n    pass\n")
    owner = Session(path)
    snippets = {s.identity: s for s in owner.snippets}
    for identity in ("python/flow/break_loop", "python/flow/continue_loop"):
        before = owner.document.state
        syntax = owner.document.syntax
        snippet = snippets[identity]
        with pytest.raises(SyntaxError):
            owner.insert_snippet(snippet, {}, edit.Target(syntax.suites[0], 0))
        assert owner.document.state is before
        owner.insert_snippet(snippet, {}, edit.Target(syntax.suites[1], 0))
        namespace = {}
        exec(owner.document.state.source, namespace)
        assert namespace["i"] == (0 if identity.endswith("break_loop") else 2)
        owner.editor.undo()
        assert owner.document.state is before


def test_data_templates_compose_without_executing_library_modules():
    snippets = {s.identity: s for s in builtin_snippets()}
    namespace = {}

    def expand(name, **bindings):
        return instantiate(snippets["python/data/" + name], bindings).source

    exec(expand("make_list", items="(2, 4)"), namespace)
    exec(expand("append", value="6"), namespace)
    assert eval(expand("item", index="-1"), namespace) == 6
    exec(expand("set_item", index="1", value="9"), namespace)
    assert eval(expand("slice_items", stop="2"), namespace) == [2, 9]
    assert eval(expand("map_values", function="abs", items="(-3, 5)"), namespace) == [
        3,
        5,
    ]
    exec(expand("make_dictionary"), namespace)
    exec(
        expand("set_item", items="lookup", index="'count'", value="len(values)"),
        namespace,
    )
    assert namespace["lookup"] == {"name": "robot", "count": 3}


@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
@pytest.mark.asyncio
async def test_learning_examples_run_on_each_virtual_hub(tmp_path, model):
    output = []
    hub = VirtualConnection(output.append, model=model)
    examples = Path(__file__).parents[1] / "examples"
    try:
        await hub.connect()
        sequence = "boost_sequence.py" if model == "boost" else "sequence.py"
        port, kind = ("D", "color_distance") if model == "boost" else ("C", "color")
        await hub.configure(port, kind, {"reflection": 0})
        async with asyncio.timeout(3):
            while hub.info.ports[port]["reflection"] != 0:
                await asyncio.sleep(0.01)
        for name, expected in (
            (sequence, b"Sequence finished"),
            ("robot_route.py", None),
            ("data_pipeline.py", b"[0, 8] 3"),
        ):
            output.clear()
            async with asyncio.timeout(12):
                if name == sequence:
                    await hub.run(examples / name)
                    await asyncio.sleep(0.15)
                    assert hub.info.running and hub.info.ports["A"]["angle"] == 0
                    await hub.configure(port, kind, {"reflection": 100})
                    await hub.done.wait()
                else:
                    await hub.run(examples / name, wait=True)
                while b"\n" not in b"".join(output):
                    await asyncio.sleep(0.01)
            if expected is not None:
                assert expected in b"".join(output)
            else:
                distance, angle = map(float, b"".join(output).split())
                assert distance == pytest.approx(90, abs=3)
                assert angle == pytest.approx(270, abs=2)
            assert not hub.info.error
            assert all(
                data["speed"] == 0
                for data in hub.info.ports.values()
                if data["type"] == "motor"
            )
        random = next(
            s for s in builtin_snippets() if s.identity.endswith("/random_integer")
        )
        expansion = instantiate(random, {"low": "3", "high": "3"})
        program = tmp_path / "random.py"
        program.write_text(
            "\n".join(expansion.imports) + "\nprint(" + expansion.source + ")\n"
        )
        output.clear()
        if model == "boost":
            with pytest.raises(ValueError, match="urandom"):
                await hub.run(program, wait=True)
        else:
            await hub.run(program, wait=True)
            async with asyncio.timeout(3):
                while b"3" not in b"".join(output):
                    await asyncio.sleep(0.01)
    finally:
        await hub.disconnect()
