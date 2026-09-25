"""Standard: a reusable movement, list, counted loop and measured distance.

All virtual models: motors A and B. For a physical chassis, configure motor
directions and measure wheel diameter and axle track before running.
"""

from pybricks.parameters import Port
from pybricks.pupdevices import Motor
from pybricks.robotics import DriveBase

left = Motor(Port.A)
right = Motor(Port.B)
drive = DriveBase(left, right, wheel_diameter=56, axle_track=112)
distances = list((20, 30, 40))


def drive_leg(distance):
    if distance > 0:
        drive.straight(distance)
        drive.turn(90)


for i in range(len(distances)):
    drive_leg(distances[i])
drive.brake()
print(round(drive.distance()), round(drive.angle()))
