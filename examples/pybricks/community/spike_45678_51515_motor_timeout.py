# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/timeout.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.parameters import Port
from pybricks.pupdevices import Motor
from pybricks.tools import multitask, run_task, wait

motor = Motor(Port.A)


async def move():
    await motor.run_angle(200, 1080)


async def timeout():
    await wait(1000)
    print("Timed out!")


async def main():
    try:
        await multitask(move(), timeout(), race=True)
    finally:
        # Cancelling an awaitable does not replace an explicit motor stop.
        motor.stop()


run_task(main())
