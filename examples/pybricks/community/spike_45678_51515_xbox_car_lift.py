# Adapted from YavuzSelimKolbasar (MIT).
# Source: https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/Remote-Car.py
# License: licenses/yavuzselimkolbasar.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.iodevices import XboxController
from pybricks.parameters import Button, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

steering = Motor(Port.B, Direction.CLOCKWISE)
drive = Motor(Port.D, Direction.CLOCKWISE)
lift = Motor(Port.E, Direction.CLOCKWISE)
# Center the front wheels before starting; there is no automatic homing.
steering.reset_angle(0)
xbox = XboxController()
arm_mode = False
previous_buttons = set()

try:
    while True:
        buttons = xbox.buttons.pressed()
        if Button.B in buttons:
            break
        if Button.Y in buttons and Button.Y not in previous_buttons:
            arm_mode = not arm_mode
            print("Lift mode" if arm_mode else "Car mode")
        previous_buttons = buttons
        horizontal, vertical = xbox.joystick_left()
        lt, rt = xbox.triggers()
        if arm_mode:
            drive.brake()
            steering.brake()
            lift.dc(vertical * 0.4)
        else:
            lift.brake()
            steering.run_target(600, horizontal * 0.9, wait=False)
            drive.dc(rt - lt)
        wait(50)
finally:
    drive.brake()
    steering.brake()
    lift.brake()
