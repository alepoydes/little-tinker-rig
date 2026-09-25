"""Beginner: use BOOST's built-in motor A and color/distance sensor D."""

from pybricks.parameters import Color, Port
from pybricks.pupdevices import ColorDistanceSensor, Motor
from pybricks.tools import wait

motor = Motor(Port.A)
sensor = ColorDistanceSensor(Port.D)
while sensor.color() != Color.WHITE:
    wait(20)
motor.run_angle(300, 90)
wait(250)
motor.run_angle(300, -90)
print("Sequence finished")
