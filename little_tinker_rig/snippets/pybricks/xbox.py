"""Xbox controller

Explicit device operations for studying complete robot programs."""

__category__ = "input"


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


@inline_block(level="advanced", icon="▶", color="value")
def controller_joystick_right(controller: "XboxController" = controller) -> "tuple":
    """Read the right Xbox joystick horizontal and vertical percentages."""
    return controller.joystick_right()


@inline_block(level="advanced", icon="▶", color="value")
def controller_buttons(controller: "XboxController" = controller) -> "set":
    """Read the pressed Xbox buttons, including bumpers and the direction pad."""
    return controller.buttons.pressed()


@inline_block(level="advanced", icon="▶", color="value")
def controller_dpad(controller: "XboxController" = controller) -> "int":
    """Read Xbox direction 1–8 clockwise from up, or 0 when released."""
    return controller.dpad()


@inline_block(level="advanced", icon="▶", color="action", category="output")
def controller_rumble(
    controller: "XboxController" = controller,
    power: "number[%]" = 100,
    duration: "number[ms]" = 200,
):
    """Vibrate the Xbox controller for feedback while the program continues."""
    controller.rumble(power, duration)
