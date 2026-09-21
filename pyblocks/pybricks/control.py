"""A small input state shared by screen controls, keyboard and SDL gamepads."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ControlState:
    left_x: float = 0
    left_y: float = 0
    right_x: float = 0
    right_y: float = 0
    buttons: int = 0
    slider: float = 0

    def __post_init__(self):
        for value in (self.left_x, self.left_y, self.right_x, self.right_y):
            if not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError("Controller axes must be finite values in [-1, 1]")
        if not math.isfinite(self.slider) or not 0 <= self.slider <= 1:
            raise ValueError("Controller slider must be in [0, 1]")
        if not isinstance(self.buttons, int) or not 0 <= self.buttons <= 0xFFFF:
            raise ValueError("Controller buttons must be a 16-bit bitmask")

    def encode(self) -> bytes:
        """16 ASCII bytes, safe for stdin (no Ctrl+C or transport framing)."""
        axes = (self.left_x, self.left_y, self.right_x, self.right_y)
        body = "".join(f"{round(value * 100) + 100:02x}" for value in axes)
        return f"~{body}{self.buttons:04x}{round(self.slider * 100):02x}\n".encode(
            "ascii"
        )

    @classmethod
    def decode(cls, frame: bytes) -> "ControlState":
        if len(frame) != 16 or frame[:1] != b"~" or frame[-1:] != b"\n":
            raise ValueError("Malformed controller frame")
        axes = [
            (int(frame[index : index + 2], 16) - 100) / 100 for index in (1, 3, 5, 7)
        ]
        return cls(*axes, int(frame[9:13], 16), int(frame[13:15], 16) / 100)


class Gamepad:
    """SDL input is created only when the user enables a physical controller."""

    def __init__(self, index: int = 0):
        import pygame

        self.pygame = pygame
        pygame.display.init()
        pygame.joystick.init()
        if index >= pygame.joystick.get_count():
            raise ValueError("No gamepad found")
        self.device = pygame.joystick.Joystick(index)
        self.device.init()

    def read(self) -> ControlState:
        self.pygame.event.pump()
        if not self.device.get_init():
            return ControlState()
        axes = [
            self.device.get_axis(index) if index < self.device.get_numaxes() else 0
            for index in range(4)
        ]
        axes = [0 if abs(value) < 0.08 else max(-1, min(1, value)) for value in axes]
        buttons = sum(
            1 << index
            for index in range(min(16, self.device.get_numbuttons()))
            if self.device.get_button(index)
        )
        return ControlState(axes[0], -axes[1], axes[2], -axes[3], buttons)

    def close(self):
        self.device.quit()
        self.pygame.joystick.quit()
