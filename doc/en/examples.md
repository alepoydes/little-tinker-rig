# LEGO set programs as blocks

The repository includes eight adapted programs from the official
[Pybricks Projects repository](https://github.com/pybricks/pybricks-projects).
Open a file from `examples/pybricks/` using **File → Open**. Select **All** in the
library to find every component used by a program. The level filter limits new
choices, never the blocks already in the document.

| File | Robot and connections | What it does |
|---|---|---|
| `boost_auto_builder.py` | BOOST Auto Builder: conveyor B, arm D | Homes both mechanisms, stacks five components and ejects the result |
| `inventor_tricky.py` | Robot Inventor Tricky: wheels A/B, ultrasonic D | Lights its eyes and turns both ways when an object is within 100 mm |
| `spike_cnc.py` | SPIKE Prime CNC: horizontal A, vertical C | Draws a rectangle and returns both axes to their starting position |
| `spike_grabber.py` | SPIKE Prime grabber: motor A, force sensor E | Closes while pressed; opens to the mechanical stop when released |
| `spike_kiki.py` | SPIKE Prime Kiki: color sensor B | Shows sky, house or grass for blue, yellow or green objects |
| `technic_buggy.py` | Technic 42124: drive A, steering B, LEGO remote | Centers the steering and drives with the remote |
| `technic_off_roader.py` | Technic 42099: front A, rear B, steering C | Calibrates steering and follows a timed route |
| `technic_off_roader_remote.py` | Same 42099 connections, LEGO remote | Controls both drive axles and steering from the remote |

Motor directions, dimensions and tuning belong to these specific LEGO builds.
Changing only ports does not adapt them to a different mechanism.

## Useful actions at each level

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

For a fully virtual starting example, open `spike_cnc.py`, connect an Inventor/Prime
virtual hub, and configure A and C as motors. Tricky also works virtually with A/B
motors and an ultrasonic sensor on D; change its distance below 100 mm to trigger
the dance. Eye brightness and display output are printed in the console.

Auto Builder, grabber and steering calibration need real mechanical end stops.
Remote pairing and motor precision profiles are not implemented by the interactive
simulator. Kiki's blue/yellow/green objects are scripted in tests; the interactive
virtual color sensor currently reports only black or white. The tests use virtual
motor motion and explicit scripted hardware inputs to compare complete command
sequences, rather than pretending to validate physical construction.

This collection covers the eight programs listed above. Large class-based walkers,
balancers and host keyboard bridges from the upstream catalog are not included.
The source revision, individual links and MIT attribution are recorded in
`examples/pybricks/README.md` and `examples/pybricks/LICENSE.txt`.
