"""Drive options

Explicit device operations for studying complete robot programs."""

__category__ = "movement"


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Use gyro steering",
    group=("Two-wheel drive bases",),
)
def drive_gyro(drive: "DriveBase" = drive, enabled: "bool" = True):
    """Use the hub gyro to maintain the driving heading."""
    drive.use_gyro(enabled)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Turn to heading",
    group=("Two-wheel drive bases",),
)
def turn_to_heading(drive: "DriveBase" = drive, heading: "number[deg]" = 90):
    """Turn to an absolute heading; requires firmware with absolute turns."""
    drive.turn(heading, absolute=True)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive_options/drive_from_motors",
    bindings={"wheel_diameter": "wheel", "axle_track": "track"},
    title="Drive base value",
)
def drivebase_left_right_wheel_diameter_axle_track(
    left: "Motor" = left,
    right: "Motor" = right,
    wheel_diameter: "number[mm]" = 56,
    axle_track: "number[mm]" = 112,
) -> "DriveBase":
    """Create a drive base from two motors and its dimensions. Options: left, right, wheel_diameter, axle_track."""
    from pybricks.robotics import DriveBase

    return DriveBase(left, right, wheel_diameter, axle_track)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    title="Drive settings",
    group=("Two-wheel drive bases",),
    readout=True,
)
def drive_settings(drive: "DriveBase" = drive) -> "tuple":
    """Read or set drive speeds and accelerations."""
    return drive.settings()


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive/drive_settings",
    variant="Straight movement settings",
    bindings={"straight_speed": "speed", "straight_acceleration": "acceleration"},
    title="Set drive speeds",
)
def drive_settings_straight_speed_straight_acceleration(
    drive: "DriveBase" = drive,
    straight_speed: "number[mm/s]" = 200,
    straight_acceleration=500,
):
    """Read or set drive speeds and accelerations. Options: straight_speed, straight_acceleration."""
    drive.settings(straight_speed, straight_acceleration)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive/drive_settings",
    variant="Restore saved settings",
    title="Set drive speeds",
)
def drive_settings_saved(drive: "DriveBase" = drive, saved: "tuple" = settings):
    """Read or set drive speeds and accelerations. Options: saved."""
    drive.settings(*saved)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive/straight",
    variant="Wait or continue immediately",
    advanced=("wait",),
    title="Drive straight",
)
def drive_straight_distance_wait(
    drive: "DriveBase" = drive, distance: "number[mm]" = 100, wait: "bool" = True
):
    """Drive straight with explicit completion options. Options: distance, wait."""
    drive.straight(distance, wait=wait)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive/straight",
    variant="Choose stop behavior",
    advanced=("then",),
    title="Drive straight",
)
def drive_straight_distance_then(
    drive: "DriveBase" = drive, distance: "number[mm]" = 100, then: "Stop" = Stop.HOLD
):
    """Drive straight with explicit completion options. Options: distance, then."""
    from pybricks.parameters import Stop

    drive.straight(distance, then=then)


@inline_block(
    level="expert",
    icon="▶",
    color="action",
    family="pybricks/drive/curve",
    title="Drive an arc",
)
def drive_arc_radius_angle(
    drive: "DriveBase" = drive, radius: "number[mm]" = 200, angle: "number[deg]" = 90
):
    """Drive along an arc with the current Pybricks radius convention. Options: radius, angle."""
    drive.arc(radius, angle)


@inline_block(
    level="intermediate",
    icon="➜",
    color="action",
    family="pybricks/drive/brake",
    variant="Coast",
    title="Stop drive base",
)
def coast_drive(drive: "DriveBase" = drive):
    """Release both wheels and let the robot coast."""
    drive.stop()


@inline_block(
    level="advanced",
    icon="➜",
    color="value",
    variant="Named dimensions",
    title="Drive base value",
    group=("Two-wheel drive bases",),
)
def drive_from_motors(
    left: "Motor" = left,
    right: "Motor" = right,
    wheel: "number[mm]" = 56,
    track: "number[mm]" = 112,
) -> "DriveBase":
    """Create a drive base value."""
    from pybricks.robotics import DriveBase

    return DriveBase(left, right, wheel_diameter=wheel, axle_track=track)


@inline_block(
    level="advanced",
    icon="⏱",
    color="value",
    category="input",
    title="Stopwatch value",
    group=("Time",),
)
def clock_value() -> "StopWatch":
    """Create a stopwatch for an object attribute or expression."""
    from pybricks.tools import StopWatch

    return StopWatch()
