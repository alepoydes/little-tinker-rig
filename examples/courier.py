"""Line-following delivery robot for a Pybricks Inventor / SPIKE Prime hub.

A/B: wheel motors; C: color; D: distance; E: emergency force button;
F: gripper motor. Wheel diameter and axle track are in millimeters.
The virtual hub needs a motor attached to F in its device panel.
"""

from pybricks.parameters import Color, Direction, Port
from pybricks.pupdevices import ColorSensor, ForceSensor, Motor, UltrasonicSensor
from pybricks.robotics import DriveBase
from pybricks.tools import StopWatch, wait


def run_route(deliveries=2, time_limit_ms=30000):
    left = Motor(Port.A, Direction.COUNTERCLOCKWISE)
    right = Motor(Port.B)
    gripper = Motor(Port.F)
    color = ColorSensor(Port.C)
    distance = UltrasonicSensor(Port.D)
    emergency = ForceSensor(Port.E)
    drive = DriveBase(left, right, wheel_diameter=56, axle_track=112)
    clock = StopWatch()
    delivered = 0
    previous_state = None

    def state(name):
        nonlocal previous_state
        if name != previous_state:
            print("state=" + name)
            previous_state = name

    try:
        state("calibrating")
        readings = []
        for _ in range(5):
            readings.append(color.reflection())
            wait(20)
        target = max(20, sum(readings) / len(readings))
        marker_ready = True

        for delivery in range(deliveries):
            gripper.run_target(400, 65)
            dark_samples = 0
            state("following")
            while True:
                if emergency.pressed():
                    state("emergency")
                    return {"status": "emergency", "delivered": delivered}
                elif clock.time() >= time_limit_ms:
                    state("timeout")
                    return {"status": "timeout", "delivered": delivered}

                if distance.distance() < 120:
                    drive.brake()
                    state("blocked")
                    wait(40)
                    continue

                state("following")
                reflection = color.reflection()
                if reflection > target * 0.6:
                    marker_ready = True
                on_marker = (
                    marker_ready and reflection < 12 and color.color() == Color.BLACK
                )
                dark_samples = dark_samples + 1 if on_marker else 0
                if dark_samples >= 3:
                    drive.brake()
                    gripper.run_target(400, 0)
                    delivered = delivery + 1
                    print("delivery=" + str(delivered))
                    marker_ready = False
                    break

                correction = max(-90, min(90, 2 * (reflection - target)))
                drive.drive(180, correction)
                wait(20)
        else:
            state("complete")
            return {"status": "complete", "delivered": delivered}
    except OSError as error:
        state("device_error")
        print(error)
        return {"status": "device_error", "delivered": delivered}
    finally:
        for motor in (left, right, gripper):
            try:
                motor.brake()
            except OSError:
                print("A motor is disconnected")


if __name__ == "__main__":
    print(run_route())
