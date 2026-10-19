"""Shared hub operations in one worker, with callbacks for desktop and terminal UIs."""

import asyncio
import codecs
from dataclasses import replace
from threading import Event, Lock, Thread

from little_tinker_rig.core.runtime_errors import Tracebacks
from little_tinker_rig.i18n import tr
from little_tinker_rig.pybricks.connection import Connection
from little_tinker_rig.pybricks.devices import HubInfo
from little_tinker_rig.pybricks.program import Program
from little_tinker_rig.pybricks.virtual import VirtualConnection


class HubWorker:
    def __init__(
        self, *, output, failed, updated, busy_changed, problem, program_started
    ):
        self._output = output
        self._failed = failed
        self._updated = updated
        self._busy_changed = busy_changed
        self._problem = problem
        self._program_started = program_started
        self.info = HubInfo()
        self.connection = None
        self.operation = self.pending = None
        self.control_lock = Lock()
        self.latest_control = None
        self.tracebacks = None
        self.stored_program = None
        self.lock = asyncio.Lock()
        self.tasks = set()
        self.generation = 0
        self.connection_generation = 0
        ready = Event()

        def run():
            with asyncio.Runner() as runner:
                self.loop = runner.get_loop()
                ready.set()
                self.loop.run_forever()

        self.thread = Thread(target=run, name="little-tinker-rig-hub", daemon=True)
        self.thread.start()
        if not ready.wait(5):
            raise RuntimeError("Could not start hub event loop")

    def _remember(self, info):
        self.info = replace(info, connection_action=self.info.connection_action)
        self._updated(self.info)

    def _connection_action(self, action):
        self.info = replace(self.info, connection_action=action)
        self._updated(self.info)

    def _clear_connection_action(self, action):
        if self.info.connection_action == action:
            self._connection_action("")

    def submit(self, coroutine, *, operation=False, interrupt=False, cleanup=None):
        if operation and self.operation and not self.operation.done():
            if not interrupt:
                coroutine.close()
                if cleanup:
                    cleanup()
                self._failed(tr("Wait for the hub operation to finish"))
                return None
        if operation:
            self.generation += 1
            if interrupt and self.operation:
                self.operation.cancel()
            with self.control_lock:
                self.latest_control = None
                if self.pending:
                    self.pending.cancel()
            self._busy_changed(True)
        generation = self.generation
        lifecycle_lock = Lock()
        started = aborted = released = False

        def release(*, succeeded=False):
            nonlocal released
            with lifecycle_lock:
                if released:
                    return
                released = True
            coroutine.close()
            if not succeeded and cleanup:
                cleanup()

        async def serialized():
            nonlocal started
            task = asyncio.current_task()
            with lifecycle_lock:
                started = True
                cancelled_before_start = aborted
            succeeded = False
            try:
                if cancelled_before_start:
                    raise asyncio.CancelledError
                if interrupt:
                    # Console writes and device configuration share this lock
                    # too. Interrupt every earlier task, including queued work.
                    for previous in self.tasks:
                        # A second cancellation can abort the first task's
                        # cleanup before it releases the connection lock.
                        if not previous.cancelling():
                            previous.cancel()
                self.tasks.add(task)
                async with self.lock:
                    with lifecycle_lock:
                        if aborted:
                            raise asyncio.CancelledError
                    result = await coroutine
                    succeeded = True
                    return result
            finally:
                self.tasks.discard(task)
                if operation and generation == self.generation:
                    self._busy_changed(False)
                release(succeeded=succeeded)

        future = asyncio.run_coroutine_threadsafe(serialized(), self.loop)

        def finished(result):
            nonlocal aborted
            if result.cancelled():
                with lifecycle_lock:
                    aborted = True
                    cancelled_before_start = not started
                if cancelled_before_start:
                    release()
                    if operation and generation == self.generation:
                        self._busy_changed(False)
                return
            try:
                result.result()
            except Exception as error:
                self._failed(str(error) or type(error).__name__)

        future.add_done_callback(finished)
        if operation:
            self.operation = future
        return future

    async def _connect(self, name, transport, model, generation):
        self._output(tr("Connecting to hub…") + "\n")
        self.tracebacks = self.stored_program = None
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def output(data):
            if generation != self.connection_generation:
                return
            text = decoder.decode(data)
            self._output(text)
            if self.tracebacks is not None:
                self.tracebacks.feed(text)

        try:
            if self.connection:
                await self._disconnect()
            factory = VirtualConnection if transport == "virtual" else Connection
            options = {"model": model} if transport == "virtual" else {}
            self.connection = factory(
                output,
                lambda info: (
                    self._remember(info)
                    if generation == self.connection_generation
                    else None
                ),
                **options,
            )
            await self.connection.connect(name, transport)
            if generation != self.connection_generation:
                raise asyncio.CancelledError
            self._output(tr("Hub connected.") + "\n")
        except BaseException as error:
            try:
                await self._disconnect()
            except Exception as cleanup_error:
                self._output(str(cleanup_error) + "\n")
            if isinstance(error, asyncio.CancelledError):
                self._output(tr("Connection cancelled.") + "\n")
            raise
        finally:
            if self.info.connection_action == "connecting":
                self._connection_action("")

    def connect_hub(self, name=None, transport="ble", model="inventor"):
        if self.info.connection_action or (
            self.operation and not self.operation.done()
        ):
            return None
        self.connection_generation += 1
        self._connection_action("connecting")
        return self.submit(
            self._connect(name, transport, model, self.connection_generation),
            operation=True,
            cleanup=lambda: self._clear_connection_action("connecting"),
        )

    def _queue_program(self, path, sources, *, run):
        if not self.connection or not self.info.connected:
            self._failed(tr("Connect a hub first"))
            return None
        if self.operation and not self.operation.done():
            self._failed(tr("Wait for the hub operation to finish"))
            return None
        program = Program(path, sources)
        return self.submit(
            self._transfer(program, run=run),
            operation=True,
            cleanup=program.cleanup,
        )

    def run_file(self, path, sources=None):
        return self._queue_program(path, sources, run=True)

    def upload_file(self, path, sources=None):
        return self._queue_program(path, sources, run=False)

    def run_stored(self):
        if self.connection and self.info.connected:

            async def run():
                if self.info.running:
                    await self.connection.stop()
                self._start_trace(self.stored_program)
                await self.connection.run()
                self._output(tr("Program started.") + "\n")

            return self.submit(run(), operation=True)
        self._failed(tr("Connect a hub first"))

    def start_monitor(self):
        if self.connection and self.info.connected:

            async def monitor():
                try:
                    await self.connection.start_monitor()
                finally:
                    self.tracebacks = None
                if not isinstance(self.connection, VirtualConnection):
                    self.stored_program = None

            return self.submit(monitor(), operation=True)
        self._failed(tr("Connect a hub first"))

    def _start_trace(self, program):
        self.tracebacks = Tracebacks(program, self._problem)
        self._program_started(program)

    async def _transfer(self, program, *, run):
        try:
            self._output(tr("Uploading {name}…", name=program.entry.name) + "\n")
            if self.info.running:
                await self.connection.stop()
            self.tracebacks = None
            self.stored_program = None
            path = (
                program
                if isinstance(self.connection, VirtualConnection)
                else program.entry
            )
            if run:
                self._start_trace(program)
                await self.connection.run(path)
            else:
                await self.connection.upload(path)
        except BaseException:
            self.tracebacks = None
            raise
        self.stored_program = program
        self._output(
            (tr("Program started.") if run else tr("Program uploaded.")) + "\n"
        )

    def stop_program(self):
        async def stop():
            if self.connection and self.info.connected:
                await self.connection.stop()

        return self.submit(stop(), operation=True, interrupt=True)

    def drive(self, commands):
        self._control("drive", commands)

    def send(self, state):
        self._control("send", state)

    def _control(self, method, value):
        with self.control_lock:
            if (
                not self.connection
                or not self.info.connected
                or self.operation
                and not self.operation.done()
            ):
                return
            # Keep one latest sample, including the final neutral frame when
            # disarming stops the UI timer. Never accumulate obsolete movement.
            self.latest_control = self.connection, method, value
            if self.pending is None or self.pending.done():
                self.pending = self.submit(self._drain_controls())

    async def _drain_controls(self):
        try:
            while True:
                with self.control_lock:
                    sample, self.latest_control = self.latest_control, None
                    if sample is None:
                        self.pending = None
                        return
                connection, method, value = sample
                await getattr(connection, method)(value)
        except BaseException:
            with self.control_lock:
                self.latest_control = self.pending = None
            raise

    def configure(self, port, kind, value=None):
        if self.info.connected and isinstance(self.connection, VirtualConnection):
            self.submit(self.connection.configure(port, kind, value))

    def write_input(self, data):
        if isinstance(self.connection, Connection) and self.info.connected:
            if not self.operation or self.operation.done():
                return self.submit(self.connection.write_input(data))

    async def _disconnect(self):
        connection = self.connection
        try:
            if connection:
                async with asyncio.timeout(5):
                    await connection.disconnect()
        except TimeoutError:
            self._output(
                tr("Hub did not acknowledge disconnection; local connection closed.")
                + "\n"
            )
        finally:
            self.connection = None
            self.tracebacks = self.stored_program = None
            self._remember(
                replace(self.info, connected=False, running=False, monitoring=False)
            )

    def disconnect_hub(self):
        if self.info.connection_action == "disconnecting":
            return self.operation
        self.connection_generation += 1
        self._connection_action("disconnecting")

        async def disconnect():
            try:
                await self._disconnect()
            finally:
                self._connection_action("")

        return self.submit(
            disconnect(),
            operation=True,
            interrupt=True,
            cleanup=lambda: self._clear_connection_action("disconnecting"),
        )

    def close(self):
        future = self.disconnect_hub()
        try:
            future.result(timeout=7)
        except Exception:
            future.cancel()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
