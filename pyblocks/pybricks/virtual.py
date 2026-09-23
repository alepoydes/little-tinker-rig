"""A local hub backend. Each program runs in a stoppable, independent process."""

import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

from .devices import PREFIX, HubInfo
from .simulation import PROFILES, World


class VirtualConnection:
    def __init__(self, output=None, changed=None, *, model="inventor"):
        self.output = output or (lambda data: None)
        self.changed = changed or (lambda info: None)
        world = World(model=model)
        self.info = HubInfo(
            name="Virtual hub",
            kind=PROFILES[model][0],
            model=model,
            firmware="PyBlocks simulator",
            transport="virtual",
        )
        self.process = None
        self.stopping = False
        self.tasks = []
        self.done = asyncio.Event()
        self.ready = asyncio.Event()
        self.write_lock = asyncio.Lock()
        self.ports = world.snapshot()

    def _update(self, **values):
        self.info = replace(self.info, **values)
        self.changed(self.info)

    async def connect(self, name=None, transport="virtual"):
        await self._spawn()

    async def _spawn(self, path=None):
        await self._terminate()
        self.ready.clear()
        self.done.clear()
        arguments = [
            sys.executable,
            "-u",
            "-m",
            "pyblocks.pybricks.sim_runtime",
            "--ports",
            json.dumps(self.ports),
            "--model",
            self.info.model,
        ]
        if path is not None:
            arguments.extend(("--program", str(Path(path).resolve())))
        self.process = await asyncio.create_subprocess_exec(
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._update(
            connected=True, running=path is not None, monitoring=path is None, error=""
        )
        self.tasks = [
            asyncio.create_task(self._stdout()),
            asyncio.create_task(self._telemetry()),
        ]
        try:
            await asyncio.wait_for(self.ready.wait(), 5)
            if not self.info.connected:
                raise ValueError(self.info.error)
        except BaseException:
            await self._terminate()
            self._update(connected=False, running=False, monitoring=False)
            raise

    async def _stdout(self):
        while data := await self.process.stdout.read(4096):
            self.output(data)

    async def _telemetry(self):
        while line := await self.process.stderr.readline():
            if not line.startswith(PREFIX):
                self.output(line)
                continue
            try:
                data = json.loads(line[len(PREFIX) :])
                if (
                    not isinstance(data, dict)
                    or not isinstance(data.get("ports"), dict)
                    or "running" not in data
                ):
                    raise ValueError("Invalid virtual telemetry")
                self._update(**data)
            except (ValueError, TypeError):
                self.output(line)
                continue
            self.ports = data["ports"]
            self.ready.set()
            if not data["running"]:
                self.done.set()
        self.done.set()
        if not self.stopping:
            self._update(
                connected=False,
                running=False,
                monitoring=False,
                error="Virtual hub process exited unexpectedly",
            )
        self.ready.set()

    async def _write(self, data):
        if (
            not self.info.connected
            or self.process is None
            or self.process.returncode is not None
        ):
            raise ValueError("Connect a virtual hub first")
        async with self.write_lock:
            self.process.stdin.write(data)
            await self.process.stdin.drain()

    async def run(self, path, *, wait=False):
        if not self.info.connected:
            raise ValueError("Connect a virtual hub first")
        if not Path(path).is_file():
            raise FileNotFoundError(path)
        await self._spawn(path)
        if wait:
            await self.done.wait()
            if self.info.error:
                raise ValueError(f"Virtual program failed: {self.info.error}")

    async def start_monitor(self):
        if not self.info.connected:
            raise ValueError("Connect a virtual hub first")
        await self._spawn()

    async def drive(self, commands):
        if not self.info.monitoring:
            raise ValueError("Start manual mode before driving motors")
        commands = tuple(commands)
        World(self.ports, self.info.model).drive(commands)
        await self._write(json.dumps({"motors": commands}).encode() + b"\n")

    async def configure(self, port, kind, value=None):
        # Validate before transmitting, using the same device rules as the child.
        check = World(self.ports, self.info.model)
        check.configure(port, kind, value)
        await self._write(
            json.dumps({"configure": dict(port=port, kind=kind, value=value)}).encode()
            + b"\n"
        )

    async def send(self, state):
        await self._write(state.encode())

    async def stop(self):
        if self.info.connected:
            await self._spawn()

    async def _terminate(self):
        self.stopping = True
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        self.process, self.tasks = None, []
        self.stopping = False

    async def disconnect(self):
        await self._terminate()
        self._update(connected=False, running=False, monitoring=False)
