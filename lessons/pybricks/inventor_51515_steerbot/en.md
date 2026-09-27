# 51515 · Steer Bot

<a name="prepare"></a>

## Prepare the model

Follow the edge of a line using steering and reflected light.

Use LEGO **51515** and the exact mechanism from the source. A matching hub alone is not enough. The programs open as ordinary editable Python, recognized by the standard block library. The linked building instructions describe the model; this lesson opens without a 3D assembly view.

- [Video](https://www.youtube.com/watch?v=i4WPa-rtFB8)
- [Building instructions](https://raw.githubusercontent.com/pybricks/pybricks-projects/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/steerbot/steerbot-instructions.pdf)

Connect the required devices using the port tables in the following stages. Keep the original gearing, motor directions and calibration positions. Use current Pybricks firmware for your hub. These models need real hardware; the virtual hub does not simulate their mechanisms, remotes or balancing.

Open a program to inspect it before Run. Calibration can move motors immediately. Mark this stage complete when the mechanism and its connections are ready. Media links need internet; the lesson text, code and dependencies are included in saved projects.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/steerbot/index.md). Gus Jansson. [MIT](LICENSE.txt).

<a name="run-1"></a>

## Try the program

[Open `inventor_51515_steerbot.py`](program:inventor_51515_steerbot.py). This is your project copy; reopening it preserves your edits.

| Port | Python device | Code name |
|---|---|---|
| A | `Motor` | `steer_motor` |
| B | `Motor` | `drive_motor` |
| C | `ColorSensor` | `sensor` |

Compare reflection on the dark line and light surface. Identify the target reflection and steering correction. Lower driving speed before testing a tighter curve.

Use Run to start this file and Stop to finish. Compare what you predicted with the robot’s behavior before marking the stage complete.

### Upstream explanation (MIT)

The following licensed notes describe the original workflow. Program links above open the adapted Studio copies; installation and terminal names may refer to Pybricks Code.

#### Description

A robot with car like steering has been one of my favorite exercises in robot
building. This project, in fact, is largely a variation of what I have
previously done with the LEGO RCX, the NXT and to a lesser extent the EV3. But
with the 51515 set I as able to take advantage of improved resolution of the
color sensor as well as some cool features of Pybricks to make the main
tracking code pretty simple.

The robot features Ackermann steering. This means that the steering linkage is
more trapezoidal than parallel. The front wheels are only parallel when the
steering is pointing straight ahead. When it turns the inside wheel turns
sharper than the outside wheel so the wheels track more accurately since the
inside wheel has a tighter turning radius. This is particularly important in
order to achieve tight overall turning radius with a relatively wide robot.

The robot uses the Color Sensor mounted on an axle high and attached to the
steering motor. This means that in order to track a line, actually just the
edge of the line, the tracking code tries to keep the sensor on the edge of
the line. If the sensor is on the edge, then as the robot drives it will follow
the edge since the robot is now steering to where the edge is in front of the
robot. The sensor is mounted high in order to give a gradual reading over the
edge so that while near the edge the program can determine where the edge is
relative to the sensor.

The driving is done through the super cool 5 gear differential that is included
with the set. This is the first time I use this LEGO differential and I love
it! The drive motor is actually gearing up with the intention of being able to
go really fast. On my tight test track I was never able to make it go full
speed without running off the line.

#### Program



[Open `inventor_51515_steerbot.py`](program:inventor_51515_steerbot.py)

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/steerbot/index.md). Gus Jansson. [MIT](LICENSE.txt).

<a name="experiment"></a>

## Predict, change, explain

Compare reflection on the dark line and light surface. Identify the target reflection and steering correction. Lower driving speed before testing a tighter curve.

Save your project to keep all programs, Scratch and green completion marks. Return to any earlier stage to compare your result.

Sources: [index.md](https://github.com/pybricks/pybricks-projects/blob/faaacce09ffe1d865fd1db241bcacb056234d597/sets/mindstorms-robot-inventor/other-models/steerbot/index.md). Gus Jansson. [MIT](LICENSE.txt).

