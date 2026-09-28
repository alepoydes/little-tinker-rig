"""Display and sound check for Robot Inventor 51515 / SPIKE Prime 45678.

Uses only the built-in display and speaker; no motors or sensors are needed.
Upload, then run the stored program. It finishes in about five seconds.
"""

from pybricks.hubs import PrimeHub
from pybricks.parameters import Icon
from pybricks.tools import wait

hub = PrimeHub()
hub.speaker.volume(30)

print("Hub check started: display and speaker.")

for number in range(1, 4):
    hub.display.number(number)
    hub.speaker.beep(400 + number * 200, 150)
    print("Step", number)
    wait(650)

hub.display.icon(Icon.HEART)
hub.speaker.beep(1200, 400)
wait(2000)
hub.display.off()
print("Hub check complete.")
