# Adapted from Pybricks Projects (MIT); see LICENSE.txt and catalog.json.
"""
This program is for MVP's basic "Buggy" mode.

Follow the corresponding building instructions in the LEGO® MINDSTORMS®
Robot Inventor App.
"""

from pybricks.pupdevices import Motor
from pybricks.parameters import Direction, Port


class MVP:
    def __init__(self):
        self.steer_motor = Motor(Port.A)
        self.drive_motor = Motor(Port.B, Direction.COUNTERCLOCKWISE)

    def calibrate(self):
        self.steer_motor.run_target(1000, 0)


# Initialize mvp and straighten its steering.
mvp = MVP()
mvp.calibrate()

# Make mvp drive in a circle.
mvp.steer_motor.run_angle(350, 50)
mvp.drive_motor.run_angle(800, 16 * 360)
