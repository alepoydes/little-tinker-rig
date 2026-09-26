# Adapted from The-GummyBears-Robotics (MIT).
# Source: https://github.com/The-GummyBears-Robotics/PybricksPythonTut/blob/5d199cfea9246176dc37a153250233f40f3d082c/10-multitask/multitaskuntilonewin.py
# License: licenses/gummybears.txt
# Changes and hardware: README.md and ../catalog.json.

from pybricks.hubs import PrimeHub
from pybricks.parameters import Color, Port
from pybricks.pupdevices import Motor, UltrasonicSensor
from pybricks.tools import multitask, run_task, wait

hub = PrimeHub()
motor = Motor(Port.A)
sonar = UltrasonicSensor(Port.C)


async def drive_forward():
    motor.run(500)
    await wait(10000)


async def watch_for_obstacle():
    # Sensor I/O must be awaited inside a coroutine.
    while await sonar.distance() > 100:
        await wait(50)


async def blink_while_moving():
    while True:
        hub.light.on(Color.YELLOW)
        await wait(300)
        hub.light.off()
        await wait(300)


async def main():
    try:
        await multitask(
            drive_forward(), watch_for_obstacle(), blink_while_moving(), race=True
        )
    finally:
        motor.stop()
        hub.light.on(Color.RED)
    print("Movement stopped: obstacle or time limit.")


run_task(main())
