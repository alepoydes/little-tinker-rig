"""Standalone Pybricks port monitor and manual motor driver (MicroPython)."""

from pybricks.parameters import Port
from pybricks.tools import StopWatch, read_input_byte, wait

# Firmware modules need not expose their children as attributes. Request the
# leaf modules explicitly; this also works with CPython's package importer.
hubs = __import__("pybricks.hubs", None, None, ("*",))
pup = __import__("pybricks.pupdevices", None, None, ("*",))

try:
    from pybricks.iodevices import PUPDevice
except ImportError:
    PUPDevice = None  # BOOST exposes typed devices but not the generic probe.


KINDS = (
    ("motor", "Motor"),
    ("color_distance", "ColorDistanceSensor"),
    ("color", "ColorSensor"),
    ("ultrasonic", "UltrasonicSensor"),
    ("force", "ForceSensor"),
)


def probe(port):
    if PUPDevice is not None:
        identifier = PUPDevice(port).info()["id"]
        kind = {
            38: "motor",
            46: "motor",
            47: "motor",
            48: "motor",
            49: "motor",
            65: "motor",
            75: "motor",
            76: "motor",
            37: "color_distance",
            61: "color",
            62: "ultrasonic",
            63: "force",
        }.get(identifier)
        for candidate, name in KINDS:
            if candidate == kind and hasattr(pup, name):
                return kind, getattr(pup, name)(port), identifier
        return "unknown", None, identifier
    for kind, name in KINDS:
        if hasattr(pup, name):
            try:
                return kind, getattr(pup, name)(port), 0
            except OSError:
                pass
    raise OSError("No supported device")


def main():
    hub = None
    identity = {}
    for name in (
        "PrimeHub",
        "InventorHub",
        "TechnicHub",
        "CityHub",
        "EssentialHub",
        "MoveHub",
    ):
        if hasattr(hubs, name):
            hub = getattr(hubs, name)()
            identity = {
                "name": hub.system.name(),
                "kind": name,
                "model": {
                    "PrimeHub": "inventor",
                    "InventorHub": "inventor",
                    "MoveHub": "boost",
                    "TechnicHub": "technic",
                }.get(name, ""),
            }
            break
    ports = {name: getattr(Port, name) for name in "ABCDEF" if hasattr(Port, name)}
    devices = {}
    buffer = bytearray()
    clock = StopWatch()
    last_input = -1000
    last_report = last_scan = -2000
    active = set()
    last_commands = {}

    def brake():
        for port in tuple(active):
            try:
                devices[port][1].brake()
            except (OSError, KeyError):
                pass
        active.clear()
        last_commands.clear()

    try:
        while True:
            now = clock.time()
            if now - last_scan >= 2000:
                last_scan = now
                for port, value in ports.items():
                    if port in devices:
                        continue
                    try:
                        devices[port] = probe(value)
                    except OSError:
                        pass

            for _ in range(256):
                value = read_input_byte()
                if value is None:
                    break
                if value != 10:
                    buffer.append(value)
                    if len(buffer) > 2048:
                        buffer = bytearray()
                    continue
                try:
                    commands = []
                    for item in bytes(buffer).decode().strip().split(";"):
                        if item:
                            port, mode, value = item.split(",")
                            commands.append((port, mode, float(value)))
                    used = set()
                    for port, mode, target in commands:
                        if (
                            port in used
                            or port not in devices
                            or devices[port][0] != "motor"
                            or mode not in ("speed", "servo")
                            or not isinstance(target, (int, float))
                            or target != target
                            or abs(target) > 10000
                        ):
                            raise ValueError("Invalid motor command")
                        used.add(port)
                    for port in active - used:
                        devices[port][1].brake()
                        last_commands.pop(port, None)
                    # Include all requested motors before issuing commands: if
                    # a later device fails, brake() must also stop earlier ones.
                    active = used
                    for port, mode, target in commands:
                        if last_commands.get(port) == (mode, target):
                            continue
                        motor = devices[port][1]
                        if mode == "servo":
                            motor.run_target(500, target, wait=False)
                        elif target:
                            motor.run(target)
                        else:
                            motor.brake()
                        last_commands[port] = (mode, target)
                    last_input = now
                except (ValueError, TypeError, KeyError, OSError):
                    brake()
                buffer = bytearray()

            if active and now - last_input > 500:
                brake()
            if now - last_report >= 200:
                last_report = now
                report = {port: {"type": "empty"} for port in ports}
                for port, (kind, device, identifier) in tuple(devices.items()):
                    data = {"type": kind, "id": identifier}
                    try:
                        if kind == "motor":
                            data.update(angle=device.angle(), speed=device.speed())
                        elif kind in ("color", "color_distance"):
                            data["reflection"] = device.reflection()
                            if kind == "color_distance":
                                data["distance_percent"] = device.distance()
                        elif kind == "ultrasonic":
                            data["distance"] = device.distance()
                        elif kind == "force":
                            data["force"] = device.force()
                        report[port] = data
                    except OSError:
                        del devices[port]
                        active.discard(port)
                        last_commands.pop(port, None)
                payload = {"ports": report, "monitoring": True, "running": False}
                payload.update(identity)
                if hub is not None:
                    payload["battery_mv"] = hub.battery.voltage()
                print("\x1ePYBLOCKS " + repr(payload))
            wait(20)
    finally:
        brake()


if __name__ == "__main__":
    main()
