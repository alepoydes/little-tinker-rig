"""Control delivery survives a final disarm sample and operation interruption."""

import asyncio
from concurrent.futures import Future
from threading import Event

import pytest

from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.control import ControlState
from little_tinker_rig.pybricks.devices import HubInfo
from little_tinker_rig.pybricks.program import Program
from little_tinker_rig.pybricks.virtual import VirtualConnection
from little_tinker_rig.pybricks.worker import HubWorker


def test_worker_close_is_idempotent():
    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.close()
    worker.close()


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


def test_failed_operation_reports_error_before_idle():
    events = []
    idle = Event()

    def busy_changed(value):
        events.append(("busy", value))
        if not value:
            idle.set()

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda error: events.append(("failed", error)),
        updated=lambda *_: None,
        busy_changed=busy_changed,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )

    async def fail():
        raise OSError("Transfer interrupted")

    try:
        future = worker.submit(fail(), operation=True)
        with pytest.raises(OSError, match="Transfer interrupted"):
            future.result(timeout=1)
        assert idle.wait(1)
        assert events == [
            ("busy", True),
            ("failed", "Transfer interrupted"),
            ("busy", False),
        ]
    finally:
        worker.close()


def test_cancelled_operation_stays_busy_until_cleanup_finishes():
    events = []
    entered, cleaning, release, idle = Event(), Event(), Event(), Event()

    def busy_changed(value):
        events.append(value)
        if not value:
            idle.set()

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=busy_changed,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )

    async def wait_forever():
        entered.set()
        await asyncio.Event().wait()

    def cleanup():
        cleaning.set()
        release.wait(1)

    try:
        future = worker.submit(wait_forever(), operation=True, cleanup=cleanup)
        assert entered.wait(1)
        future.cancel()
        assert cleaning.wait(1)
        assert events == [True]
        release.set()
        assert idle.wait(1)
        assert events == [True, False]
    finally:
        release.set()
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


@pytest.mark.parametrize("action", ["run_file", "upload_file"])
def test_failed_transfer_cleans_temporary_snapshot(tmp_path, monkeypatch, action):
    snapshots = []
    original = Program

    def capture(path, sources):
        program = original(path, sources)
        snapshots.append(program.entry.parent)
        return program

    monkeypatch.setattr("little_tinker_rig.pybricks.worker.Program", capture)

    class Transport:
        async def run(self, path):
            raise RuntimeError("transfer failed")

        async def upload(self, path):
            raise RuntimeError("transfer failed")

        async def disconnect(self):
            pass

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print(42)\n", encoding="utf-8")
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)
    try:
        with pytest.raises(RuntimeError, match="transfer failed"):
            getattr(worker, action)(path).result(timeout=2)
        assert snapshots and not snapshots[0].exists()
        assert worker.stored_program is None
    finally:
        worker.close()


def test_interrupted_transfer_cleans_temporary_snapshot(tmp_path, monkeypatch):
    entered = Event()
    snapshots = []
    original = Program

    def capture(path, sources):
        program = original(path, sources)
        snapshots.append(program.entry.parent)
        return program

    monkeypatch.setattr("little_tinker_rig.pybricks.worker.Program", capture)

    class Transport:
        async def upload(self, path):
            entered.set()
            await asyncio.Event().wait()

        async def stop(self):
            pass

        async def disconnect(self):
            pass

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print(42)\n", encoding="utf-8")
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)
    try:
        transfer = worker.upload_file(path)
        assert entered.wait(2)
        worker.stop_program().result(timeout=2)
        assert transfer.cancelled()
        assert snapshots and not snapshots[0].exists()
    finally:
        worker.close()


def test_stop_cancels_transfer_queued_before_worker_loop_runs(tmp_path, monkeypatch):
    entered, release = Event(), Event()
    snapshots, calls = [], []
    original = Program

    def capture(path, sources):
        program = original(path, sources)
        snapshots.append(program.entry.parent)
        return program

    monkeypatch.setattr("little_tinker_rig.pybricks.worker.Program", capture)

    class Transport:
        async def upload(self, path):
            calls.append("upload")

        async def stop(self):
            calls.append("stop")

        async def disconnect(self):
            pass

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    path = tmp_path / "main.py"
    path.write_text("print(42)\n", encoding="utf-8")
    worker.connection = Transport()
    worker.info = HubInfo(connected=True)

    def hold_loop():
        entered.set()
        release.wait(2)

    try:
        worker.loop.call_soon_threadsafe(hold_loop)
        assert entered.wait(2)
        transfer = worker.upload_file(path)
        stop = worker.stop_program()
        release.set()
        stop.result(timeout=2)
        assert transfer.cancelled()
        assert calls == ["stop"]
        assert snapshots and not snapshots[0].exists()
    finally:
        release.set()
        worker.close()


@pytest.mark.parametrize("queued", ["connect", "disconnect"])
def test_stop_clears_queued_connection_action(queued):
    entered, release = Event(), Event()
    calls = []

    class Transport:
        async def stop(self):
            calls.append("stop")

        async def disconnect(self):
            calls.append("disconnect")

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    if queued == "disconnect":
        worker.connection = Transport()
        worker.info = HubInfo(connected=True)

    def hold_loop():
        entered.set()
        release.wait(2)

    try:
        worker.loop.call_soon_threadsafe(hold_loop)
        assert entered.wait(2)
        pending = (
            worker.connect_hub(transport="virtual")
            if queued == "connect"
            else worker.disconnect_hub()
        )
        stop = worker.stop_program()
        release.set()
        stop.result(timeout=2)
        assert pending.cancelled()
        assert worker.info.connection_action == ""
        assert calls == ([] if queued == "connect" else ["stop"])
    finally:
        release.set()
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


@pytest.mark.parametrize("elapsed, expected", [(0, [0, 1, 0]), (1, [0, 0])])
def test_button_edges_survive_coalescing_but_expire_if_transport_stalls(
    monkeypatch, elapsed, expected
):
    import little_tinker_rig.pybricks.worker as worker_module

    now = [0.0]
    monkeypatch.setattr(worker_module, "monotonic", lambda: now[0])
    entered = Event()
    release = asyncio.Event()
    frames = []

    class Peer:
        async def send(self, state):
            frames.append(state.buttons)
            if len(frames) == 1:
                entered.set()
                await release.wait()

        async def disconnect(self):
            pass

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.connection = Peer()
    worker.info = HubInfo(connected=True, running=True)
    try:
        worker.send(ControlState())
        assert entered.wait(1)
        pending = worker.pending
        worker.send(ControlState(buttons=1))
        worker.send(ControlState())
        now[0] = elapsed
        worker.loop.call_soon_threadsafe(release.set)
        pending.result(timeout=1)
        assert frames == expected
    finally:
        worker.loop.call_soon_threadsafe(release.set)
        worker.close()


@pytest.mark.parametrize("operation", ["stop_program", "disconnect_hub"])
def test_interruption_discards_queued_button_edges(operation):
    entered = Event()
    release = asyncio.Event()
    frames = []

    class Peer:
        async def send(self, state):
            frames.append(state.buttons)
            entered.set()
            await release.wait()

        async def stop(self):
            frames.append("stop")

        async def disconnect(self):
            frames.append("disconnect")

    worker = HubWorker(
        output=lambda *_: None,
        failed=lambda *_: None,
        updated=lambda *_: None,
        busy_changed=lambda *_: None,
        problem=lambda *_: None,
        program_started=lambda *_: None,
    )
    worker.connection = Peer()
    worker.info = HubInfo(connected=True, running=True)
    try:
        worker.send(ControlState(buttons=1))
        assert entered.wait(1)
        worker.send(ControlState())
        worker.send(ControlState(buttons=2))
        getattr(worker, operation)().result(timeout=1)
        assert frames == [1, "stop" if operation == "stop_program" else "disconnect"]
        assert not worker.control_edges
    finally:
        worker.loop.call_soon_threadsafe(release.set)
        worker.close()


@pytest.mark.parametrize("monitoring", [False, True])
@pytest.mark.parametrize("rearm", [False, True])
@pytest.mark.parametrize("elapsed", [0, 1])
def test_disarming_discards_queued_input_and_keeps_neutral_before_rearming(
    monitoring, rearm, elapsed, monkeypatch
):
    import little_tinker_rig.pybricks.worker as worker_module

    now = [0.0]
    monkeypatch.setattr(worker_module, "monotonic", lambda: now[0])
    entered, release = Event(), asyncio.Event()
    frames, failures = [], []

    class Peer:
        async def send(self, state):
            frames.append(state)
            if len(frames) == 1:
                entered.set()
                await release.wait()

        drive = send

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
    worker.connection = Peer()
    worker.info = HubInfo(connected=True, running=not monitoring, monitoring=monitoring)
    neutral = () if monitoring else ControlState()
    pressed = (("A", "speed", 100),) if monitoring else ControlState(buttons=1)
    control = worker.drive if monitoring else worker.send
    try:
        control(neutral)
        assert entered.wait(1)
        pending = worker.pending
        control(pressed)
        worker.release_controls()
        if rearm:
            control(pressed)
        now[0] = elapsed
        worker.loop.call_soon_threadsafe(release.set)
        pending.result(timeout=1)
        assert frames == [neutral, neutral] + ([pressed] if rearm else [])
        assert not failures
    finally:
        worker.loop.call_soon_threadsafe(release.set)
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
