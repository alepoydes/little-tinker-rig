# LEGO set programs as blocks

The repository includes all 37 Python files for the supported hub families from the official
[Pybricks Projects repository](https://github.com/pybricks/pybricks-projects).
Together with the 42109 Xbox adaptation and 31 programs from project pages,
the catalog contains 69 Python files.
Open a file using **File → Examples → pybricks** or **File → Open**. Select **All** in the
library to find every component used by a program. The level filter limits new
choices, never the blocks already in the document.

| File | Robot and connections | What it does |
|---|---|---|
| `boost_17101_auto_builder.py` | BOOST Auto Builder: conveyor B, arm D | Homes both mechanisms, stacks five components and ejects the result |
| `inventor_51515_tricky.py` | Robot Inventor Tricky: wheels A/B, ultrasonic D | Lights its eyes and turns both ways when an object is within 100 mm |
| `spike_45678_cnc.py` | SPIKE Prime CNC: horizontal A, vertical C | Draws a rectangle and returns both axes to their starting position |
| `spike_45678_grabber.py` | SPIKE Prime grabber: motor A, force sensor E | Closes while pressed; opens to the mechanical stop when released |
| `spike_45678_kiki.py` | SPIKE Prime Kiki: color sensor B | Shows sky, house or grass for blue, yellow or green objects |
| `technic_42124_buggy.py` | Technic 42124: drive A, steering B, LEGO remote | Centers the steering and drives with the remote |
| `technic_42099_off_roader.py` | Technic 42099: front A, rear B, steering C | Calibrates steering and follows a timed route |
| `technic_42099_off_roader_remote.py` | Same 42099 connections, LEGO remote | Controls both drive axles and steering from the remote |

Motor directions, dimensions and tuning belong to these specific LEGO builds.
Changing only ports does not adapt them to a different mechanism.

## Technic 42109 with Xbox

Open [technic_42109_xbox.py](../../examples/pybricks/technic_42109_xbox.py) through
**File → Examples → pybricks**. It uses standard Advanced blocks: steering motor B,
drive motor D, automatic steering calibration, left-stick steering and trigger
power control. The right trigger drives forward; the left drives backward.
The loop waits 50 ms between updates. Calibration requires the assembled car's
mechanical stops; controller pairing is not implemented by the virtual hub.

Use Pybricks 3.5+ and a compatible Bluetooth Xbox controller. On first use, switch
on the controller and hold its pairing button until the light flashes rapidly,
then run the program. Later runs only need the controller switched on.
The Technic hub disconnects from the computer to connect to Xbox. **Press the
green hub button to stop**, then reconnect Studio to edit the program.
See the [official Pybricks guide](https://pybricks.com/project/technic-42109-xbox/).

## Useful actions at each level

The [website examples](../../examples/pybricks/website/README.md) add modern
remote/Xbox programs for 42099, 42109, 42124, 42129, 42131, 42146 and 42160,
the Inventor/SPIKE ball balancer, hub menus, and small input/motor tutorials.
The crane needs two Technic hubs and Pybricks 4; its base and crane files run on
different hubs. Camera projects require the external Pybricks Code vision host;
Studio does not process camera data. These requirements are recorded per file.
SPIKE Essential, Duplo and EV3 examples remain outside the supported hub scope.
The beginner palette stays unchanged; task, radio and external-app blocks are Expert.

**Beginner** adds four complete actions: transfer a conveyor part, draw a rectangle,
turn one way and back, and operate a force-controlled gripper. These are ordinary
Python fragments, recognized in the example programs and available independently
in **Robot activities**. The initial palette now has twenty blocks.

**Intermediate** adds limited-power homing, measured steering centering, coasting,
ultrasonic eye brightness and clearing the display. Homing needs a physical stop;
resetting the angle alone is not calibration.

**Advanced** exposes stalled-angle readings, explicit hold/coast modes, background
target motion, acceleration limits, motor precision profiles, a single snapshot
of all remote buttons, and custom display patterns. Named icons keep their simpler
icon block. All these actions are grouped with their related motors, sensors, hub
or remote blocks in the panel and the generated reference.

Expand a complete activity to inspect or change its individual actions. Source
remains visible even while the activity is treated as one block. Expansion changes
the editing view, not the program; edits trigger recognition again. Calibration
and motor controller details can be studied after the complete activity works.

## Behavior and simulation

The adaptations preserve the original algorithms, including details that matter
on hardware: a nonblocking target remains nonblocking; `run(0)` is not replaced
with braking; the grabber finishes opening before checking the next press.
Remote programs keep running until **Stop** and do not gain a center-button exit.
Kiki uses the current `display.icon()` name for the same original pixel patterns.

For a fully virtual starting example, open `spike_45678_cnc.py`, connect an Inventor/Prime
virtual hub, and configure A and C as motors. Tricky also works virtually with A/B
motors and an ultrasonic sensor on D; change its distance below 100 mm to trigger
the dance. Eye brightness and display output are printed in the console.

Auto Builder, grabber and steering calibration need real mechanical end stops.
Remote pairing and motor precision profiles are not implemented by the interactive
simulator. Kiki's blue/yellow/green objects are scripted in tests; the interactive
virtual color sensor currently reports only black or white. The tests use virtual
motor motion and explicit scripted hardware inputs to compare complete command
sequences, rather than pretending to validate physical construction.

The table above lists the eight introductory activities. The [complete catalog](../../examples/pybricks/README.md)
also includes BOOST R2-D2 (75253), Inventor Blast/MVP/Gelo, the exploration rover,
balancer, block flipper, mini-loader, Steerbot, the API reference and all Technic
keyboard/remote/Xbox programs at the pinned revision. EV3 is excluded.

Keep the Gelo modules together so Upload/Run can include their local dependency.
The REPL file is interactive; the API reference should be studied in sections.
Filenames include set numbers. The catalog records dependencies, extra equipment,
upstream sources and the exact extent of validation for each file.

Advanced adds keyboard input, Xbox control, colors and gears. Expert exposes
controller tuning, display options, hub measurements, classes, contexts and
generators. Ordinary function calls can edit their callable and argument list;
this also applies to custom robot methods. These additions do not increase the
Beginner palette.

All catalog files compile for both MPY ABIs and rebuild without changing their executable
structure. Full interactive simulations of walking, balancing and tipping are not
implemented. Xbox tests preserve input sampling, motor ports and loop timing.
The compatibility helpers preserve keyboard nonblocking reads and old curve
signs. Gelo's missing const import and Audi's missing hub initialization are fixed.
Upstream attribution is retained in `examples/pybricks/LICENSE.txt`.
