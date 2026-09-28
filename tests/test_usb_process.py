"""Native USB stalls cannot prevent cancellation or retain a device handle."""

import asyncio
import sys

import pytest

pytest.importorskip("pybricksdev")
from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.usb_process import USBHub

# A real child with deliberately blocking calls, never a USB device.
DRIVER = """
import json, sys, time
mode = sys.argv[1]
if mode == 'connect':
    time.sleep(60)
print(json.dumps({'reply': 0, 'value': {'name': 'Test', 'firmware': '4.1.0', 'kind': 129}}), flush=True)
for line in sys.stdin:
    identifier, method, args, options = json.loads(line)
    if method == mode:
        time.sleep(60)
    if method == 'write':
        print(json.dumps({'output': args[0]}), flush=True)
    print(json.dumps({'reply': identifier}), flush=True)
    if method == 'disconnect':
        break
"""


@pytest.fixture
def driver(monkeypatch):
    spawn = asyncio.create_subprocess_exec
    processes = []
    mode = ["connect"]

    async def start(*args, **options):
        process = await spawn(sys.executable, "-u", "-c", DRIVER, mode[0], **options)
        processes.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", start)
    return mode, processes


@pytest.mark.asyncio
async def test_cancel_blocked_native_connect_reaps_child_and_allows_reconnect(driver):
    mode, processes = driver
    hub = USBHub()
    task = asyncio.create_task(hub.connect())
    async with asyncio.timeout(3):
        while hub.process is None:
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert processes[0].returncode is not None
    assert hub.process is None
    mode[0] = "normal"
    output = []
    hub.stdout_observable.subscribe(output.append)
    try:
        await hub.connect()
        await hub.write(b"hello\x00\xff\n")
        assert output == [b"hello\x00\xff\n"]
        assert hub.name == "Test"
    finally:
        await hub.disconnect()
    assert all(p.returncode is not None for p in processes)


@pytest.mark.asyncio
async def test_connection_timeout_kills_blocked_usb_discovery(driver):
    _, processes = driver
    hub = Connection()
    hub.connect_timeout = 0.15
    async with asyncio.timeout(3):
        with pytest.raises(TimeoutError, match="Hub connection timed out"):
            await hub.connect(transport="usb")
    assert processes and processes[0].returncode is not None
    assert hub.hub is None and not hub.info.connected


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["run", "disconnect"])
async def test_unresponsive_native_operation_cannot_block_disconnect(driver, method):
    mode, processes = driver
    mode[0] = method
    hub = USBHub()
    hub.close_timeout = 0.1
    await hub.connect()
    async with asyncio.timeout(3):
        if method == "run":
            task = asyncio.create_task(hub.run("main.py"))
            await asyncio.sleep(0.03)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        await hub.disconnect()
    assert hub.process is None
    assert processes[0].returncode is not None
