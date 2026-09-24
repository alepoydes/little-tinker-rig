"""A thin async wrapper over public pybricksdev APIs."""

import asyncio
import codecs
import sys
from dataclasses import replace
from pathlib import Path

from .control import ControlState
from .devices import HubInfo, TelemetryStream, encode_commands


class Connection:
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
        if self._monitor_requested:
            self._update(
                monitoring=True,
                **{
                    key: data[key]
                    for key in ("ports", "battery_mv", "name", "kind", "model")
                    if key in data
                },
            )

    async def connect(self, name: str | None = None, transport: str = "ble") -> None:
        await self.disconnect()
        if transport == "ble":
            from pybricksdev.ble import find_device
            from pybricksdev.connections.pybricks import PybricksHubBLE

            device = await find_device(name)
            hub = PybricksHubBLE(device)
        elif transport == "usb":
            from pybricksdev.connections.pybricks import PybricksHubUSB
            from pybricksdev.usb import LEGO_USB_VID
            from usb.core import find

            device = await asyncio.to_thread(
                find,
                custom_match=lambda d: d.idVendor == LEGO_USB_VID
                and (d.product or "").endswith("Pybricks"),
            )
            if device is None:
                raise ValueError("No Pybricks USB hub found")
            hub = PybricksHubUSB(device)
        else:
            raise ValueError("Transport must be 'ble' or 'usb'")
        try:
            await hub.connect()
        except BaseException:
            await hub.disconnect()
            raise
        self.hub = hub
        kind = getattr(getattr(hub, "hub_kind", None), "name", "Hub")
        model = {
            "BOOST": "boost",
            "TECHNIC": "technic",
            "TECHNIC_LARGE": "inventor",
        }.get(kind, "")
        self._update(
            name=name or "Pybricks",
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
            await hub.run(
                str(path.resolve()) if path is not None else None,
                wait=wait,
                print_output=False,
                line_handler=False,
            )
        except BaseException:
            self._update(running=False)
            raise
        if wait:
            self._update(running=False)

    async def stop(self) -> None:
        self._monitor_requested = False
        await self._connected().stop_user_program()
        self._update(running=False, monitoring=False)

    async def start_monitor(self):
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
                        await hub.stop_user_program()
                finally:
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
