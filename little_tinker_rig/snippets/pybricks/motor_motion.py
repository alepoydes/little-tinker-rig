"""Motor motion options

Explicit device operations for studying complete robot programs."""

__category__ = "movement"


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motor_motion/geared_motor",
    variant="Port",
)
def motor_port(port: "Port" = Port.A) -> "Motor":
    """Create a motor from a port, with optional direction or gears. Options: port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    return Motor(port)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motor_motion/geared_motor",
    variant="Gear list",
    advanced=("direction", "gears"),
)
def motor_port_direction_gears(
    port: "Port" = Port.A, direction: "Direction" = Direction.CLOCKWISE, gears=[12, 36]
) -> "Motor":
    """Create a motor from a port, with optional direction or gears. Options: port, direction, gears."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    return Motor(port, direction, gears=gears)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motor_motion/geared_motor",
    variant="Positive direction",
    advanced=("direction",),
)
def motor_port_direction(
    port: "Port" = Port.A, direction: "Direction" = Direction.CLOCKWISE
) -> "Motor":
    """Create a motor from a port, with optional direction or gears. Options: port, direction."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    return Motor(port, direction)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/turn_motor",
    variant="Wait setting",
    bindings={"rotation_angle": "angle"},
    advanced=("wait",),
)
def motor_run_angle_speed_rotation_angle_wait(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    rotation_angle: "number[deg]" = 90,
    wait: "bool" = True,
):
    """Turn a motor through an angle with explicit motion options. Options: speed, rotation_angle, wait."""
    motor.run_angle(speed, rotation_angle, wait=wait)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/turn_motor",
    variant="Completion settings",
    bindings={"rotation_angle": "angle"},
    advanced=("then", "wait"),
)
def motor_run_angle_speed_rotation_angle_then_wait(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    rotation_angle: "number[deg]" = 90,
    then: "Stop" = Stop.HOLD,
    wait: "bool" = True,
):
    """Turn a motor through an angle with explicit motion options. Options: speed, rotation_angle, then, wait."""
    from pybricks.parameters import Stop

    motor.run_angle(speed, rotation_angle, then=then, wait=wait)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/motor_target",
    variant="Completion settings",
    bindings={"target_angle": "angle"},
    advanced=("wait", "then"),
)
def motor_run_target_speed_target_angle_wait_then(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    target_angle: "number[deg]" = 0,
    wait: "bool" = True,
    then: "Stop" = Stop.HOLD,
):
    """Move a motor to an angle with explicit motion options. Options: speed, target_angle, wait, then."""
    from pybricks.parameters import Stop

    motor.run_target(speed, target_angle, wait=wait, then=then)


@inline_block(level="expert", icon="▶", color="action")
def motor_reset_angle(motor: "Motor" = motor):
    """Reset the motor to its absolute encoder angle."""
    motor.reset_angle()


@inline_block(level="expert", icon="▶", color="action")
def motor_track_target_target_angle(
    motor: "Motor" = motor, target_angle: "number[deg]" = 0
):
    """Continuously track a changing target angle. Options: target_angle."""
    motor.track_target(target_angle)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/motor_time",
    variant="Wait setting",
    bindings={"time": "duration"},
    advanced=("wait",),
)
def motor_run_time_speed_time_wait(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    time: "number[ms]" = 500,
    wait: "bool" = True,
):
    """Run a motor for a time with explicit motion options. Options: speed, time, wait."""
    motor.run_time(speed, time, wait=wait)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/stop_motor",
    variant="Hold position",
)
def motor_hold(motor: "Motor" = motor):
    """Hold the motor at its current angle."""
    motor.hold()


@inline_block(level="expert", icon="▶", color="action")
def motor_done(motor: "Motor | DriveBase" = motor) -> "bool":
    """Check whether the motor has finished its movement."""
    return motor.done()


@inline_block(level="expert", icon="▶", color="action")
def motor_stalled(motor: "Motor | DriveBase" = motor) -> "bool":
    """Check whether the motor cannot follow its commanded motion."""
    return motor.stalled()


@inline_block(level="expert", icon="▶", color="action")
def motor_load(motor: "Motor" = motor) -> "number":
    """Read estimated motor load in millinewton meters."""
    return motor.load()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/until_stalled",
    variant="Stop and power settings",
    advanced=("then",),
)
def motor_run_until_stalled_speed_then_duty_limit(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    then: "Stop" = Stop.HOLD,
    duty_limit: "number[%]" = 30,
) -> "number[deg]":
    """Run to a mechanical stop and read the resulting angle. Options: speed, then, duty_limit."""
    from pybricks.parameters import Stop

    return motor.run_until_stalled(speed, then=then, duty_limit=duty_limit)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/motor_target",
    variant="Stop setting",
    bindings={"target_angle": "angle"},
    advanced=("then",),
)
def motor_run_target_speed_target_angle_then(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    target_angle: "number[deg]" = 0,
    then: "Stop" = Stop.HOLD,
):
    """Move a motor to an angle with explicit motion options. Options: speed, target_angle, then."""
    from pybricks.parameters import Stop

    motor.run_target(speed, target_angle, then=then)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/motor_target",
    bindings={"target_angle": "angle"},
    advanced=("then", "wait"),
)
def motor_run_target_speed_target_angle_then_wait(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    target_angle: "number[deg]" = 0,
    then: "Stop" = Stop.HOLD,
    wait: "bool" = True,
):
    """Move a motor to an angle with explicit motion options. Options: speed, target_angle, then, wait."""
    from pybricks.parameters import Stop

    motor.run_target(speed, target_angle, then=then, wait=wait)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/until_stalled",
    variant="Stop setting",
    advanced=("then",),
)
def motor_run_until_stalled_speed_then(
    motor: "Motor" = motor, speed: "number[deg/s]" = 300, then: "Stop" = Stop.HOLD
) -> "number[deg]":
    """Run to a mechanical stop and read the resulting angle. Options: speed, then."""
    from pybricks.parameters import Stop

    return motor.run_until_stalled(speed, then)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motor_motion/geared_motor",
    variant="Position profile",
    advanced=("direction", "profile"),
)
def motor_port_direction_profile(
    port: "Port" = Port.A,
    direction: "Direction" = Direction.CLOCKWISE,
    profile: "number[deg]" = 360,
) -> "Motor":
    """Create a motor from a port, with optional direction or gears. Options: port, direction, profile."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    return Motor(port, direction, profile=profile)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/turn_motor",
    variant="Stop setting",
    bindings={"rotation_angle": "angle"},
    advanced=("then",),
)
def motor_run_angle_speed_rotation_angle_then(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    rotation_angle: "number[deg]" = 90,
    then: "Stop" = Stop.HOLD,
):
    """Turn a motor through an angle with explicit motion options. Options: speed, rotation_angle, then."""
    from pybricks.parameters import Stop

    motor.run_angle(speed, rotation_angle, then=then)


@inline_block(level="expert", icon="▶", color="action")
def dcmotor_port(port: "Port" = Port.A) -> "DCMotor":
    """Create a motor controlled by raw power. Options: port."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import DCMotor

    return DCMotor(port)


@inline_block(
    level="advanced",
    icon="⚙",
    color="value",
    variant="Gear train",
    advanced=("direction", "gears"),
)
def geared_motor(
    port: "Port" = Port.A, direction: "Direction" = Direction.CLOCKWISE, gears=None
) -> "Motor":
    """Create a motor value.

    Connect a motor and account for its gears in every movement."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    return Motor(port, direction, gears)
