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
    left_trigger: float = 0
    right_trigger: float = 0

    def __post_init__(self):
        for value in (self.left_x, self.left_y, self.right_x, self.right_y):
            if not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError("Controller axes must be finite values in [-1, 1]")
        for value in (self.slider, self.left_trigger, self.right_trigger):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Controller slider and triggers must be in [0, 1]")
        if not isinstance(self.buttons, int) or not 0 <= self.buttons <= 0xFFFF:
            raise ValueError("Controller buttons must be a 16-bit bitmask")

    def encode(self) -> bytes:
        """ASCII stdin frame; old 16-byte frames remain valid without triggers."""
        axes = (self.left_x, self.left_y, self.right_x, self.right_y)
        body = "".join(f"{round(value * 100) + 100:02x}" for value in axes)
        triggers = (
            f"{round(self.left_trigger * 100):02x}{round(self.right_trigger * 100):02x}"
            if self.left_trigger or self.right_trigger
            else ""
        )
        return f"~{body}{self.buttons:04x}{round(self.slider * 100):02x}{triggers}\n".encode(
            "ascii"
        )

    @classmethod
    def decode(cls, frame: bytes) -> "ControlState":
        if len(frame) not in (16, 20) or frame[:1] != b"~" or frame[-1:] != b"\n":
            raise ValueError("Malformed controller frame")
        axes = [
            (int(frame[index : index + 2], 16) - 100) / 100 for index in (1, 3, 5, 7)
        ]
        triggers = (
            [int(frame[i : i + 2], 16) / 100 for i in (15, 17)]
            if len(frame) == 20
            else [0, 0]
        )
        return cls(*axes, int(frame[9:13], 16), int(frame[13:15], 16) / 100, *triggers)


class Gamepad:
    """SDL's documented controller API gives stable Xbox axes and button names."""

    def __init__(self, index: int = 0):
        import pygame
        from pygame._sdl2 import controller

        self.pygame = pygame
        pygame.display.init()
        controller.init()
        if index >= controller.get_count() or not controller.is_controller(index):
            raise ValueError(
                "No supported controller found; connect an Xbox-compatible SDL controller"
            )
        self.device = controller.Controller(index)

    def read(self) -> ControlState:
        self.pygame.event.pump()
        if not self.device.attached():
            raise ValueError("Physical controller disconnected")
        axes = [self.device.get_axis(index) / 32767 for index in range(4)]
        axes = [0 if abs(value) < 0.08 else max(-1, min(1, value)) for value in axes]
        buttons = sum(
            1 << index for index in range(15) if self.device.get_button(index)
        )
        triggers = [
            max(0, min(1, self.device.get_axis(index) / 32767)) for index in (4, 5)
        ]
        return ControlState(
            axes[0],
            -axes[1],
            axes[2],
            -axes[3],
            buttons,
            left_trigger=triggers[0],
            right_trigger=triggers[1],
        )

    def close(self):
        self.device.quit()
