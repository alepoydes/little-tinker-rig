"""Imported activities must rebuild from the palette without changing behavior."""

import ast
import inspect
import sys
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from pyblocks.core import edit
from pyblocks.core.session import Session
from pyblocks.core.snippets import builtin_snippets, instantiate, recognize
from pyblocks.pybricks.sim_runtime import install_modules
from pyblocks.pybricks.simulation import World

EXAMPLES = Path(__file__).parents[1] / "examples/pybricks"
PROGRAMS = sorted(EXAMPLES.glob("*.py"))


class EndInputs(Exception):
    """End an otherwise infinite activity after its scripted input sequence."""


def rebuild(source, snippets):
    session = Session.fragment(source, snippets)
    replacements = []
    for match in session.matches:
        expansion = instantiate(match.snippet, match.bindings, local_names=match.locals)
        column = session.document.syntax.position(match.span.start)[1]
        lines = expansion.source.splitlines()
        replacement = "\n".join([lines[0], *(" " * column + s for s in lines[1:])])
        replacements.append((match.span, replacement))
    return edit.patches(source, replacements)


@contextmanager
def virtual_activity(name):
    """Real virtual motor motion, with explicit scripted hardware boundaries.

    Mechanical stops, controller tuning, colored objects and BLE remote input
    are supplied here, not claimed as physical models of the interactive hub.
    """
    model = (
        "boost"
        if name.startswith("boost")
        else "technic" if name.startswith("technic") else "inventor"
    )
    world = World(model=model)
    for port in world.available_ports:
        world.configure(port, "motor")
    if name == "inventor_tricky":
        world.configure("D", "ultrasonic")
    if name == "spike_grabber":
        world.configure("E", "force")
    if name == "spike_kiki":
        world.configure("B", "color")
    trace, elapsed = [], [0.0]

    def advance(seconds):
        elapsed[0] += seconds
        world.advance(seconds)

    def plain(value):
        if isinstance(value, Enum):
            return type(value).__name__ + "." + value.name
        if isinstance(value, (list, tuple, set)):
            return tuple(plain(v) for v in value)
        return value

    def spy(owner, attribute, label):
        original = getattr(owner, attribute)
        signature = inspect.signature(original)

        def call(*args, **kwargs):
            arguments = signature.bind(*args, **kwargs)
            arguments.apply_defaults()
            trace.append(
                (label, tuple((k, plain(v)) for k, v in arguments.arguments.items()))
            )
            return original(*args, **kwargs)

        setattr(owner, attribute, call)

    def readings(values):
        values = iter(values)

        def read():
            try:
                return next(values)
            except StopIteration:
                raise EndInputs from None

        return read

    with (
        patch.dict(sys.modules),
        patch("pyblocks.pybricks.sim_runtime.time.sleep", advance),
        patch("pyblocks.pybricks.sim_runtime.time.monotonic", lambda: elapsed[0]),
    ):
        install_modules(world, Queue())
        from pybricks import hubs, pupdevices, robotics, tools
        from pybricks.parameters import Button, Color, Direction, Stop

        base_motor = pupdevices.Motor

        class Motor(base_motor):
            def __init__(
                self, port, positive_direction=Direction.CLOCKWISE, profile=None
            ):
                super().__init__(port, positive_direction)
                trace.append(("motor", (port.name, positive_direction.name, profile)))

                def limits(acceleration):
                    trace.append((self.port + ".acceleration", acceleration))

                self.control = SimpleNamespace(limits=limits)
                for method in (
                    "run",
                    "run_angle",
                    "run_time",
                    "run_target",
                    "reset_angle",
                    "run_until_stalled",
                ):
                    spy(self, method, self.port + "." + method)

            def run_until_stalled(self, speed, then=Stop.COAST, duty_limit=None):
                # Endpoints are physical shaft coordinates, independent of the
                # caller's current zero and positive direction.
                shaft = -105 if speed * self.sign < 0 else 95
                target = shaft * self.sign - self.zero
                self.run_target(abs(speed), target, then=then)
                return self.angle()

        pupdevices.Motor = Motor
        base_drive = robotics.DriveBase

        def drive_base(left_motor, right_motor, wheel_diameter, axle_track):
            drive = base_drive(left_motor, right_motor, wheel_diameter, axle_track)
            trace.append(
                (
                    "drive_base",
                    (left_motor.port, right_motor.port, wheel_diameter, axle_track),
                )
            )
            spy(drive, "turn", "drive.turn")
            return drive

        robotics.DriveBase = drive_base
        if name == "inventor_tricky":
            sensor = pupdevices.UltrasonicSensor

            def distance_sensor(port):
                result = sensor(port)
                result.distance = readings((200, 50, 150))
                spy(result.lights, "on", "eyes.on")
                spy(result.lights, "off", "eyes.off")
                return result

            pupdevices.UltrasonicSensor = distance_sensor
        if name == "spike_grabber":
            sensor = pupdevices.ForceSensor

            def force_sensor(port):
                result = sensor(port)
                result.pressed = readings((True, False, True))
                return result

            pupdevices.ForceSensor = force_sensor
        if name == "spike_kiki":
            sensor, hub = pupdevices.ColorSensor, hubs.PrimeHub

            def color_sensor(port):
                result = sensor(port)
                # The source reads again for each elif. Feed complete decision
                # paths for blue, yellow, green and an unrecognized color.
                result.color = readings(
                    (
                        Color.BLUE,
                        Color.YELLOW,
                        Color.YELLOW,
                        Color.GREEN,
                        Color.GREEN,
                        Color.GREEN,
                        Color.WHITE,
                        Color.WHITE,
                        Color.WHITE,
                    )
                )
                return result

            def prime_hub():
                result = hub()
                spy(result.display, "icon", "display.icon")
                spy(result.display, "off", "display.off")
                # Only for comparing the upstream v3 example with the v4 API.
                result.display.image = result.display.icon
                return result

            pupdevices.ColorSensor, hubs.PrimeHub = color_sensor, prime_hub
        if "remote" in name or name == "technic_buggy":
            inputs = (
                (),
                (Button.LEFT_PLUS,),
                (Button.RIGHT_PLUS,),
                (Button.LEFT_MINUS, Button.RIGHT_MINUS),
                (
                    Button.LEFT_PLUS,
                    Button.LEFT_MINUS,
                    Button.RIGHT_PLUS,
                    Button.RIGHT_MINUS,
                ),
                (),
            )
            pupdevices.Remote = lambda: SimpleNamespace(
                buttons=SimpleNamespace(pressed=readings(inputs))
            )
        spy(tools, "wait", "wait")
        yield world, trace


def execute(source, name):
    with virtual_activity(name) as (world, trace):
        try:
            exec(compile(source, name, "exec"), {})
        except EndInputs:
            assert name not in {"boost_auto_builder", "spike_cnc", "technic_off_roader"}
        return trace, world.snapshot(), world.feedback.copy()


@pytest.mark.parametrize("path", PROGRAMS, ids=lambda p: p.stem)
def test_examples_rebuild_from_standard_palette_and_keep_commands(path):
    snippets = builtin_snippets()
    source = path.read_text()
    session = Session.fragment(source, snippets)
    assert not session.analysis.diagnostics()
    # A broad assignment/call placeholder must not conceal an unsupported API.
    operations = tuple(
        s
        for s in session.available_snippets
        if s.expression
        or not (
            len(s.body) == 1
            and (
                isinstance(s.body[0], ast.Assign)
                and hasattr(s.body[0].value, "template_parameter")
                or isinstance(s.body[0], ast.Expr)
                and isinstance(s.body[0].value, ast.Call)
                and hasattr(s.body[0].value.func, "template_parameter")
            )
        )
    )
    matches = recognize(session.document.syntax, operations, session.analysis)
    for node in ast.walk(session.document.syntax.tree):
        if isinstance(node, ast.Call):
            span = session.document.syntax.spans[node]
            assert any(
                m.span.start <= span.start and span.end <= m.span.end for m in matches
            ), ast.unparse(node)
    rebuilt = rebuild(source, snippets)
    before = execute(source, path.stem)
    assert execute(rebuilt, path.stem) == before
    trace, ports, _ = before
    if path.stem == "boost_auto_builder":
        assert [
            dict(args)["target_angle"]
            for label, args in trace
            if label == "B.run_target"
        ][1:] == [0, 697, 365, 697, 244, 697, 521, 697, 128, 697, 0]
    if path.stem == "spike_cnc":
        assert ports["A"]["angle"] == ports["C"]["angle"] == 0
        assert [
            dict(args)["rotation_angle"]
            for label, args in trace
            if label.endswith(".run_angle")
        ] == [400, 100, -400, -100]
    if path.stem == "spike_grabber":
        assert [
            label for label, _ in trace if label in {"A.run", "A.run_until_stalled"}
        ] == ["A.run", "A.run_until_stalled", "A.run"]
    if path.stem == "inventor_tricky":
        assert [
            dict(args)["angle"] for label, args in trace if label == "drive.turn"
        ] == [360, -360]
    if path.stem == "spike_kiki":
        displays = [
            dict(args)["icon"] for label, args in trace if label == "display.icon"
        ]
        assert len(displays) == 3 and displays[1] == "Icon.UP"
        assert any(label == "display.off" for label, _ in trace)
    if path.stem.startswith("technic"):
        assert ports["A"]["speed"] == 0
        speeds = [dict(args)["speed"] for label, args in trace if label == "A.run"]
        assert any(s > 0 for s in speeds) and any(s < 0 for s in speeds)


def test_pattern_and_named_icon_keep_distinct_fields_and_shared_feedback():
    with virtual_activity("spike_cnc") as (world, _):
        from pybricks.hubs import PrimeHub

        hub = PrimeHub()
        pattern = [[100] * 5] + [[0] * 5 for _ in range(4)]
        hub.display.icon(pattern)
        pattern[0][0] = 0
        assert world.feedback["display"][0][0] == 100
        with pytest.raises(ValueError, match="five rows"):
            hub.display.icon([[100]])

    snippets = builtin_snippets()
    for value, expected in (
        ("Icon.UP", "icon"),
        ("[[0]*5 for _ in range(5)]", "display_pattern"),
    ):
        session = Session.fragment(
            "hub = PrimeHub()\nhub.display.icon(" + value + ")\n", snippets
        )
        assert session.matches[-1].snippet.identity == "pybricks/hubs/" + expected


def test_imported_programs_open_with_their_blocks_available_in_the_panel(
    tmp_path, qt_app
):
    from pyblocks.qt.app import Studio
    from pyblocks.qt.library import IDENTITY

    for example in PROGRAMS:
        path = tmp_path / example.name
        source = example.read_text()
        path.write_text(source)
        window = Studio(path)
        loaded = window.session.document.state.source
        assert ast.dump(ast.parse(loaded)) == ast.dump(ast.parse(source))
        try:
            window.show()
            window.level_filter.setCurrentIndex(window.level_filter.findData("all"))
            qt_app.processEvents()
            identities = {
                window.library.topLevelItem(i).child(j).data(0, IDENTITY)
                for i in range(window.library.topLevelItemCount())
                for j in range(window.library.topLevelItem(i).childCount())
            }
            assert {m.snippet.identity for m in window.session.matches} <= identities
            assert window.session.document.state.source == loaded
        finally:
            window.close()
