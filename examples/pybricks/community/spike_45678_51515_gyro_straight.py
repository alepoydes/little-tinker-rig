# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/7-sensors/imu-drivingbase1.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.hubs import PrimeHub
from pybricks.parameters import Color, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

hub = PrimeHub()
left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B)
robot = DriveBase(left, right, 56, 112)

# Keep the robot still while the gyro calibrates.
while not hub.imu.ready():
    wait(50)
robot.use_gyro(True)
hub.display.text("GYRO ON")
wait(2000)

hub.light.on(Color.GREEN)
try:
    robot.straight(1000)
finally:
    robot.brake()
hub.light.on(Color.BLUE)
hub.display.text("DONE")
