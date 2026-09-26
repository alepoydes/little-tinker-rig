# LEGO 42100 lower hub; Pybricks 4+. See README.md for setup and credits.
from pybricks.hubs import TechnicHub
from pybricks.iodevices import XboxController
from pybricks.messaging import BLERadio
from pybricks.parameters import Button, Color, Direction, Port
from pybricks.pupdevices import Motor
from pybricks.tools import wait

hub = TechnicHub()
radio = BLERadio(broadcast_channel=100)
left_track = Motor(Port.A, Direction.CLOCKWISE)
right_track = Motor(Port.B, Direction.COUNTERCLOCKWISE)
turntable = Motor(Port.D, Direction.COUNTERCLOCKWISE)
motors = (left_track, right_track, turntable)

# Motor shaft speeds in degrees/second, before gearing. X reduces all speeds.
track_speed = 600
turn_speed = 300
slow_percent = 40
for motor in motors:
    motor.control.limits(acceleration=1000)

hub.light.on(Color.BLUE)
xbox = XboxController()
sequence = 0

try:
    while True:
        # Sample each input once before issuing any motor commands.
        pressed = xbox.buttons.pressed()
        left_trigger, right_trigger = xbox.triggers()
        unused, boom_command = xbox.joystick_left()
        tilt_command, arm_command = xbox.joystick_right()
        if Button.Y in pressed:
            break

        speed_percent = slow_percent if Button.X in pressed else 100
        hub.light.on(Color.YELLOW if Button.X in pressed else Color.GREEN)

        # Triggers drive forward, bumpers reverse. Opposing inputs stop a track.
        left_command = (
            (0 if left_trigger else -100) if Button.LB in pressed else left_trigger
        )
        right_command = (
            (0 if right_trigger else -100) if Button.RB in pressed else right_trigger
        )
        turn_command = 100 * ((Button.RIGHT in pressed) - (Button.LEFT in pressed))
        for motor, command, maximum in (
            (left_track, left_command, track_speed),
            (right_track, right_command, track_speed),
            (turntable, turn_command, turn_speed),
        ):
            speed = command * maximum * speed_percent / 10000
            if speed:
                motor.run(speed)
            else:
                motor.brake()

        # Packet: model tag, changing sequence, then four signed percentages.
        # The sequence lets the upper hub reject endlessly repeated old data.
        bucket_command = 100 * ((Button.A in pressed) - (Button.B in pressed))
        commands = tuple(
            int(value * speed_percent / 100)
            for value in (boom_command, arm_command, tilt_command, bucket_command)
        )
        radio.broadcast((42100, sequence) + commands)
        sequence = (sequence + 1) % 256
        wait(50)
finally:
    # Also runs when reading a disconnected Xbox raises OSError.
    for motor in motors:
        motor.brake()
    radio.broadcast(None)
