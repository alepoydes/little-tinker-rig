"""Run ordinary user Python in a separate process with explicit Pybricks models.

This is a learning simulator, not a sandbox. Unsupported API calls fail normally.
"""

import argparse
import json
import math
import queue
import runpy
import sys
import time
import traceback
from enum import Enum
from pathlib import Path
from threading import Lock, Thread
from types import ModuleType, SimpleNamespace

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

        def angle(self):
            return round(
                world.device(self.port, "motor")["angle"] * self.sign - self.zero
            )

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
                while abs(self.angle() - target_angle) > 1:
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
            self.left, self.right = left_motor, right_motor
            self.wheel, self.track = wheel_diameter, axle_track

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
        "parameters": dict(Port=Port, Direction=Direction, Stop=Stop, Color=Color),
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
    if world.model != "boost":
        modules["iodevices"] = dict(PUPDevice=PUPDevice)
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
