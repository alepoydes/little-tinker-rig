"""Pybricks USB Serial (profile 1.6+), shared by Prime/Inventor and EV3.

Wire format: pybricks-micropython/lib/pbio/include/pbio/{protocol,cobs}.h.
This fills a gap in pybricksdev 2.3; replace it with its public serial adapter
when one is available. Compilation and protocol constants remain upstream-owned.
Only one request is outstanding. An ambiguous timeout closes the connection,
so a late response can never acknowledge a later command after tag wraparound.
"""

import asyncio
import struct

from packaging.version import Version
from pybricksdev.ble.lwp3.bytecodes import HubKind
from pybricksdev.ble.pybricks import (
    Command,
    Event,
    HubCapabilityFlag,
    StatusFlag,
    unpack_hub_capabilities,
    unpack_pnp_id,
)
from pybricksdev.compile import compile_multi_file
from pybricksdev.connections import ConnectionState
from reactivex.subject import BehaviorSubject, Subject
from tqdm import tqdm

from little_tinker_rig.i18n import tr

# Profile 1.5 flag not yet named in pybricksdev 2.3's public enum.
NATIVE_MPY_6_3 = 1 << 5


def encode(data: bytes) -> bytes:
    """SPIKE COBS: escape 0..2, XOR the body, terminate with 0x02."""
    result = bytearray([255])
    code, size = 0, 1
    for value in data:
        if value > 2:
            result.append(value)
            size += 1
        if value <= 2 or size > 84:
            if value <= 2:
                result[code] = value * 84 + size + 2
            code, size = len(result), 1
            result.append(255)
    result[code] = size + 2
    return bytes(value ^ 3 for value in result) + b"\x02"


def decode(frame: bytes) -> bytes:
    """Decode a frame body, rejecting truncated blocks and escaped delimiters."""
    data = bytes(value ^ 3 for value in frame)
    result = bytearray()
    index = 0
    while index < len(data):
        code = data[index]
        if code < 3:
            raise ValueError("Invalid COBS code")
        value, size = divmod(code - 3, 84) if code != 255 else (None, 84)
        end = index + 1 + size
        if end > len(data) or any(byte <= 2 for byte in data[index + 1 : end]):
            raise ValueError("Invalid COBS block")
        result.extend(data[index + 1 : end])
        if end < len(data) and value is not None:
            result.append(value)
        index = end
    return bytes(result)


class Frames:
    """Bound memory and resynchronize after corruption at the next delimiter."""

    def __init__(self, limit=66560):
        self.limit = limit
        self.buffer = bytearray()
        self.overflow = False

    def feed(self, data):
        for value in data:
            if value == 1:
                self.buffer.clear()
                self.overflow = False
            elif value == 2:
                if not self.overflow and self.buffer:
                    try:
                        yield decode(self.buffer)
                    except ValueError:
                        pass
                self.buffer.clear()
                self.overflow = False
            elif not self.overflow:
                self.buffer.append(value)
                if len(self.buffer) > self.limit:
                    self.buffer.clear()
                    self.overflow = True


class SerialHub:
    def __init__(self, device):
        self.device = device
        self.name = ""
        self.stdout_observable = Subject()
        self.status_observable = BehaviorSubject(StatusFlag(0))
        self.connection_state_observable = BehaviorSubject(ConnectionState.DISCONNECTED)
        self._port = None
        self._reader = None
        self._pending = None
        self._lock = asyncio.Lock()
        self._tag = 0
        self._slot = 0
        self._status_serial = 0
        self.timeout = 5

    async def connect(self):
        import serial

        # Opening is quick; doing it on the owner loop also makes cancellation
        # atomic with acquiring the serial handle. All blocking I/O is threaded.
        try:
            self._port = serial.Serial(
                self.device, baudrate=115200, timeout=0.1, write_timeout=2
            )
        except OSError as error:
            from .serial_access import opening_error

            raise ConnectionError(opening_error(self.device, error)) from error
        self._reader = asyncio.create_task(self._receive(self._port))
        try:
            protocol = Version((await self._read(1, 0x2A28)).decode())
            if not Version("1.6") <= protocol < Version("2"):
                raise ValueError(tr("Unsupported Pybricks USB Serial protocol"))
            self.fw_version = (await self._read(1, 0x2A26)).decode()
            self.name = (await self._read(1, 0x2A00)).decode()
            vendor_type, vendor, kind, _ = unpack_pnp_id(await self._read(1, 0x2A50))
            if (vendor_type, vendor) != ("BT", 0x0397):
                raise ValueError(tr("USB device is not a Pybricks LEGO hub"))
            self.hub_kind = HubKind(kind)
            self._max_write, self._flags, self._max_program, self._slots = (
                unpack_hub_capabilities(await self._read(2, 3))
            )
            if self._max_write <= 5 or self._max_program <= 0:
                raise ValueError(tr("Invalid hub capabilities"))
            await self._send(b"\x01\x01")
            self.connection_state_observable.on_next(ConnectionState.CONNECTED)
        except BaseException:
            await self.disconnect()
            raise

    async def _send(self, message):
        if self._port is None:
            raise ConnectionError(tr("USB hub disconnected"))
        data = encode(message)
        write = asyncio.create_task(asyncio.to_thread(self._port.write, data))
        try:
            count = await asyncio.shield(write)
        except asyncio.CancelledError:
            # A cancelled to_thread call still runs. Finish it before closing
            # the handle or allowing another connection to open this port.
            await write
            raise
        if count != len(data):
            raise ConnectionError(tr("Incomplete USB write"))

    async def _exchange(self, message, key):
        async with self._lock:
            reply = asyncio.get_running_loop().create_future()
            self._pending = key, reply
            try:
                async with asyncio.timeout(self.timeout):
                    await self._send(message)
                    return await reply
            except BaseException as error:
                # Neither cancellation nor a timeout tells us whether the hub
                # executed the command. Do not continue using this byte stream.
                reply.cancel()
                await self.disconnect()
                if isinstance(error, TimeoutError):
                    raise TimeoutError(
                        tr(
                            "No response from USB hub. Check that it runs compatible Pybricks beta firmware and that no other application is using the port."
                        )
                    ) from error
                raise
            finally:
                self._pending = None

    async def _read(self, service, characteristic):
        selector = struct.pack("<BH", service, characteristic)
        data, _ = await self._exchange(b"\x03" + selector, b"\x03" + selector)
        return data

    async def command(self, data):
        self._tag = (self._tag + 1) % 256
        tag = self._tag
        result, status_serial = await self._exchange(
            bytes((2, tag)) + data, bytes((1, tag))
        )
        status = struct.unpack("<I", result)[0]
        if status:
            raise ValueError(
                tr("Hub rejected command: {status}").format(status=hex(status))
            )
        return status_serial

    async def _receive(self, port):
        frames = Frames()
        try:
            while self._port is port:
                data = await asyncio.to_thread(
                    lambda: port.read(max(1, min(port.in_waiting, 4096)))
                )
                for frame in frames.feed(data):
                    if len(frame) >= 2 and frame[0] == 2:
                        if frame[1] == Event.WRITE_STDOUT:
                            self.stdout_observable.on_next(frame[2:])
                        elif frame[1] == Event.STATUS_REPORT and len(frame) >= 6:
                            self._status_serial += 1
                            if len(frame) >= 8:
                                self._slot = frame[7]
                            self.status_observable.on_next(
                                StatusFlag(struct.unpack_from("<I", frame, 2)[0])
                            )
                    elif self._pending:
                        key, future = self._pending
                        if (
                            frame.startswith(key)
                            and not future.done()
                            and (key[0] != 1 or len(frame) == 6)
                        ):
                            future.set_result((frame[len(key) :], self._status_serial))
        except (OSError, ValueError) as error:
            self._lost(error)

    def _lost(self, error):
        if self._pending and not self._pending[1].done():
            self._pending[1].set_exception(error)
        if self._port is not None:
            self._port.close()
            self._port = None
        self.connection_state_observable.on_next(ConnectionState.DISCONNECTED)

    async def disconnect(self):
        port, self._port = self._port, None
        reader, self._reader = self._reader, None
        try:
            if reader:
                await reader  # The serial read has a bounded timeout.
        finally:
            if port:
                port.close()
            self._lost(ConnectionError(tr("USB hub disconnected")))

    async def download(self, script_path):
        if not self._flags & (
            HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6
            | HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6_1_NATIVE
            | NATIVE_MPY_6_3
        ):
            raise ValueError(tr("Hub does not support the available Python compiler"))
        abi = 6
        if self._flags & NATIVE_MPY_6_3:
            abi = (6, 3)
        elif self._flags & HubCapabilityFlag.USER_PROG_MULTI_FILE_MPY6_1_NATIVE:
            abi = (6, 1)
        program = await compile_multi_file(script_path, abi)
        if len(program) > self._max_program:
            raise ValueError(tr("Program is too large for this hub"))
        await self.command(struct.pack("<BI", Command.WRITE_USER_PROGRAM_META, 0))
        size = self._max_write - 5
        with tqdm(total=len(program), unit="B", unit_scale=True) as progress:
            for offset in range(0, len(program), size):
                chunk = program[offset : offset + size]
                await self.command(
                    struct.pack("<BI", Command.COMMAND_WRITE_USER_RAM, offset) + chunk
                )
                progress.update(len(chunk))
        await self.command(
            struct.pack("<BI", Command.WRITE_USER_PROGRAM_META, len(program))
        )

    async def run(
        self, path=None, *, wait=True, print_output=False, line_handler=False
    ):
        if path is not None:
            await self.download(path)
        queue = asyncio.Queue()
        subscription = self.status_observable.subscribe(
            lambda status: queue.put_nowait((self._status_serial, status))
        )
        disconnected = self.connection_state_observable.subscribe(
            lambda state: (
                queue.put_nowait(None)
                if state == ConnectionState.DISCONNECTED
                else None
            )
        )
        try:
            queue.get_nowait()  # Discard BehaviorSubject's pre-start status.
            command = bytes((Command.START_USER_PROGRAM,))
            if self._slots:
                command += bytes((self._slot,))
            acknowledged = await self.command(command)
            if wait:
                # Status reports are periodic, even when a short program has
                # already finished. Wait for a post-command idle report.
                while True:
                    item = await queue.get()
                    if item is None:
                        raise ConnectionError(tr("USB hub disconnected"))
                    serial, status = item
                    if (
                        serial > acknowledged
                        and not status & StatusFlag.USER_PROGRAM_RUNNING
                    ):
                        break
        finally:
            subscription.dispose()
            disconnected.dispose()

    async def stop_user_program(self):
        await self.command(bytes((Command.STOP_USER_PROGRAM,)))

    async def write(self, data):
        size = self._max_write - 1
        for offset in range(0, len(data), size):
            await self.command(
                bytes((Command.WRITE_STDIN,)) + data[offset : offset + size]
            )


def find_hub(selector=None):
    """Prefer CDC devices; retain the public legacy USB adapter as a fallback."""
    from pybricksdev.usb import (
        EV3_USB_PID,
        LEGO_USB_VID,
        MINDSTORMS_INVENTOR_USB_PID,
        SPIKE_ESSENTIAL_USB_PID,
        SPIKE_PRIME_USB_PID,
    )
    from serial.tools.list_ports import comports

    ports = [
        port
        for port in comports()
        if port.vid == LEGO_USB_VID
        and port.pid
        in (
            EV3_USB_PID,
            SPIKE_PRIME_USB_PID,
            SPIKE_ESSENTIAL_USB_PID,
            MINDSTORMS_INVENTOR_USB_PID,
        )
        and (not selector or selector in (port.device, port.serial_number))
    ]
    if len(ports) > 1:
        raise ValueError(
            tr("Choose a USB port: {ports}").format(
                ports=", ".join(port.device for port in ports)
            )
        )
    if ports:
        return SerialHub(ports[0].device)

    from pybricksdev.connections.pybricks import PybricksHubUSB
    from usb.core import find

    devices = list(
        find(
            find_all=True,
            idVendor=LEGO_USB_VID,
            custom_match=lambda device: (device.product or "").endswith("Pybricks")
            and (not selector or selector in (device.product, device.serial_number)),
        )
    )
    if len(devices) != 1:
        raise ValueError(tr("Connect exactly one Pybricks USB hub or specify its port"))
    return PybricksHubUSB(devices[0])
