"""Xbox controller

Explicit device operations for studying complete robot programs."""

@inline_block(level="advanced", icon="▶", color="action")
def xboxcontroller() -> "XboxController":
    """Connect a Bluetooth Xbox controller (Pybricks 3.5 or later)."""
    from pybricks.iodevices import XboxController

    return XboxController()


@inline_block(level="advanced", icon="▶", color="action")
def controller_joystick_left(controller: "XboxController" = controller) -> "tuple":
    """Read the left Xbox joystick horizontal and vertical percentages."""
    return controller.joystick_left()


@inline_block(level="advanced", icon="▶", color="action")
def controller_triggers(controller: "XboxController" = controller) -> "tuple":
    """Read the Xbox brake and acceleration trigger percentages."""
    return controller.triggers()
