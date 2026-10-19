"""A thin async wrapper over public pybricksdev APIs."""

import asyncio
import codecs
import math
import sys
from dataclasses import replace
from pathlib import Path

from little_tinker_rig.i18n import tr

from .control import ControlState
from .devices import HubInfo, TelemetryStream, encode_commands


class Connection:
    connect_timeout = 20
    disconnect_timeout = 3

    def __init__(self, output=None, changed=None):
        self.output = output or (lambda data: None)
        self.changed = changed or (lambda info: None)
        self.info = HubInfo()
        self._monitor_requested = False
        self._telemetry = TelemetryStream(self.output, self._received)
        self.hub = None
        self._subscription = None
        self._status_subscriptions = []
        self._write_lock = asyncio.Lock()

    def _update(self, **values):
        self.info = replace(self.info, **values)
        self.changed(self.info)

    def _received(self, data):
        if not self._monitor_requested:
            return False

        def number(value):
            try:
                return type(value) in (int, float) and math.isfinite(value)
            except OverflowError:
                return False

        ports = data.get("ports")
        if not isinstance(ports, dict) or any(
            type(port) is not str
            or len(port) != 1
            or port not in "ABCDEF"
            or not isinstance(device, dict)
            or not isinstance(device.get("type", "empty"), str)
            or any(
                not number(device[field])
                for field in (
                    "angle",
                    "speed",
                    "reflection",
                    "distance_percent",
                    "distance",
                    "force",
                )
                if field in device
            )
            for port, device in ports.items()
        ):
            return False
        if "battery_mv" in data and not number(data["battery_mv"]):
            return False
        if any(
            key in data and not isinstance(data[key], str)
            for key in ("name", "kind", "model")
        ):
            return False
        self._update(
            monitoring=True,
            **{
                key: data[key]
                for key in ("ports", "battery_mv", "name", "kind", "model")
                if key in data
            },
        )
        return True

    async def connect(self, name: str | None = None, transport: str = "ble") -> None:
        await self.disconnect()
        try:
            async with asyncio.timeout(self.connect_timeout):
                await self._connect(name, transport)
        except BaseException as error:
            try:
                await self.disconnect()
            except Exception:
                pass  # Preserve the connection failure or explicit cancellation.
            if isinstance(error, TimeoutError):
                raise TimeoutError(
                    tr(
                        "Hub connection timed out. Check the cable, firmware and connection mode."
                    )
                ) from error
            raise

    async def _connect(self, name, transport):
        if transport == "ble":
            from pybricksdev.ble import find_device
            from pybricksdev.connections.pybricks import PybricksHubBLE

            device = await find_device(name)
            hub = PybricksHubBLE(device)
        elif transport == "usb":
            from .usb_process import USBHub

            hub = USBHub(name)
        else:
            raise ValueError("Transport must be 'ble' or 'usb'")
        self.hub = hub
        await hub.connect()
        kind = getattr(getattr(hub, "hub_kind", None), "name", "Hub")
        model = {
            "BOOST": "boost",
            "TECHNIC": "technic",
            "TECHNIC_LARGE": "inventor",
            "EV3": "ev3",
        }.get(kind, "")
        self._update(
            name=getattr(hub, "name", None) or name or "Pybricks",
            kind=kind,
            model=model,
            firmware=str(getattr(hub, "fw_version", "") or ""),
            transport=transport,
            connected=True,
        )
        self._subscription = hub.stdout_observable.subscribe(self._telemetry.feed)
        if hasattr(hub, "connection_state_observable"):
            self._status_subscriptions.append(
                hub.connection_state_observable.subscribe(
                    lambda state: (
                        self._update(connected=False, running=False, monitoring=False)
                        if state.name == "DISCONNECTED"
                        else None
                    )
                )
            )
        if hasattr(hub, "status_observable"):
            from pybricksdev.ble.pybricks import StatusFlag

            self._status_subscriptions.append(
                hub.status_observable.subscribe(
                    lambda flags: self._update(
                        running=bool(flags & StatusFlag.USER_PROGRAM_RUNNING)
                        and not self._monitor_requested,
                        monitoring=self.info.monitoring
                        and bool(flags & StatusFlag.USER_PROGRAM_RUNNING),
                    )
                )
            )

    def _connected(self):
        if self.hub is None:
            raise ValueError("Connect a Pybricks hub first")
        return self.hub

    async def upload(self, path: Path) -> None:
        await self.stop()
        await self._connected().download(str(path.resolve()))

    async def run(self, path: Path | None = None, *, wait: bool = False) -> None:
        hub = self._connected()
        self._monitor_requested = False
        self._update(monitoring=False)
        try:
            await hub.stop_user_program()
            self._update(running=True)

            async def start():
                await hub.run(
                    str(path.resolve()) if path is not None else None,
                    wait=False,
                    print_output=False,
                    line_handler=False,
                )

            if wait:
                await self._wait_stopped(hub, start)
            else:
                await start()
        except BaseException:
            self._update(running=False)
            raise
        if wait:
            self._update(running=False)

    async def _wait_stopped(self, hub, start):
        from pybricksdev.ble.pybricks import StatusFlag
        from reactivex import operators as op

        finished = asyncio.get_running_loop().create_future()
        running_seen = False
        start_returned = False

        def status(flags):
            nonlocal running_seen
            if flags & StatusFlag.USER_PROGRAM_RUNNING:
                running_seen = True
            elif not finished.done() and (running_seen or start_returned):
                finished.set_result(None)

        def connection(state):
            if state.name == "DISCONNECTED" and not finished.done():
                finished.set_exception(ConnectionError(tr("Hub disconnected.")))

        # Subscribe before START so a short program cannot finish during the
        # start request. Ignore cached and pre-start idle reports; a running
        # report followed by idle, or a fresh idle after START returns, confirms
        # completion without a guessed startup delay.
        with (
            hub.status_observable.pipe(op.skip(1)).subscribe(status),
            hub.connection_state_observable.subscribe(connection),
        ):
            await start()
            start_returned = True
            await finished

    async def stop(self) -> None:
        self._monitor_requested = False
        await self._connected().stop_user_program()
        self._update(running=False, monitoring=False)

    async def start_monitor(self):
        if self.info.model == "ev3":
            raise ValueError(tr("EV3 port monitoring is not supported yet"))
        await self.stop()
        self._monitor_requested = True
        try:
            await self._connected().run(
                str(Path(__file__).with_name("hub_monitor.py")),
                wait=False,
                print_output=False,
                line_handler=False,
            )
        except BaseException:
            self._monitor_requested = False
            self._update(monitoring=False)
            raise

    async def drive(self, commands):
        if not self.info.monitoring:
            raise ValueError("Start manual mode before driving motors")
        async with self._write_lock:
            await self._connected().write(encode_commands(commands))

    async def send(self, state: ControlState) -> None:
        async with self._write_lock:
            await self._connected().write(state.encode())

    async def write_input(self, data: bytes) -> None:
        async with self._write_lock:
            if self.info.monitoring or self._monitor_requested:
                raise ValueError("Stop the port monitor before sending program input")
            await self._connected().write(data)

    async def disconnect(self) -> None:
        hub, self.hub = self.hub, None
        monitoring = self._monitor_requested
        self._monitor_requested = False
        if self._subscription:
            self._subscription.dispose()
            self._subscription = None
        for subscription in self._status_subscriptions:
            subscription.dispose()
        self._status_subscriptions.clear()
        self._telemetry.finish()
        try:
            if hub:
                try:
                    if monitoring:
                        async with asyncio.timeout(min(1, self.disconnect_timeout)):
                            await hub.stop_user_program()
                finally:
                    async with asyncio.timeout(self.disconnect_timeout):
                        await hub.disconnect()
        finally:
            self._update(connected=False, running=False, monitoring=False)


async def run_file(
    path: Path, name: str | None = None, transport: str = "ble", model: str = "inventor"
) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def output(data):
        sys.stdout.write(decoder.decode(data))
        sys.stdout.flush()

    if transport == "virtual":
        from .virtual import VirtualConnection

        connection = VirtualConnection(output, model=model)
    else:
        connection = Connection(output)
    try:
        await connection.connect(name, transport)
        await connection.run(path, wait=True)
    finally:
        await connection.disconnect()
