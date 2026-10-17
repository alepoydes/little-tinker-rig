"""Control delivery survives a final disarm sample and operation interruption."""

import asyncio
from threading import Event

import pytest

from little_tinker_rig.pybricks.worker import HubWorker


@pytest.mark.parametrize("method", ["drive", "send"])
def test_latest_control_is_delivered_and_stop_discards_queued_motion(method):
    entered, delivered = Event(), Event()
    frames, failures = [], []
    release = asyncio.Event()

    class Connection:
        async def write(self, value):
            frames.append(value)
            if value:
                entered.set()
                await release.wait()
            else:
                delivered.set()

        drive = send = write

        async def stop(self):
            frames.append("stop")

        async def disconnect(self):
            pass

    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.connection = Connection()
    control = getattr(worker, method)
    try:
        control(1)
        assert entered.wait(1)
        control(2)
        control(0)
        worker.loop.call_soon_threadsafe(release.set)
        assert delivered.wait(1)
        assert frames == [1, 0]
        worker.loop.call_soon_threadsafe(release.clear)
        entered.clear()
        control(3)
        assert entered.wait(1)
        control(4)
        worker.stop_program().result(timeout=1)
        assert frames == [1, 0, 3, "stop"]
        assert not failures
    finally:
        worker.close()
