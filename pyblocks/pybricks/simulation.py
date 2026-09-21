"""Small deterministic device model; time is advanced explicitly by the runtime."""

import math
from threading import RLock

PROFILES = {
    "inventor": ("Robot Inventor / SPIKE Prime", "ABCDEF", ()),
    "boost": ("BOOST Move Hub", "ABCD", ("A", "B")),
    "technic": ("LEGO Technic Hub", "ABCD", ()),
}
DEFAULT_PORTS = {
    "A": "motor",
    "B": "motor",
    "C": "color",
    "D": "ultrasonic",
    "E": "force",
    "F": "empty",
}
SENSOR_VALUES = {
    "color": {"reflection": (50, 100)},
    "color_distance": {"reflection": (50, 100), "distance_percent": (50, 100)},
    "ultrasonic": {"distance": (500, 2000)},
    "force": {"force": (0, 10)},
}


class World:
    def __init__(self, ports=None, model="inventor"):
        if model not in PROFILES:
            raise ValueError("Virtual hub model must be inventor, boost or technic")
        self.model = model
        _, self.available_ports, self.built_in = PROFILES[model]
        self.lock = RLock()
        self.ports = {}
        self.active = set()
        self.age = 0
        defaults = {port: DEFAULT_PORTS[port] for port in self.available_ports}
        if model == "boost":
            defaults.update(C="motor", D="color_distance")
        for name, kind in (ports or defaults).items():
            data = kind if isinstance(kind, dict) else {"type": kind}
            self.configure(name, data["type"])
            if data["type"] == "motor":
                self.ports[name]["angle"] = data.get("angle", 0)
            elif data["type"] in SENSOR_VALUES:
                self.configure(
                    name,
                    data["type"],
                    {
                        field: data.get(field, default)
                        for field, (default, _) in SENSOR_VALUES[data["type"]].items()
                    },
                )

    def configure(self, port, kind, value=None):
        if port not in self.available_ports or kind not in {
            *SENSOR_VALUES,
            "motor",
            "empty",
        }:
            raise ValueError("Unknown virtual port or device")
        if port in self.built_in and kind != "motor":
            raise ValueError("BOOST ports A and B are built-in motors")
        values = {}
        if value is not None:
            fields = SENSOR_VALUES.get(kind, {})
            if not fields:
                raise ValueError("Only sensors accept input values")
            values = value if isinstance(value, dict) else {next(iter(fields)): value}
            for field, number in values.items():
                if (
                    field not in fields
                    or not math.isfinite(number)
                    or not 0 <= number <= fields[field][1]
                ):
                    raise ValueError("Sensor value is outside its modeled range")
        with self.lock:
            if self.ports.get(port, {}).get("type") != kind:
                data = {"type": kind}
                if kind == "motor":
                    data.update(angle=0.0, speed=0.0, target=None, limit=500.0)
                elif kind in SENSOR_VALUES:
                    data.update(
                        {
                            field: default
                            for field, (default, _) in SENSOR_VALUES[kind].items()
                        }
                    )
                self.ports[port] = data
                self.active.discard(port)
            self.ports[port].update(
                {field: float(number) for field, number in values.items()}
            )

    def device(self, port, kind):
        data = self.ports.get(port)
        if data is None or data["type"] != kind:
            raise OSError(f"Port {port}: attach a {kind} in the virtual hub panel")
        return data

    def drive(self, commands):
        with self.lock:
            selected = set()
            for port, mode, value in commands:
                self.device(port, "motor")
                if (
                    port in selected
                    or mode not in {"speed", "servo"}
                    or not math.isfinite(value)
                    or abs(value) > 10000
                ):
                    raise ValueError("Invalid motor command")
                selected.add(port)
            for port in self.active - selected:
                self.stop(port)
            for port, mode, value in commands:
                self.command(
                    port,
                    value if mode == "speed" else 0,
                    value if mode == "servo" else None,
                )
            self.active, self.age = selected, 0

    def command(self, port, speed=0, target=None, limit=500):
        if not all(math.isfinite(value) for value in (speed, limit)) or (
            target is not None and not math.isfinite(target)
        ):
            raise ValueError("Motor command must be finite")
        with self.lock:
            self.device(port, "motor").update(
                speed=speed, target=target, limit=abs(limit)
            )

    def stop(self, port):
        with self.lock:
            self.device(port, "motor").update(speed=0.0, target=None)

    def advance(self, seconds):
        if not math.isfinite(seconds) or seconds < 0:
            raise ValueError("Time step must be finite and nonnegative")
        with self.lock:
            # Integrate only up to the lease boundary; late sampling must not
            # give a stale command an extra full time step of movement.
            active_time = min(seconds, max(0, 0.5 - self.age))
            for port, data in self.ports.items():
                if data["type"] != "motor":
                    continue
                dt = active_time if port in self.active else seconds
                if data["target"] is None:
                    data["angle"] += data["speed"] * dt
                else:
                    delta = data["target"] - data["angle"]
                    travel = max(-data["limit"] * dt, min(data["limit"] * dt, delta))
                    data["angle"] += travel
                    data["speed"] = (
                        travel / dt if dt and abs(delta) > abs(travel) else 0
                    )
            self.age += seconds
            if self.age >= 0.5:
                for port in self.active:
                    self.stop(port)
                self.active.clear()

    def snapshot(self):
        with self.lock:
            return {
                port: {
                    key: round(value, 2) if isinstance(value, float) else value
                    for key, value in data.items()
                    if key not in {"target", "limit"}
                }
                for port, data in self.ports.items()
            }
