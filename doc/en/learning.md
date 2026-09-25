# From first actions to Python

The library opens at **Beginner** on a fresh installation. Levels accumulate:
**Standard** adds to Beginner, **Expert** adds to Standard. **All** shows every
level too; it is a browsing option, not a fourth difficulty. Your choice is saved.
Levels filter the library, never restrict the program or hide existing code.
Help groups include all their blocks and label the level at which each is introduced.

![The nine-block starter library](images/learning.png)

## Beginner: connect, act, wait

Nine blocks introduce a sequence of visible actions:

| Group | Blocks |
|---|---|
| Motors | Connect a motor; run for a set time; turn through an angle |
| Sensors and timing | Connect a SPIKE color sensor; connect a BOOST color/distance sensor; wait for a color; wait for a time |
| Python basics | Display a value; repeat a given number of times |

Start with **Connect a motor** and **Turn a motor through an angle**. Choose the
same motor name in both blocks. Change the angle from `90` to `-90` to reverse it.
Timed and angled moves finish before the next action begins. Use **Stop / F6** to
stop a running program.

Next connect a color sensor, wait for white, turn, pause, and turn back.
Open `examples/sequence.py` for Inventor/Prime or Technic (motor A, SPIKE color
sensor C); use `examples/boost_sequence.py` for BOOST (built-in motor A, combined
sensor D). Connect the matching **Virtual hub** and run. In Control, set the
sensor's reflection below 50: the sequence waits. Set it to 50 or above: the
virtual sensor reports white and the sequence starts. This simulator models
black/white from reflection; physical sensors distinguish more colors.

Try changing the angle and pause, then put the actions inside a repeat block.
There is no need to introduce variables, Boolean algebra or functions yet.
This stage takes inspiration from the motor-and-sensor activities of
[LEGO BOOST](https://www.lego.com/en-au/product/boost-creative-toolbox-17101).

## Standard: sense, decide, control

Add open-ended motor motion, braking, target angles, direction, angle/speed
readings, ultrasonic and force sensors, reflection, distance, conditions and
sensor waits. A drive base adds distance moves and turns; a stopwatch measures
time. Python blocks add variables, arithmetic, comparisons, Boolean expressions,
loops, loop exit, lists, text conversion and reusable functions.

Suggested progression:

1. Run a motor, wait for a sensor condition, then brake. Read measurements in the
   console before choosing a threshold. Ultrasonic distance is in millimeters;
   BOOST distance is a relative percentage, not millimeters.
2. Use `if / else` to choose an action. Add a short wait to continuous sensor loops.
3. Connect two motors and a drive base. Move a measured distance and turn in place.
   On a physical chassis, set motor directions and measure wheel diameter and
   axle track; the default dimensions are examples.
4. Open `examples/robot_route.py`. It stores three distances in a list, calls your
   own `drive_leg` function in a counted loop, and prints measured distance and
   angle (approximately `90 270`). It runs on every virtual hub profile.
5. Add a stopwatch limit, compare sensor values, or choose a random route.
   The random-number block uses `urandom`, available on Inventor/Prime and Technic,
   but absent from BOOST firmware. The virtual profiles preserve that distinction.

These topics follow the learning progression of
[MINDSTORMS flow, sensor and data blocks](https://ev3-help-online.api.education.lego.com/Retail/en-us/index.html).
PyBlocks targets Pybricks hubs; this is not an EV3 hardware compatibility layer.
See the [drive-base API](https://docs.pybricks.com/en/stable/robotics.html) and
[random-number API](https://docs.pybricks.com/en/stable/micropython/urandom.html)
for the underlying Python operations.

## Expert: express the algorithm

Expert adds iteration over collections, `continue`, dictionaries, membership,
slices, list comprehensions, conditional expressions, specific exception handlers,
`try / finally`, raising errors and debugging assertions. Proportional line
following is a worked robotics algorithm to inspect and adapt.

Open `examples/data_pipeline.py`: a function validates and transforms values,
a loop collects successful results, and a dictionary records their count. It
prints `[0, 8] 3` on a computer or any virtual hub. Change its transformation,
then add another report field. Use **My functions** to insert calls; edit their
argument lists and use the inline diagnostics to correct signature mistakes.

The goal is fluency with Python, not a card for every language feature. Open
**Python** to add imports, classes, complex signatures, comprehensions or APIs
that are clearer as source. You can edit a single fragment with F2 and return to
**Blocks** whenever useful. Unrecognized valid Python remains visible and editable;
levels never translate it into a separate language. A physical hub runs MicroPython
and only its available modules; ordinary desktop Python is broader.
