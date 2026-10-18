from pathlib import Path

import pytest

from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.control import ControlState


@pytest.mark.parametrize(
    "payload",
    [
        b"{'ports': []}",
        b"{'ports': {'A': []}}",
        b"{'ports': {'A': {'type': 'motor', 'angle': 'broken'}}}",
        b"{'ports': {'A': {'type': 'motor'}}, 'battery_mv': 'low'}",
        b'{"ports": {"A": {"type": "motor", "angle": NaN}}}',
    ],
)
def test_bad_monitor_telemetry_stays_in_console_without_poisoning_hub_info(payload):
    output = []
    connection = Connection(output.append)
    connection._monitor_requested = True
    wire = b"\x1eLITTLE_TINKER_RIG " + payload + b"\n"
    connection._telemetry.feed(wire)
    assert b"".join(output) == wire
    assert not connection.info.monitoring
    assert connection.info.ports == {}


def test_program_output_that_looks_like_telemetry_is_not_lost():
    output = []
    connection = Connection(output.append)
    wire = b"\x1eLITTLE_TINKER_RIG {'ports': {}}\n"
    connection._telemetry.feed(wire)
    assert b"".join(output) == wire
    assert not connection.info.monitoring


@pytest.mark.asyncio
async def test_disconnected_operations_fail_explicitly():
    connection = Connection()
    for operation in (
        lambda: connection.run(Path("main.py")),
        connection.stop,
        lambda: connection.send(ControlState()),
    ):
        with pytest.raises(ValueError, match="Connect"):
            await operation()
    await connection.disconnect()


@pytest.mark.asyncio
async def test_transport_boundary_receives_source_controls_and_shutdown(
    tmp_path, monkeypatch
):
    pytest.importorskip("pybricksdev")
    from pybricksdev import ble
    from pybricksdev.connections import pybricks
    from reactivex.subject import Subject

    events = []

    class Hub:
        def __init__(self, device):
            self.stdout_observable = Subject()

        async def connect(self):
            events.append("connect")

        async def run(self, path, **options):
            assert events[-1] == "stop"
            assert Path(path).read_text() == "print(1)\n"
            assert options == {
                "wait": False,
                "print_output": False,
                "line_handler": False,
            }
            self.stdout_observable.on_next(b"hello\n")

        async def write(self, data):
            events.append(ControlState.decode(data))

        async def stop_user_program(self):
            events.append("stop")

        async def disconnect(self):
            events.append("disconnect")

    async def discover(name):
        assert name == "Classroom"
        return object()

    monkeypatch.setattr(ble, "find_device", discover)
    monkeypatch.setattr(pybricks, "PybricksHubBLE", Hub)
    output = []
    connection = Connection(output.append)
    await connection.connect("Classroom")
    path = tmp_path / "main.py"
    path.write_text("print(1)\n")
    await connection.run(path)
    state = ControlState(0.5, -1)
    await connection.send(state)
    await connection.stop()
    await connection.disconnect()
    assert output == [b"hello\n"]
    assert events == ["connect", "stop", state, "stop", "disconnect"]


@pytest.mark.asyncio
async def test_real_transport_monitor_identity_telemetry_and_braking(monkeypatch):
    pytest.importorskip("pybricksdev")
    from pybricksdev import ble
    from pybricksdev.ble.lwp3 import HubKind
    from pybricksdev.ble.pybricks import StatusFlag
    from pybricksdev.connections import pybricks
    from reactivex.subject import BehaviorSubject, Subject

    from little_tinker_rig.pybricks.devices import encode_commands

    events = []

    class Hub:
        hub_kind = HubKind.BOOST
        fw_version = "3.6.0"

        def __init__(self, device):
            self.stdout_observable = Subject()
            self.status_observable = BehaviorSubject(StatusFlag(0))

        async def connect(self):
            pass

        async def stop_user_program(self):
            events.append("stop")
            self.status_observable.on_next(StatusFlag(0))

        async def run(self, path, **options):
            self.status_observable.on_next(StatusFlag.USER_PROGRAM_RUNNING)
            self.stdout_observable.on_next(
                b"\x1eLITTLE_TINKER_RIG {'name': 'Classroom', 'model': 'boost', 'ports': {'A': {'type': 'motor', 'angle': 15}}, 'battery_mv': 7900}\n"
            )

        async def write(self, data):
            events.append(data)

        async def disconnect(self):
            events.append("disconnect")

    async def discover(name):
        return object()

    monkeypatch.setattr(ble, "find_device", discover)
    monkeypatch.setattr(pybricks, "PybricksHubBLE", Hub)
    info, output = [], []
    connection = Connection(output.append, info.append)
    await connection.connect()
    assert connection.info.model == "boost"
    await connection.start_monitor()
    assert connection.info.monitoring and not connection.info.running
    assert connection.info.name == "Classroom"
    assert connection.info.battery_mv == 7900
    assert connection.info.ports["A"]["angle"] == 15
    await connection.drive((("A", "servo", 90),))
    await connection.disconnect()
    assert events == [
        "stop",
        encode_commands((("A", "servo", 90),)),
        "stop",
        "disconnect",
    ]
    assert not connection.info.connected
    assert output == []


@pytest.mark.asyncio
async def test_upload_uses_download_without_running_and_stored_run_sends_no_source(
    tmp_path,
):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    path = tmp_path / "main.py"
    path.write_text("print(1)\n")
    hub = SimpleNamespace(
        stop_user_program=AsyncMock(), download=AsyncMock(), run=AsyncMock()
    )
    connection = Connection()
    connection.hub = hub
    await connection.upload(path)
    hub.stop_user_program.assert_awaited_once()
    hub.download.assert_awaited_once_with(str(path.resolve()))
    hub.run.assert_not_awaited()
    assert not connection.info.running
    await connection.run()
    hub.run.assert_awaited_once_with(
        None, wait=False, print_output=False, line_handler=False
    )
    assert hub.download.await_count == 1


@pytest.mark.asyncio
async def test_console_input_serializes_writes_and_does_not_enter_monitor():
    import asyncio

    connection = Connection()
    with pytest.raises(ValueError, match="Connect"):
        await connection.write_input(b"go\r")
    active, received = False, []

    class Hub:
        async def write(self, data):
            nonlocal active
            assert not active
            active = True
            await asyncio.sleep(0)
            received.append(data)
            active = False

    connection.hub = Hub()
    await asyncio.gather(connection.write_input(b"a"), connection.write_input(b"b"))
    assert received == [b"a", b"b"]
    async with connection._write_lock:
        pending = asyncio.create_task(connection.write_input(b"unexpected\r"))
        await asyncio.sleep(0)
        connection._update(monitoring=True)
    with pytest.raises(ValueError, match="Stop the port monitor"):
        await pending
    assert received == [b"a", b"b"]


@pytest.mark.asyncio
async def test_ble_timeout_preserves_failure_and_bounds_cleanup(monkeypatch):
    import asyncio

    pytest.importorskip("pybricksdev")
    from pybricksdev import ble
    from pybricksdev.connections import pybricks

    disconnected = []

    class Hub:
        def __init__(self, device):
            pass

        async def connect(self):
            await asyncio.Event().wait()

        async def disconnect(self):
            disconnected.append(True)
            await asyncio.Event().wait()

    async def discover(name):
        return object()

    monkeypatch.setattr(ble, "find_device", discover)
    monkeypatch.setattr(pybricks, "PybricksHubBLE", Hub)
    connection = Connection()
    connection.connect_timeout = connection.disconnect_timeout = 0.02
    async with asyncio.timeout(0.5):
        with pytest.raises(TimeoutError, match="Hub connection timed out"):
            await connection.connect()
    assert disconnected == [True]
    assert connection.hub is None and not connection.info.connected
