# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
from pybricks.parameters import Button, Direction, Port, Stop
from pybricks.pupdevices import Motor, Remote
from pybricks.tools import wait


# --- automatically managed helpers ---
def _pyblocks_pybricks_remote_center_steering_4b19cf12a3ec(
    steering: "Motor", speed: "number[deg/s]"
):
    """Find both steering stops and start returning to the center.

    The midpoint is measured, not assumed. Returning to zero does not wait;
    subsequent remote commands can immediately replace that target."""
    from pybricks.parameters import Stop

    left_end = steering.run_until_stalled(-speed, then=Stop.HOLD)
    right_end = steering.run_until_stalled(speed, then=Stop.HOLD)
    steering.reset_angle((right_end - left_end) / 2)
    steering.run_target(speed, 0, wait=False)


# --- user program ---

# Initialize the motors.
steer = Motor(Port.B)
front = Motor(Port.A, Direction.COUNTERCLOCKWISE)

# Lower the acceleration so the car starts and stops realistically.
front.control.limits(acceleration=1000)

# Connect to the remote.
remote = Remote()

_pyblocks_pybricks_remote_center_steering_4b19cf12a3ec(steer, 200)

# Now we can start driving!
while True:
    # Check which buttons are pressed.
    pressed = remote.buttons.pressed()

    # Choose the steer angle based on the right controls.
    steer_angle = 0
    if Button.RIGHT_MINUS in pressed:
        steer_angle -= 75
    if Button.RIGHT_PLUS in pressed:
        steer_angle += 75

    # Steer to the selected angle.
    steer.run_target(500, steer_angle, wait=False)

    # Choose the drive speed based on the left controls.
    drive_speed = 0
    if Button.LEFT_PLUS in pressed:
        drive_speed += 1000
    if Button.LEFT_MINUS in pressed:
        drive_speed -= 1000

    # Apply the selected speed.
    front.run(drive_speed)

    # Wait.
    wait(10)
