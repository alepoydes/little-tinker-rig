"""Keep native USB discovery and drivers out of the cancellable host event loop.

The child owns every USB handle. Its public adapter is unchanged; if a driver
or its disconnect handshake hangs, terminating the child releases those handles.
Stdout carries JSON events and replies; diagnostics/progress use stderr.
"""

import asyncio
import codecs
import contextlib
import json
import sys

from pybricksdev.ble.lwp3.bytecodes import HubKind
from pybricksdev.connections import ConnectionState
from reactivex.subject import BehaviorSubject, Subject

from little_tinker_rig.i18n import language, set_language, tr


class USBHub:
    def __init__(self, selector=None):
        self.selector = selector
        self.process = None
        self.stdout_observable = Subject()
        self.status_observable = BehaviorSubject(0)
        self.connection_state_observable = BehaviorSubject(ConnectionState.DISCONNECTED)
        self._readers = []
        self._replies = {}
        self._serial = 0
        self._lock = asyncio.Lock()
        self.close_timeout = 2

    async def connect(self):
        ready = asyncio.get_running_loop().create_future()
        self._replies[0] = ready
        launch = asyncio.create_task(
            asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
                "-m",
                __name__,
                self.selector or "",
                language(),
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        )
        try:
            try:
                self.process = await asyncio.shield(launch)
            except asyncio.CancelledError:
                self.process = await launch
                raise
            self._readers = [
                asyncio.create_task(self._events(self.process.stdout)),
                asyncio.create_task(self._diagnostics(self.process.stderr)),
            ]
            info = await ready
            self.name, self.fw_version = info["name"], info["firmware"]
            self.hub_kind = HubKind(info["kind"])
            self.connection_state_observable.on_next(ConnectionState.CONNECTED)
        except BaseException:
            ready.cancel()
            await self.abort()
            raise
        finally:
            self._replies.pop(0, None)

    async def _events(self, stream):
        try:
            while line := await stream.readline():
                event = json.loads(line)
                if "reply" in event:
                    future = self._replies.get(event["reply"])
                    if future is not None and not future.done():
                        if "error" in event:
                            future.set_exception(ValueError(event["error"]))
                        else:
                            future.set_result(event.get("value"))
                elif "output" in event:
                    self.stdout_observable.on_next(bytes.fromhex(event["output"]))
                elif "status" in event:
                    self.status_observable.on_next(event["status"])
                elif event.get("disconnected"):
                    break
        finally:
            self.connection_state_observable.on_next(ConnectionState.DISCONNECTED)
            for future in self._replies.values():
                if not future.done():
                    future.set_exception(ConnectionError(tr("USB hub disconnected")))

    async def _diagnostics(self, stream):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while data := await stream.read(4096):
            sys.stderr.write(decoder.decode(data))
            sys.stderr.flush()
        sys.stderr.write(decoder.decode(b"", final=True))

    async def _request(self, method, *args, **options):
        async with self._lock:
            if self.process is None or self.process.returncode is not None:
                raise ConnectionError(tr("USB hub disconnected"))
            self._serial += 1
            identifier = self._serial
            reply = asyncio.get_running_loop().create_future()
            self._replies[identifier] = reply
            try:
                self.process.stdin.write(
                    (json.dumps([identifier, method, args, options]) + "\n").encode()
                )
                await self.process.stdin.drain()
                return await reply
            except asyncio.CancelledError:
                await self.abort()
                raise
            finally:
                self._replies.pop(identifier, None)
                if not reply.done():
                    reply.cancel()
                elif not reply.cancelled():
                    reply.exception()

    async def abort(self):
        process, self.process = self.process, None
        try:
            if process is not None and process.returncode is None:
                with contextlib.suppress(ProcessLookupError):
                    process.kill()
                await asyncio.wait_for(process.wait(), self.close_timeout)
        finally:
            for task in self._readers:
                task.cancel()
            await asyncio.gather(*self._readers, return_exceptions=True)
            self._readers.clear()
            self.connection_state_observable.on_next(ConnectionState.DISCONNECTED)

    async def disconnect(self):
        try:
            if self.process is not None:
                async with asyncio.timeout(self.close_timeout):
                    await self._request("disconnect")
        except (TimeoutError, ConnectionError):
            pass
        finally:
            await self.abort()

    async def download(self, path):
        await self._request("download", path)

    async def run(self, path=None, **options):
        await self._request("run", path, **options)

    async def stop_user_program(self):
        await self._request("stop_user_program")

    async def write(self, data):
        await self._request("write", data.hex())


async def serve(selector, emit):
    from .usb import find_hub

    hub = None
    subscriptions = []
    try:
        hub = find_hub(selector)
        try:
            await hub.connect()
        except OSError as error:
            if isinstance(error, TimeoutError):
                raise TimeoutError(
                    tr(
                        "No response from USB hub. Check that it runs compatible Pybricks beta firmware and that no other application is using the port."
                    )
                ) from error
            if hasattr(hub, "port"):
                from .serial_access import opening_error

                raise ConnectionError(opening_error(hub.port, error)) from error
            raise
        # CDC exposes negotiated limits through the public characteristic API.
        # Legacy USB keeps its existing single-packet write contract.
        payload_size = None
        if hasattr(hub, "port"):
            from pybricksdev.ble.pybricks import (
                PYBRICKS_HUB_CAPABILITIES_UUID,
                unpack_hub_capabilities,
            )

            limits = unpack_hub_capabilities(
                await hub.read_gatt_char(PYBRICKS_HUB_CAPABILITIES_UUID)
            )
            payload_size = limits[0] - 1
            if payload_size < 1:
                raise ValueError(tr("Invalid hub capabilities"))
        emit(
            reply=0,
            value={
                "name": getattr(hub, "name", None) or selector or "Pybricks",
                "kind": int(getattr(hub, "hub_kind", 0x81)),
                "firmware": str(hub.fw_version),
            },
        )
        subscriptions = [
            hub.stdout_observable.subscribe(
                lambda data: emit(output=bytes(data).hex())
            ),
            hub.status_observable.subscribe(lambda flags: emit(status=int(flags))),
            hub.connection_state_observable.subscribe(
                lambda state: (
                    emit(disconnected=True)
                    if state == ConnectionState.DISCONNECTED
                    else None
                )
            ),
        ]
        while line := await asyncio.to_thread(sys.stdin.buffer.readline):
            identifier, method, args, options = json.loads(line)
            try:
                if method not in {
                    "download",
                    "run",
                    "stop_user_program",
                    "write",
                    "disconnect",
                }:
                    raise ValueError("Unknown USB operation")
                if method == "write":
                    data = bytes.fromhex(args[0])
                    if payload_size is None:
                        await hub.write(data)
                    else:
                        for offset in range(0, len(data), payload_size):
                            await hub.write(data[offset : offset + payload_size])
                else:
                    await getattr(hub, method)(*args, **options)
                emit(reply=identifier)
            except Exception as error:
                emit(reply=identifier, error=str(error) or type(error).__name__)
            if method == "disconnect":
                return
    except Exception as error:
        emit(reply=0, error=str(error) or type(error).__name__)
    finally:
        for subscription in subscriptions:
            subscription.dispose()
        if hub:
            await hub.disconnect()


def main():
    stream = sys.stdout

    def emit(**event):
        stream.write(json.dumps(event) + "\n")
        stream.flush()

    set_language(sys.argv[2])
    with contextlib.redirect_stdout(sys.stderr):
        asyncio.run(serve(sys.argv[1] or None, emit))


if __name__ == "__main__":
    main()
