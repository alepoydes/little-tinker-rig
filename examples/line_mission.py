"""A finite line-following mission: motors A/B, SPIKE color sensor C."""

# --- automatically managed imports ---
from pybricks.parameters import Direction
from pybricks.parameters import Port
from pybricks.pupdevices import ColorSensor
from pybricks.pupdevices import Motor
from pybricks.robotics import DriveBase
from pybricks.tools import StopWatch

# --- user imports ---


# --- automatically managed helpers ---
def follow_for(
    drive: "DriveBase",
    sensor: "ColorSensor | ColorDistanceSensor",
    duration: "number[ms]",
    speed: "number[mm/s]",
    target: "number[%]",
    gain,
):
    """Follow a line edge for a set time, then brake.

    Target is the reflection at the edge. Reverse gain to follow the other edge.
    View the definition to inspect the timer, measurement and correction."""
    from pybricks.tools import StopWatch, wait

    # Measure the duration independently of each sensor reading.
    clock: "StopWatch" = StopWatch()
    try:
        while clock.time() < duration:
            error = sensor.reflection() - target
            drive.drive(speed, gain * error)
            wait(10)
    finally:
        drive.brake()


# --- user program ---

left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.B)
drive = DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)

sensor = ColorSensor(Port.C)

follow_for(drive, sensor, 1000, 100, 50, 2)

drive.straight(50)
print("Mission finished")
