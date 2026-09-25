"""Motor actions and values for Pybricks hubs; parsed as static templates."""


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
