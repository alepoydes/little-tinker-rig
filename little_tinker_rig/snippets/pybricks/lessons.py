"""Robot activities

Short complete behaviors implemented as ordinary Python functions."""

__category__ = "movement"

# Set activities adapted from Pybricks Projects, copyright 2018-2023 The Pybricks
# Authors (MIT). Full notice: examples/pybricks/LICENSE.txt, included in distributions.


@block(level="beginner", icon="◇", color="control")
def stop_at_line(
    drive: "DriveBase" = drive,
    sensor: "ColorSensor | ColorDistanceSensor" = sensor,
    threshold: "number[%]" = 30,
    speed: "number[mm/s]" = 100,
):
    """Drive until a dark line, then brake.

    Works with SPIKE and BOOST reflection sensors. If already on the line,
    the robot stays still. Stop cancels a wait for a line that never arrives."""
    from pybricks.tools import wait

    try:
        while sensor.reflection() > threshold:
            drive.drive(speed, 0)
            wait(20)
    finally:
        drive.brake()


@block(level="intermediate", icon="◇", color="control")
def stop_near_object(
    drive: "DriveBase" = drive,
    sensor: "UltrasonicSensor" = distance,
    distance: "number[mm]" = 100,
    speed: "number[mm/s]" = 100,
):
    """Drive until an ultrasonic obstacle, then brake.

    Distance is in millimeters. Use a relative threshold with the BOOST sensor
    instead; its distance reading is not measured in millimeters."""
    from pybricks.tools import wait

    try:
        while sensor.distance() > distance:
            drive.drive(speed, 0)
            wait(20)
    finally:
        drive.brake()


@block(level="beginner", icon="▣", color="state")
def follow_for(
    drive: "DriveBase" = drive,
    sensor: "ColorSensor | ColorDistanceSensor" = sensor,
    duration: "number[ms]" = 3000,
    speed: "number[mm/s]" = 100,
    target: "number[%]" = 50,
    gain=2,
):
    """Follow a line edge for a set time, then brake.

    Target is the reflection at the edge. Reverse gain to follow the other edge.
    View the definition to inspect the timer, measurement and correction."""
    from pybricks.tools import StopWatch, wait

    # Measure the duration independently of each sensor reading.
    clock: "StopWatch" = StopWatch()
    try:
        while clock.time() < duration:
            error = sensor.reflection() - target
            drive.drive(speed, gain * error)
            wait(10)
    finally:
        drive.brake()


@block(level="beginner", icon="▶", color="action")
def conveyor_transfer(
    arm: "Motor" = arm,
    belt: "Motor" = belt,
    pickup: "number[deg]" = 0,
    destination: "number[deg]" = 697,
):
    """Pick up a conveyor part and place it at the assembly position.

    For the homed BOOST Auto Builder: belt positions are motor degrees.
    View the definition to study the lift, speeds, and two-second arm strokes."""
    from pybricks.tools import wait

    # Move the belt to the selected component.
    belt.run_target(200, pickup)

    # Grab the component, then lift it clear of the belt.
    arm.run_time(300, 2000)
    arm.run_target(300, 55)

    # Carry it to the assembly position and let the mechanism settle.
    belt.run_target(200, destination)
    wait(500)

    # Put the component down and lift the arm back up.
    arm.run_time(300, 2000)
    arm.run_target(300, 0)


@block(level="beginner", icon="▶", color="action")
def draw_rectangle(
    horizontal: "Motor" = horizontal_motor,
    vertical: "Motor" = vertical_motor,
    width: "number[deg]" = 400,
    height: "number[deg]" = 100,
    speed: "number[deg/s]" = 1000,
):
    """Draw a rectangle with two motor axes and return to the start.

    Width and height are motor degrees, not millimeters. Motor gearing and the
    drawing mechanism determine the physical size."""
    # Trace four sides; reversing each axis returns to the starting position.
    horizontal.run_angle(speed, width)
    vertical.run_angle(speed, height)
    horizontal.run_angle(speed, -width)
    vertical.run_angle(speed, -height)


@block(level="beginner", icon="▶", color="action")
def dance_turns(drive: "DriveBase" = drive, angle: "number[deg]" = 360):
    """Turn one way and back, like Tricky's dance."""
    # Turn both ways to finish facing the original direction.
    drive.turn(angle)
    drive.turn(-angle)


@block(level="beginner", icon="⟳", color="loop")
def force_gripper(
    motor: "Motor" = motor,
    sensor: "ForceSensor" = force_sensor,
    speed: "number[deg/s]" = 1000,
):
    """Close a gripper while pressed; open to its stop when released.

    Repeats until the program is stopped. Opening waits for a mechanical stall,
    so a new press is handled after opening finishes. Requires physical stops."""
    while True:
        if sensor.pressed():
            motor.run(-speed)
        else:
            motor.run_until_stalled(speed)
