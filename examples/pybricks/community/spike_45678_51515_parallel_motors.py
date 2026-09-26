# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/twomotors.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.
from pybricks.pupdevices import Motor
from pybricks.parameters import Port
from pybricks.tools import multitask, run_task

motor_a = Motor(Port.A)
motor_b = Motor(Port.B)


async def move_a():
    await motor_a.run_angle(500, 360)


async def move_b():
    await motor_b.run_angle(300, 720)


async def main():
    # Both motors move simultaneously instead of one after the other
    await multitask(move_a(), move_b())


run_task(main())
