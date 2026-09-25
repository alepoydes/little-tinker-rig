"""A finite line-following mission: motors A/B, SPIKE color sensor C."""

# --- automatically managed imports ---
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import ColorSensor, Motor
from pybricks.robotics import DriveBase
from pybricks.tools import StopWatch, wait

# --- user imports ---

left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.B)
drive = DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)

sensor = ColorSensor(Port.C)

clock = StopWatch()
try:
    while clock.time() < 1000:
        error = sensor.reflection() - 50
        drive.drive(100, 2 * error)
        wait(10)
finally:
    drive.brake()

drive.straight(50)
print("Mission finished")
