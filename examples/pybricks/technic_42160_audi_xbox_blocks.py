# Adapted from Pybricks Projects (MIT); see LICENSE.txt and catalog.json.
from pybricks.iodevices import XboxController
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor
from pybricks.robotics import Car

# Set up all devices.
front = Motor(Port.A, Direction.CLOCKWISE)
rear = Motor(Port.B, Direction.CLOCKWISE)
steer = Motor(Port.D, Direction.CLOCKWISE)
car = Car(steer, [front, rear])
controller = XboxController()


# The main program starts here.
while True:
    car.drive_power(controller.triggers()[1] - controller.triggers()[0])
    car.steer(controller.joystick_left()[0])
