# LEGO set programs as blocks

The repository includes all 37 Python files for the supported hub families from the official
[Pybricks Projects repository](https://github.com/pybricks/pybricks-projects).
Together with the 42109 Xbox adaptation and 15 community programs, the catalog
contains 53 Python files. Website-only programs remain external links.
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
green hub button to stop**, then reconnect LittleTinker Rig to edit the program.
See the [official Pybricks guide](https://pybricks.com/project/technic-42109-xbox/).

## Technic 42100 excavator with Xbox

Use the two files under **File → Examples → pybricks → community** with
Pybricks **4.0+ on both Technic hubs** and a Bluetooth Xbox controller:

| Program | Hub and original motor connections |
|---|---|
| [technic_42100_base_xbox.py](../../examples/pybricks/community/technic_42100_base_xbox.py) | Lower: A left track, B right track, D turntable |
| [technic_42100_upper.py](../../examples/pybricks/community/technic_42100_upper.py) | Upper: A boom, B arm, C bucket tilt, D bucket opening |

Upload each file to its corresponding hub. They run separately and do not import
each other. Pair Xbox as described above, start the lower hub's stored program,
then start the upper one with the controls released. The lower hub shows blue
while connecting, green while driving, and yellow in slow mode. The upper hub
shows yellow while waiting and green while receiving fresh commands; it can
also start first and wait. The lower hub disconnects from LittleTinker Rig to use Xbox.

| Xbox input | Action |
|---|---|
| LT / RT | Left / right track forward |
| LB / RB | Left / right track backward |
| D-pad left / right | Rotate the platform |
| Left stick vertical | Move the boom |
| Right stick vertical / horizontal | Move the arm / tilt the bucket |
| A / B | Open / close the bucket |
| Hold X | Slow mode: 40% of all configured speeds |
| Y | Stop the lower program; upper motors stop on timeout |

Release a control to brake; opposite directions pressed together also brake.
The green button on either hub stops that hub's program. Stopping only the upper
hub leaves the base running. Stop the lower program before reconnecting LittleTinker Rig.

Loops update every 50 ms. A changing sequence in each radio message prevents
the upper hub from continuing indefinitely on repeated old commands: it brakes
after 500 ms without an update, checked every 50 ms. Xbox disconnection and Y stop
the base immediately when detected and stop broadcasting; the upper motors stop
within that timeout plus one polling interval. Both files use channel 100;
change both together if another excavator is nearby.

Adjust `track_speed`, `turn_speed`, upper `maximum_speeds` (degrees/second at the
motor shaft), and `slow_percent`. Initial speed limits and directions need checking
on the assembled model. Start with X held and move one mechanism at a time.
There is no homing or endpoint detection: release controls at the travel limits.
Tests use virtual motors with scripted radio/controller inputs; interactive
simulation has neither Xbox pairing nor hub-to-hub radio. Physical behavior has
not been verified. See the [complete guide and credits](../../examples/pybricks/community/README.md).

## Useful actions at each level

The [website link inventory](../../examples/pybricks/website/README.md) points to external
remote/Xbox programs for 42099, 42109, 42124, 42129, 42131, 42146 and 42160,
the Inventor/SPIKE ball balancer, hub menus, and small input/motor tutorials.
The crane needs two Technic hubs and Pybricks 4; its base and crane files run on
different hubs. Camera projects require the external Pybricks Code vision host;
LittleTinker Rig does not process camera data. These programs are not bundled; requirements are recorded alongside their links.
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

The direct imports preserve the original algorithms, including details that matter
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

## More community programs

Open **File → Examples → pybricks → community**. These 13 additions target
Pybricks **4.0+**, use existing palette blocks, and retain pinned source links
in their first comments. SPIKE **45678** / Inventor **51515** filenames identify
compatible parts, not a ready-made official robot.

| Program | Suggested level |
|---|---|
| [Obstacle avoidance](../../examples/pybricks/community/spike_45678_51515_obstacle_avoidance.py) | Intermediate |
| [Follow an object](../../examples/pybricks/community/spike_45678_51515_follow_object.py) | Advanced |
| [Follow a wall](../../examples/pybricks/community/spike_45678_51515_follow_wall.py) | Advanced |
| [Stop at red](../../examples/pybricks/community/spike_45678_51515_stop_at_red.py) | Intermediate |
| [Gyro straight driving](../../examples/pybricks/community/spike_45678_51515_gyro_straight.py) | Intermediate |
| [Parallel motors](../../examples/pybricks/community/spike_45678_51515_parallel_motors.py) | Expert |
| [Motor timeout](../../examples/pybricks/community/spike_45678_51515_motor_timeout.py) | Expert |
| [Obstacle/task race](../../examples/pybricks/community/spike_45678_51515_obstacle_race.py) | Expert |
| [Xbox drive and arm](../../examples/pybricks/community/spike_45678_51515_xbox_drive_arm.py) | Advanced |
| [Xbox car and lift](../../examples/pybricks/community/spike_45678_51515_xbox_car_lift.py) | Advanced |
| [Xbox boxer](../../examples/pybricks/community/spike_45678_51515_xbox_boxer.py) | Advanced |
| [42100 lower remote](../../examples/pybricks/community/technic_42100_base_remote.py) | Advanced |
| [42100 upper remote](../../examples/pybricks/community/technic_42100_upper_remote.py) | Advanced |

The five driving lessons use left motor **A counterclockwise**, right motor
**B clockwise**, **56 mm wheels** and **112 mm axle track**. Set those dimensions
to match the build. Sonar **C** faces forward for avoidance/following, right for
wall following. For red-line stopping, use a downward color sensor on **C**.
The gyro lesson needs a level, still hub at startup. Following stops on a missing
measurement and resumes when readings recover; its speed/turn rate is bounded.

The task examples need motors **A/B** (parallel), **A** (timeout), or motor **A**
and sonar **C** (obstacle race). The last is a one-motor demonstration. Async
programs require a real Pybricks hub; the interactive simulator has no full task
scheduler. Automated checks script this boundary explicitly.

The custom Xbox programs use **RT forward / LT reverse**, the left stick for
steering and **B to exit**. Drive-and-arm uses **C left clockwise, D right
counterclockwise, E arm**; **A** lowers the arm, release raises it. Start raised.
Car-and-lift uses **B steering, D drive, E lift**, all clockwise; start with the
wheels centered. **Y** switches modes once per press; the vertical stick moves
the lift. Inactive motors brake. Boxer uses **A left counterclockwise, B right,
C/D arms clockwise**; start with arms at rest. **LB/RB** punch, **A** defends.
Actions occur once per press and return after 500 ms without blocking steering.
SPIKE 45678 needs a fourth motor for this build. These programs have no automatic
homing; shaft angles and gearing must suit the mechanism.

The two new **42100 LEGO-remote** files need **two Powered Up remotes 88010**, one
per hub. Lower motors: A/B tracks, D turntable. Upper: A/B boom/arm, C/D bucket.
Pair hubs/remotes one at a time. Left red selects A/B; right red selects the other
group. The ± keys control its motors; the center button exits only that hub.
Initial duty is 40%, and inactive groups brake. These retain the author's
**experimental, physically untested** clockwise motor layout; verify direction
and travel before use. They operate independently, without the Xbox pair's radio.

[Originals, equipment and adaptation details](../../examples/pybricks/community/README.md)
and the [source review / licenses](../../examples/pybricks/community/SOURCES.md)
are bundled with the examples. All additions compile and rebuild from blocks;
scripted checks exercise controls, stopping, sensor thresholds and task errors.
Physical models and Bluetooth operation have not been verified.
