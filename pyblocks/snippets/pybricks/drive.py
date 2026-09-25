"""Drive-base and clock building blocks."""


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
