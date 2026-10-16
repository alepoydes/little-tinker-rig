"""Color measurements

Explicit device operations for studying complete robot programs."""

__category__ = "input"


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    variant="Color sensor",
    title="Sensor value",
)
def colorsensor_port(port: "Port" = Port.A) -> "ColorSensor":
    """Create a sensor value.

    Connect a color sensor. Options: port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorSensor

    return ColorSensor(port)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    family="pybricks/sensor_values/colorsensor_port",
    variant="Ultrasonic sensor",
    title="Sensor value",
)
def ultrasonicsensor_port(port: "Port" = Port.A) -> "UltrasonicSensor":
    """Connect a distance sensor. Options: port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import UltrasonicSensor

    return UltrasonicSensor(port)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    title="Read HSV color",
    group=("Color and reflection",),
)
def sensor_hsv(sensor: "ColorSensor | ColorDistanceSensor" = sensor) -> "Color":
    """Read the measured hue, saturation and brightness."""
    return sensor.hsv()


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    title="Set detectable colors",
    group=("Color and reflection",),
)
def sensor_detectable_colors_colors(
    sensor: "ColorSensor | ColorDistanceSensor" = sensor, colors=[Color.RED, Color.BLUE]
):
    """Choose the colors the sensor should recognize. Options: colors."""
    from pybricks.parameters import Color

    sensor.detectable_colors(colors)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    family="pybricks/sensors/color",
    variant="Surface or light source",
    title="Detected color",
)
def sensor_color_surface(
    sensor: "ColorSensor | ColorDistanceSensor" = sensor, surface: "bool" = True
) -> "Color":
    """Read a recognized color. Options: surface."""
    return sensor.color(surface)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    category="values",
    title="Create HSV color",
)
def color_h_s_v(h: "number" = 0, s: "number[%]" = 100, v: "number[%]" = 100) -> "Color":
    """Create a color from hue, saturation and brightness. Options: h, s, v."""
    from pybricks.parameters import Color

    return Color(h, s, v)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    title="Ambient light",
    group=("Color and reflection",),
)
def sensor_ambient(sensor: "ColorSensor | ColorDistanceSensor" = sensor) -> "number[%]":
    """Read ambient light intensity."""
    return sensor.ambient()
