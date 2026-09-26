# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/color-stopatcolor.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.hubs import PrimeHub
from pybricks.parameters import Color, Direction, Icon, Port
from pybricks.pupdevices import ColorSensor, Motor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

hub = PrimeHub()
left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B)
sensor = ColorSensor(Port.C)  # Face down, close to the mat.
robot = DriveBase(left, right, 56, 112)

try:
    robot.drive(200, 0)
    hub.display.icon(Icon.ARROW_RIGHT)
    while sensor.color() != Color.RED:
        wait(10)
finally:
    robot.brake()

hub.display.icon(Icon.PAUSE)
hub.speaker.beep(600, 300)
print("Red detected!")
