"""Motor actions and values for Pybricks hubs; parsed as static templates."""

# Homing adapted from Pybricks Projects (MIT); see the upstream copyright and
# permission notice in examples/pybricks/LICENSE.txt.


def create_motor(name=motor, port: "Port" = Port.A):
    """Connect a motor to a hub port.

    Choose a port and an unquoted motor name, such as left_motor.
    Available ports depend on the hub model."""
    from pybricks.parameters import Port
    from pybricks.pupdevices import Motor

    name = Motor(port)


def create_oriented_motor(
    name=motor,
    port: "Port" = Port.A,
    direction: "Direction" = Direction.COUNTERCLOCKWISE,
):
    """Connect a motor and choose its positive direction."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    name = Motor(port, direction)


def run_motor(motor: "Motor" = motor, speed: "deg/s" = 500):
    """Run a motor at a chosen speed.

    Speed is in degrees per second. Negative values reverse direction.
    The motor keeps running until another command stops or changes it."""
    motor.run(speed)


def stop_motor(motor: "Motor" = motor):
    """Stop a motor with braking."""
    motor.brake()


def turn_motor(motor: "Motor" = motor, angle: "deg" = 90, speed: "deg/s" = 300):
    """Turn a motor through an angle and wait until it finishes."""
    motor.run_angle(speed, angle)


def motor_target(motor: "Motor" = motor, angle: "deg" = 0, speed: "deg/s" = 300):
    """Turn the motor to a target position and wait until it finishes."""
    motor.run_target(speed, angle)


def motor_time(motor: "Motor" = motor, duration: "ms" = 1000, speed: "deg/s" = 300):
    """Run the motor for a set time, then stop."""
    motor.run_time(speed, duration)


def reset_motor_angle(motor: "Motor" = motor, angle: "deg" = 0):
    """Set the angle reading at the current motor position."""
    motor.reset_angle(angle)


def motor_angle(motor: "Motor" = motor) -> "deg":
    """Read the current motor angle."""
    return motor.angle()


def motor_speed(motor: "Motor" = motor) -> "deg/s":
    """Read the current motor speed."""
    return motor.speed()


def motor_power(motor: "Motor" = motor, power: "%" = 0):
    """Set raw motor power from -100% to 100%.

    Power is a duty cycle, not regulated speed. Load changes the actual speed."""
    motor.dc(power)


def create_profiled_motor(
    name=motor,
    port: "Port" = Port.A,
    direction: "Direction" = Direction.COUNTERCLOCKWISE,
    tolerance: "deg" = 360,
):
    """Connect a motor with a position tolerance profile.

    A larger tolerance trades precision for smoother motion. Virtual hubs do
    not model this controller profile."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor

    name = Motor(port, direction, profile=tolerance)


def acceleration(motor: "Motor" = motor, acceleration: "deg/s²" = 1000):
    """Set the motor acceleration limit.

    This changes how quickly regulated motion starts and stops on a real motor."""
    motor.control.limits(acceleration=acceleration)


def coast_motor(motor: "Motor" = motor):
    """Release a motor and let it coast."""
    motor.stop()


def target_background(motor: "Motor" = motor, angle: "deg" = 0, speed: "deg/s" = 300):
    """Start moving to a target without waiting.

    The following actions run while the motor moves. A new command replaces
    the previous target."""
    motor.run_target(speed, angle, wait=False)


def target_coast(motor: "Motor" = motor, angle: "deg" = 0, speed: "deg/s" = 300):
    """Move to a target, then release the motor."""
    from pybricks.parameters import Stop

    motor.run_target(speed, angle, then=Stop.COAST)


def until_stalled(motor: "Motor" = motor, speed: "deg/s" = 100) -> "deg":
    """Run until the motor stalls and read its final angle.

    Requires a mechanism with a physical stop. The normal motor power limit
    applies; use limited homing when the mechanism needs reduced power."""
    return motor.run_until_stalled(speed)


def stall_hold(motor: "Motor" = motor, speed: "deg/s" = 100) -> "deg":
    """Run to a mechanical stop, hold, and read the angle."""
    from pybricks.parameters import Stop

    return motor.run_until_stalled(speed, then=Stop.HOLD)


def stall_limited(
    motor: "Motor" = motor, speed: "deg/s" = -100, power: "%" = 30
) -> "deg":
    """Run to a mechanical stop with limited power and read the angle."""
    return motor.run_until_stalled(speed, duty_limit=power)


def home_motor(motor: "Motor" = motor, speed: "deg/s" = -100, power: "%" = 30):
    """Find a mechanical stop with limited power and set zero there.

    Used by the BOOST arm and conveyor. Choose a speed direction toward the
    stop. Calibration requires a physical stop, not an arbitrary software zero."""
    motor.run_until_stalled(speed, duty_limit=power)
    motor.reset_angle(0)
