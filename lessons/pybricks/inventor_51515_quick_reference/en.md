# 51515 · API exploration

<a name="prepare"></a>

## Prepare the model

Study the API examples one section at a time.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.


No complete building guide is supplied by this upstream project; match its model before running.

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/quick-reference/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Study the reference

[Open `inventor_51515_quick_reference.py`](program:inventor_51515_quick_reference.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `left_wheel` |
| B | `Motor` | `right_wheel` |
| C | `ColorSensor` | `color_sensor` |
| D | `UltrasonicSensor` | `eyes` |
| E | `Motor` | `arm` |

This is a reference, not a single robot mission. Open a new program and reconstruct one short example with blocks. Choose equipment matching that section.

Do not run the whole reference as a robot program; copy one matching section into a new program. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Description

You can use the code for this project as a quick reference to the various Pybricks
functions available for the hub, motors, and sensors that come in the 51515 kit. 
The program includes most (but not all) of the functions available for these devices.

You can actually run the entire program on an Inventor hub with 3 motors on ports 
A, B, and E, color sensor on C, and distance sensor on D, but the real purpose is 
to show function syntax examples in the code. 

##### Understanding the Python Syntax

If you are new to Python programming, note that most of the Pybricks commands will
fit on one line and consist of three parts, for example:
```python
    arm.run_angle(500, 180)     # rotate at speed 500 for 180 degrees
```
1. Here ``arm`` is the name of the *object*, which is the motor, sensor, or device
that the command refers to. These names are defined at the top of the program
in the Getting Started section.
2. ``run_angle`` is the *function* name. Pybricks defines these, and this Quick 
Reference will help you discover and learn them.
3. The numbers ``(500, 180)`` are the *input parameters*, which give the function
additional information it needs to do the desired action.

Any text after the ``#`` symbol is a *comment*, which is just a note for human readers 
(ignored by the computer) to make the code easier to understand.

To make the input parameters easier to understand, many of the examples in the program
use *variables* (names) for them like this: 
```python
    speed = 500     # (deg/s)
    angle = 180     # (deg)

    arm.run_angle(speed, angle)     # rotate by angle
```
For other parts of general Python syntax, the program has a quick guide at the end
for the most common structures.

#### Program


[Open `inventor_51515_quick_reference.py`](program:inventor_51515_quick_reference.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/quick-reference/index.md). Dave Parker. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

This is a reference, not a single robot mission. Open a new program and reconstruct one short example with blocks. Choose equipment matching that section.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/quick-reference/index.md). Dave Parker. [MIT](LICENSE.txt).

