"""Sensor and timing templates."""


def wait_ms(duration: "ms" = 1000):
    """Wait for a number of milliseconds. 1000 ms = 1 second."""
    from pybricks.tools import wait

    wait(duration)


def create_color_sensor(name=sensor, port: "Port" = Port.C):
    """Connect a color sensor to a hub port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorSensor

    name = ColorSensor(port)


def reflection_below(sensor: "ColorSensor" = sensor, threshold: "%" = 30) -> "bool":
    """Check whether a surface is darker than a reflection threshold."""
    return sensor.reflection() < threshold


def follow_edge(
    drive: "DriveBase" = drive, sensor: "ColorSensor" = sensor, target: "%" = 50, gain=2
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


def create_ultrasonic_sensor(name=distance, port: "Port" = Port.D):
    """Connect an ultrasonic distance sensor."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import UltrasonicSensor

    name = UltrasonicSensor(port)


def create_force_sensor(name=button, port: "Port" = Port.E):
    """Connect a force sensor or emergency button."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ForceSensor

    name = ForceSensor(port)


def create_color_distance_sensor(name=sensor, port: "Port" = Port.D):
    """Connect a BOOST color and distance sensor."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import ColorDistanceSensor

    name = ColorDistanceSensor(port)


def reflection(sensor: "ColorSensor" = sensor) -> "%":
    """Measure surface reflection from 0 to 100%."""
    return sensor.reflection()


def distance(sensor: "UltrasonicSensor" = distance) -> "mm":
    """Measure obstacle distance in millimeters."""
    return sensor.distance()


def boost_distance(sensor: "ColorDistanceSensor" = sensor) -> "%":
    """Measure relative distance with a BOOST sensor."""
    return sensor.distance()


def force(sensor: "ForceSensor" = button) -> "N":
    """Measure pressing force in newtons."""
    return sensor.force()


def pressed(sensor: "ForceSensor" = button) -> "bool":
    """Check whether the force sensor button is pressed."""
    return sensor.pressed()


def color(sensor: "ColorSensor" = sensor) -> "Color":
    """Read the surface color under the sensor."""
    return sensor.color()
