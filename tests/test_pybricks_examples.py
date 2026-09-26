"""Imported activities must rebuild from the palette without changing behavior."""

import ast
import inspect
import json
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
CATALOG = json.loads((EXAMPLES / "catalog.json").read_text())
PROGRAMS = sorted(EXAMPLES.glob("*.py"))
TRACE_PROGRAMS = [
    EXAMPLES / name
    for name in (
        "boost_17101_auto_builder.py",
        "inventor_51515_tricky.py",
        "spike_45678_cnc.py",
        "spike_45678_grabber.py",
        "spike_45678_kiki.py",
        "technic_42099_off_roader.py",
        "technic_42099_off_roader_remote.py",
        "technic_42124_buggy.py",
    )
]


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
    if name == "inventor_51515_tricky":
        world.configure("D", "ultrasonic")
    if name == "spike_45678_grabber":
        world.configure("E", "force")
    if name == "spike_45678_kiki":
        world.configure("B", "color")
    if name == "inventor_51515_blast":
        world.configure("E", "color")
        world.configure("F", "ultrasonic")
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
        if name == "inventor_51515_blast":
            hub_class = hubs.PrimeHub

            def prime_hub():
                hub = hub_class()
                hub.display.orientation = lambda up: trace.append(
                    ("orientation", up.name)
                )
                spy(hub.display, "icon", "display.icon")
                hub.display.image = lambda image: hub.display.icon(image)
                return hub

            hubs.PrimeHub = hubs.InventorHub = prime_hub
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
        if name == "inventor_51515_tricky":
            sensor = pupdevices.UltrasonicSensor

            def distance_sensor(port):
                result = sensor(port)
                result.distance = readings((200, 50, 150))
                spy(result.lights, "on", "eyes.on")
                spy(result.lights, "off", "eyes.off")
                return result

            pupdevices.UltrasonicSensor = distance_sensor
        if name == "spike_45678_grabber":
            sensor = pupdevices.ForceSensor

            def force_sensor(port):
                result = sensor(port)
                result.pressed = readings((True, False, True))
                return result

            pupdevices.ForceSensor = force_sensor
        if name == "spike_45678_kiki":
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
        if "remote" in name or name == "technic_42124_buggy":
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
            assert name not in {
                "boost_17101_auto_builder",
                "spike_45678_cnc",
                "technic_42099_off_roader",
            }
        return trace, world.snapshot(), world.feedback.copy()


@pytest.mark.parametrize(
    "path",
    TRACE_PROGRAMS
    + [EXAMPLES / "inventor_51515_mvp.py", EXAMPLES / "inventor_51515_blast.py"],
    ids=lambda p: p.stem,
)
def test_examples_rebuild_from_standard_palette_and_keep_commands(path):
    snippets = builtin_snippets()
    source = path.read_text()
    session = Session.fragment(source, snippets)
    assert not session.analysis.diagnostics()
    rebuilt = rebuild(source, snippets)
    before = execute(source, path.stem)
    assert execute(rebuilt, path.stem) == before
    trace, ports, _ = before
    if path.stem == "boost_17101_auto_builder":
        assert [
            dict(args)["target_angle"]
            for label, args in trace
            if label == "B.run_target"
        ][1:] == [0, 697, 365, 697, 244, 697, 521, 697, 128, 697, 0]
    if path.stem == "spike_45678_cnc":
        assert ports["A"]["angle"] == ports["C"]["angle"] == 0
        assert [
            dict(args)["rotation_angle"]
            for label, args in trace
            if label.endswith(".run_angle")
        ] == [400, 100, -400, -100]
    if path.stem == "spike_45678_grabber":
        assert [
            label for label, _ in trace if label in {"A.run", "A.run_until_stalled"}
        ] == ["A.run", "A.run_until_stalled", "A.run"]
    if path.stem == "inventor_51515_tricky":
        assert [
            dict(args)["angle"] for label, args in trace if label == "drive.turn"
        ] == [360, -360]
    if path.stem == "spike_45678_kiki":
        displays = [
            dict(args)["icon"] for label, args in trace if label == "display.icon"
        ]
        assert len(displays) == 3 and displays[1] == "Icon.UP"
        assert any(label == "display.off" for label, _ in trace)
    if path.stem == "inventor_51515_mvp":
        assert ports["A"]["angle"] == pytest.approx(50, abs=1)
        assert ports["B"]["angle"] == pytest.approx(-16 * 360, abs=1)
    if path.stem == "inventor_51515_blast":
        assert [
            dict(args)["rotation_angle"]
            for label, args in trace
            if label == "D.run_angle"
        ] == [-850, 800, -800]
    if path.stem.startswith("technic"):
        assert ports["A"]["speed"] == 0
        speeds = [dict(args)["speed"] for label, args in trace if label == "A.run"]
        assert any(s > 0 for s in speeds) and any(s < 0 for s in speeds)


def test_pattern_and_named_icon_keep_distinct_fields_and_shared_feedback():
    with virtual_activity("spike_45678_cnc") as (world, _):
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


@pytest.mark.parametrize("path", PROGRAMS, ids=lambda p: p.stem)
async def test_entire_catalog_compiles_and_rebuilds_without_changing_algorithms(path):
    from pybricksdev.compile import compile_multi_file

    source = path.read_text()
    session = Session.fragment(source, builtin_snippets())
    assert not session.analysis.diagnostics()
    rebuilt = rebuild(source, session.snippets)

    class RuntimeTree(ast.NodeTransformer):
        def visit_AnnAssign(self, node):
            if node.value is None:
                return node
            return ast.Assign(targets=[node.target], value=self.visit(node.value))

    # Recognition may add string type hints to declarations. All executable
    # expressions, calls, branches, timing and loop bodies must stay identical.
    assert ast.dump(RuntimeTree().visit(ast.parse(rebuilt))) == ast.dump(
        RuntimeTree().visit(ast.parse(source))
    )
    for abi in (5, 6):
        compiled = await compile_multi_file(str(path.resolve()), abi)
        assert compiled
    item = next(item for item in CATALOG["examples"] if item["file"] == path.name)
    for dependency in item["dependencies"]:
        assert dependency.removesuffix(".py").encode() in compiled


def test_catalog_has_unique_set_names_and_local_dependencies():
    files = {item["file"] for item in CATALOG["examples"]}
    assert len(files) == len(CATALOG["examples"])
    assert files == {p.name for p in PROGRAMS}
    hashes = {}
    for item in CATALOG["examples"]:
        assert f"_{item['set']}_" in item["file"]
        assert set(item["dependencies"]) <= files
        assert item["source"].split("/")[1] in CATALOG["families"]
        # One upstream program can be adapted for more than one LEGO build.
        assert hashes.setdefault(item["source"], item["sha256"]) == item["sha256"]


@pytest.mark.parametrize(
    "filename,ports,powers,waits",
    [
        ("technic_42160_audi_xbox_blocks.py", ("D", ("A", "B")), [6, 22], []),
        ("technic_42160_audi_xbox_python.py", ("D", ("A", "B")), [8, 16, 24, 32], []),
        ("technic_42109_xbox.py", ("B", ("D",)), [6, 22], [50, 50]),
    ],
)
def test_xbox_examples_preserve_input_sampling_and_commands(
    filename, ports, powers, waits
):
    path = EXAMPLES / filename

    def run(source):
        with virtual_activity(path.stem) as (_, trace):
            from pybricks import iodevices, robotics

            def triggers():
                count[0] += 1
                if count[0] > 4:
                    raise EndInputs
                trace.append(("triggers", count[0]))
                return (count[0] * 2, count[0] * 10)

            class Car:
                def __init__(self, steering, motors):
                    if not isinstance(motors, (list, tuple)):
                        motors = (motors,)
                    trace.append(
                        ("car", (steering.port, tuple(m.port for m in motors)))
                    )

                def drive_power(self, power):
                    trace.append(("power", power))

                def steer(self, angle):
                    trace.append(("steer", angle))

            count = [0]
            robotics.Car = Car
            iodevices.XboxController = lambda: SimpleNamespace(
                triggers=triggers, joystick_left=lambda: (25, 0)
            )
            with pytest.raises(EndInputs):
                exec(source, {})
            return trace

    source = path.read_text()
    trace = run(source)
    assert run(rebuild(source, builtin_snippets())) == trace
    assert [value for label, value in trace if label == "car"] == [ports]
    assert [value for label, value in trace if label == "power"] == powers
    assert {value for label, value in trace if label == "steer"} == {25}
    assert [
        dict(value)["milliseconds"] for label, value in trace if label == "wait"
    ] == waits


def test_keyboard_block_is_nonblocking_and_reads_one_character():
    snippet = next(
        s for s in builtin_snippets() if s.identity == "pybricks/keyboard/read_key_code"
    )
    expansion = instantiate(snippet, {})
    from types import ModuleType

    stdin = SimpleNamespace(read=lambda count: calls.append(("read", count)) or "q")
    calls = []
    ready = [False]

    class Poll:
        def register(self, stream):
            assert stream is stdin

        def poll(self, timeout):
            calls.append(("poll", timeout))
            return [1] if ready[0] else []

    sys_module, select_module = ModuleType("usys"), ModuleType("uselect")
    sys_module.stdin, select_module.poll = stdin, Poll
    with patch.dict(sys.modules, usys=sys_module, uselect=select_module):
        scope = {}
        exec("\n".join(expansion.helpers), scope)
        assert eval(expansion.source, scope) is None
        assert calls == [("poll", 0)]
        ready[0] = True
        assert eval(expansion.source, scope) == ord("q")
        assert calls[-2:] == [("poll", 0), ("read", 1)]


@pytest.mark.parametrize(
    "radius,angle", [(200, 90), (200, -90), (-200, 90), (-200, -90)]
)
def test_old_curve_adapter_preserves_distance_and_heading_signs(radius, angle):
    snippet = next(
        s for s in builtin_snippets() if s.identity == "pybricks/drive/legacy_curve"
    )
    expansion = instantiate(snippet, {"radius": str(radius), "angle": str(angle)})
    calls = []
    scope = {"drive": SimpleNamespace(arc=lambda r, a: calls.append((r, a)))}
    exec("\n".join(expansion.helpers), scope)
    exec(expansion.source, scope)
    r, a = calls[0]
    assert abs(r) == abs(radius) and abs(a) == abs(angle)
    assert (a > 0) == (radius > 0)
    assert (r * a > 0) == (angle > 0)


def test_hardware_operations_have_specific_palette_blocks():
    # Inspect device calls independently of broad assignment/function placeholders.
    snippets = tuple(
        s
        for s in builtin_snippets()
        if s.identity != "python/basics/assign"
        and s.identity
        not in {"python/basics/call_function", "python/basics/call_value"}
    )
    for path in PROGRAMS:
        source = path.read_text()
        session = Session.fragment(source, snippets)
        tree, syntax = session.document.syntax.tree, session.document.syntax
        device_names = {
            a.asname or a.name
            for n in tree.body
            if isinstance(n, ast.ImportFrom)
            and (n.module or "").startswith("pybricks.")
            for a in n.names
        }
        item = next(item for item in CATALOG["examples"] if item["file"] == path.name)
        trees = [
            tree,
            *(
                ast.parse((EXAMPLES / dependency).read_text())
                for dependency in item["dependencies"]
            ),
        ]
        local_methods = {
            n.name
            for module in trees
            for c in ast.walk(module)
            if isinstance(c, ast.ClassDef)
            for n in c.body
            if isinstance(n, ast.FunctionDef)
        }
        matches = recognize(syntax, snippets, session.analysis)
        from pyblocks.core.helpers import helper_section

        managed = helper_section(source)
        for node in ast.walk(tree):
            if (
                not isinstance(node, ast.Call)
                or managed
                and managed.contains(syntax.spans[node].start)
            ):
                continue
            device = isinstance(node.func, ast.Name) and node.func.id in device_names
            device |= (
                isinstance(node.func, ast.Attribute)
                and node.func.attr not in local_methods
            )
            if not device:
                continue
            span = syntax.spans[node]
            assert any(
                m.span.start <= span.start and span.end <= m.span.end for m in matches
            ), (path.name, ast.unparse(node))
