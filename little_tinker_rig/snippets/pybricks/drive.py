"""Drive bases and clocks

Drive-base and clock building blocks."""

__category__ = "movement"


@inline_block(
    level="beginner",
    icon="➜",
    color="state",
    names=("name",),
    title="Set up drive base",
    group=("Two-wheel drive bases",),
)
def create_robot(
    name=drive,
    left_port: "Port" = Port.A,
    right_port: "Port" = Port.B,
    wheel: "number[mm]" = 56,
    track: "number[mm]" = 112,
):
    """Set up a two-wheel robot in one block.

    Choose different motor ports and measure the wheel diameter and axle track.
    The left motor is reversed for a mirrored two-wheel chassis.
    Expand the block to change motor directions or reuse its individual motors."""
    from pybricks.parameters import Direction, Port
    from pybricks.pupdevices import Motor
    from pybricks.robotics import DriveBase

    left_motor: "Motor" = Motor(left_port, Direction.COUNTERCLOCKWISE)
    right_motor: "Motor" = Motor(right_port)
    name: "DriveBase" = DriveBase(
        left_motor, right_motor, wheel_diameter=wheel, axle_track=track
    )


@inline_block(
    level="intermediate",
    icon="➜",
    color="state",
    names=("name",),
    title="Create drive base",
    group=("Two-wheel drive bases",),
)
def create_drive(
    name=drive,
    left: "Motor" = left,
    right: "Motor" = right,
    wheel: "number[mm]" = 56,
    track: "number[mm]" = 112,
):
    """Create a two-wheel robot from the left and right motors."""
    from pybricks.robotics import DriveBase

    name: "DriveBase" = DriveBase(left, right, wheel_diameter=wheel, axle_track=track)


@inline_block(
    level="intermediate",
    icon="➜",
    color="action",
    title="Drive continuously",
    group=("Two-wheel drive bases",),
)
def drive(
    drive: "DriveBase" = drive, speed: "number[mm/s]" = 180, turn: "number[deg/s]" = 0
):
    """Drive at the chosen speed and turn rate."""
    drive.drive(speed, turn)


@inline_block(
    level="beginner",
    icon="➜",
    color="action",
    variant="Brake",
    title="Stop drive base",
    group=("Two-wheel drive bases",),
)
def brake(drive: "DriveBase" = drive):
    """Stop both robot wheels.

    Brake both robot wheels."""
    drive.brake()


@inline_block(
    level="beginner",
    icon="➜",
    color="action",
    variant="Wait until finished",
    title="Drive straight",
    group=("Two-wheel drive bases",),
)
def straight(drive: "DriveBase" = drive, distance: "number[mm]" = 200):
    """Drive a measured distance.

    Drive a distance, then stop.

    Distance is in millimeters. Negative values drive backward.
    The next action waits for the movement to finish."""
    drive.straight(distance)


@inline_block(
    level="beginner",
    icon="➜",
    color="action",
    title="Turn drive base",
    group=("Two-wheel drive bases",),
)
def turn(drive: "DriveBase" = drive, angle: "number[deg]" = 90):
    """Turn the robot in place, then stop.

    Positive angles turn right; negative angles turn left.
    The next action waits for the movement to finish."""
    drive.turn(angle)


@inline_block(
    level="intermediate",
    icon="➜",
    color="action",
    title="Travelled distance",
    group=("Two-wheel drive bases",),
    readout=True,
)
def drive_distance(drive: "DriveBase" = drive) -> "number[mm]":
    """Read the distance traveled by the robot."""
    return drive.distance()


@inline_block(
    level="intermediate",
    icon="➜",
    color="action",
    title="Drive base angle",
    group=("Two-wheel drive bases",),
    readout=True,
)
def drive_angle(drive: "DriveBase" = drive) -> "number[deg]":
    """Read the robot's turn angle."""
    return drive.angle()


@inline_block(
    level="intermediate",
    icon="⏱",
    color="state",
    names=("name",),
    category="input",
    title="Create stopwatch",
    group=("Time",),
)
def create_clock(name=clock):
    """Create a stopwatch to measure time."""
    from pybricks.tools import StopWatch

    name: "StopWatch" = StopWatch()


@inline_block(
    level="intermediate",
    icon="⏱",
    color="action",
    category="input",
    title="Elapsed time",
    group=("Time",),
    readout=True,
)
def elapsed(clock: "StopWatch" = clock) -> "number[ms]":
    """Read elapsed milliseconds from the stopwatch."""
    return clock.time()


@inline_block(
    level="intermediate",
    icon="⏱",
    color="action",
    category="input",
    title="Reset stopwatch",
    group=("Time",),
)
def reset_clock(clock: "StopWatch" = clock):
    """Restart the stopwatch."""
    clock.reset()


@inline_block(
    level="advanced",
    icon="➜",
    color="action",
    variant="Speed and acceleration",
    advanced=("turn_acceleration",),
    title="Set drive speeds",
    group=("Two-wheel drive bases",),
)
def drive_settings(
    drive: "DriveBase" = drive,
    speed: "number[mm/s]" = 200,
    acceleration=400,
    turn_rate: "number[deg/s]" = 90,
    turn_acceleration=180,
):
    """Configure finite robot movements.

    Set the speed and acceleration of finite robot moves.

    Straight acceleration is in mm/s²; turn acceleration is in deg/s².
    Continuous drive commands use their own speed and turn rate."""
    drive.settings(speed, acceleration, turn_rate, turn_acceleration)


@inline_block(
    level="advanced",
    icon="➜",
    color="action",
    variant="Current arc convention",
    title="Drive an arc",
    group=("Two-wheel drive bases",),
)
def curve(
    drive: "DriveBase" = drive, radius: "number[mm]" = 200, angle: "number[deg]" = 90
):
    """Drive along an arc, then stop.

    Positive radius curves right; negative radius curves left.
    Negative angle drives backward. Radius must not be zero."""
    drive.arc(radius, angle=angle)


@inline_block(
    level="advanced",
    icon="➜",
    color="action",
    title="Reset odometry",
    group=("Two-wheel drive bases",),
)
def reset_drive(drive: "DriveBase" = drive):
    """Stop and reset the robot's distance and angle readings."""
    drive.reset()


@inline_block(
    level="advanced",
    icon="➜",
    color="state",
    names=("name",),
    title="Create steering car",
    group=("Steering chassis",),
)
def create_car(
    name=car, steering: "Motor" = steering, propulsion: "Motor | list | tuple" = motor
):
    """Set up a car with a steering motor.

    Pybricks finds the steering endpoints automatically: use a mechanism with
    physical steering stops. Propulsion can also be a tuple of drive motors.
    Steering calibration is not modeled by the virtual hub."""
    from pybricks.robotics import Car

    name: "Car" = Car(steering, propulsion)


@inline_block(
    level="advanced",
    icon="➜",
    color="action",
    title="Steer car",
    group=("Steering chassis",),
)
def steer_car(car: "Car" = car, steering: "number[%]" = 0):
    """Set car steering between -100 and 100 percent."""
    car.steer(steering)


@inline_block(
    level="advanced",
    icon="➜",
    color="action",
    title="Power car",
    group=("Steering chassis",),
)
def power_car(car: "Car" = car, power: "number[%]" = 0):
    """Set car propulsion power; zero lets the car coast.

    Positive power drives forward and negative power drives backward.
    This is motor power, not a measured vehicle speed."""
    car.drive_power(power)


@block(
    level="advanced",
    icon="➜",
    color="action",
    title="Drive arc (Pybricks 3)",
    group=("Two-wheel drive bases",),
)
def legacy_curve(
    drive: "DriveBase" = drive, radius: "number[mm]" = 200, angle: "number[deg]" = 90
):
    """Drive a curve using the Pybricks 3.x sign convention.

    Radius selects forward/backward travel; angle selects right/left turning.
    The helper translates these signs to the current arc API and evaluates each
    input once. Use this when adapting an older curve(radius, angle) program."""
    drive.arc(
        abs(radius) if radius * angle >= 0 else -abs(radius),
        abs(angle) if radius >= 0 else -abs(angle),
    )
