import asyncio
import queue
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("serial")
pytest.importorskip("pybricksdev")

from pybricksdev.connections import ConnectionState

from little_tinker_rig.pybricks import usb_serial
from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.usb_serial import Frames, SerialHub, decode, encode


def test_cobs_wire_vectors_boundaries_and_fragmented_resynchronization():
    # Published SPIKE COBS vectors, also used by upstream test_cobs.c.
    assert encode(b"\0") == b"\0\0\x02"
    assert encode(b"ABC") == b"\x05\x42\x41\x40\x02"
    messages = [bytes(range(256)), b"\0\x01\x02" * 100]
    messages += [b"A" * length for length in (83, 84, 85, 167, 168, 169)]
    for message in messages:
        frame = encode(message)
        assert not {1, 2, 3}.intersection(frame[:-1])
        assert decode(frame[:-1]) == message
        for split in range(len(frame) + 1):
            parser = Frames()
            assert list(parser.feed(frame[:split])) + list(
                parser.feed(frame[split:])
            ) == [message]
    parser = Frames(limit=20)
    stream = b"A" * 40 + b"\x02\xff\x02" + encode(b"hello") + encode(b"world")
    assert list(parser.feed(stream)) == [b"hello", b"world"]
    assert list(parser.feed(b"junk\x01" + encode(b"hello"))) == [b"hello"]
    with pytest.raises(ValueError):
        decode(b"\xff")


class HubPort:
    """A byte-stream peer: replies are fragmented, events share the same stream."""

    def __init__(self, kind=0x81):
        self.kind = kind
        self.incoming = queue.Queue()
        self.closed = False
        self.messages = []
        self.reply = True

    @property
    def in_waiting(self):
        return self.incoming.qsize()

    def emit(self, *messages):
        for byte in b"".join(encode(message) for message in messages):
            self.incoming.put(bytes([byte]))

    def read(self, size):
        try:
            item = self.incoming.get(timeout=0.01)
        except queue.Empty:
            return b""
        if isinstance(item, Exception):
            raise item
        return item

    def write(self, data):
        message = decode(data[:-1])
        self.messages.append(message)
        if not self.reply:
            return len(data)
        if message[0] == 3:
            service, characteristic = struct.unpack("<BH", message[1:])
            value = {
                (1, 0x2A00): b"Classroom",
                (1, 0x2A26): b"4.1.0b4",
                (1, 0x2A28): b"1.7.0",
                (1, 0x2A50): struct.pack("<BHHH", 1, 0x0397, self.kind, 0),
                (2, 3): struct.pack(
                    "<HIIB", 20, 34 if self.kind == 0x81 else 2, 4096, 5
                ),
            }[service, characteristic]
            self.emit(message + value)
        elif message[0] == 2:
            # Deliberately include a wrong tag and an unrelated stdout event.
            response = bytes((1, message[1])) + b"\0" * 4
            if message[2] == 1:
                self.emit(self.status(0), response, self.status(64))
            else:
                self.emit(
                    bytes((1, message[1] ^ 128)) + b"\0" * 4, b"\x02\x01ok\n", response
                )
        elif message == b"\x01\x01":
            self.emit(self.status(0))
        return len(data)

    def status(self, flags):
        return b"\x02\x00" + struct.pack("<IBB", flags, 0, 3)

    def close(self):
        self.closed = True


async def connected(monkeypatch, kind=0x81):
    import serial

    port = HubPort(kind)
    monkeypatch.setattr(serial, "Serial", lambda *args, **kwargs: port)
    hub = SerialHub("test")
    await hub.connect()
    return hub, port


@pytest.mark.parametrize("kind,model", [(0x81, "inventor"), (0xE2, "ev3")])
async def test_usb_upload_run_console_and_identity(kind, model, tmp_path, monkeypatch):
    hub, port = await connected(monkeypatch, kind)
    # Exercise the same public wrapper as Qt/TUI, including stdout forwarding.
    monkeypatch.setattr(
        "little_tinker_rig.pybricks.usb_process.USBHub", lambda name: hub
    )
    monkeypatch.setattr(hub, "connect", AsyncMock())
    output = []
    connection = Connection(output.append)
    await connection.connect(transport="usb")
    assert (connection.info.name, connection.info.model) == ("Classroom", model)
    payload = bytes(range(200))
    compiler = AsyncMock(return_value=payload)
    monkeypatch.setattr(usb_serial, "compile_multi_file", compiler)
    try:
        await connection.upload(tmp_path / "main.py")
        assert compiler.call_args.args[1] == ((6, 3) if kind == 0x81 else 6)
        commands = [message[2:] for message in port.messages if message[0] == 2]
        assert not any(command[0] == 1 for command in commands)
        assert commands[1] == b"\x03\0\0\0\0"
        chunks = [command for command in commands if command[0] == 4]
        assert [struct.unpack_from("<I", chunk, 1)[0] for chunk in chunks] == list(
            range(0, 200, 15)
        )
        assert b"".join(chunk[5:] for chunk in chunks) == payload
        assert commands[-1] == b"\x03" + struct.pack("<I", len(payload))
        assert b"ok\n" in output

        task = asyncio.create_task(connection.run(wait=True))
        async with asyncio.timeout(2):
            while not any(
                message[:1] == b"\x02" and message[2] == 1 for message in port.messages
            ):
                await asyncio.sleep(0.001)
        await asyncio.sleep(0.02)
        assert not task.done()  # The idle report before START's ack is stale.
        await connection.write_input(b"go\n")
        port.emit(port.status(0))
        await asyncio.wait_for(task, 2)
        assert not connection.info.running
        assert compiler.await_count == 1  # Running stored code does not upload.
        assert any(
            message[2:] == b"\x06go\n" for message in port.messages if message[0] == 2
        )
        if model == "ev3":
            with pytest.raises(ValueError, match="not supported"):
                await connection.start_monitor()
    finally:
        await connection.disconnect()
    assert port.closed and not connection.info.connected


@pytest.mark.parametrize("failure", ["timeout", "cancel", "unplug"])
async def test_pending_request_failure_closes_stream_and_fails_future_work(
    failure, monkeypatch
):
    hub, port = await connected(monkeypatch)
    port.reply = False
    hub.timeout = 0.03
    pending = asyncio.create_task(hub.write(b"test"))
    await asyncio.sleep(0.01)
    if failure == "cancel":
        pending.cancel()
    elif failure == "unplug":
        port.incoming.put(OSError("unplugged"))
    with pytest.raises((TimeoutError, asyncio.CancelledError, OSError)):
        await pending
    assert port.closed
    assert hub.connection_state_observable.value == ConnectionState.DISCONNECTED
    # A late reply cannot make another command appear successful.
    port.emit(b"\x01\x01\0\0\0\0")
    with pytest.raises(ConnectionError):
        await hub.write(b"later")


async def test_failed_upload_never_commits_partial_program(monkeypatch):
    hub, port = await connected(monkeypatch)
    monkeypatch.setattr(
        usb_serial, "compile_multi_file", AsyncMock(return_value=b"A" * 32)
    )
    original = port.write

    def reject_chunk(data):
        message = decode(data[:-1])
        if message[0] == 2 and message[2] == 4:
            port.messages.append(message)
            port.emit(bytes((1, message[1], 0x13, 0, 0, 0)))
            return len(data)
        return original(data)

    port.write = reject_chunk
    try:
        with pytest.raises(ValueError, match="rejected"):
            await hub.download("main.py")
        assert [msg[2:] for msg in port.messages if msg[0] == 2 and msg[2] == 3] == [
            b"\x03\0\0\0\0"
        ]
    finally:
        await hub.disconnect()


def test_usb_discovery_selects_cdc_ports_or_retains_legacy_backend(monkeypatch):
    import serial.tools.list_ports
    import usb.core
    from pybricksdev.connections import pybricks

    ports = [
        SimpleNamespace(vid=0x0694, pid=pid, device=name, serial_number=name)
        for pid, name in [(0x10, "COM3"), (5, "COM4")]
    ]
    monkeypatch.setattr(serial.tools.list_ports, "comports", lambda: ports)
    assert usb_serial.find_hub("COM4").device == "COM4"
    with pytest.raises(ValueError, match="COM3.*COM4"):
        usb_serial.find_hub()
    ports.clear()
    device = SimpleNamespace(product="Hub Pybricks")
    monkeypatch.setattr(
        usb.core,
        "find",
        lambda **kwargs: [device] if kwargs["custom_match"](device) else [],
    )
    monkeypatch.setattr(pybricks, "PybricksHubUSB", lambda d: ("legacy", d))
    assert usb_serial.find_hub() == ("legacy", device)
