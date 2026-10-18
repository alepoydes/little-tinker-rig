"""Control delivery survives a final disarm sample and operation interruption."""

import asyncio
from concurrent.futures import Future
from threading import Event

import pytest

from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.devices import HubInfo
from little_tinker_rig.pybricks.program import Program
from little_tinker_rig.pybricks.virtual import VirtualConnection
from little_tinker_rig.pybricks.worker import HubWorker


def test_disconnected_worker_rejects_program_actions_and_releases_connection(tmp_path):
    calls, failures = [], []

    class Transport:
        async def disconnect(self):
            calls.append("disconnect")

        async def stop(self):
            calls.append("stop")

        async def run(self, path=None):
            calls.append("run")

    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)
    try:
        worker.disconnect_hub().result(timeout=1)
        assert worker.connection is None
        assert worker.run_file(path) is None
        assert worker.upload_file(path) is None
        assert worker.run_stored() is None
        assert worker.start_monitor() is None
        assert calls == ["disconnect"]
        assert len(failures) == 4 and all("Connect" in error for error in failures)
    finally:
        worker.close()


def test_worker_rejects_upload_after_unexpected_connection_loss(tmp_path):
    failures = []
    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print('hello')\n", encoding="utf-8")

    class Transport:
        async def disconnect(self):
            pass

    worker.connection = Transport()
    worker.info = HubInfo(connected=False)
    try:
        assert worker.upload_file(path) is None
        assert failures == ["Connect a hub first"]
        assert worker.stop_program().result(timeout=1) is None
    finally:
        worker.close()


def test_failed_disconnect_clears_old_transport():
    output = []

    class Transport:
        async def disconnect(self):
            raise TimeoutError

    worker = HubWorker(
        output=output.append,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)
    try:
        worker.disconnect_hub().result(timeout=1)
        assert worker.connection is None and not worker.info.connected
        assert any("did not acknowledge" in message for message in output)
    finally:
        worker.close()


@pytest.mark.parametrize("action", ["run_file", "upload_file"])
def test_busy_worker_rejects_transfer_before_building_snapshot(monkeypatch, action):
    failures = []
    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )

    class Transport:
        async def disconnect(self):
            pass

    worker.connection = Transport()
    worker.info = HubInfo(connected=True)
    worker.operation = Future()

    def unexpected_snapshot(*args):
        pytest.fail("A busy hub must not build a program snapshot")

    monkeypatch.setattr(
        "little_tinker_rig.pybricks.worker.Program", unexpected_snapshot
    )
    try:
        assert getattr(worker, action)("unused.py") is None
        assert failures == ["Wait for the hub operation to finish"]
    finally:
        worker.close()


def test_transfer_rejected_during_snapshot_creation_cleans_temporary_files(
    tmp_path, monkeypatch
):
    failures, snapshots = [], []
    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )

    class Transport:
        async def disconnect(self):
            pass

    path = tmp_path / "main.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)

    def race(path, sources):
        program = Program(path, sources)
        snapshots.append(program.entry.parent)
        worker.operation = Future()
        return program

    monkeypatch.setattr("little_tinker_rig.pybricks.worker.Program", race)
    try:
        assert worker.run_file(path) is None
        assert snapshots and not snapshots[0].exists()
        assert failures == ["Wait for the hub operation to finish"]
    finally:
        worker.close()


def test_virtual_worker_uses_one_process_transition_per_program_action(
    tmp_path, monkeypatch
):
    launches, failures = [], []
    original = VirtualConnection._spawn

    async def counted(self, path=None):
        launches.append(path)
        return await original(self, path)

    monkeypatch.setattr(VirtualConnection, "_spawn", counted)
    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print('hello')\n", encoding="utf-8")
    try:
        worker.connect_hub(transport="virtual").result(timeout=8)
        assert len(launches) == 1
        worker.upload_file(path).result(timeout=8)
        assert len(launches) == 2
        worker.run_stored().result(timeout=8)
        assert len(launches) == 3 and launches[-1] is not None
        worker.stop_program().result(timeout=8)
        before = len(launches)
        worker.run_file(path).result(timeout=8)
        assert len(launches) == before + 1 and launches[-1] is not None
        worker.start_monitor().result(timeout=8)
        assert len(launches) == before + 2 and launches[-1] is None
        assert not failures
    finally:
        worker.close()


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
    worker.info = HubInfo(connected=True)
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


@pytest.mark.parametrize("operation", ["stop_program", "disconnect_hub"])
def test_interrupt_cancels_active_and_queued_console_writes(operation):
    entered = Event()
    calls, failures = [], []

    class Transport:
        async def write(self, data):
            calls.append(data)
            entered.set()
            await asyncio.Event().wait()

        async def stop_user_program(self):
            calls.append("stop")

        async def disconnect(self):
            calls.append("disconnect")

    worker = HubWorker(
        output=lambda *_: None,
        failed=failures.append,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.connection = Connection()
    worker.connection.hub = Transport()
    worker.info = HubInfo(connected=True, running=True)
    try:
        first = worker.write_input(b"first")
        assert entered.wait(1)
        second = worker.write_input(b"queued")
        getattr(worker, operation)().result(timeout=1)
        assert first.cancelled() and second.cancelled()
        assert calls == [
            b"first",
            "stop" if operation == "stop_program" else "disconnect",
        ]
        assert not failures
    finally:
        worker.close()
