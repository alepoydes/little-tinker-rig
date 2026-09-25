# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
"""
This program is for Tricky's Intro dance.

Follow the corresponding building instructions in the LEGO® MINDSTORMS®
Robot Inventor App.

Trigger Tricky to dance by placing something near its Distance Sensor.
"""

from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.robotics import DriveBase
from pybricks.tools import wait

# Configure the Drive Base and the Distance Sensor.
left_motor = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right_motor = Motor(Port.B)
drive_base = DriveBase(left_motor, right_motor, wheel_diameter=44, axle_track=88)

distance_sensor = UltrasonicSensor(Port.D)


# Turn the Distance Sensor lights off and on.
distance_sensor.lights.off()
wait(1000)
distance_sensor.lights.on(100)

# Tricky begins dancing/turning whenever the Distance Sensor detects
# something closer than 10 cm (100 mm).
while True:
    if distance_sensor.distance() < 100:
        drive_base.turn(360)
        drive_base.turn(-360)
    wait(10)
