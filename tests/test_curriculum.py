"""The small LEGO-style activities must compose, stop, and survive source edits."""

import asyncio
import math
import sys
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pyblocks.core import edit
from pyblocks.core.parameters import choices, default_bindings
from pyblocks.core.project import Project
from pyblocks.core.session import Session
from pyblocks.core.snippets import builtin_snippets, instantiate
from pyblocks.pybricks.sim_runtime import install_modules
from pyblocks.pybricks.simulation import World
from pyblocks.pybricks.virtual import VirtualConnection


@pytest.fixture
def blocks():
    return {s.identity: s for s in builtin_snippets()}


def execute(blocks, name, namespace, **bindings):
    expansion = instantiate(blocks["pybricks/" + name], bindings)
    source = "\n".join((*expansion.imports, *expansion.helpers, expansion.source))
    exec(source, namespace)


def test_old_level_setting_migrates_and_groups_limit_visual_load(tmp_path, qt_app):
    from pyblocks.qt.app import QSettings, Studio

    QSettings().setValue("blockLevel", "standard")
    window = Studio(tmp_path / "main.py")
    try:
        assert window.level_filter.currentData() == "intermediate"
        groups = [
            window.library.topLevelItem(i)
            for i in range(window.library.topLevelItemCount())
        ]
        assert all(not group.isExpanded() for group in groups)
        window.search.setText("speaker")
        matches = [group for group in groups if not group.isHidden()]
        assert matches and all(group.isExpanded() for group in matches)
        window.search.clear()
        assert all(not group.isExpanded() for group in groups)
        assert QSettings().value("blockLevel") == "intermediate"
        window.level_filter.setCurrentIndex(window.level_filter.findData("beginner"))
        window.search.setText("speaker")
        window.level_filter.setCurrentIndex(window.level_filter.findData("advanced"))
        window.search.clear()
        assert all(not group.isExpanded() for group in groups)
    finally:
        window.close()


def test_setup_and_recipe_insert_recognize_expand_and_undo(tmp_path, blocks):
    path = tmp_path / "robot.py"
    project = Project(path)
    project.pins = {"python": "1.1.0", "pybricks": "1.1.0"}
    project.save()
    owner = Session(path)
    for identity in (
        "drive/create_robot",
        "sensors/create_color_sensor",
        "lessons/follow_for",
    ):
        block = blocks["pybricks/" + identity]
        target = edit.Target(
            owner.document.syntax.suites[0], len(owner.document.syntax.tree.body)
        )
        owner.insert_snippet(
            block,
            default_bindings(owner, block, len(owner.document.state.source)),
            target,
        )
    assert not owner.analysis.diagnostics()
    recipe = next(
        m for m in owner.matches if m.snippet.identity.endswith("/follow_for")
    )
    source = owner.document.state.source
    owner.editor.selection = next(
        n
        for n, span in owner.document.syntax.spans.items()
        if span.start == recipe.span.start
    )
    owner.toggle_expansion()
    assert recipe not in owner.visible_matches
    assert owner.document.state.source == source
    owner.editor.undo()
    assert not any(m.snippet.identity.endswith("/follow_for") for m in owner.matches)


@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
def test_sensor_activities_poll_and_brake_on_completion_and_error(
    model, blocks, monkeypatch
):
    world = World(model=model)
    port, kind = ("D", "color_distance") if model == "boost" else ("C", "color")
    now = [0.0]
    steps = []

    def tick(seconds):
        now[0] += seconds
        world.advance(seconds)
        steps.append(world.snapshot()["A"]["speed"])
        if len(steps) == 3:
            world.configure(port, kind, {"reflection": 10})

    monkeypatch.setattr("pyblocks.pybricks.sim_runtime.time.sleep", tick)
    monkeypatch.setattr("pyblocks.pybricks.sim_runtime.time.monotonic", lambda: now[0])
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        namespace = {}
        execute(blocks, "drive/create_robot", namespace)
        sensor = (
            "create_color_distance_sensor"
            if model == "boost"
            else "create_color_sensor"
        )
        execute(blocks, "sensors/" + sensor, namespace, port=f"Port.{port}")
        execute(blocks, "lessons/stop_at_line", namespace)
        assert len(steps) == 3 and all(speed < 0 for speed in steps)
        assert all(world.snapshot()[p]["speed"] == 0 for p in "AB")
        before = len(steps)
        execute(blocks, "lessons/stop_at_line", namespace)
        assert len(steps) == before  # Already on the line: do not start a motor.
        execute(blocks, "lessons/follow_for", namespace, duration="50")
        assert now[0] >= 0.11
        assert all(world.snapshot()[p]["speed"] == 0 for p in "AB")
        namespace["drive"].drive(100, 0)
        world.configure(port, "empty")
        with pytest.raises(OSError):
            execute(blocks, "lessons/stop_at_line", namespace)
        assert all(world.snapshot()[p]["speed"] == 0 for p in "AB")


@pytest.mark.parametrize(
    "radius,angle", [(200, 90), (-200, 90), (200, -90), (-200, -90)]
)
def test_curves_have_signed_distance_heading_and_synchronized_wheels(
    radius, angle, blocks, monkeypatch
):
    world = World()
    monkeypatch.setattr("pyblocks.pybricks.sim_runtime.time.sleep", world.advance)
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        namespace = {}
        execute(blocks, "drive/create_robot", namespace)
        execute(blocks, "drive/drive_settings", namespace, speed="100")
        robot = namespace["drive"]
        robot.arc(radius, angle=angle, wait=False)
        duration = math.pi
        world.advance(duration / 2)
        assert robot.distance() == pytest.approx(
            math.copysign(math.pi * 100 / 2, angle), abs=1
        )
        assert robot.angle() == pytest.approx(
            angle / 2 * (1 if radius > 0 else -1), abs=1
        )
        world.advance(duration / 2 + 0.01)
        assert robot.distance() == pytest.approx(
            math.copysign(math.pi * 100, angle), abs=1
        )
        assert robot.angle() == pytest.approx(angle * (1 if radius > 0 else -1), abs=1)
        execute(blocks, "drive/reset_drive", namespace)
        assert robot.distance() == robot.angle() == 0
        with pytest.raises(ValueError):
            robot.arc(0, angle=90)


@pytest.mark.parametrize("fail", [False, True])
def test_remote_activity_brakes_on_release_exit_and_disconnect(
    blocks, monkeypatch, fail
):
    world = World()
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        from pybricks import pupdevices
        from pybricks.parameters import Button

        # Script only the external remote; run the actual generated control
        # algorithm against the same motor/drive model as the virtual hub.
        inputs = iter(({Button.LEFT_PLUS}, set(), {Button.RIGHT_PLUS}, {Button.CENTER}))
        disconnected = []

        def pressed():
            value = next(inputs)
            if fail and value == {Button.RIGHT_PLUS}:
                raise OSError("Remote disconnected")
            return value

        pupdevices.Remote = lambda: SimpleNamespace(
            buttons=SimpleNamespace(pressed=pressed),
            disconnect=lambda: disconnected.append(True),
        )
        observed = []

        def tick(seconds):
            observed.append(tuple(world.snapshot()[p]["speed"] for p in "AB"))
            world.advance(seconds)

        monkeypatch.setattr("pyblocks.pybricks.sim_runtime.time.sleep", tick)
        namespace = {}
        execute(blocks, "drive/create_robot", namespace)
        if fail:
            with pytest.raises(OSError, match="disconnected"):
                execute(blocks, "remote/remote_drive", namespace)
        else:
            execute(blocks, "remote/remote_drive", namespace)
            assert observed[2][0] < 0 and observed[2][1] < 0  # Turn in place.
        assert observed[0][0] < 0 < observed[0][1]
        assert observed[1] == (0, 0)
        assert disconnected == [True]
        assert all(world.snapshot()[p]["speed"] == 0 for p in "AB")


@pytest.mark.parametrize(
    "model,setup",
    [("inventor", "prime_hub"), ("boost", "move_hub"), ("technic", "technic_hub")],
)
def test_hub_feedback_and_capabilities(model, setup, blocks, monkeypatch):
    world = World(model=model)
    monkeypatch.setattr("pyblocks.pybricks.sim_runtime.time.sleep", world.advance)
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        namespace = {}
        execute(blocks, "hubs/" + setup, namespace)
        execute(blocks, "hubs/light", namespace, color="Color.RED")
        assert world.feedback["light"] == "RED"
        if model == "inventor":
            execute(blocks, "hubs/icon", namespace)
            assert world.feedback["display"] == "HEART"
            execute(blocks, "hubs/beep", namespace)
            assert world.feedback["tone"] is None
        else:
            assert not hasattr(namespace["hub"], "display")
            assert not hasattr(namespace["hub"], "speaker")
        assert hasattr(namespace["hub"].imu, "heading") == (model != "boost")


def test_hub_bindings_and_dotted_readings_are_suggested(tmp_path, blocks):
    path = tmp_path / "main.py"
    path.write_text(
        "from pybricks.hubs import PrimeHub\nbrick = PrimeHub()\nbrick.imu.heading()\n"
    )
    owner = Session(path)
    offset = len(owner.document.state.source)
    assert (
        default_bindings(owner, blocks["pybricks/hubs/light"], offset)["hub"] == "brick"
    )
    reading = owner.document.syntax.tree.body[-1].value
    assert owner.analysis.type_of(reading) == "number"
    parameter = blocks["pybricks/drive/turn"].parameters[1]
    assert "brick.imu.heading()" in choices(owner, parameter, offset)
    icon = blocks["pybricks/hubs/icon"].parameters[1]
    assert "Icon.HEART" in choices(owner, icon, offset)


@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
@pytest.mark.asyncio
async def test_finite_mission_returns_to_the_next_action_on_virtual_hubs(
    tmp_path, model
):
    source = (Path(__file__).parents[1] / "examples/line_mission.py").read_text()
    if model == "boost":
        source = source.replace("ColorSensor", "ColorDistanceSensor").replace(
            "Port.C", "Port.D"
        )
    path = tmp_path / "mission.py"
    path.write_text(source)
    output = []
    hub = VirtualConnection(output.append, model=model)
    try:
        await hub.connect()
        async with asyncio.timeout(6):
            await hub.run(path, wait=True)
            while b"Mission finished" not in b"".join(output):
                await asyncio.sleep(0.01)
        assert not hub.info.error
        assert all(hub.info.ports[p]["speed"] == 0 for p in "AB")
    finally:
        await hub.disconnect()
