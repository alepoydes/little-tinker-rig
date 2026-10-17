"""Exercise the pinned CDC client through the real USB child and a synthetic PTY."""

import asyncio
import contextlib
import os
import struct
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("pybricksdev")
pytest.importorskip("serial")
from pybricksdev.usb.cobs import pack, unpack

from little_tinker_rig.pybricks.connection import Connection


class Peer:
    def __init__(self, master, kind):
        self.master, self.kind = master, kind
        self.requests = asyncio.Queue()
        self.commands = []
        self.output = []
        self.started = asyncio.Event()
        self.written = asyncio.Event()
        self.silent = self.reject_upload = False
        self.buffer = bytearray()

    def read(self):
        self.buffer.extend(os.read(self.master, 4096))
        while b"\x02" in self.buffer:
            frame, _, rest = self.buffer.partition(b"\x02")
            self.buffer[:] = rest
            if frame:
                self.requests.put_nowait(unpack(frame))

    def emit(self, message):
        framed = pack(message)
        os.write(self.master, framed[:2])
        os.write(self.master, framed[2:])

    def status(self, flags):
        self.emit(b"\x02\x00" + struct.pack("<IBB", flags, 0, 3))

    async def serve(self):
        while True:
            request = await self.requests.get()
            if request[0] == 3:
                value = {
                    b"\x01\x28\x2a": b"1.7.0",
                    b"\x01\x00\x2a": b"Classroom",
                    b"\x01\x26\x2a": b"4.1.0b6",
                    b"\x01\x50\x2a": struct.pack("<BHHH", 1, 0x397, self.kind, 0),
                    b"\x02\x03\x00": struct.pack(
                        "<HIIB", 20, 34 if self.kind == 0x81 else 2, 4096, 5
                    ),
                }[request[1:]]
                self.emit(request + value)
            elif request[0] == 2:
                command = request[2:]
                self.commands.append(command)
                self.written.set()
                if self.silent:
                    continue
                if command[0] == 1:
                    self.status(0)  # Idle before START acknowledgement is stale.
                    self.started.set()
                # A reply with a different tag must not acknowledge this command.
                self.emit(bytes([1, request[1] ^ 128, 0, 0, 0, 0]))
                status = 0x13 if command[0] == 4 and self.reject_upload else 0
                self.emit(bytes([1, request[1], status, 0, 0, 0]))
            elif request == b"\x01\x01":
                # Deliberately withhold the first status: START must use the
                # hub's selected slot without requiring a warm-up notification.
                pass


@pytest.fixture
async def cdc(monkeypatch, request):
    if os.name != "posix":
        pytest.skip("PTY requires POSIX")
    import pty

    master, slave = pty.openpty()
    os.set_blocking(master, False)
    peer = Peer(master, getattr(request, "param", 0x81))
    loop = asyncio.get_running_loop()
    loop.add_reader(master, peer.read)
    serving = asyncio.create_task(peer.serve())
    spawn = asyncio.create_subprocess_exec
    script = """
import sys
from pybricksdev.connections.serial import PybricksHubSerial
from little_tinker_rig.pybricks import usb, usb_process
usb.find_hub = lambda selector: PybricksHubSerial(selector, timeout=0.2)
usb_process.main()
"""

    async def start(*args, **options):
        if args[1:3] == ("-u", "-m") and args[3].endswith("usb_process"):
            args = (sys.executable, "-u", "-c", script, *args[4:])
        return await spawn(*args, **options)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", start)
    connection = Connection(peer.output.append)
    try:
        await connection.connect(os.ttyname(slave), "usb")
        yield connection, peer
    finally:
        await connection.disconnect()
        serving.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await serving
        loop.remove_reader(master)
        os.close(master)
        os.close(slave)


@pytest.mark.parametrize("cdc", [0x81, 0xE2], indirect=True)
async def test_public_client_upload_run_binary_input_and_short_completion(
    cdc, tmp_path
):
    connection, peer = cdc
    assert connection.info.name == "Classroom"
    assert connection.info.model == ("inventor" if peer.kind == 0x81 else "ev3")
    source = tmp_path / "main.py"
    source.write_text("print('ready')\n", encoding="utf-8")
    await connection.upload(source)
    chunks = [command for command in peer.commands if command[0] == 4]
    program = b"".join(command[5:] for command in chunks)
    assert program[4:].startswith(b"__main__\0M\x06")
    assert peer.commands[-1] == b"\x03" + struct.pack("<I", len(program))
    assert not any(command[0] == 1 for command in peer.commands)
    task = asyncio.create_task(connection.run(wait=True))
    try:
        await asyncio.wait_for(peer.started.wait(), 1)
        # Exceed the dependency's one-second short-program heuristic. Only a
        # fresh idle report, not silence or a pre-START idle, confirms completion.
        await asyncio.sleep(1.1)
        assert not task.done()
        assert next(command for command in peer.commands if command[0] == 1) == b"\x01"
        payload = bytes(range(256)) + "Привет\n".encode()
        peer.emit(b"\x02\x01hello\n")
        await connection.write_input(payload)
        assert b"".join(c[1:] for c in peer.commands if c[0] == 6) == payload
        assert b"".join(peer.output) == b"hello\n"
        peer.status(0)
        await asyncio.wait_for(task, 1)
        assert not connection.info.running
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("cancel", [False, True])
async def test_interrupted_write_disconnects_and_allows_reconnect(cdc, cancel):
    connection, peer = cdc
    selector = connection.hub.selector
    peer.silent = True
    task = asyncio.create_task(connection.write_input(b"input"))
    await asyncio.wait_for(peer.written.wait(), 1)
    if cancel:
        task.cancel()
    with pytest.raises(
        asyncio.CancelledError if cancel else (ValueError, ConnectionError)
    ):
        await asyncio.wait_for(task, 1)
    await connection.disconnect()
    peer.silent = False
    await connection.connect(selector, "usb")
    await connection.stop()
    assert connection.info.connected


async def test_failed_upload_does_not_commit_partial_program(cdc, tmp_path):
    connection, peer = cdc
    source = tmp_path / "main.py"
    source.write_text("print(42)\n", encoding="utf-8")
    peer.reject_upload = True
    with pytest.raises(ValueError, match="Write failed"):
        await connection.upload(source)
    assert [c for c in peer.commands if c[0] == 3] == [b"\x03\0\0\0\0"]
    peer.reject_upload = False
    await connection.upload(source)
    assert struct.unpack_from("<I", peer.commands[-1], 1)[0] > 0


async def test_pinned_compiler_uploads_viper_and_precompiled_import(cdc, tmp_path):
    from pybricksdev.compile import compile_file

    connection, peer = cdc
    utility = tmp_path / "utility.py"
    utility.write_text("value = 42\n", encoding="utf-8")
    utility.with_suffix(".mpy").write_bytes(
        await compile_file(str(tmp_path), utility.name, 6)
    )
    utility.unlink()
    source = tmp_path / "main.py"
    source.write_text(
        "import micropython\nfrom utility import value\n"
        "@micropython.viper\ndef add(a: int, b: int) -> int: return a + b\n"
        "print(add(value, 1))\n",
        encoding="utf-8",
    )
    await connection.upload(source)
    package = b"".join(c[5:] for c in peer.commands if c[0] == 4)
    modules = {}
    while package:
        size = int.from_bytes(package[:4], "little")
        name, _, data = package[4:].partition(b"\0")
        modules[name.decode()] = data[:size]
        package = data[size:]
    assert set(modules) == {"__main__", "utility"}
    assert modules["__main__"][:4] == b"M\x06\x1f\x1f"
    assert modules["utility"][:4] == b"M\x06\x00\x1f"


@pytest.mark.parametrize("cancel", [False, True])
async def test_waiting_run_releases_on_disconnect_or_cancellation(cdc, cancel):
    connection, peer = cdc
    task = asyncio.create_task(connection.run(wait=True))
    await asyncio.wait_for(peer.started.wait(), 1)
    # Ensure START has completed and the wait owns its subscriptions.
    await connection.write_input(b"ready\n")
    if cancel:
        task.cancel()
    else:
        await connection.disconnect()
    with pytest.raises(asyncio.CancelledError if cancel else ConnectionError):
        await asyncio.wait_for(task, 1)
    if cancel:
        await connection.stop()
        assert connection.info.connected


def test_discovery_selects_cdc_ports_or_retains_legacy_backend(monkeypatch):
    import serial.tools.list_ports
    import usb.core
    from pybricksdev.connections import pybricks

    from little_tinker_rig.pybricks.usb import find_hub

    ports = [
        SimpleNamespace(vid=0x0694, pid=pid, device=name, serial_number=name)
        for pid, name in [(0x10, "COM3"), (5, "COM4")]
    ]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)
    assert find_hub("COM4").port == "COM4"
    with pytest.raises(ValueError, match="COM3.*COM4"):
        find_hub()
    ports.clear()
    device = SimpleNamespace(product="Hub Pybricks")
    monkeypatch.setattr(
        usb.core,
        "find",
        lambda **kwargs: [device] if kwargs["custom_match"](device) else [],
    )
    monkeypatch.setattr(pybricks, "PybricksHubUSB", lambda d: ("legacy", d))
    assert find_hub() == ("legacy", device)
