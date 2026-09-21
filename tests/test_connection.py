from pathlib import Path

import pytest

from pyblocks.pybricks.connection import Connection
from pyblocks.pybricks.control import ControlState


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
    assert events == ["connect", state, "stop", "disconnect"]
