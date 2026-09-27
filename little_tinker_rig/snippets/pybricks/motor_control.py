"""Motor controller tuning

Explicit device operations for studying complete robot programs."""

@inline_block(level="expert", icon="▶", color="action")
def motor_control_limits(motor: "Motor" = motor) -> "tuple":
    """Read or set motor speed, acceleration and torque limits."""
    return motor.control.limits()


@inline_block(level="expert", icon="▶", color="action")
def motor_control_limits_speed_acceleration_torque(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    acceleration: "number[deg/s²] | tuple" = 1000,
    torque=100,
):
    """Read or set motor speed, acceleration and torque limits. Options: speed, acceleration, torque."""
    motor.control.limits(speed, acceleration, torque)


@inline_block(level="expert", icon="▶", color="action")
def motor_control_target_tolerances(motor: "Motor" = motor) -> "tuple":
    """Read or set motor completion tolerances."""
    return motor.control.target_tolerances()


@inline_block(level="expert", icon="▶", color="action")
def motor_control_target_tolerances_speed_position(
    motor: "Motor" = motor, speed: "number[deg/s]" = 300, position: "number[deg]" = 10
):
    """Read or set motor completion tolerances. Options: speed, position."""
    motor.control.target_tolerances(speed, position)


@inline_block(level="expert", icon="▶", color="action")
def motor_control_limits_saved(motor: "Motor" = motor, saved: "tuple" = settings):
    """Read or set motor speed, acceleration and torque limits. Options: saved."""
    motor.control.limits(*saved)


@inline_block(level="expert", icon="▶", color="action")
def motor_control_pid(motor: "Motor" = motor) -> "tuple":
    """Read or tune motor PID gains."""
    return motor.control.pid()


@inline_block(level="expert", icon="▶", color="action")
def motor_control_limits_speed(motor: "Motor" = motor, speed: "number[deg/s]" = 300):
    """Read or set motor speed, acceleration and torque limits. Options: speed."""
    motor.control.limits(speed=speed)


@inline_block(level="expert", icon="▶", color="action")
def motor_control_pid_kp_ki(motor: "Motor" = motor, kp=1000, ki=0):
    """Read or tune motor PID gains. Options: kp, ki."""
    motor.control.pid(kp=kp, ki=ki)


@inline_block(level="expert", icon="▶", color="action")
def motor_control_limits_speed_acceleration(
    motor: "Motor" = motor,
    speed: "number[deg/s]" = 300,
    acceleration: "number[deg/s²] | tuple" = 1000,
):
    """Read or set motor speed, acceleration and torque limits. Options: speed, acceleration."""
    motor.control.limits(speed=speed, acceleration=acceleration)
