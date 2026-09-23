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
