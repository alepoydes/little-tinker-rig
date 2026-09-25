"""Drive-base and clock building blocks."""


def create_robot(
    name=drive,
    left_port: "Port" = Port.A,
    right_port: "Port" = Port.B,
    wheel: "mm" = 56,
    track: "mm" = 112,
):
    """Set up a two-wheel robot in one block.

    Choose different motor ports and measure the wheel diameter and axle track.
    The left motor is reversed for a mirrored two-wheel chassis.
    Expand the block to change motor directions or reuse its individual motors."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor
    from pybricks.robotics import DriveBase

    left_motor = Motor(left_port, Direction.COUNTERCLOCKWISE)
    right_motor = Motor(right_port)
    name = DriveBase(left_motor, right_motor, wheel_diameter=wheel, axle_track=track)


def create_drive(
    name=drive,
    left: "Motor" = left,
    right: "Motor" = right,
    wheel: "mm" = 56,
    track: "mm" = 112,
):
    """Create a two-wheel robot from the left and right motors."""
    from pybricks.robotics import DriveBase

    name = DriveBase(left, right, wheel_diameter=wheel, axle_track=track)


def drive(drive: "DriveBase" = drive, speed: "mm/s" = 180, turn: "deg/s" = 0):
    """Drive at the chosen speed and turn rate."""
    drive.drive(speed, turn)


def brake(drive: "DriveBase" = drive):
    """Brake both robot wheels."""
    drive.brake()


def straight(drive: "DriveBase" = drive, distance: "mm" = 200):
    """Drive a distance, then stop.

    Distance is in millimeters. Negative values drive backward.
    The next action waits for the movement to finish."""
    drive.straight(distance)


def turn(drive: "DriveBase" = drive, angle: "deg" = 90):
    """Turn the robot in place, then stop.

    Positive angles turn right; negative angles turn left.
    The next action waits for the movement to finish."""
    drive.turn(angle)


def drive_distance(drive: "DriveBase" = drive) -> "mm":
    """Read the distance traveled by the robot."""
    return drive.distance()


def drive_angle(drive: "DriveBase" = drive) -> "deg":
    """Read the robot's turn angle."""
    return drive.angle()


def create_clock(name=clock):
    """Create a stopwatch to measure time."""
    from pybricks.tools import StopWatch

    name = StopWatch()


def elapsed(clock: "StopWatch" = clock) -> "ms":
    """Read elapsed milliseconds from the stopwatch."""
    return clock.time()


def reset_clock(clock: "StopWatch" = clock):
    """Restart the stopwatch."""
    clock.reset()


def drive_settings(
    drive: "DriveBase" = drive,
    speed: "mm/s" = 200,
    acceleration=400,
    turn_rate: "deg/s" = 90,
    turn_acceleration=180,
):
    """Set the speed and acceleration of finite robot moves.

    Straight acceleration is in mm/s²; turn acceleration is in deg/s².
    Continuous drive commands use their own speed and turn rate."""
    drive.settings(speed, acceleration, turn_rate, turn_acceleration)


def curve(drive: "DriveBase" = drive, radius: "mm" = 200, angle: "deg" = 90):
    """Drive along an arc, then stop.

    Positive radius curves right; negative radius curves left.
    Negative angle drives backward. Radius must not be zero."""
    drive.arc(radius, angle=angle)


def reset_drive(drive: "DriveBase" = drive):
    """Stop and reset the robot's distance and angle readings."""
    drive.reset()


def create_car(name=car, steering: "Motor" = steering, propulsion: "Motor" = motor):
    """Set up a car with a steering motor.

    Pybricks finds the steering endpoints automatically: use a mechanism with
    physical steering stops. Propulsion can also be a tuple of drive motors.
    Steering calibration is not modeled by the virtual hub."""
    from pybricks.robotics import Car

    name = Car(steering, propulsion)


def steer_car(car: "Car" = car, steering: "%" = 0):
    """Set car steering between -100 and 100 percent."""
    car.steer(steering)


def power_car(car: "Car" = car, power: "%" = 0):
    """Set car propulsion power; zero lets the car coast.

    Positive power drives forward and negative power drives backward.
    This is motor power, not a measured vehicle speed."""
    car.drive_power(power)
