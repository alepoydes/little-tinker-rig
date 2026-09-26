# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
from pybricks.parameters import Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait


# --- automatically managed helpers ---
def _pyblocks_pybricks_lessons_conveyor_transfer_0a4e99628417(
    arm: "Motor",
    belt: "Motor",
    pickup: "number[deg]",
    destination: "number[deg]",
):
    """Pick up a conveyor part and place it at the assembly position.

    For the homed BOOST Auto Builder: belt positions are motor degrees.
    View the definition to study the lift, speeds, and two-second arm strokes."""
    from pybricks.tools import wait

    # Move the belt to the selected component.
    belt.run_target(200, pickup)

    # Grab the component, then lift it clear of the belt.
    arm.run_time(300, 2000)
    arm.run_target(300, 55)

    # Carry it to the assembly position and let the mechanism settle.
    belt.run_target(200, destination)
    wait(500)

    # Put the component down and lift the arm back up.
    arm.run_time(300, 2000)
    arm.run_target(300, 0)


def _pyblocks_pybricks_motors_home_motor_5ca9fab66554(
    motor: "Motor", speed: "number[deg/s]", power: "number[%]"
):
    """Find a mechanical stop with limited power and set zero there.

    Used by the BOOST arm and conveyor. Choose a speed direction toward the
    stop. Calibration requires a physical stop, not an arbitrary software zero."""
    motor.run_until_stalled(speed, duty_limit=power)
    motor.reset_angle(0)


# --- user program ---

# Initialize the arm motor
arm = Motor(Port.D)
_pyblocks_pybricks_motors_home_motor_5ca9fab66554(arm, -100, 30)

# Initialize the belt motor
belt = Motor(Port.B)
_pyblocks_pybricks_motors_home_motor_5ca9fab66554(belt, -100, 30)

# Component positions
FEET = 0
BELLY = 365
HEAD = 128
ARMS = 244
NECK = 521
BASE = 697

# Place all the elements
for element in (FEET, BELLY, ARMS, NECK, HEAD):

    _pyblocks_pybricks_lessons_conveyor_transfer_0a4e99628417(arm, belt, element, BASE)

# When we are done, eject the result
belt.run_target(200, FEET)
