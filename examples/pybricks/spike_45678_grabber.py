# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
# Hand-Controlled Grabber:
# press the Force Sensor to grab objects,
# and release the Force Sensor to let go.


from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import ForceSensor, Motor


# --- automatically managed helpers ---
def force_gripper(
    motor: "Motor",
    sensor: "ForceSensor",
    speed: "number[deg/s]",
):
    """Close a gripper while pressed; open to its stop when released.

    Repeats until the program is stopped. Opening waits for a mechanical stall,
    so a new press is handled after opening finishes. Requires physical stops."""
    while True:
        if sensor.pressed():
            motor.run(-speed)
        else:
            motor.run_until_stalled(speed)


# --- user program ---

# Configure the Hub, the Force Sensor and the Motor
hub = PrimeHub()
force_sensor = ForceSensor(Port.E)
motor = Motor(Port.A)


force_gripper(motor, force_sensor, 1000)
