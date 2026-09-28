import asyncio
import json
import sys
from pathlib import Path

import pytest

from little_tinker_rig.pybricks.control import ControlState
from little_tinker_rig.pybricks.devices import (
    MotorBinding,
    TelemetryStream,
    encode_commands,
    motor_commands,
)
from little_tinker_rig.pybricks.simulation import World
from little_tinker_rig.pybricks.virtual import VirtualConnection


def test_manual_speed_servo_and_expired_command_have_physical_results():
    world = World()
    bindings = (
        MotorBinding("A", "left_y", scale=200),
        MotorBinding("B", "right_trigger", "servo", 90, 20),
    )
    world.drive(motor_commands(bindings, ControlState(left_y=1, right_trigger=1)))
    world.advance(0.2)
    assert world.snapshot()["A"]["angle"] == 40
    assert world.snapshot()["B"]["angle"] == 100
    world.advance(0.8)
    snapshot = world.snapshot()
    assert snapshot["A"]["angle"] == 100
    assert snapshot["B"]["angle"] == 110
    assert snapshot["A"]["speed"] == snapshot["B"]["speed"] == 0
    world.drive(motor_commands(bindings, ControlState()))
    world.advance(0.2)
    assert world.snapshot()["B"]["angle"] == 20
    world.drive(())
    before = world.snapshot()
    world.advance(10)
    assert world.snapshot() == before


def test_duplicate_port_mapping_is_rejected_before_movement():
    with pytest.raises(ValueError, match="once"):
        motor_commands(
            (MotorBinding("A", "left_x"), MotorBinding("A", "right_x")), ControlState()
        )
    world = World()
    before = world.snapshot()
    with pytest.raises(OSError):
        world.drive((("A", "speed", 500), ("C", "speed", 500)))
    assert world.snapshot() == before


def test_timed_motion_integrates_only_until_deadline_and_can_be_replaced():
    world = World()
    first = world.command("A", speed=100, duration=0.25)
    world.advance(0.125)
    assert world.pending("A", first)
    second = world.command("A", speed=200, duration=0.5)
    world.advance(0.25)  # The old deadline must not stop the new command.
    assert not world.pending("A", first)
    assert world.pending("A", second)
    assert world.snapshot()["A"]["speed"] == 200
    world.advance(1)
    assert not world.pending("A", second)
    assert world.snapshot()["A"]["angle"] == 112.5
    assert world.snapshot()["A"]["speed"] == 0
    world.advance(10)
    assert world.snapshot()["A"]["angle"] == 112.5


@pytest.mark.parametrize("action", ["run_time", "run_target", "straight"])
def test_waiting_motion_does_not_stop_a_replacement(monkeypatch, action):
    from queue import Queue
    from unittest.mock import patch

    from little_tinker_rig.pybricks.sim_runtime import install_modules

    world = World()
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        from pybricks.parameters import Port
        from pybricks.pupdevices import Motor
        from pybricks.robotics import DriveBase

        motor = Motor(Port.A)
        right = Motor(Port.B)

        def replace(_):
            motor.run(500)
            right.run(400)

        monkeypatch.setattr(
            "little_tinker_rig.pybricks.sim_runtime.time.sleep", replace
        )
        if action == "run_time":
            motor.run_time(100, 200)
        elif action == "run_target":
            motor.run_target(100, 200)
        else:
            DriveBase(motor, right, 56, 112).straight(200)
        world.advance(1)
        assert motor.speed() == 500 and right.speed() == 400
        assert motor.angle() == 500


def test_nonblocking_timed_motor_is_synchronous_to_start_and_replace():
    from queue import Queue
    from unittest.mock import patch

    from little_tinker_rig.pybricks.sim_runtime import install_modules

    world = World()
    with patch.dict(sys.modules):
        install_modules(world, Queue())
        from pybricks.parameters import Port
        from pybricks.pupdevices import Motor

        motor = Motor(Port.A)
        motor.run_time(100, 200, wait=False)
        assert motor.speed() == 100
        world.advance(0.1)
        motor.run(500)
        world.advance(1)
        assert motor.speed() == 500 and motor.angle() == 510
        motor.run_time(100, 200, wait=False)
        world.advance(1)
        assert motor.speed() == 0 and motor.angle() == 530


@pytest.mark.parametrize("encode", [json.dumps, repr])
def test_telemetry_and_unicode_console_survive_every_packet_boundary(encode):
    text = "Привет, робот!\n".encode()
    payload = {"ports": {"A": {"angle": 42}}, "monitoring": True}
    wire = (
        text
        + b"\x1eLITTLE_TINKER_RIG "
        + encode(payload).encode()
        + b"\n"
        + b"prompt> "
    )
    for size in range(1, len(wire) + 1):
        output, packets = [], []
        stream = TelemetryStream(output.append, packets.append)
        for start in range(0, len(wire), size):
            stream.feed(wire[start : start + size])
        stream.finish()
        assert b"".join(output) == text + b"prompt> "
        assert packets == [payload]


def test_controller_triggers_round_trip_and_legacy_frame():
    state = ControlState(left_y=0.75, left_trigger=0.25, right_trigger=1)
    assert ControlState.decode(state.encode()) == state
    assert len(ControlState().encode()) == 16


async def wait_until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.02)


@pytest.mark.asyncio
async def test_virtual_hub_program_sensors_console_and_stop(tmp_path):
    output = []
    hub = VirtualConnection(output.append)
    try:
        await hub.connect()
        assert hub.info.connected and hub.info.monitoring
        await hub.configure("C", "color", 73)
        await wait_until(lambda: hub.info.ports["C"].get("reflection") == 73)
        program = tmp_path / "robot.py"
        program.write_text(
            "from pybricks.pupdevices import Motor, ColorSensor\nfrom pybricks.parameters import Port\nm = Motor(Port.A)\nm.run_angle(360, 90)\nprint('Датчик:', ColorSensor(Port.C).reflection())\n",
            encoding="utf-8",
        )
        await hub.run(program, wait=True)
        await wait_until(lambda: b"73" in b"".join(output))
        assert "Датчик:" in b"".join(output).decode()
        assert hub.info.ports["A"]["angle"] == pytest.approx(90, abs=1)
        assert hub.info.ports["A"]["speed"] == 0
        program.write_text("while True:\n    pass\n")
        await hub.run(program)
        process = hub.process
        assert hub.info.running
        await hub.stop()
        assert process.returncode is not None
        assert hub.info.connected and not hub.info.running
        assert hub.info.monitoring
    finally:
        await hub.disconnect()
    assert not hub.info.connected and hub.process is None


@pytest.fixture
def generated_helper_program(tmp_path):
    from little_tinker_rig.core.session import Session
    from little_tinker_rig.core.snippets import load_module

    (snippet,) = load_module(
        """
def advance(motor, angle=90):
    motor.run_angle(360, angle)

@block(level="beginner", icon="↻", color="action")
def turn(motor: "Motor" = motor, angle: "number[deg]" = 90) -> "number[deg]":
    initial = motor.angle()
    advance(motor, angle)
    return motor.angle() - initial
""",
        "test/motors",
        "1",
    )
    session = Session(tmp_path / "turn.py")
    setup = next(
        s for s in session.snippets if s.identity == "pybricks/motors/create_motor"
    )
    session.insert_snippet(setup, {"name": "motor"})
    session.editor.commit(session.document.state.source + "result = None\n")
    session.editor.select(session.document.state.source.index("None"))
    session.insert_snippet(snippet, {})
    session.editor.commit(
        session.document.state.source + "print('turn:', result, motor.angle())\n"
    )
    session.project.save()
    return session.project.path


@pytest.mark.parametrize("model", ["inventor", "boost", "technic"])
@pytest.mark.asyncio
async def test_generated_block_helpers_drive_virtual_hub(
    generated_helper_program, model
):
    output = []
    hub = VirtualConnection(output.append, model=model)
    try:
        await hub.connect()
        await hub.run(generated_helper_program, wait=True)
        await wait_until(lambda: b"turn:" in b"".join(output))
        line = next(
            line for line in b"".join(output).splitlines() if line.startswith(b"turn:")
        )
        assert tuple(map(float, line.split()[1:])) == pytest.approx((90, 90), abs=1)
        assert hub.info.ports["A"]["angle"] == pytest.approx(90, abs=1)
        assert hub.info.ports["A"]["speed"] == 0
    finally:
        await hub.disconnect()


@pytest.mark.asyncio
async def test_generated_block_helpers_compile_for_hub_abis(generated_helper_program):
    from pybricksdev.compile import compile_file

    for abi in (5, 6):
        compiled = await compile_file(
            str(generated_helper_program.parent), generated_helper_program.name, abi
        )
        assert compiled[:2] == bytes((ord("M"), abi))


@pytest.mark.asyncio
async def test_virtual_manual_motor_lease_and_disconnect():
    hub = VirtualConnection()
    await hub.connect()
    process = hub.process
    try:
        await hub.drive((("A", "speed", 200),))
        await wait_until(lambda: hub.info.ports["A"]["angle"] > 10)
        await wait_until(lambda: hub.info.ports["A"]["speed"] == 0)
        assert hub.info.ports["A"]["angle"] == pytest.approx(100, abs=2)
    finally:
        await hub.disconnect()
    assert process.returncode is not None


@pytest.mark.parametrize(
    "model, ports", [("inventor", "ABCDEF"), ("boost", "ABCD"), ("technic", "ABCD")]
)
@pytest.mark.asyncio
async def test_target_hub_profiles_and_real_monitor_program(model, ports):
    # Launch the actual hub monitor against modeled public Pybricks APIs. BOOST
    # deliberately has no iodevices module, as on the target firmware.
    monitor = Path(__file__).parents[1] / "little_tinker_rig/pybricks/hub_monitor.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "-m",
        "little_tinker_rig.pybricks.sim_runtime",
        "--model",
        model,
        "--program",
        str(monitor),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    output, reports = [], []
    stream = TelemetryStream(output.append, reports.append)

    async def report():
        async with asyncio.timeout(5):
            while True:
                line = await process.stdout.readline()
                assert line, b"".join(output)
                stream.feed(line)
                if reports:
                    return reports.pop(0)

    try:
        first = await report()
        assert set(first["ports"]) == set(ports)
        assert first["ports"]["A"]["type"] == "motor"
        if model == "boost":
            assert first["ports"]["B"]["type"] == "motor"
            assert first["ports"]["D"]["type"] == "color_distance"
        process.stdin.write(encode_commands((("A", "speed", 200),)))
        await process.stdin.drain()
        moved = await report()
        assert moved["ports"]["A"]["angle"] > first["ports"]["A"]["angle"]
        assert moved["ports"]["A"]["speed"] > 0
        async with asyncio.timeout(5):
            while (await report())["ports"]["A"]["speed"] != 0:
                pass
    finally:
        process.terminate()
        await process.wait()


@pytest.mark.asyncio
async def test_virtual_error_and_stderr_do_not_break_telemetry(tmp_path):
    output = []
    hub = VirtualConnection(output.append, model="boost")
    program = tmp_path / "error.py"
    program.write_text(
        'import sys\nsys.stderr.write(\'42\\n{"log": 1}\\n\')\nraise RuntimeError("test failure")\n'
    )
    try:
        await hub.connect()
        await hub.configure(
            "D", "color_distance", {"reflection": 12, "distance_percent": 81}
        )
        await wait_until(lambda: hub.info.ports["D"]["distance_percent"] == 81)
        with pytest.raises(ValueError, match="test failure"):
            await hub.run(program, wait=True)
        assert hub.info.connected and hub.info.monitoring
        assert hub.info.ports["D"]["reflection"] == 12
        assert hub.info.ports["D"]["distance_percent"] == 81
        await wait_until(lambda: b'{"log": 1}' in b"".join(output))
        program.write_text("import os\nos._exit(3)\n")
        with pytest.raises(ValueError, match="exited unexpectedly"):
            await hub.run(program, wait=True)
        assert not hub.info.connected
    finally:
        await hub.disconnect()


@pytest.mark.parametrize(
    "model, ports", [("inventor", "ABCDEF"), ("boost", "ABCD"), ("technic", "ABCD")]
)
def test_monitor_imports_firmware_modules_and_reports_ports(model, ports, capsys):
    import builtins
    import queue
    from unittest.mock import patch

    from little_tinker_rig.pybricks.sim_runtime import install_modules

    class Finished(BaseException):
        pass

    world = World(model=model)
    with patch.dict(sys.modules):
        install_modules(world, queue.Queue())
        package = sys.modules["pybricks"]
        modules = {
            "pybricks." + name: value
            for name, value in vars(package).items()
            if not name.startswith("_")
        }
        for name in tuple(vars(package)):
            if not name.startswith("_"):
                delattr(package, name)

        def firmware_import(name, globals=None, locals=None, fromlist=(), level=0):
            # Built-in firmware modules are registered by full name and return
            # the leaf, even without fromlist. There is no parent.hubs attribute.
            if name.startswith("pybricks."):
                if name not in modules:
                    raise ImportError(name)
                return modules[name]
            return builtins.__import__(name, globals, locals, fromlist, level)

        def finish(milliseconds):
            raise Finished()

        modules["pybricks.tools"].wait = finish
        monitor = (
            Path(__file__).parents[1] / "little_tinker_rig/pybricks/hub_monitor.py"
        )
        with pytest.raises(Finished):
            exec(
                compile(monitor.read_text(), str(monitor), "exec"),
                {
                    "__name__": "__main__",
                    "__builtins__": dict(vars(builtins), __import__=firmware_import),
                },
            )
    reports = []
    TelemetryStream(lambda text: None, reports.append).feed(
        capsys.readouterr().out.encode()
    )
    assert len(reports) == 1
    assert reports[0]["model"] == model
    assert set(reports[0]["ports"]) == set(ports)
    assert reports[0]["ports"]["A"]["type"] == "motor"
    assert reports[0]["battery_mv"] > 0
    assert reports[0]["monitoring"] is True


def test_monitor_redetects_unknown_devices_and_unplugged_ports(monkeypatch, capsys):
    import queue
    import runpy
    from unittest.mock import patch

    from little_tinker_rig.pybricks.sim_runtime import install_modules

    class Finished(BaseException):
        pass

    now = 0
    with patch.dict(sys.modules):
        install_modules(World(), queue.Queue())
        from pybricks import tools
        from pybricks.iodevices import PUPDevice

        info = PUPDevice.info

        def identify(device):
            if device.port == "A":
                if now == 0:
                    return {"id": 999}
                if now == 2000:
                    raise OSError("Device unplugged")
            if device.port == "B" and now == 0:
                return {"id": 999}
            return info(device)

        def advance(milliseconds):
            nonlocal now
            now += 2000
            if now > 4000:
                raise Finished()

        monkeypatch.setattr(PUPDevice, "info", identify)
        monkeypatch.setattr(tools.StopWatch, "time", lambda self: now)
        monkeypatch.setattr(tools, "wait", advance)
        monitor = (
            Path(__file__).parents[1] / "little_tinker_rig/pybricks/hub_monitor.py"
        )
        with pytest.raises(Finished):
            runpy.run_path(str(monitor), run_name="__main__")

    reports = []
    TelemetryStream(lambda text: None, reports.append).feed(
        capsys.readouterr().out.encode()
    )
    assert [r["ports"]["A"]["type"] for r in reports] == ["unknown", "empty", "motor"]
    assert [r["ports"]["B"]["type"] for r in reports] == ["unknown", "motor", "motor"]


def test_monitor_brakes_started_motors_if_later_device_fails(monkeypatch):
    import queue
    import runpy
    from unittest.mock import patch

    from little_tinker_rig.pybricks.sim_runtime import install_modules

    class Finished(BaseException):
        pass

    world = World()
    incoming = queue.Queue()
    for byte in encode_commands((("A", "speed", 200), ("B", "speed", 200))):
        incoming.put(byte)
    with patch.dict(sys.modules):
        install_modules(world, incoming)
        from pybricks import tools
        from pybricks.pupdevices import Motor

        run_motor = Motor.run

        def run(self, speed):
            if self.port == "B":
                raise OSError("Motor disconnected during command")
            run_motor(self, speed)

        def end_cycle(milliseconds):
            assert world.snapshot()["A"]["speed"] == 0
            raise Finished()

        monkeypatch.setattr(Motor, "run", run)
        monkeypatch.setattr(tools, "wait", end_cycle)
        monitor = (
            Path(__file__).parents[1] / "little_tinker_rig/pybricks/hub_monitor.py"
        )
        with pytest.raises(Finished):
            runpy.run_path(str(monitor), run_name="__main__")


@pytest.mark.asyncio
@pytest.mark.parametrize("finish", ["complete", "emergency", "device_error"])
async def test_courier_obstacle_delivery_and_shutdown(finish):
    output = []
    hub = VirtualConnection(output.append)

    def printed(text):
        return text.encode() in b"".join(output)

    try:
        await hub.connect()
        await hub.configure("F", "motor")
        await wait_until(lambda: hub.info.ports["F"]["type"] == "motor")
        await hub.run(Path(__file__).parents[1] / "examples/courier.py")
        await wait_until(lambda: printed("state=following"))
        await wait_until(lambda: hub.info.ports["A"]["speed"] != 0)
        await hub.configure("D", "ultrasonic", 50)
        await wait_until(
            lambda: printed("state=blocked")
            and hub.info.ports["A"]["speed"] == 0
            and hub.info.ports["B"]["speed"] == 0
        )
        await hub.configure("D", "ultrasonic", 500)
        await wait_until(lambda: hub.info.ports["A"]["speed"] != 0)
        await hub.configure("C", "color", 5)
        await wait_until(lambda: printed("delivery=1"))
        await hub.configure("C", "color", 50)
        await wait_until(lambda: hub.info.ports["A"]["speed"] != 0)
        if finish == "complete":
            await hub.configure("C", "color", 5)
        elif finish == "device_error":
            await hub.configure("E", "empty")
        else:
            await hub.configure("E", "force", 5)
        await wait_until(lambda: not hub.info.running)
        await wait_until(lambda: printed("state=" + finish))
        assert not hub.info.error
        assert printed("delivery=2") == (finish == "complete")
        assert all(hub.info.ports[port]["speed"] == 0 for port in "ABF")
    finally:
        await hub.disconnect()


@pytest.mark.asyncio
async def test_courier_deadline_stops_every_motor(tmp_path):
    from shutil import copyfile

    copyfile(Path(__file__).parents[1] / "examples/courier.py", tmp_path / "courier.py")
    program = tmp_path / "deadline.py"
    program.write_text(
        "from courier import run_route\nprint(run_route(time_limit_ms=1))\n"
    )
    output = []
    hub = VirtualConnection(output.append)
    try:
        await hub.connect()
        await hub.configure("F", "motor")
        await wait_until(lambda: hub.info.ports["F"]["type"] == "motor")
        await hub.run(program, wait=True)
        await wait_until(lambda: b"state=timeout" in b"".join(output))
        assert not hub.info.error
        assert all(hub.info.ports[port]["speed"] == 0 for port in "ABF")
    finally:
        await hub.disconnect()
