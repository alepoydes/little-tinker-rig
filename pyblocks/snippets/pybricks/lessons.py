"""Short complete behaviors, recognizable and decomposable as ordinary Python."""


def stop_at_line(
    drive: "DriveBase" = drive,
    sensor: "ColorSensor | ColorDistanceSensor" = sensor,
    threshold: "%" = 30,
    speed: "mm/s" = 100,
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


def stop_near_object(
    drive: "DriveBase" = drive,
    sensor: "UltrasonicSensor" = distance,
    distance: "mm" = 100,
    speed: "mm/s" = 100,
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


def follow_for(
    drive: "DriveBase" = drive,
    sensor: "ColorSensor | ColorDistanceSensor" = sensor,
    duration: "ms" = 3000,
    speed: "mm/s" = 100,
    target: "%" = 50,
    gain=2,
):
    """Follow a line edge for a set time, then brake.

    Target is the reflection at the edge. Reverse gain to follow the other edge.
    Expand the block to inspect the timer, repeated measurement and correction."""
    from pybricks.tools import StopWatch, wait

    clock = StopWatch()
    try:
        while clock.time() < duration:
            error = sensor.reflection() - target
            drive.drive(speed, gain * error)
            wait(10)
    finally:
        drive.brake()
