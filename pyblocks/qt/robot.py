"""Own hub I/O in one asyncio worker; GUI widgets communicate through signals."""

import asyncio
import codecs
from concurrent.futures import CancelledError
from threading import Event, Thread

from PySide6.QtCore import QObject, Signal

from pyblocks.core.runtime_errors import Tracebacks
from pyblocks.i18n import tr
from pyblocks.pybricks.connection import Connection
from pyblocks.pybricks.devices import HubInfo
from pyblocks.pybricks.program import Program
from pyblocks.pybricks.virtual import VirtualConnection


class Robot(QObject):
    output = Signal(str)
    failed = Signal(str)
    updated = Signal(object)
    busy_changed = Signal(bool)
    problem = Signal(object)
    program_started = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.info = HubInfo()
        self.updated.connect(self._remember)
        self.connection = None
        self.operation = self.pending = None
        self.tracebacks = None
        self.stored_program = None
        self.lock = asyncio.Lock()
        self.generation = 0
        ready = Event()

        def run():
            with asyncio.Runner() as runner:
                self.loop = runner.get_loop()
                ready.set()
                self.loop.run_forever()

        self.thread = Thread(target=run, name="pyblocks-hub", daemon=True)
        self.thread.start()
        if not ready.wait(5):
            raise RuntimeError("Could not start hub event loop")

    def _remember(self, info):
        self.info = info

    def submit(self, coroutine, *, operation=False, interrupt=False):
        if operation and self.operation and not self.operation.done():
            if interrupt:
                self.operation.cancel()
            else:
                coroutine.close()
                self.failed.emit(tr("Wait for the hub operation to finish"))
                return None
        if operation:
            self.generation += 1
            if self.pending:
                self.pending.cancel()
            self.busy_changed.emit(True)
        generation = self.generation

        async def serialized():
            try:
                async with self.lock:
                    return await coroutine
            finally:
                coroutine.close()

        future = asyncio.run_coroutine_threadsafe(serialized(), self.loop)

        def finished(result):
            try:
                result.result()
            except CancelledError:
                pass
            except Exception as error:
                self.failed.emit(str(error) or type(error).__name__)
            finally:
                if operation and generation == self.generation:
                    self.busy_changed.emit(False)

        future.add_done_callback(finished)
        if operation:
            self.operation = future
        return future

    async def _connect(self, name, transport, model):
        self.output.emit(tr("Connecting to hub…") + "\n")
        self.tracebacks = self.stored_program = None
        if self.connection:
            await self.connection.disconnect()
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

        def output(data):
            text = decoder.decode(data)
            self.output.emit(text)
            if self.tracebacks is not None:
                self.tracebacks.feed(text)

        factory = VirtualConnection if transport == "virtual" else Connection
        options = {"model": model} if transport == "virtual" else {}
        self.connection = factory(
            output,
            self.updated.emit,
            **options,
        )
        await self.connection.connect(name, transport)
        self.output.emit(tr("Hub connected.") + "\n")

    def connect_hub(self, name=None, transport="ble", model="inventor"):
        return self.submit(self._connect(name, transport, model), operation=True)

    def run_file(self, path):
        if self.connection:
            return self.submit(self._transfer(Program(path), run=True), operation=True)
        self.failed.emit(tr("Connect a hub first"))

    def upload_file(self, path):
        if self.connection:
            return self.submit(self._transfer(Program(path), run=False), operation=True)
        self.failed.emit(tr("Connect a hub first"))

    def run_stored(self):
        if self.connection:

            async def run():
                await self.connection.stop()
                self._start_trace(self.stored_program)
                await self.connection.run()
                self.output.emit(tr("Program started.") + "\n")

            return self.submit(run(), operation=True)
        self.failed.emit(tr("Connect a hub first"))

    def start_monitor(self):
        if self.connection:

            async def monitor():
                await self.connection.stop()
                self.tracebacks = None
                if not isinstance(self.connection, VirtualConnection):
                    self.stored_program = None
                await self.connection.start_monitor()

            return self.submit(monitor(), operation=True)
        self.failed.emit(tr("Connect a hub first"))

    def _start_trace(self, program):
        self.tracebacks = Tracebacks(program, self.problem.emit)
        self.program_started.emit(program)

    async def _transfer(self, program, *, run):
        self.output.emit(tr("Uploading {name}…", name=program.entry.name) + "\n")
        await self.connection.stop()
        self.tracebacks = None
        self.stored_program = None
        path = (
            program if isinstance(self.connection, VirtualConnection) else program.entry
        )
        if run:
            self._start_trace(program)
            await self.connection.run(path)
        else:
            await self.connection.upload(path)
        self.stored_program = program
        self.output.emit(
            (tr("Program started.") if run else tr("Program uploaded.")) + "\n"
        )

    def stop_program(self):
        async def stop():
            if self.connection:
                await self.connection.stop()

        return self.submit(stop(), operation=True, interrupt=True)

    def drive(self, commands):
        if self.pending and not self.pending.done():
            return  # Send the latest sample next tick; never queue old controls.
        if self.connection:
            self.pending = self.submit(self.connection.drive(commands))

    def send(self, state):
        if self.pending and not self.pending.done():
            return
        if self.connection:
            self.pending = self.submit(self.connection.send(state))

    def configure(self, port, kind, value=None):
        if isinstance(self.connection, VirtualConnection):
            self.submit(self.connection.configure(port, kind, value))

    def disconnect_hub(self):
        async def disconnect():
            if self.connection:
                await self.connection.disconnect()

        return self.submit(disconnect(), operation=True, interrupt=True)

    def close(self):
        async def disconnect():
            if self.connection:
                await self.connection.disconnect()

        future = self.submit(disconnect(), operation=True, interrupt=True)
        try:
            future.result(timeout=5)
        except Exception:
            future.cancel()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=5)
