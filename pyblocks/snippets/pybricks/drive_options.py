"""Drive options

Explicit device operations for studying complete robot programs."""

@inline_block(level="expert", icon="▶", color="action")
def drivebase_left_right_wheel_diameter_axle_track(
    left: "Motor" = left,
    right: "Motor" = right,
    wheel_diameter: "number[mm]" = 56,
    axle_track: "number[mm]" = 112,
) -> "DriveBase":
    """Create a drive base from two motors and its dimensions. Options: left, right, wheel_diameter, axle_track."""
    from pybricks.robotics import DriveBase

    return DriveBase(left, right, wheel_diameter, axle_track)


@inline_block(level="expert", icon="▶", color="action")
def drive_settings(drive: "DriveBase" = drive) -> "tuple":
    """Read or set drive speeds and accelerations."""
    return drive.settings()


@inline_block(level="expert", icon="▶", color="action")
def drive_settings_straight_speed_straight_acceleration(
    drive: "DriveBase" = drive,
    straight_speed: "number[mm/s]" = 200,
    straight_acceleration=500,
):
    """Read or set drive speeds and accelerations. Options: straight_speed, straight_acceleration."""
    drive.settings(straight_speed, straight_acceleration)


@inline_block(level="expert", icon="▶", color="action")
def drive_settings_saved(drive: "DriveBase" = drive, saved: "tuple" = settings):
    """Read or set drive speeds and accelerations. Options: saved."""
    drive.settings(*saved)


@inline_block(level="expert", icon="▶", color="action")
def drive_straight_distance_wait(
    drive: "DriveBase" = drive, distance: "number[mm]" = 100, wait: "bool" = True
):
    """Drive straight with explicit completion options. Options: distance, wait."""
    drive.straight(distance, wait=wait)


@inline_block(level="expert", icon="▶", color="action")
def drive_straight_distance_then(
    drive: "DriveBase" = drive, distance: "number[mm]" = 100, then: "Stop" = Stop.HOLD
):
    """Drive straight with explicit completion options. Options: distance, then."""
    from pybricks.parameters import Stop

    drive.straight(distance, then=then)


@inline_block(level="expert", icon="▶", color="action")
def drive_arc_radius_angle(
    drive: "DriveBase" = drive, radius: "number[mm]" = 200, angle: "number[deg]" = 90
):
    """Drive along an arc with the current Pybricks radius convention. Options: radius, angle."""
    drive.arc(radius, angle)


@inline_block(level="intermediate", icon="➜", color="action")
def coast_drive(drive: "DriveBase" = drive):
    """Release both wheels and let the robot coast."""
    drive.stop()


@inline_block(level="advanced", icon="➜", color="value")
def drive_from_motors(
    left: "Motor" = left,
    right: "Motor" = right,
    wheel: "number[mm]" = 56,
    track: "number[mm]" = 112,
) -> "DriveBase":
    """Build a drive base for a robot attribute or expression."""
    from pybricks.robotics import DriveBase

    return DriveBase(left, right, wheel_diameter=wheel, axle_track=track)


@inline_block(level="advanced", icon="⏱", color="value")
def clock_value() -> "StopWatch":
    """Create a stopwatch for an object attribute or expression."""
    from pybricks.tools import StopWatch

    return StopWatch()
