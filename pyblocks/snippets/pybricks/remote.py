"""LEGO Powered Up remote control; no host protocol or event framework."""

# Steering calibration adapted from Pybricks Projects (MIT); see the upstream
# copyright and permission notice in examples/pybricks/LICENSE.txt.


def remote_drive(drive: "DriveBase" = drive, speed: "mm/s" = 150, turn: "deg/s" = 90):
    """Drive with a LEGO remote until its center button is pressed.

    Turn on the remote first. Left +/- controls forward/backward; right +/- turns.
    Releasing buttons brakes. The center button ends this block so the next
    action can run. A connection error also brakes before propagating."""
    from pybricks.parameters import Button
    from pybricks.pupdevices import Remote
    from pybricks.tools import wait

    drive.brake()
    controller = Remote()
    try:
        while True:
            pressed = controller.buttons.pressed()
            if Button.CENTER in pressed:
                break
            forward = (Button.LEFT_PLUS in pressed) - (Button.LEFT_MINUS in pressed)
            steering = (Button.RIGHT_PLUS in pressed) - (Button.RIGHT_MINUS in pressed)
            if forward or steering:
                drive.drive(speed * forward, turn * steering)
            else:
                drive.brake()
            wait(20)
    finally:
        drive.brake()
        controller.disconnect()


def create_remote(name=remote):
    """Connect a LEGO Powered Up remote for your own control loop."""
    from pybricks.pupdevices import Remote

    name = Remote()


def remote_pressed(
    remote: "Remote" = remote, button: "Button" = Button.LEFT_PLUS
) -> "bool":
    """Check a LEGO remote button in your own control loop."""
    from pybricks.parameters import Button

    return button in remote.buttons.pressed()


def buttons(remote: "Remote" = remote) -> "set":
    """Read all pressed remote buttons once.

    Save the result to make several decisions using the same input sample."""
    return remote.buttons.pressed()


def center_steering(steering: "Motor" = steer, speed: "deg/s" = 200):
    """Find both steering stops and start returning to the center.

    The midpoint is measured, not assumed. Returning to zero does not wait;
    subsequent remote commands can immediately replace that target."""
    from pybricks.parameters import Stop

    left_end = steering.run_until_stalled(-speed, then=Stop.HOLD)
    right_end = steering.run_until_stalled(speed, then=Stop.HOLD)
    steering.reset_angle((right_end - left_end) / 2)
    steering.run_target(speed, 0, wait=False)
