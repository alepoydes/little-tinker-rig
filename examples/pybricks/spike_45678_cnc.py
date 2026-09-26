# Adapted from Pybricks Projects (MIT); see README.md and LICENSE.txt.
"""
This program is for CNC Machine
(in the "Invention Squad: Broken" lesson unit).

Follow the corresponding building instructions in the LEGO® SPIKE™ Prime App.

This program will draw a rectangle.
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Port
from pybricks.pupdevices import Motor


# --- automatically managed helpers ---
def _pyblocks_pybricks_lessons_draw_rectangle_4dac17c6a7c8(
    horizontal: "Motor",
    vertical: "Motor",
    width: "number[deg]",
    height: "number[deg]",
    speed: "number[deg/s]",
):
    """Draw a rectangle with two motor axes and return to the start.

    Width and height are motor degrees, not millimeters. Motor gearing and the
    drawing mechanism determine the physical size."""
    # Trace four sides; reversing each axis returns to the starting position.
    horizontal.run_angle(speed, width)
    vertical.run_angle(speed, height)
    horizontal.run_angle(speed, -width)
    vertical.run_angle(speed, -height)


# --- user program ---

# Configure the Hub, the Force Sensor and the Motor
hub = PrimeHub()
horizontal_motor = Motor(Port.A)
vertical_motor = Motor(Port.C)

_pyblocks_pybricks_lessons_draw_rectangle_4dac17c6a7c8(
    horizontal_motor, vertical_motor, 400, 100, 1000
)
