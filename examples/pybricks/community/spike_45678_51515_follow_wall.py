# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/distance-wallfollow.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B)
sonar = UltrasonicSensor(Port.C)  # Face the wall on the robot's RIGHT.
robot = DriveBase(left, right, 56, 112)
target = 200

try:
    while True:
        distance = sonar.distance()
        if distance == 2000:
            robot.brake()
        else:
            # Positive turn rates steer toward a wall that is too far away.
            error = distance - target
            turn_rate = max(-90, min(90, error * 0.3))
            robot.drive(150, turn_rate)
        wait(10)
finally:
    robot.brake()
