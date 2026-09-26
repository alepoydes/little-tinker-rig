# Adapted from YavuzSelimKolbasar (MIT).
# Source: https://github.com/yavuzselimkolbasar/Pybricks-Lego-Spike/blob/79199995d335f8eaeaf262079960376dbf2c5b97/Boxing.py
# License: licenses/yavuzselimkolbasar.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.iodevices import XboxController
from pybricks.parameters import Button, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import StopWatch, wait

left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
right = Motor(Port.B, Direction.CLOCKWISE)
left_arm = Motor(Port.C, Direction.CLOCKWISE)
right_arm = Motor(Port.D, Direction.CLOCKWISE)
# Place both arms in their resting positions before starting.
left_arm.reset_angle(0)
right_arm.reset_angle(0)
xbox = XboxController()
clock = StopWatch()
left_return = -1
right_return = -1
previous_buttons = set()

try:
    while True:
        buttons = xbox.buttons.pressed()
        if Button.B in buttons:
            break
        lt, rt = xbox.triggers()
        horizontal, vertical = xbox.joystick_left()
        throttle = rt - lt
        steering = horizontal * 0.5
        left_power = throttle - steering
        right_power = throttle + steering
        scale = 100 / max(100, abs(left_power), abs(right_power))
        left.dc(left_power * scale)
        right.dc(right_power * scale)

        # Timed returns keep drive input responsive during arm movements.
        now = clock.time()
        if left_return >= 0 and now >= left_return:
            left_arm.run_target(100, 0, wait=False)
            left_return = -1
        if right_return >= 0 and now >= right_return:
            right_arm.run_target(100, 0, wait=False)
            right_return = -1
        if Button.A in buttons and Button.A not in previous_buttons:
            left_arm.run_target(100, 90, wait=False)
            right_arm.run_target(100, 90, wait=False)
            left_return = now + 500
            right_return = now + 500
        else:
            if Button.LB in buttons and Button.LB not in previous_buttons:
                left_arm.run_time(100, 500, wait=False)
                left_return = now + 500
            if Button.RB in buttons and Button.RB not in previous_buttons:
                right_arm.run_time(100, 500, wait=False)
                right_return = now + 500
        previous_buttons = buttons
        wait(50)
finally:
    left.brake()
    right.brake()
    left_arm.brake()
    right_arm.brake()
