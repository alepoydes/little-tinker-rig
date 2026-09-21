"""Copy the Controller helper beside this file before uploading; see doc/robotics.md."""

from pyblocks_controller import Controller
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B)
drive = DriveBase(left, right, wheel_diameter=56, axle_track=114)
controller = Controller()

while True:
    controller.update()
    drive.drive(controller.left_y * 300, controller.left_x * 120)
    wait(20)
