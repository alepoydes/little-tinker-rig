"""Sensors and timing

Sensor and timing templates."""

@inline_block(level="beginner", icon="⏱", color="action")
def wait_ms(duration: "number[ms]" = 1000):
    """Wait for a number of milliseconds. 1000 ms = 1 second."""
    from pybricks.tools import wait

    wait(duration)


@inline_block(level="beginner", icon="◉", color="state", names=("name",))
def create_color_sensor(name=sensor, port: "Port" = Port.C):
    """Connect a color sensor to a hub port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorSensor

    name: "ColorSensor" = ColorSensor(port)


@inline_block(level="intermediate", icon="◉", color="value")
def reflection_below(
    sensor: "ColorSensor | ColorDistanceSensor" = sensor, threshold: "number[%]" = 30
) -> "bool":
    """Check whether a surface is darker than a reflection threshold."""
    return sensor.reflection() < threshold


@inline_block(level="advanced", icon="◉", color="loop")
def follow_edge(
    drive: "DriveBase" = drive,
    sensor: "ColorSensor | ColorDistanceSensor" = sensor,
    target: "number[%]" = 50,
    gain=2,
):
    """Follow a line edge using proportional control.

    drive is an existing DriveBase; sensor measures reflection.
    target is the reflection at the edge; gain sets correction strength.
    The loop continues until the program is stopped."""
    from pybricks.tools import wait

    while True:
        error = sensor.reflection() - target
        drive.drive(200, gain * error)
        wait(10)


@inline_block(level="intermediate", icon="◉", color="state", names=("name",))
def create_ultrasonic_sensor(name=distance, port: "Port" = Port.D):
    """Connect an ultrasonic distance sensor."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import UltrasonicSensor

    name: "UltrasonicSensor" = UltrasonicSensor(port)


@inline_block(level="intermediate", icon="◉", color="state", names=("name",))
def create_force_sensor(name=button, port: "Port" = Port.E):
    """Connect a force sensor to measure presses."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ForceSensor

    name: "ForceSensor" = ForceSensor(port)


@inline_block(level="beginner", icon="◉", color="state", names=("name",))
def create_color_distance_sensor(name=sensor, port: "Port" = Port.D):
    """Connect a BOOST color and distance sensor."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorDistanceSensor

    name: "ColorDistanceSensor" = ColorDistanceSensor(port)


@inline_block(level="intermediate", icon="◉", color="action")
def reflection(sensor: "ColorSensor | ColorDistanceSensor" = sensor) -> "number[%]":
    """Measure surface reflection from 0 to 100%."""
    return sensor.reflection()


@inline_block(level="intermediate", icon="◉", color="action")
def distance(sensor: "UltrasonicSensor" = distance) -> "number[mm]":
    """Measure obstacle distance in millimeters."""
    return sensor.distance()


@inline_block(level="intermediate", icon="◉", color="action")
def boost_distance(sensor: "ColorDistanceSensor" = sensor) -> "number[%]":
    """Measure relative distance with a BOOST sensor."""
    return sensor.distance()


@inline_block(level="intermediate", icon="◉", color="action")
def force(sensor: "ForceSensor" = button) -> "number[N]":
    """Measure pressing force in newtons."""
    return sensor.force()


@inline_block(level="intermediate", icon="◉", color="action")
def pressed(sensor: "ForceSensor" = button) -> "bool":
    """Check whether the force sensor button is pressed."""
    return sensor.pressed()


@inline_block(level="intermediate", icon="◉", color="action")
def color(sensor: "ColorSensor | ColorDistanceSensor" = sensor) -> "Color":
    """Read the surface color under the sensor."""
    return sensor.color()


@inline_block(level="beginner", icon="◉", color="loop")
def wait_color(
    sensor: "ColorSensor | ColorDistanceSensor" = sensor, color: "Color" = Color.WHITE
):
    """Wait until the sensor sees a chosen color.

    Connect a color sensor first. This works with SPIKE and BOOST color sensors.
    The next action starts when the color matches; Stop cancels the program."""
    from pybricks.parameters import Color
    from pybricks.tools import wait

    while sensor.color() != color:
        wait(20)


@inline_block(level="intermediate", icon="◉", color="loop")
def wait_until(test: "bool" = False):
    """Wait until a sensor condition becomes true.

    Replace False with a reading or comparison, such as distance.distance() < 100.
    The condition is checked repeatedly, every 20 milliseconds."""
    from pybricks.tools import wait

    while not test:
        wait(20)


@inline_block(level="intermediate", icon="◉", color="action")
def distance_lights(
    sensor: "UltrasonicSensor | ColorSensor" = distance,
    brightness: "number[%] | list | tuple" = 100,
):
    """Set the ultrasonic sensor eye brightness."""
    sensor.lights.on(brightness)


@inline_block(level="intermediate", icon="◉", color="action")
def distance_lights_off(sensor: "UltrasonicSensor | ColorSensor" = distance):
    """Turn off the ultrasonic sensor eyes."""
    sensor.lights.off()
