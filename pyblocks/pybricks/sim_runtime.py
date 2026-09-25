"""Run ordinary user Python in a separate process with explicit Pybricks models.

This is a learning simulator, not a sandbox. Unsupported API calls fail normally.
"""

import argparse
import json
import math
import queue
import random
import runpy
import sys
import time
import traceback
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from types import ModuleType, SimpleNamespace

from pyblocks.core.parameters import ENUM_VALUES

from .devices import PREFIX
from .simulation import World


def install_modules(world, incoming):
    Port = Enum("Port", {port: port for port in world.available_ports})

    class Direction(Enum):
        CLOCKWISE = 1
        COUNTERCLOCKWISE = -1

    class Stop(Enum):
        COAST, BRAKE, HOLD = range(3)

    class Color(Enum):
        RED, GREEN, BLUE, WHITE, BLACK, YELLOW, NONE = range(7)

    Button = Enum("Button", {name: name for name in ENUM_VALUES["Button"]})
    Side = Enum("Side", {name: name for name in ENUM_VALUES["Side"]})

    class Motor:
        def __init__(
            self,
            port,
            positive_direction=Direction.CLOCKWISE,
            gears=None,
            reset_angle=True,
            profile=None,
        ):
            if gears or profile:
                raise NotImplementedError(
                    "Virtual motor gears and control profiles are not modeled"
                )
            self.port, self.sign = port.value, positive_direction.value
            self.zero = (
                world.device(self.port, "motor")["angle"] * self.sign
                if reset_angle
                else 0
            )

        def _position(self):
            return world.device(self.port, "motor")["angle"] * self.sign - self.zero

        def angle(self):
            return round(self._position())

        def speed(self):
            return round(world.device(self.port, "motor")["speed"] * self.sign)

        def reset_angle(self, angle=0):
            self.zero = world.device(self.port, "motor")["angle"] * self.sign - angle

        def run(self, speed):
            world.command(self.port, speed * self.sign)

        def dc(self, duty):
            if not -100 <= duty <= 100:
                raise ValueError("Duty must be −100…100")
            self.run(duty * 10)

        def stop(self):
            world.stop(self.port)

        brake = hold = stop

        def run_target(self, speed, target_angle, then=Stop.HOLD, wait=True):
            if speed <= 0:
                raise ValueError("Target speed must be positive")
            world.command(
                self.port, target=(target_angle + self.zero) * self.sign, limit=speed
            )
            if wait:
                while abs(self._position() - target_angle) > 1:
                    time.sleep(0.01)
                self.stop()

        def run_angle(self, speed, rotation_angle, then=Stop.HOLD, wait=True):
            self.run_target(
                abs(speed),
                self.angle() + rotation_angle * (1 if speed >= 0 else -1),
                then,
                wait,
            )

        def run_time(self, speed, duration, then=Stop.HOLD, wait=True):
            def motion():
                self.run(speed)
                time.sleep(max(0, duration) / 1000)
                self.stop()

            if wait:
                motion()
            else:
                Thread(target=motion, daemon=True).start()

    class ColorSensor:
        def __init__(self, port):
            self.port = port.value
            world.device(self.port, "color")

        def reflection(self):
            return world.device(self.port, "color")["reflection"]

        def color(self):
            return Color.WHITE if self.reflection() >= 50 else Color.BLACK

    class UltrasonicSensor:
        def __init__(self, port):
            self.port = port.value
            world.device(self.port, "ultrasonic")

        def distance(self):
            return world.device(self.port, "ultrasonic")["distance"]

    class ColorDistanceSensor(ColorSensor):
        def __init__(self, port):
            self.port = port.value
            world.device(self.port, "color_distance")

        def reflection(self):
            return world.device(self.port, "color_distance")["reflection"]

        def distance(self):
            return world.device(self.port, "color_distance")["distance_percent"]

    class ForceSensor:
        def __init__(self, port):
            self.port = port.value
            world.device(self.port, "force")

        def force(self):
            return world.device(self.port, "force")["force"]

        def pressed(self, force=3):
            return self.force() >= force

    class StopWatch:
        def __init__(self):
            self.reset()

        def reset(self):
            self.started = time.monotonic()

        def time(self):
            return int((time.monotonic() - self.started) * 1000)

    class DriveBase:
        def __init__(self, left_motor, right_motor, wheel_diameter, axle_track):
            if wheel_diameter <= 0 or axle_track <= 0:
                raise ValueError("Robot dimensions must be positive")
            if left_motor.port == right_motor.port:
                raise ValueError("A drive base needs two different motor ports")
            self.left, self.right = left_motor, right_motor
            self.wheel, self.track = wheel_diameter, axle_track
            self.origins = (self.left.angle(), self.right.angle())
            self.offsets = (0, 0)
            self._settings = (200, 400, 90, 180)

        def distance(self):
            left = self.left.angle() - self.origins[0]
            right = self.right.angle() - self.origins[1]
            return (left + right) * math.pi * self.wheel / 720 + self.offsets[0]

        def angle(self):
            left = self.left.angle() - self.origins[0]
            right = self.right.angle() - self.origins[1]
            return (left - right) * self.wheel / (2 * self.track) + self.offsets[1]

        def _move(self, left, right, then, wait, duration):
            targets = (self.left.angle() + left, self.right.angle() + right)
            for motor, target, delta in zip(
                (self.left, self.right), targets, (left, right), strict=True
            ):
                if delta:
                    motor.run_target(abs(delta) / duration, target, then, wait=False)
                else:
                    motor.stop()
            if wait:
                while any(
                    abs(motor._position() - target) > 1
                    for motor, target in zip(
                        (self.left, self.right), targets, strict=True
                    )
                ):
                    time.sleep(0.01)
                self.stop()

        def straight(self, distance, then=Stop.HOLD, wait=True):
            rotation = distance * 360 / (math.pi * self.wheel)
            self._move(
                rotation, rotation, then, wait, abs(distance) / self._settings[0]
            )

        def turn(self, angle, then=Stop.HOLD, wait=True, absolute=False):
            delta = angle - self.angle() if absolute else angle
            rotation = delta * self.track / self.wheel
            self._move(rotation, -rotation, then, wait, abs(delta) / self._settings[2])

        def arc(self, radius, angle=None, distance=None, then=Stop.HOLD, wait=True):
            if not radius or (angle is None) == (distance is None):
                raise ValueError(
                    "An arc needs a nonzero radius and either angle or distance"
                )
            distance = (
                math.radians(angle) * abs(radius) if angle is not None else distance
            )
            turn = distance / radius
            factor = 360 / (math.pi * self.wheel)
            self._move(
                (distance + turn * self.track / 2) * factor,
                (distance - turn * self.track / 2) * factor,
                then,
                wait,
                abs(distance) / self._settings[0],
            )

        def settings(
            self,
            straight_speed=None,
            straight_acceleration=None,
            turn_rate=None,
            turn_acceleration=None,
        ):
            values = (
                straight_speed,
                straight_acceleration,
                turn_rate,
                turn_acceleration,
            )
            if all(value is None for value in values):
                return self._settings
            if any(
                value is not None and (not math.isfinite(value) or value == 0)
                for value in values
            ):
                raise ValueError(
                    "Virtual drive settings must be finite nonzero numbers"
                )
            self._settings = tuple(
                previous if value is None else abs(value)
                for previous, value in zip(self._settings, values, strict=True)
            )

        def reset(self, distance=0, angle=0):
            self.stop()
            self.origins = (self.left.angle(), self.right.angle())
            self.offsets = (distance, angle)

        def drive(self, speed, turn_rate):
            differential = math.radians(turn_rate) * self.track / 2
            self.left.run((speed + differential) * 360 / (math.pi * self.wheel))
            self.right.run((speed - differential) * 360 / (math.pi * self.wheel))

        def stop(self):
            self.left.stop()
            self.right.stop()

        brake = stop

    class Hub:
        def __init__(self):
            self.battery = SimpleNamespace(voltage=lambda: 8000, current=lambda: 100)
            self.system = SimpleNamespace(name=lambda: "Virtual hub")
            self.light = SimpleNamespace(
                on=lambda color: self._feedback("light", color.name),
                off=lambda: self._feedback("light", None),
            )
            self.buttons = SimpleNamespace(
                pressed=lambda: {Button[name] for name in world.hub_inputs["buttons"]}
            )
            self.imu = SimpleNamespace(up=lambda: Side[world.hub_inputs["up"]])
            if world.model != "boost":
                self.imu.heading = lambda: world.hub_inputs["heading"]
            if world.model == "inventor":
                self.display = SimpleNamespace(
                    icon=lambda icon: self._feedback("display", icon.name),
                    number=lambda number: self._feedback("display", number),
                )
                self.speaker = SimpleNamespace(beep=self._beep)

        def _feedback(self, channel, value):
            world.feedback[channel] = value
            print(f"[Virtual hub {channel}] {value}", flush=True)

        def _beep(self, frequency=500, duration=100):
            if not 64 <= frequency <= 24000:
                raise ValueError("Tone frequency must be 64–24000 Hz")
            self._feedback("tone", frequency)
            if duration >= 0:
                time.sleep(duration / 1000)
                world.feedback["tone"] = None

    class PUPDevice:
        def __init__(self, port):
            self.port = port.value
            if world.ports[self.port]["type"] == "empty":
                raise OSError("No device attached")

        def info(self):
            return {
                "id": {
                    "motor": 48,
                    "color": 61,
                    "color_distance": 37,
                    "ultrasonic": 62,
                    "force": 63,
                }[world.ports[self.port]["type"]]
            }

    def read_input_byte():
        try:
            return incoming.get_nowait()
        except queue.Empty:
            return None

    modules = {
        "parameters": dict(
            Port=Port,
            Direction=Direction,
            Stop=Stop,
            Color=Color,
            Button=Button,
            Side=Side,
        ),
        "pupdevices": dict(
            Motor=Motor,
            ColorSensor=ColorSensor,
            ColorDistanceSensor=ColorDistanceSensor,
            UltrasonicSensor=UltrasonicSensor,
            ForceSensor=ForceSensor,
        ),
        "tools": dict(
            wait=lambda milliseconds: time.sleep(max(0, milliseconds) / 1000),
            StopWatch=StopWatch,
            read_input_byte=read_input_byte,
        ),
        "robotics": dict(DriveBase=DriveBase),
        "hubs": {
            name: Hub
            for name in {
                "inventor": ("PrimeHub", "InventorHub"),
                "boost": ("MoveHub",),
                "technic": ("TechnicHub",),
            }[world.model]
        },
    }
    if world.model == "inventor":
        # Only named icons used by the library are modeled, not matrix arithmetic.
        modules["parameters"]["Icon"] = Enum(
            "Icon", {name: name for name in ENUM_VALUES["Icon"]}
        )
    if world.model != "boost":
        modules["iodevices"] = dict(PUPDevice=PUPDevice)
        generator = random.Random()
        module = ModuleType("urandom")
        for name in (
            "randint",
            "random",
            "getrandbits",
            "randrange",
            "uniform",
            "choice",
            "seed",
        ):
            setattr(module, name, getattr(generator, name))
        sys.modules["urandom"] = module
    else:
        # Do not accidentally expose a host-installed compatibility package.
        sys.modules["urandom"] = None
    package = ModuleType("pybricks")
    package.__path__ = []
    sys.modules["pybricks"] = package
    for name, members in modules.items():
        module = ModuleType("pybricks." + name)
        module.__dict__.update(members)
        sys.modules[module.__name__] = module
        setattr(package, name, module)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--program", type=Path)
    parser.add_argument("--ports", default="{}")
    parser.add_argument("--model", default="inventor")
    arguments = parser.parse_args()
    world = World(json.loads(arguments.ports) or None, arguments.model)
    incoming = queue.Queue()
    install_modules(world, incoming)
    running = bool(arguments.program)
    error = ""
    output_lock = Lock()

    def report():
        payload = {
            "ports": world.snapshot(),
            "battery_mv": 8000,
            "running": running,
            "monitoring": not running,
            "error": error,
        }
        with output_lock:
            # Telemetry has its own pipe, so print(..., end='') remains immediate.
            sys.stderr.write(PREFIX.decode() + json.dumps(payload) + "\n")
            sys.stderr.flush()

    def tick():
        previous = last_report = time.monotonic()
        while True:
            now = time.monotonic()
            world.advance(now - previous)
            previous = now
            if now - last_report >= 0.1:
                report()
                last_report = now
            time.sleep(0.01)

    def receive():
        for line in sys.stdin.buffer:
            if not line.lstrip().startswith(b"{"):
                for byte in line:
                    incoming.put(byte)
                continue
            try:
                command = json.loads(line)
                if "configure" in command:
                    world.configure(**command["configure"])
                elif "motors" in command:
                    world.drive(command["motors"])
            except (ValueError, TypeError, KeyError, OSError) as error:
                print(str(error), flush=True)

    Thread(target=tick, daemon=True).start()
    Thread(target=receive, daemon=True).start()
    report()
    if arguments.program:
        sys.path.insert(0, str(arguments.program.resolve().parent))
        try:
            runpy.run_path(str(arguments.program), run_name="__main__")
        except BaseException as exception:
            if not isinstance(exception, SystemExit) or exception.code not in (None, 0):
                error = f"{type(exception).__name__}: {exception}"
                traceback.print_exc(file=sys.stdout)
        finally:
            running = False
            for port, data in world.snapshot().items():
                if data["type"] == "motor":
                    world.stop(port)
            report()
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
