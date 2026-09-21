"""Pybricks hub: turn the motor connected to port A by 90 degrees."""

from pybricks.parameters import Port
from pybricks.pupdevices import Motor

motor = Motor(Port.A)
motor.run_angle(300, 90)
motor.brake()
