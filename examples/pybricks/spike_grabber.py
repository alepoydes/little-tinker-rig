# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
# Hand-Controlled Grabber:
# press the Force Sensor to grab objects,
# and release the Force Sensor to let go.


from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import ForceSensor, Motor

# Configure the Hub, the Force Sensor and the Motor
hub = PrimeHub()
force_sensor = ForceSensor(Port.E)
motor = Motor(Port.A)


while True:
    # Grab when the Force Sensor is pressed
    if force_sensor.pressed():
        motor.run(-1000)

    # else let go
    else:
        motor.run_until_stalled(1000)
