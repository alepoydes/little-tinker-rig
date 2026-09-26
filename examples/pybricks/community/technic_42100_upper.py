# LEGO 42100 upper hub; Pybricks 4+. See README.md for setup and credits.
from pybricks.hubs import TechnicHub
from pybricks.messaging import BLERadio
from pybricks.parameters import Color, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import StopWatch, wait

hub = TechnicHub()
radio = BLERadio(broadcast_channel=None, observe_channels=[100])
boom = Motor(Port.A, Direction.COUNTERCLOCKWISE)
arm = Motor(Port.B, Direction.COUNTERCLOCKWISE)
bucket_tilt = Motor(Port.C, Direction.CLOCKWISE)
bucket_open = Motor(Port.D, Direction.CLOCKWISE)
motors = (boom, arm, bucket_tilt, bucket_open)

# Motor shaft speeds in degrees/second. No homing or travel limits are assumed.
maximum_speeds = (600, 450, 450, 300)
timeout_ms = 500
for motor in motors:
    motor.control.limits(acceleration=1000)

clock = StopWatch()
last_sequence = None
hub.light.on(Color.YELLOW)

try:
    while True:
        message = radio.observe(100)
        commands = (0, 0, 0, 0)
        # Ignore unrelated or malformed broadcasts instead of driving from them.
        valid = (
            isinstance(message, tuple)
            and len(message) == 6
            and all(isinstance(value, int) for value in message)
            and message[0] == 42100
            and 0 <= message[1] < 256
            and all(-100 <= value <= 100 for value in message[2:])
        )
        if valid:
            if message[1] != last_sequence:
                last_sequence = message[1]
                clock.reset()
            if clock.time() < timeout_ms:
                commands = message[2:]
        hub.light.on(
            Color.GREEN if valid and clock.time() < timeout_ms else Color.YELLOW
        )

        for motor, command, maximum in zip(motors, commands, maximum_speeds):
            speed = command * maximum / 100
            if speed:
                motor.run(speed)
            else:
                motor.brake()
        wait(50)
finally:
    for motor in motors:
        motor.brake()
