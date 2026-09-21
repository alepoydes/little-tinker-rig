"""A thin async wrapper over public pybricksdev APIs."""

import asyncio
import codecs
import sys
from pathlib import Path

from .control import ControlState


class Connection:
    def __init__(self, output=None):
        self.output = output or (lambda data: None)
        self.hub = None
        self._subscription = None
        self._write_lock = asyncio.Lock()

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
        self._subscription = hub.stdout_observable.subscribe(self.output)

    def _connected(self):
        if self.hub is None:
            raise ValueError("Connect a Pybricks hub first")
        return self.hub

    async def run(self, path: Path, *, wait: bool = False) -> None:
        hub = self._connected()
        await hub.run(
            str(path.resolve()), wait=wait, print_output=False, line_handler=False
        )

    async def stop(self) -> None:
        await self._connected().stop_user_program()

    async def send(self, state: ControlState) -> None:
        async with self._write_lock:
            await self._connected().write(state.encode())

    async def disconnect(self) -> None:
        hub, self.hub = self.hub, None
        if self._subscription:
            self._subscription.dispose()
            self._subscription = None
        if hub:
            await hub.disconnect()


async def run_file(path: Path, name: str | None = None, transport: str = "ble") -> None:
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def output(data):
        sys.stdout.write(decoder.decode(data))
        sys.stdout.flush()

    connection = Connection(output)
    try:
        await connection.connect(name, transport)
        await connection.run(path, wait=True)
    finally:
        await connection.disconnect()
