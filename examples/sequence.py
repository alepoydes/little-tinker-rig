"""Beginner: wait for white, turn a motor, pause, then turn it back.

Inventor/Prime or Technic: motor A and SPIKE color sensor C.
The virtual sensor sees white at reflection >= 50; black below 50.
"""

from pybricks.parameters import Color, Port
from pybricks.pupdevices import ColorSensor, Motor
from pybricks.tools import wait

motor = Motor(Port.A)
sensor = ColorSensor(Port.C)
while sensor.color() != Color.WHITE:
    wait(20)
motor.run_angle(300, 90)
wait(250)
motor.run_angle(300, -90)
print("Sequence finished")
