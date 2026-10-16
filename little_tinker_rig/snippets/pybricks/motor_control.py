"""Motor controller tuning

Explicit device operations for studying complete robot programs."""

__category__ = "movement"


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Read motor limits",
    group=("Individual motors", "Measurements"),
)
def motor_control_limits(motor: "Motor" = motor) -> "tuple":
    """Read or set motor speed, acceleration and torque limits."""
    return motor.control.limits()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/acceleration",
    variant="Speed, acceleration and torque",
    title="Set motor limits",
)
def motor_control_limits_speed_acceleration_torque(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    acceleration: "number[deg/s²] | tuple" = 1000,
    torque=100,
):
    """Read or set motor speed, acceleration and torque limits. Options: speed, acceleration, torque."""
    motor.control.limits(speed, acceleration, torque)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Read motor tolerances",
    group=("Individual motors", "Measurements"),
)
def motor_control_target_tolerances(motor: "Motor" = motor) -> "tuple":
    """Read or set motor completion tolerances."""
    return motor.control.target_tolerances()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Set motor tolerances",
    group=("Individual motors", "Control tuning"),
)
def motor_control_target_tolerances_speed_position(
    motor: "Motor" = motor, speed: "number[deg/s]" = 300, position: "number[deg]" = 10
):
    """Read or set motor completion tolerances. Options: speed, position."""
    motor.control.target_tolerances(speed, position)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/acceleration",
    variant="Restore saved limits",
    title="Set motor limits",
)
def motor_control_limits_saved(motor: "Motor" = motor, saved: "tuple" = settings):
    """Read or set motor speed, acceleration and torque limits. Options: saved."""
    motor.control.limits(*saved)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Read PID gains",
    group=("Individual motors", "Measurements"),
)
def motor_control_pid(motor: "Motor" = motor) -> "tuple":
    """Read or tune motor PID gains."""
    return motor.control.pid()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/acceleration",
    variant="Speed",
    title="Set motor limits",
)
def motor_control_limits_speed(motor: "Motor" = motor, speed: "number[deg/s]" = 300):
    """Read or set motor speed, acceleration and torque limits. Options: speed."""
    motor.control.limits(speed=speed)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Set PID gains",
    group=("Individual motors", "Control tuning"),
)
def motor_control_pid_kp_ki(motor: "Motor" = motor, kp=1000, ki=0):
    """Read or tune motor PID gains. Options: kp, ki."""
    motor.control.pid(kp=kp, ki=ki)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/motors/acceleration",
    variant="Speed and acceleration",
    title="Set motor limits",
)
def motor_control_limits_speed_acceleration(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    acceleration: "number[deg/s²] | tuple" = 1000,
):
    """Read or set motor speed, acceleration and torque limits. Options: speed, acceleration."""
    motor.control.limits(speed=speed, acceleration=acceleration)
