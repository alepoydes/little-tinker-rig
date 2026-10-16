"""Hub lights, sound and motion

Small hub actions; capabilities remain explicit in types and help."""

__category__ = "devices"


@inline_block(
    level="intermediate",
    icon="▣",
    color="state",
    names=("name",),
    variant="Prime / Inventor Hub",
)
def prime_hub(name=hub):
    """Connect to the SPIKE Prime or Robot Inventor hub."""
    from pybricks.hubs import PrimeHub

    name: "PrimeHub" = PrimeHub()


@inline_block(
    level="intermediate",
    icon="▣",
    color="state",
    names=("name",),
    family="pybricks/hubs/prime_hub",
    variant="Move Hub",
)
def move_hub(name=hub):
    """Connect to the BOOST Move Hub."""
    from pybricks.hubs import MoveHub

    name: "MoveHub" = MoveHub()


@inline_block(
    level="intermediate",
    icon="▣",
    color="state",
    names=("name",),
    family="pybricks/hubs/prime_hub",
    variant="Technic Hub",
)
def technic_hub(name=hub):
    """Connect to the Technic Hub."""
    from pybricks.hubs import TechnicHub

    name: "TechnicHub" = TechnicHub()


@inline_block(
    level="intermediate", icon="▶", color="action", category="output", variant="On"
)
def light(
    hub: "PrimeHub | InventorHub | MoveHub | TechnicHub" = hub,
    color: "Color" = Color.GREEN,
):
    """Change the hub status light."""
    from pybricks.parameters import Color

    hub.light.on(color)


@inline_block(
    level="intermediate",
    icon="▶",
    color="action",
    category="output",
    family="pybricks/hubs/light",
    variant="Off",
)
def light_off(hub: "PrimeHub | InventorHub | MoveHub | TechnicHub" = hub):
    """Turn off the hub status light."""
    hub.light.off()


@inline_block(
    level="intermediate",
    icon="▶",
    color="action",
    category="output",
    variant="Built-in icon",
)
def icon(hub: "PrimeHub | InventorHub" = hub, icon: "Icon" = Icon.HEART):
    """Show an icon on the Prime or Inventor display."""
    from pybricks.parameters import Icon

    hub.display.icon(icon)


@inline_block(
    level="intermediate",
    icon="▶",
    color="action",
    category="output",
    variant="Frequency and duration",
)
def beep(
    hub: "PrimeHub | InventorHub" = hub,
    frequency: "int[Hz]" = 500,
    duration: "number[ms]" = 100,
):
    """Play a tone on the Prime or Inventor speaker.

    Frequency is 64–24000 Hz. A finite duration waits for the tone to finish.
    Recorded sounds and speech require a computer and are not hub tones."""
    hub.speaker.beep(frequency, duration)


@inline_block(level="advanced", icon="▶", color="action", category="output")
def display_number(hub: "PrimeHub | InventorHub" = hub, value: "number" = 0):
    """Show a number on the Prime or Inventor display."""
    hub.display.number(value)


@inline_block(level="intermediate", icon="＝", color="value", category="input")
def button_pressed(
    hub: "PrimeHub | InventorHub | MoveHub | TechnicHub" = hub,
    button: "Button" = Button.CENTER,
) -> "bool":
    """Check whether a hub button is pressed.

    Available buttons depend on the hub. The center button normally stops the
    program; use left/right on Prime or Inventor without changing that behavior."""
    from pybricks.parameters import Button

    return button in hub.buttons.pressed()


@inline_block(level="intermediate", icon="＝", color="value", category="input")
def tilted(
    hub: "PrimeHub | InventorHub | MoveHub | TechnicHub" = hub,
    side: "Side" = Side.LEFT,
) -> "bool":
    """Check which side of the hub faces upward."""
    from pybricks.parameters import Side

    return hub.imu.up() == side


@inline_block(level="advanced", icon="▶", color="action", category="input")
def heading(hub: "PrimeHub | InventorHub | TechnicHub" = hub) -> "number[deg]":
    """Read the gyro heading in degrees.

    Positive angles turn clockwise. BOOST has tilt sensing, not a gyro heading."""
    return hub.imu.heading()


@inline_block(level="advanced", icon="▶", color="action")
def battery_voltage(
    hub: "PrimeHub | InventorHub | MoveHub | TechnicHub" = hub,
) -> "number":
    """Read the battery voltage in millivolts."""
    return hub.battery.voltage()


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    category="output",
    family="pybricks/hubs/icon",
    variant="Brightness matrix",
)
def display_pattern(
    hub: "PrimeHub | InventorHub" = hub,
    pixels: "list | tuple | Matrix" = [
        [0, 0, 0, 0, 0],
        [0, 100, 0, 100, 0],
        [0, 0, 0, 0, 0],
        [0, 100, 100, 100, 0],
        [0, 0, 0, 0, 0],
    ],
):
    """Display a custom five-by-five brightness pattern.

    Each row contains five brightness values from 0 to 100. Named icons use
    the simpler icon block."""
    hub.display.icon(pixels)


@inline_block(level="intermediate", icon="▶", color="action", category="output")
def display_off(hub: "PrimeHub | InventorHub" = hub):
    """Clear the hub display."""
    hub.display.off()
