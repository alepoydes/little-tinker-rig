"""Remote control

LEGO Powered Up remote control; no host protocol or event framework."""

__category__ = "input"

# Steering calibration adapted from Pybricks Projects (MIT); see the upstream
# copyright and permission notice in examples/pybricks/LICENSE.txt.


@block(
    level="beginner",
    icon="▶",
    color="action",
    category="movement",
    title="Drive with remote",
    group=("Two-wheel drive bases",),
)
def remote_drive(
    drive: "DriveBase" = drive, speed: "number[mm/s]" = 150, turn: "number[deg/s]" = 90
):
    """Drive with a LEGO remote until its center button is pressed.

    Turn on the remote first. Left +/- controls forward/backward; right +/- turns.
    Releasing buttons brakes. The center button ends this block so the next
    action can run. A connection error also brakes before propagating."""
    from pybricks.parameters import Button
    from pybricks.pupdevices import Remote
    from pybricks.tools import wait

    drive.brake()
    controller: "Remote" = Remote()
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


@inline_block(
    level="advanced",
    icon="▣",
    color="state",
    names=("name",),
    title="Connect LEGO remote",
    group=("Buttons and controllers", "LEGO remote"),
)
def create_remote(name=remote):
    """Connect a LEGO Powered Up remote for your own control loop."""
    from pybricks.pupdevices import Remote

    name: "Remote" = Remote()


@inline_block(
    level="advanced",
    icon="＝",
    color="value",
    title="Remote button pressed",
    group=("Buttons and controllers", "LEGO remote"),
)
def remote_pressed(
    remote: "Remote" = remote, button: "Button" = Button.LEFT_PLUS
) -> "bool":
    """Check a LEGO remote button in your own control loop."""
    from pybricks.parameters import Button

    return button in remote.buttons.pressed()


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    title="Remote buttons",
    group=("Buttons and controllers", "LEGO remote"),
)
def buttons(remote: "Remote" = remote) -> "set":
    """Read all pressed remote buttons once.

    Save the result to make several decisions using the same input sample."""
    return remote.buttons.pressed()


@block(
    level="intermediate",
    icon="▣",
    color="state",
    category="movement",
    title="Centre steering",
    group=("Steering chassis",),
)
def center_steering(steering: "Motor" = steer, speed: "number[deg/s]" = 200):
    """Find both steering stops and start returning to the center.

    The midpoint is measured, not assumed. Returning to zero does not wait;
    subsequent remote commands can immediately replace that target."""
    from pybricks.parameters import Stop

    left_end = steering.run_until_stalled(-speed, then=Stop.HOLD)
    right_end = steering.run_until_stalled(speed, then=Stop.HOLD)
    steering.reset_angle((right_end - left_end) / 2)
    steering.run_target(speed, 0, wait=False)


@inline_block(
    level="advanced",
    icon="▶",
    color="action",
    category="output",
    title="Set remote light",
    group=("Status lights",),
)
def remote_light(remote: "Remote" = remote, color: "Color" = Color.GREEN):
    """Set the remote light to show the selected driving mode."""
    from pybricks.parameters import Color

    remote.light.on(color)
