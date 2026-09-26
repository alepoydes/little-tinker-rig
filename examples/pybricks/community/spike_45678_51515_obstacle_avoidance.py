# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-avoid.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.hubs import PrimeHub
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

hub = PrimeHub()
left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B)
sonar = UltrasonicSensor(Port.C)  # Face forward.
robot = DriveBase(left, right, 56, 112)

try:
    while True:
        if sonar.distance() < 300:
            robot.straight(-100)
            robot.turn(90)
            hub.speaker.beep(800, 100)
        else:
            robot.drive(150, 0)
        wait(50)
finally:
    robot.brake()
