"""Device snapshots and motor mappings shared by real and virtual hubs."""

import ast
import json
import math
from dataclasses import dataclass, field

from .control import ControlState


@dataclass(frozen=True)
class HubInfo:
    name: str = ""
    kind: str = ""
    firmware: str = ""
    transport: str = ""
    model: str = ""
    connected: bool = False
    running: bool = False
    monitoring: bool = False
    battery_mv: int | None = None
    ports: dict = field(default_factory=dict)
    error: str = ""


SOURCES = ("left_x", "left_y", "right_x", "right_y", "left_trigger", "right_trigger")


@dataclass(frozen=True)
class MotorBinding:
    port: str
    source: str
    mode: str = "speed"
    scale: float = 500
    center: float = 0
    inverted: bool = False

    def __post_init__(self):
        if self.port not in "ABCDEF" or len(self.port) != 1:
            raise ValueError("Motor port must be A–F")
        if self.source not in SOURCES or self.mode not in {"speed", "servo"}:
            raise ValueError("Unknown motor source or mode")
        if not all(math.isfinite(v) for v in (self.scale, self.center)):
            raise ValueError("Motor settings must be finite")
        if not 0 <= self.scale <= 2000 or not -3600 <= self.center <= 3600:
            raise ValueError("Motor scale must be 0–2000; center must be within ±3600°")

    def command(self, state: ControlState) -> tuple[str, str, float]:
        value = getattr(state, self.source) * self.scale * (-1 if self.inverted else 1)
        return (
            self.port,
            self.mode,
            round(value + (self.center if self.mode == "servo" else 0), 2),
        )


def motor_commands(bindings, state):
    commands = tuple(binding.command(state) for binding in bindings)
    if len({command[0] for command in commands}) != len(commands):
        raise ValueError("Assign each motor port only once")
    return commands


def encode_commands(commands):
    """Compact ASCII commands need no JSON module on memory-limited BOOST hubs."""
    fields = []
    used = set()
    for port, mode, value in commands:
        if (
            port not in "ABCDEF"
            or len(port) != 1
            or port in used
            or mode not in {"speed", "servo"}
        ):
            raise ValueError("Invalid motor command")
        if not math.isfinite(value) or abs(value) > 10000:
            raise ValueError("Invalid motor value")
        used.add(port)
        fields.append(f"{port},{mode},{value:g}")
    return (";".join(fields) + "\n").encode("ascii")


PREFIX = b"\x1ePYBLOCKS "


class TelemetryStream:
    """Separate framed dict telemetry (JSON or MicroPython repr) from stdout."""

    def __init__(self, output, received):
        self.output, self.received = output, received
        self.buffer = b""

    def feed(self, data):
        self.buffer += data
        while self.buffer:
            index = self.buffer.find(PREFIX)
            if index == 0:
                end = self.buffer.find(b"\n")
                if end < 0 and len(self.buffer) < 65536:
                    return
                if end >= 0:
                    line, self.buffer = (
                        self.buffer[len(PREFIX) : end],
                        self.buffer[end + 1 :],
                    )
                    try:
                        payload = json.loads(line)
                    except (ValueError, UnicodeError):
                        try:
                            payload = ast.literal_eval(line.decode("utf-8"))
                        except (ValueError, SyntaxError, UnicodeError):
                            self.output(PREFIX + line + b"\n")
                            continue
                    if isinstance(payload, dict):
                        self.received(payload)
                    continue
                index = len(self.buffer)
            if index < 0:
                keep = next(
                    (
                        n
                        for n in range(min(len(PREFIX) - 1, len(self.buffer)), 0, -1)
                        if self.buffer.endswith(PREFIX[:n])
                    ),
                    0,
                )
                index = len(self.buffer) - keep
            if index == 0:
                return
            self.output(self.buffer[:index])
            self.buffer = self.buffer[index:]

    def finish(self):
        if self.buffer:
            self.output(self.buffer)
            self.buffer = b""
