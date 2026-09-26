# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-follow.py
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
target = 300  # Distance in millimeters.

try:
    while True:
        distance = sonar.distance()
        # 2000 means no valid measurement; do not chase a missing object.
        if distance == 2000:
            robot.brake()
        else:
            error = distance - target
            speed = max(-150, min(150, error * 0.5))
            robot.drive(speed, 0)
        hub.display.number(distance // 10)
        wait(50)
finally:
    robot.brake()
