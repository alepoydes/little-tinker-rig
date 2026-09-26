# Adapted from Pybricks Projects (MIT); see LICENSE.txt and catalog.json.
# LEGO 42109 configuration: https://pybricks.com/project/technic-42109-xbox/
from pybricks.iodevices import XboxController
from pybricks.parameters import Direction, Port
from pybricks.pupdevices import Motor
from pybricks.robotics import Car
from pybricks.tools import wait

# Car calibrates steering against the model's mechanical stops.
steering = Motor(Port.B, Direction.CLOCKWISE)
drive = Motor(Port.D, Direction.CLOCKWISE)
car = Car(steering, drive)

# Pair the controller before running. Press the hub button to stop.
controller = XboxController()

while True:
    # Left stick: steering. Right/left triggers: forward/reverse power.
    car.steer(controller.joystick_left()[0])
    car.drive_power(controller.triggers()[1] - controller.triggers()[0])
    wait(50)
