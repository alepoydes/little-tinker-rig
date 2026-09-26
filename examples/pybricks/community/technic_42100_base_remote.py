# Adapted from Tcm0 (MIT).
# Source: https://github.com/Tcm0/PybricksRemoteLayouts/blob/7e2580ec5e525cb017ffa10348abee71fceac800/42100%20LOWER%20HUB%20EXPERIMENTAL.py
# License: licenses/tcm0.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.parameters import Button, Port
from pybricks.pupdevices import Motor, Remote
from pybricks.tools import wait

# Experimental upstream layout: verify motor directions on the assembled model.
left = Motor(Port.A)
right = Motor(Port.B)
turntable = Motor(Port.D)
remote = Remote()
mode = 0
power = 40

try:
    while True:
        pressed = remote.buttons.pressed()
        if Button.CENTER in pressed:
            break
        if Button.LEFT in pressed:
            mode = 0
        elif Button.RIGHT in pressed:
            mode = 1
        left_input = (Button.LEFT_PLUS in pressed) - (Button.LEFT_MINUS in pressed)
        right_input = (Button.RIGHT_PLUS in pressed) - (Button.RIGHT_MINUS in pressed)
        if mode == 0:
            turntable.brake()
            left.dc(power * left_input)
            right.dc(power * right_input)
        else:
            left.brake()
            right.brake()
            turntable.dc(power * right_input)
        wait(100)
finally:
    left.brake()
    right.brake()
    turntable.brake()
