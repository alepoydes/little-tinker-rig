# Adapted from YavuzSelimKolbasar (MIT).
# Source: https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/DrivingBaseXboxController.py
# License: licenses/yavuzselimkolbasar.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.iodevices import XboxController
from pybricks.parameters import Button, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

left = Motor(Port.C, Direction.CLOCKWISE)
right = Motor(Port.D, Direction.COUNTERCLOCKWISE)
arm = Motor(Port.E, Direction.CLOCKWISE)
# Place the arm at its raised position before starting; this is its zero.
arm.reset_angle(0)
xbox = XboxController()
deadzone = 80
power_limit = 80

try:
    while True:
        buttons = xbox.buttons.pressed()
        if Button.B in buttons:
            break
        lt, rt = xbox.triggers()
        horizontal, vertical = xbox.joystick_left()
        if abs(horizontal) < deadzone:
            horizontal = 0
        throttle = rt - lt
        steering = horizontal * 0.8
        left_power = throttle - steering
        right_power = throttle + steering
        # Normalize the pair to preserve the turn ratio within the power limit.
        scale = power_limit / max(100, abs(left_power), abs(right_power))
        left.dc(left_power * scale)
        right.dc(right_power * scale)
        arm.run_target(300, -90 if Button.A in buttons else 0, wait=False)
        wait(50)
finally:
    left.brake()
    right.brake()
    arm.brake()
